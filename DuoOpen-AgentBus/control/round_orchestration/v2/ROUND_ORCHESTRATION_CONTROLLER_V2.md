# Duo Open Round Orchestration Controller V2 — Capacity-Calibrated Mesh

Status: ACTIVE-ON-SERVICE-PACK-APPLY  
Supersedes: V1 where explicitly stated; all V1 authority/safety boundaries otherwise remain.

## New V2 rules
1. Hard concurrent-session ceiling remains **20 including Primary**.
2. Nominal target is **18 SESSION_STARTED sessions** (90%) with a clamped ±20% target band of **14–20**.
3. Target utilization is subordinate to useful parallelism: never create duplicate/busywork lanes merely to reach 18.
4. Ticket creation is logical spawning only. Current normal-chat host capability remains `MANUAL_FALLBACK` until a separately validated Spawn Adapter proves otherwise.
5. Once per day, Primary runs `ARTIFACTORY_DAILY_CAPACITY_PROTOCOL_V1.md`: STOP_WORK barrier -> one controlled 90% adapter probe -> publish result -> RESUME.
6. Write-batch capacity and chat-session concurrency are separate variables. Success at 18 Library operations does not prove 18 simultaneous agents or an Artifactory backend maximum.
7. Each substantive agent work unit follows `MUST_INVOKE_OR_JUSTIFY`: bounded HELP/SPAWN request or explicit no-help justification.
8. Liveness uses the DMSH/presence plane; immutable `/messages/` are reserved for material state/knowledge/authority transitions and required ACKs. A required material-message failure remains fail-closed.
9. Library path creation is not CAS. Returned path must equal requested path and readback hash must match before publication ACK; auto-renamed siblings are collisions/aliases, not successful idempotent creates.
10. Singleton Primary fencing remains blocked until a truly linearizable conditional-write backend is validated. V2 capacity calibration does not change that.

## Stop barrier states
`RUNNING -> STOP_REQUESTED -> SAFE_CHECKPOINT -> STOPPED/RELEASED`. Independently expired/dead workers may be `STALE` after normal lease/liveness validation. Primary must not call a worker stopped merely because a chat is dormant or a ticket is unclaimed.

## Allocation algorithm
- `raw_target = floor(20 * 0.90) = 18`.
- `recommended = min(raw_target, 1 + useful_independent_sibling_lanes)` when the lane count is known.
- If recommended < 14, record an under-target justification.
- Never exceed 20 active `SESSION_STARTED` sessions.
- Do not count tickets, actuation attempts, dormant chats, or stalled/unverified sessions as active without current evidence.

## Current round bootstrap
The 2026-10-03 round opens with Primary + 1 Manager + 16 Research logical slots. The live host is `MANUAL_FALLBACK`; therefore the 17 child tickets are pending until individually claimed by actual sessions. Lane assignments deliberately split physical Fold7 P0 work from Artifactory/control-plane hardening.

## Field priority
Physical Fold7 evidence remains the product center of gravity. No service-pack/controller success may be promoted as proof that the INNER display early-enable or first-open crash is fixed. Runtime promotion still requires useful-pixel and process/lifecycle evidence from the device.
