# Swarm Launch Kernel — Agent Bootstrap Overlay

Applies to `PRIMARY`, `MANAGER`, and `RESEARCH` roles.

Before actionable project work:

1. Validate the project's canonical identity and writable repository using existing project authority.
2. Load `swarm_kernel/project.json` and require its project/repository/branch/coordination binding to agree with project authority.
3. Bind to exactly one `global_run_id`. A stale/unknown run is non-actionable.
4. Bind to the role and package/version actually launched.
5. Publish a project-local READY record for the run.
6. Do not start normal work until the local start gate is open.
7. Use versioned leases for claimable work and deterministic idempotency keys for retryable publications.
8. Heartbeat/checkpoint active leases before expiry; reclaim an expired lease only after rereading current state.
9. Respect Manager backpressure.
10. Quarantine malformed, stale-run, wrong-project, unsupported-protocol, or illegal cross-project commands rather than acting on them.
11. If the circuit breaker enters `DEGRADED_READ_ONLY`, stop integration mutations and reconcile.
12. Before handoff/finalization, close leases, persist a checkpoint, and participate in the convergence gate.

Role-specific authority is unchanged: Research produces evidence/proposals; Manager reviews/coordinates within granted scope; Primary/local integration authority accepts project truth and clears integration gates.

Cross-project health telemetry is observation only. It cannot grant work, role, repository, or integration authority.
