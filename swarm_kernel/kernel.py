from __future__ import annotations

import hashlib
import json
import random
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

KERNEL_VERSION = "1.2.1"
SUPPORTED_PROJECT_KERNEL_VERSIONS = frozenset({"1.0.0", "1.1.0", "1.2.0", "1.2.1"})
SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")
RUN_STATES = {"PREPARING", "READY", "ACTIVE", "DEGRADED_READ_ONLY", "CONVERGING", "COMPLETE", "ABORTED"}
ROLES = {"PRIMARY", "MANAGER", "RESEARCH"}
QUARANTINE_REASONS = {"PROJECT_MISMATCH", "STALE_RUN", "MALFORMED", "UNSUPPORTED_PROTOCOL", "ILLEGAL_CROSS_PROJECT_COMMAND", "LEASE_CONFLICT", "INVARIANT_FAILURE"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or utc_now()).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def require_safe_id(value: str, name: str) -> str:
    if not SAFE_ID.fullmatch(value):
        raise ValueError(f"unsafe {name}: {value!r}")
    return value


@dataclass(frozen=True)
class ProjectConfig:
    project_id: str
    repository: str
    canonical_branch: str
    coordination_root: str
    state_root: str = ".swarm"
    lease_ttl_seconds: int = 1800
    heartbeat_interval_seconds: int = 300
    circuit_breaker_threshold: int = 3
    manager_queue_soft_limit: int = 8
    manager_queue_hard_limit: int = 15
    max_active_specialists: int = 8
    kernel_version: str = KERNEL_VERSION

    @classmethod
    def load(cls, path: str | Path) -> "ProjectConfig":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        project_kernel_version = str(data.get("kernel_version", ""))
        if project_kernel_version not in SUPPORTED_PROJECT_KERNEL_VERSIONS:
            raise ValueError("unsupported swarm-kernel version")
        cfg = cls(
            project_id=data["project_id"], repository=data["repository"],
            canonical_branch=data.get("canonical_branch", "main"), coordination_root=data["coordination_root"],
            state_root=data.get("state_root", ".swarm"), lease_ttl_seconds=int(data.get("lease_ttl_seconds", 1800)),
            heartbeat_interval_seconds=int(data.get("heartbeat_interval_seconds", 300)), circuit_breaker_threshold=int(data.get("circuit_breaker_threshold", 3)),
            manager_queue_soft_limit=int(data.get("manager_queue_soft_limit", 8)), manager_queue_hard_limit=int(data.get("manager_queue_hard_limit", 15)),
            max_active_specialists=int(data.get("max_active_specialists", 8)), kernel_version=project_kernel_version,
        )
        require_safe_id(cfg.project_id, "project_id")
        if "/" not in cfg.repository:
            raise ValueError("repository must be owner/name")
        if cfg.state_root != ".swarm":
            raise ValueError("state_root must remain project-local .swarm")
        if cfg.max_active_specialists < 1:
            raise ValueError("max_active_specialists must be positive")
        return cfg


def validate_binding(cfg: ProjectConfig, project_id: str, repository: str) -> None:
    if project_id != cfg.project_id or repository != cfg.repository:
        raise PermissionError("project/repository binding mismatch; fail closed")


def new_global_run_id(prefix: str = "run") -> str:
    require_safe_id(prefix, "run prefix")
    return f"{prefix}_{utc_now().strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:12]}"


def operation_id(project_id: str, global_run_id: str, operation: str, subject: str) -> str:
    for value, name in ((project_id, "project_id"), (global_run_id, "global_run_id"), (operation, "operation"), (subject, "subject")):
        require_safe_id(value, name)
    return hashlib.sha256("|".join((project_id, global_run_id, operation, subject)).encode()).hexdigest()


def record_path(kind: str, global_run_id: str, record_id: str) -> str:
    if kind not in {"epochs", "ready", "leases", "idempotency", "quarantine", "health", "checkpoints", "convergence"}:
        raise ValueError("unsupported state kind")
    require_safe_id(global_run_id, "global_run_id")
    require_safe_id(record_id, "record_id")
    return f".swarm/{kind}/{global_run_id}/{record_id}.json"


