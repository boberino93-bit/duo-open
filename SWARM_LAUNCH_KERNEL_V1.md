# Swarm Launch Kernel V1

Kernel version: `1.0.0`

This project uses the common Swarm Launch Kernel for high-concurrency multi-agent research rounds.

## Hard invariants

- Runtime coordination state is project-local under `.swarm/`.
- Every record carries `project_id` and `global_run_id`.
- Cross-project telemetry is read-only. It never conveys commands or authority.
- A project may write only its own repository/authoritative coordination surface.
- No force pushes or blind overwrites are permitted for coordination state.
- Existing AgentBus/Artifactory history remains append-only.
- Stale run epochs, project mismatches, malformed messages, unsupported protocols, and illegal cross-project commands are quarantined rather than executed.
- A circuit breaker may place only this project into `DEGRADED_READ_ONLY`; it does not stop unrelated projects.
- The kernel cannot wake dormant sessions and is not a background daemon.

## Launch lifecycle

`BOOT -> IDENTITY -> PACKAGE -> GLOBAL RUN -> ROLE -> READY -> LOCAL START GATE -> WORK`

The local start gate opens only when expected workers are READY or the authorized local controller explicitly closes the startup window with missing workers recorded.

## Work lifecycle

`IDENTIFY -> VALIDATE RUN -> ACQUIRE/VERIFY LEASE -> READ -> WORK -> IDEMPOTENT PERSIST -> VERIFY -> CHECKPOINT -> HANDOFF`

Claims are versioned leases. On GitHub, creation of a new lease path is create-if-absent; renewal/reassignment of an existing lease must use the currently observed blob SHA plus the lease's expected version. A stale write must reread, reconcile, apply deterministic bounded backoff, and retry. It must never force-push.

## State layout

- `.swarm/epochs/<run>/<record>.json`
- `.swarm/ready/<run>/<agent>.json`
- `.swarm/leases/<run>/<task>.json`
- `.swarm/idempotency/<run>/<operation>.json`
- `.swarm/quarantine/<run>/<record>.json`
- `.swarm/health/<run>/<project>.json`
- `.swarm/checkpoints/<run>/<record>.json`
- `.swarm/convergence/<run>/<record>.json`

Separate files deliberately avoid one global mutable state hotspot.

## Backpressure

Managers publish queue depth. At the soft limit, agents slow/defer secondary work. At the hard limit, no new secondary work begins until the queue recovers. Assigned critical work and safety/recovery actions may continue subject to local authority.

## Circuit breaker

Repeated invariant failures at or above the project threshold move the project into `DEGRADED_READ_ONLY`. Existing evidence can be read and diagnostics can be published locally; production/integration mutations pause until the Primary/local authority clears the condition after reconciliation.

## Completion gate

A round is not complete until research work is accounted for, manager dispositions are complete, Primary/local integration decisions are persisted, package parity is restored, no unresolved leases remain, and a valid recovery checkpoint exists.

## Agent package requirement

Every PRIMARY, MANAGER, and RESEARCH package must include or load this protocol, `swarm_kernel/project.json`, `swarm_kernel/AGENT_BOOTSTRAP_OVERLAY.md`, and a compatible `swarm_kernel/kernel.py`.

Project-specific authority remains defined by the project's own identity/AgentBus contracts. The kernel adds concurrency control; it does not replace project governance.
