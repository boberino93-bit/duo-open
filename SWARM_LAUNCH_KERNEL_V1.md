# Swarm Launch Kernel V1

Kernel version: `1.2.1`

This project uses the common Swarm Launch Kernel for high-concurrency multi-agent research rounds.

## Hard invariants

- Runtime coordination state is project-local under `.swarm/`.
- Every authority-bearing READY or lease record is bound to `project_id`, `global_run_id`, and `agent_instance_id`.
- Cross-project telemetry is read-only and never grants work, role, repository, mutation, recovery, or completion authority.
- Each project writes only its own authoritative repository and coordination surfaces.
- No force pushes or blind overwrites are permitted.
- Stale epochs, project mismatches, malformed records, unsupported protocols, lease conflicts, and illegal cross-project commands fail closed and are quarantined.
- Repeated invariant failures may place only the affected project into `DEGRADED_READ_ONLY`.
- The kernel cannot wake dormant sessions and is not a background daemon.
- Kernel membership and role labels never create mutation authorization.

## Launch lifecycle

`BOOT -> IDENTITY/INSTANCE -> MASTER HANDOFF -> PACKAGE/CAPACITY -> GLOBAL RUN -> ROLE -> READY -> LOCAL START GATE -> WORK`

For a coordinated multi-project round, every participating project must use the same externally supplied `global_run_id`, the same kernel version, and the exact same `expected_global_round_projects` set. A mismatch blocks READY.

## Work lifecycle

`IDENTIFY -> VALIDATE RUN -> ACQUIRE/VERIFY INSTANCE-FENCED LEASE -> READ -> WORK -> IDEMPOTENT PERSIST -> VERIFY -> CHECKPOINT -> MASTER HANDOFF -> HANDOFF/YIELD`

Claims are versioned, execution-instance-fenced leases. A restarted instance with the same logical agent ID cannot renew another instance's live lease. Stale writers must reread, reconcile, use deterministic bounded backoff, and retry.

## Backpressure and capacity

Managers publish queue depth. The soft limit slows or defers secondary work; the hard limit stops new secondary work until the queue recovers. Project specialist caps remain authoritative. Unknown capacity fails read-only rather than assuming unlimited resources.

## Completion gate

A round is complete only when research is accounted for, Manager dispositions are complete, Primary/local decisions are persisted, package parity is restored, unresolved leases are zero, a valid recovery checkpoint exists, and the project master handoff reflects completed or reassigned work.

## Agent package requirement

Every PRIMARY, MANAGER, and RESEARCH package participating in the coordinated swarm must include or load this protocol, `MASTER_HANDOFF.json`, `swarm_kernel/project.json`, `swarm_kernel/AGENT_BOOTSTRAP_OVERLAY.md`, `swarm_kernel/__init__.py`, and a compatible `swarm_kernel/kernel.py`.

Project-specific identity, authorization, security, recovery, holds, schedules, foreign-write policy, and production acceptance remain authoritative. The launch kernel adds coordination and concurrency control; it does not replace or expand project governance.