def ready_record(cfg: ProjectConfig, global_run_id: str, agent_id: str, agent_instance_id: str, role: str, package_version: str, source_revision: str, execution_mode: str | None = None) -> dict[str, Any]:
    require_safe_id(global_run_id, "global_run_id")
    require_safe_id(agent_id, "agent_id")
    require_safe_id(agent_instance_id, "agent_instance_id")
    if role not in ROLES:
        raise ValueError("invalid role")
    return {"schema": "swarm-kernel/ready/v2", "kernel_version": cfg.kernel_version, "project_id": cfg.project_id, "repository": cfg.repository, "global_run_id": global_run_id, "agent_id": agent_id, "agent_instance_id": agent_instance_id, "role": role, "execution_mode": execution_mode, "package_version": package_version, "source_revision": source_revision, "status": "READY", "timestamp_utc": iso()}


def can_open_start_gate(expected_agents: Sequence[str], ready_agents: Sequence[str], explicit_close: bool = False) -> tuple[bool, list[str]]:
    missing = sorted(set(expected_agents) - set(ready_agents))
    return (not missing or explicit_close), missing


def new_lease(cfg: ProjectConfig, global_run_id: str, task_id: str, agent_id: str, agent_instance_id: str, expected_version: int, now: datetime | None = None) -> dict[str, Any]:
    now = now or utc_now()
    for value, name in ((global_run_id, "global_run_id"), (task_id, "task_id"), (agent_id, "agent_id"), (agent_instance_id, "agent_instance_id")):
        require_safe_id(value, name)
    if expected_version < 0:
        raise ValueError("expected_version must be non-negative")
    return {"schema": "swarm-kernel/lease/v2", "project_id": cfg.project_id, "repository": cfg.repository, "global_run_id": global_run_id, "task_id": task_id, "owner_agent_id": agent_id, "owner_agent_instance_id": agent_instance_id, "version": expected_version + 1, "heartbeat_at": iso(now), "expires_at": iso(now + timedelta(seconds=cfg.lease_ttl_seconds)), "status": "HELD"}


def lease_transition_allowed(current: Mapping[str, Any] | None, expected_version: int, agent_id: str, agent_instance_id: str, now: datetime | None = None) -> tuple[bool, str]:
    now = now or utc_now()
    require_safe_id(agent_id, "agent_id")
    require_safe_id(agent_instance_id, "agent_instance_id")
    if current is None:
        return (expected_version == 0, "NEW" if expected_version == 0 else "VERSION_MISMATCH")
    if int(current.get("version", -1)) != expected_version:
        return False, "VERSION_MISMATCH"
    expires = datetime.fromisoformat(str(current["expires_at"]).replace("Z", "+00:00"))
    same_instance = current.get("owner_agent_id") == agent_id and current.get("owner_agent_instance_id") == agent_instance_id
    if same_instance:
        return True, "RENEW"
    if expires <= now:
        return True, "EXPIRED_RECLAIM"
    if current.get("owner_agent_id") == agent_id:
        return False, "STALE_INSTANCE"
    return False, "LEASE_HELD"


def deterministic_backoff(operation_key: str, attempt: int, cap_seconds: float = 8.0) -> float:
    if attempt < 0:
        raise ValueError("attempt must be non-negative")
    seed = int(hashlib.sha256(f"{operation_key}|{attempt}".encode()).hexdigest()[:16], 16)
    ceiling = min(cap_seconds, 0.25 * (2 ** min(attempt, 8)))
    return random.Random(seed).uniform(0.05, max(0.05, ceiling))


def idempotency_record(cfg: ProjectConfig, global_run_id: str, op_id: str, result_ref: str) -> dict[str, Any]:
    require_safe_id(global_run_id, "global_run_id")
    require_safe_id(op_id, "operation_id")
    return {"schema": "swarm-kernel/idempotency/v1", "project_id": cfg.project_id, "global_run_id": global_run_id, "operation_id": op_id, "result_ref": result_ref, "committed_at": iso()}


