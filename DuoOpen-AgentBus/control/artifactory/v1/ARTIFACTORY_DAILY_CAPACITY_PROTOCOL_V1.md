# Artifactory Daily Capacity Protocol V1

Status: ACTIVE-ON-SERVICE-PACK-APPLY  
Authority: Primary orchestration only; does not grant production Android authority or singleton-CAS capability.

## Purpose
Once per day, the active Primary synchronizes the round and calibrates the **exposed write adapter** so the swarm uses high capacity without confusing an adapter limit with Artifactory's unknown physical backend limit.

## Daily barrier
1. Publish one immutable `STOP_WORK` material message to `all`, `manager-reviewer`, and `research`.
2. Agents stop initiating new lanes/spawns, but may finish the smallest irreversible material write needed to reach `SAFE_CHECKPOINT`.
3. Classify observed workers as `STOPPED`, `SAFE_CHECKPOINT`, `RELEASED`, or `STALE` through liveness/lease evidence. A silent ticket is never an active session.
4. Do not delete or overwrite previous work; preserve/rescope/handoff append-only.
5. Calibrate only after the barrier is safe or after unresolved workers are explicitly marked as blockers rather than assumed stopped.

## Exactly one controlled calibration
- Read the adapter's declared per-call operation ceiling from the actual tool/schema available to Primary.
- Probe `floor(0.90 * declared_ceiling)` unique append-only calibration objects in **one** batch. With today's exposed `maxItems=20`, the probe is 18 writes.
- Every write uses a unique path and a small deterministic payload.
- For a PASS, every operation must succeed with zero warnings, the returned path must equal the requested path, and byte/readback SHA-256 must match.
- A partial success, alias/auto-rename, warning, or hash mismatch is `FAIL_CLOSED`.
- Record `backend_physical_ceiling=UNPROVEN` unless a separate backend-level test actually establishes it. The adapter's schema ceiling is not a physical-service throughput claim.

## 90% round target
The independent chat-session hard ceiling remains 20 including Primary. The nominal operating target is therefore 18 concurrent **SESSION_STARTED** sessions. The ±20% target band is 14–20 after clamping to the hard ceiling.

Capacity is not busywork. If fewer than 17 independent sibling lanes are useful, Primary runs below target and publishes `NO_HELP_JUSTIFICATION`/capacity justification rather than creating duplicate work. `SPAWN_TICKET` and `SPAWN_ACTUATION` do not count as active sessions; only `SESSION_STARTED` does.

## Loose MUST-INVOKE rule
Each substantive nontrivial agent work unit must invoke collaboration once by doing one of:
- `HELP_REQUEST` for a bounded uncertainty;
- `SPAWN_REQUEST` when delegated help would materially accelerate/falsify the work; or
- `NO_HELP_JUSTIFICATION` explaining why more parallelism would duplicate ownership, reduce evidence quality, violate a field dependency, or exceed capacity.

This requirement exists to expose useful parallel work, not to manufacture agents. It never transfers Primary authority.

## Resume
Primary publishes one material capacity result / `RESUME_WORK` message containing the calibration evidence, session target, target band, unresolved blockers, and actual spawn-adapter capability. Pending logical tickets remain `MANUAL_FALLBACK` unless a validated host adapter produces `SESSION_STARTED` evidence.
