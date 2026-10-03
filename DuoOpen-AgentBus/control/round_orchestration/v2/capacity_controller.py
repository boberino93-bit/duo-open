#!/usr/bin/env python3
"""Duo Open Round Orchestration V2 reference model.

This module is deliberately host-neutral. It models policy and evidence semantics only;
it does not create ChatGPT sessions or claim backend capabilities that were not measured.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math
from typing import Iterable, Mapping

HARD_SESSION_CEILING = 20
DEFAULT_TARGET_UTILIZATION = 0.90
DEFAULT_TOLERANCE = 0.20
MATERIAL_EVENTS = {
    "CLAIM", "RESCOPE", "FINDING", "BLOCKER", "CONTRADICTION", "REVIEW_REQUEST",
    "REVIEW_DISPOSITION", "DECISION", "HANDOFF", "SUPERSEDE", "ROUND_OPEN",
    "ROUND_CLOSE", "SESSION_RELEASED", "REQUIRED_ACK", "CAPACITY_CALIBRATION",
    "STOP_WORK", "RESUME_WORK",
}
VALID_INVOCATIONS = {"HELP_REQUEST", "SPAWN_REQUEST", "NO_HELP_JUSTIFICATION"}

@dataclass(frozen=True)
class CapacityPlan:
    hard_ceiling: int
    raw_target_sessions: int
    recommended_sessions: int
    minimum_tolerance_sessions: int
    maximum_tolerance_sessions: int
    under_target_justification_required: bool

@dataclass(frozen=True)
class CalibrationResult:
    adapter_declared_operation_ceiling: int
    target_utilization: float
    attempted: int
    succeeded: int
    warnings: int
    exact_path_matches: int
    readback_hash_matches: int
    status: str
    proven_safe_batch_floor: int
    backend_physical_ceiling: str = "UNPROVEN"

@dataclass
class RoundState:
    hard_ceiling: int = HARD_SESSION_CEILING
    active_sessions: set[str] = field(default_factory=set)
    ticket_to_session: dict[str, str] = field(default_factory=dict)

    def apply(self, event: Mapping[str, object]) -> None:
        kind = str(event.get("event_type", ""))
        if kind == "SESSION_STARTED":
            session_id = str(event["session_id"])
            ticket_id = str(event["ticket_id"])
            if session_id in self.active_sessions:
                return
            if len(self.active_sessions) >= self.hard_ceiling:
                raise ValueError("hard session ceiling exceeded")
            existing = self.ticket_to_session.get(ticket_id)
            if existing and existing != session_id:
                raise ValueError("ticket already claimed by another active session")
            self.active_sessions.add(session_id)
            self.ticket_to_session[ticket_id] = session_id
        elif kind == "SESSION_RELEASED":
            session_id = str(event["session_id"])
            self.active_sessions.discard(session_id)
            for ticket, session in list(self.ticket_to_session.items()):
                if session == session_id:
                    del self.ticket_to_session[ticket]
        elif kind in {"SPAWN_TICKET", "SPAWN_ACTUATION", "HELP_REQUEST", "SPAWN_REQUEST"}:
            # Logical control records are not active-session evidence.
            return


def capacity_plan(hard_ceiling: int = HARD_SESSION_CEILING,
                  utilization: float = DEFAULT_TARGET_UTILIZATION,
                  tolerance: float = DEFAULT_TOLERANCE,
                  useful_parallel_lanes: int | None = None) -> CapacityPlan:
    """Return the 90%-target plan, bounded by useful independent work.

    useful_parallel_lanes counts sibling lanes. Primary is included separately, so 17 useful
    sibling lanes support the normal target of 18 total sessions. A lower useful-work count is
    permitted and must be recorded as an intentional under-target justification, never filled
    with duplicate/busywork lanes.
    """
    if hard_ceiling < 1:
        raise ValueError("hard_ceiling must be >= 1")
    if not 0 < utilization <= 1:
        raise ValueError("utilization must be in (0, 1]")
    if tolerance < 0:
        raise ValueError("tolerance must be >= 0")
    raw_target = max(1, math.floor(hard_ceiling * utilization))
    low = max(1, math.floor(raw_target * (1 - tolerance)))
    high = min(hard_ceiling, math.ceil(raw_target * (1 + tolerance)))
    if useful_parallel_lanes is None:
        recommended = raw_target
    else:
        if useful_parallel_lanes < 0:
            raise ValueError("useful_parallel_lanes must be >= 0")
        recommended = min(raw_target, 1 + useful_parallel_lanes)
    return CapacityPlan(
        hard_ceiling=hard_ceiling,
        raw_target_sessions=raw_target,
        recommended_sessions=recommended,
        minimum_tolerance_sessions=low,
        maximum_tolerance_sessions=high,
        under_target_justification_required=recommended < low,
    )


def calibration_probe_count(adapter_operation_ceiling: int,
                            utilization: float = DEFAULT_TARGET_UTILIZATION) -> int:
    if adapter_operation_ceiling < 1:
        raise ValueError("adapter_operation_ceiling must be >= 1")
    if not 0 < utilization <= 1:
        raise ValueError("utilization must be in (0, 1]")
    return max(1, math.floor(adapter_operation_ceiling * utilization))


def evaluate_calibration(adapter_operation_ceiling: int, attempted: int, succeeded: int,
                         warnings: int, exact_path_matches: int,
                         readback_hash_matches: int,
                         utilization: float = DEFAULT_TARGET_UTILIZATION) -> CalibrationResult:
    target = calibration_probe_count(adapter_operation_ceiling, utilization)
    if attempted != target:
        status = "INVALID_PROBE_SIZE"
    elif min(succeeded, exact_path_matches, readback_hash_matches) == attempted and warnings == 0:
        status = "PASS_ADAPTER_BATCH_TARGET"
    else:
        status = "FAIL_CLOSED"
    safe = attempted if status == "PASS_ADAPTER_BATCH_TARGET" else max(
        0, min(succeeded, exact_path_matches, readback_hash_matches)
    )
    return CalibrationResult(
        adapter_declared_operation_ceiling=adapter_operation_ceiling,
        target_utilization=utilization,
        attempted=attempted,
        succeeded=succeeded,
        warnings=warnings,
        exact_path_matches=exact_path_matches,
        readback_hash_matches=readback_hash_matches,
        status=status,
        proven_safe_batch_floor=safe,
    )


def publication_ack(requested_path: str, actual_path: str,
                    expected_sha256: str, readback_sha256: str) -> bool:
    """A storage ACK is valid only for exact path + byte-identity evidence."""
    return requested_path == actual_path and expected_sha256 == readback_sha256


def should_write_material_message(event_kind: str, finding_delta: str | None = None,
                                  required_ack: bool = False) -> bool:
    if required_ack:
        return True
    if event_kind in MATERIAL_EVENTS:
        return True
    return bool(finding_delta and finding_delta not in {"NO_DELTA", "NONE", ""})


def valid_collaboration_invocation(kind: str, body: str | None = None) -> bool:
    """Loose MUST-invoke rule: request bounded help or explain why more agents would hurt."""
    if kind not in VALID_INVOCATIONS:
        return False
    if kind == "NO_HELP_JUSTIFICATION":
        return bool(body and body.strip())
    return True


def stop_barrier_satisfied(worker_states: Iterable[str]) -> bool:
    """Resume only after every observed worker reached a safe state.

    STALE means the worker was independently aged out by lease/liveness logic; it is not an ACK.
    SAFE_CHECKPOINT lets an agent finish the smallest irreversible write/handoff before stopping.
    """
    safe = {"STOPPED", "SAFE_CHECKPOINT", "STALE", "RELEASED"}
    states = list(worker_states)
    return bool(states) and all(s in safe for s in states)