def quarantine_record(cfg: ProjectConfig, global_run_id: str, item_id: str, reason: str, details: str) -> dict[str, Any]:
    if reason not in QUARANTINE_REASONS:
        raise ValueError("unsupported quarantine reason")
    return {"schema": "swarm-kernel/quarantine/v1", "project_id": cfg.project_id, "global_run_id": global_run_id, "item_id": require_safe_id(item_id, "item_id"), "reason": reason, "details": details, "timestamp_utc": iso(), "action": "NO_EXECUTION"}


def circuit_state(cfg: ProjectConfig, consecutive_invariant_failures: int) -> str:
    return "DEGRADED_READ_ONLY" if consecutive_invariant_failures >= cfg.circuit_breaker_threshold else "ACTIVE"


def backpressure_state(cfg: ProjectConfig, manager_queue_depth: int) -> str:
    if manager_queue_depth >= cfg.manager_queue_hard_limit:
        return "HARD_STOP_SECONDARY_WORK"
    if manager_queue_depth >= cfg.manager_queue_soft_limit:
        return "SLOW_SECONDARY_WORK"
    return "NORMAL"


def admission_state(cfg: ProjectConfig, active_specialists: int, *, capacity_known: bool) -> str:
    if not capacity_known:
        return "CAPACITY_UNKNOWN_READ_ONLY"
    if active_specialists >= cfg.max_active_specialists:
        return "MAX_ACTIVE_SPECIALISTS_REACHED"
    return "ADMIT"


def preflight(cfg: ProjectConfig, checks: Mapping[str, bool]) -> dict[str, Any]:
    required = ("identity_binding", "instance_binding", "run_epoch", "role_binding", "master_handoff_loaded", "package_parity", "capacity_admission", "recovery_state", "manager_presence", "foreign_write_policy", "tests")
    missing = [name for name in required if name not in checks]
    failed = [name for name in required if checks.get(name) is not True]
    return {"schema": "swarm-kernel/preflight/v2", "project_id": cfg.project_id, "kernel_version": cfg.kernel_version, "required_checks": list(required), "missing": missing, "failed": failed, "ready": not missing and not failed, "timestamp_utc": iso()}


def convergence_gate(*, research_accounted: bool, manager_dispositions_complete: bool, primary_decisions_persisted: bool, package_parity_restored: bool, unresolved_leases: int, recovery_checkpoint_valid: bool, master_handoff_checkpointed: bool = True) -> dict[str, Any]:
    checks = {"research_accounted": research_accounted, "manager_dispositions_complete": manager_dispositions_complete, "primary_decisions_persisted": primary_decisions_persisted, "package_parity_restored": package_parity_restored, "no_unresolved_leases": unresolved_leases == 0, "recovery_checkpoint_valid": recovery_checkpoint_valid, "master_handoff_checkpointed": master_handoff_checkpointed}
    return {"schema": "swarm-kernel/convergence/v2", "checks": checks, "complete": all(checks.values())}


def health_snapshot(cfg: ProjectConfig, global_run_id: str, *, state: str, active_agents: int, manager_queue_depth: int, collisions: int, failed_checks: int, last_accepted_integration: str | None, package_version: str, capacity_known: bool = True) -> dict[str, Any]:
    if state not in RUN_STATES:
        raise ValueError("invalid run state")
    return {"schema": "swarm-kernel/health/v2", "kernel_version": cfg.kernel_version, "project_id": cfg.project_id, "repository": cfg.repository, "global_run_id": global_run_id, "state": state, "active_agents": active_agents, "manager_queue_depth": manager_queue_depth, "backpressure": backpressure_state(cfg, manager_queue_depth), "admission": admission_state(cfg, active_agents, capacity_known=capacity_known), "collisions": collisions, "failed_checks": failed_checks, "last_accepted_integration": last_accepted_integration, "package_version": package_version, "cross_project_authority": "NONE", "telemetry_visibility": "READ_ONLY", "swarm_state_authority": "PROJECT_LOCAL_OPERATIONAL_RECOVERY_STATE", "timestamp_utc": iso()}
