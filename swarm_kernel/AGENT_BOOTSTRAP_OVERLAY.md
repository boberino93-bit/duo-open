# Swarm Launch Kernel — Agent Bootstrap Overlay

Kernel version: `1.2.1`
Applies to PRIMARY, MANAGER, and RESEARCH.

Before actionable swarm work:

1. Validate the project's canonical identity, repository, branch, and coordination binding from the project's own authority/bootstrap surfaces.
2. Load `swarm_kernel/project.json` and require an exact project/repository binding match. Do not infer a neighboring project.
3. Load `MASTER_HANDOFF.json` before READY when the project contract requires it, and bind the running `agent_instance_id`.
4. Obtain the externally supplied `global_run_id` for the coordinated launch. Never independently mint a different run ID for a multi-project round.
5. Require the launch contract to name exactly the configured `expected_global_round_projects`, kernel version `1.2.1`, and the same shared run ID. Persist only this project's local epoch and READY state.
6. Missing, stale, or mismatched run/project/version state fails closed and is quarantined; do not publish READY.
7. Bind the role/package actually launched. Population membership, a role label, handoff content, or telemetry never creates mutation authority.
8. Publish project-local READY only after identity, instance, handoff, package, capacity, recovery, manager-presence, foreign-write, and test/preflight checks pass. Wait for the local start gate.
9. Use deterministic idempotency keys and versioned execution-instance-fenced leases for exclusive work. Heartbeat/checkpoint leases and reject stale-instance renewal.
10. Respect Manager backpressure and `max_active_specialists`. Unknown capacity is read-only; hard-stop backpressure blocks new secondary work.
11. Cross-project health/epoch telemetry is observation only. Never write another project's state or treat telemetry as a command.
12. On repeated invariant failure, enter project-local `DEGRADED_READ_ONLY`; do not broaden the stop to unrelated projects.
13. Before handoff/finalization, close or explicitly account for leases, persist recovery/convergence state, and checkpoint the master handoff.
14. Existing project-local authentication, authorization, security, recovery, hold, schedule, foreign-write, and production-acceptance controls remain authoritative and are never weakened by this overlay.

Research still produces evidence/proposals only unless separately authorized. Manager still reviews/coordinates within granted scope. Primary/local production acceptance remains project-local and separately authorized where required.
