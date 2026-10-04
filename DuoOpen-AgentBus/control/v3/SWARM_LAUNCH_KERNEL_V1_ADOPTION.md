# Duo Open — Swarm Launch Kernel V1 Adoption

Status: ACTIVE
Kernel: `1.0.0`
Project: `duo-open`
Repository: `boberino93-bit/duo-open`
Canonical coordination: `/DuoOpen-AgentBus/`

By explicit human direction, all new and regenerated PRIMARY, MANAGER/REVIEWER, and RESEARCH deployment/bootstrap/replication packages must include or load:

- `/SWARM_LAUNCH_KERNEL_V1.md`
- `/swarm_kernel/project.json`
- `/swarm_kernel/AGENT_BOOTSTRAP_OVERLAY.md`
- `/swarm_kernel/kernel.py`

Agents must bind a project-local `global_run_id`, register READY before ordinary round work, use versioned leases for claimable work, use idempotency keys for retryable material publications, obey Manager backpressure, quarantine stale/wrong-project/illegal cross-project work, and participate in the convergence gate before the round is complete.

This does not replace DMSH/3, the active service interval, review pipeline, regression-continuity contract, or Primary production authority. It supplies additional concurrency semantics for full-system simultaneous research rounds.

Cross-project health telemetry is read-only and carries no work, command, role, repository, or integration authority. No shared writable cross-project bus is authorized.

Existing AgentBus history is immutable. Older packages are evidence only for future launches if they do not carry the kernel; regenerate packages before using them in a new global run.
