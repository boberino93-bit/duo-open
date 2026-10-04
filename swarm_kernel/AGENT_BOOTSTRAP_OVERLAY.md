# Swarm Launch Kernel — Agent Bootstrap Overlay

Applies to `PRIMARY`, `MANAGER`, and `RESEARCH` roles.

Before actionable project work:

1. Validate the project's canonical identity and writable repository using existing project authority.
2. Load `swarm_kernel/project.json` and require its project/repository/branch/coordination binding to agree with project authority.
3. Obtain the externally supplied `global_run_id` for the coordinated launch. Do not independently mint a different run ID when participating in a multi-project round.
4. Require the launch contract to name exactly the `expected_global_round_projects` from `swarm_kernel/project.json`, the same kernel version, and the same global run ID used by the other participating projects. Persist only Duo Open's local epoch record; never write another project's epoch.
5. If the launch epoch or project set is missing, stale, or mismatched, fail closed and quarantine it; do not publish READY.
6. Bind to the role and package/version actually launched.
7. Publish a project-local READY record for the run.
8. Do not start normal work until the local start gate is open.
9. Use versioned leases for claimable work and deterministic idempotency keys for retryable publications.
10. Heartbeat/checkpoint active leases before expiry; reclaim an expired lease only after rereading current state.
11. Respect Manager backpressure.
12. Quarantine malformed, stale-run, wrong-project, unsupported-protocol, or illegal cross-project commands rather than acting on them.
13. If the circuit breaker enters `DEGRADED_READ_ONLY`, stop integration mutations and reconcile.
14. Before handoff/finalization, close leases, persist a checkpoint, and participate in the convergence gate.

Role-specific authority is unchanged: Research produces evidence/proposals; Manager/Reviewer reviews and coordinates within granted scope; Primary alone retains Duo Open production acceptance/integration authority.

Cross-project health and epoch telemetry are observation only. They cannot grant work, role, repository, command, or integration authority. The shared run value synchronizes round identity; it does not create shared mutable project state.
