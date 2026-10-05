# Fold7 S1T Physical Validation Protocol

Status: `FROZEN BEFORE DEVICE EXECUTION`
Date: 2026-10-05
Target: Samsung Galaxy Z Fold7
Stage: `S1T_CYCLE_AWARE_NATIVE_COVER_V1`

## Frozen software baseline

Use exactly the successfully reconstructed S1T artifact from GitHub Actions run `37305259258`:

- repository head: `c1f6b0dd742862c20622938303a43a3711a19380`
- artifact: `DuoOpen-S1T-Cycle-Aware-Terminal-Fence-V1`
- artifact id: `11344130205`
- artifact digest: `sha256:d1877f1df434489bd448de039189d4834205fc7cb253d8893440ca5e713e44cf`
- versionCode: `54`
- versionName: `5.1.0-beta2-zfold7-s1t`

The artifact includes the APK, APK hash, reconstructed runtime-critical source snapshot, materialized-source SHA-256 manifest, and complete materialized runtime patch. Do not substitute another APK while retaining the S1T label.

## Question under test

Does the physical Fold7 preserve S1T's intended close-cycle behavior within one daemon lifetime?

The intended behavior is narrow:

1. once close cycle `C1` legitimately reaches native cover, delayed work from `C1` or an older cycle must not resurrect the secondary cover route;
2. a strictly newer close cycle `C2 > C1` must still be allowed to prepare the cover again;
3. the completed terminal close-cycle identity must never regress within one `shellSession`;
4. a service/recovery rollover may reset the terminal-cycle fence by design and therefore must be classified as a new daemon lifetime rather than as continuation of the prior lifetime.

This protocol does not attempt to prove every Duo Open continuity property at once.

## Evidence fields

Retain the Gen4 receipt fields for every relevant transition. S1T must expose at least:

- `ok`
- `stale`
- `cleanupRequired`
- `operation`
- `decision`
- `error`
- `gen4Phase`
- `gen4RecoveryReady`
- `gen4IntentSequence`
- `gen4TerminalCloseCycleId`
- `shellSession`
- `shellRevision`
- `leaseState`
- `leaseId`
- `leaseEpoch`
- `ownerGeneration`
- `ownerServiceEpoch`
- `ownerCloseCycleId`
- `physicalDisplayId`
- `targetDisplayId`
- `physicalLeaseHeld`
- `routeReady`

Also retain wall-clock/monotonic capture time and the physical observation for each sample. Do not infer a missing field from another field.

## Evidence integrity

For the device session record:

- record the exact APK SHA-256 before install;
- record device model/build/One UI/Android version and Duo package/version;
- record whether the install was fresh or an upgrade;
- record Shizuku state and whether the shell service restarted during the test;
- preserve raw Gen4 receipts/logs before writing any interpretation;
- preserve failures and anomalous cycles rather than rerunning until a clean result appears;
- if `shellSession` changes, split the evidence into separate daemon lifetimes immediately.

A physical pass may not be claimed from screenshots alone. A telemetry-only pass may not be claimed if the visible display behavior contradicts it.

## Phase A — establish a clean lifetime

1. Start from the device physically open with the inner display as the native/default display.
2. Start Duo Open and establish Shizuku/shell connectivity.
3. Capture the first valid Gen4 receipt after startup/reconciliation.
4. Require:
   - `gen4=true`;
   - `gen4RecoveryReady=true`;
   - a nonzero `shellSession`;
   - no unresolved cleanup error.
5. Record this value as lifetime `S`.
6. If startup begins in `RECOVERING`, retain that evidence and wait only for the bounded existing recovery path. Do not manually rewrite state to force a clean start.

## Phase B — first complete close cycle C1

From the stable open/inner state:

1. Close the Fold7 normally once.
2. Retain all Gen4 receipts for the transition.
3. Identify the accepted close cycle as `C1` from `ownerCloseCycleId` / `leaseEpoch` while the owner is live.
4. Require `C1 > 0`.
5. During preparation, observe the expected state progression without inventing missing intermediate samples. Valid observed states may include:
   - `COVER_PREPARING` / `PREWARM_IN_FLIGHT`;
   - `COVER_READY_HIDDEN` / `HELD` when the route becomes ready.
6. When Samsung/native cover authority is restored, require the final Gen4 state to be native/idle and retain `gen4TerminalCloseCycleId`.
7. Require `gen4TerminalCloseCycleId == C1` once C1 has completed to native cover.
8. Record visible behavior: which panel is showing content, whether the expected home/app continuity appeared, whether a stale mirrored/secondary route resurfaced, and any black/frozen/incorrect frame interval. Record timing; do not apply an invented pass threshold.

## Phase C — stale-work containment after C1

Keep the same `shellSession = S`.

1. Leave the phone in the completed/native-cover condition long enough to capture any naturally delayed Gen4 activity produced by the real device path.
2. Require `gen4TerminalCloseCycleId` to remain `C1` throughout this lifetime until a newer cycle completes.
3. Require no receipt attributable to owner close cycle `<= C1` to return the authority to `COVER_PREPARING` or `COVER_READY_HIDDEN` after C1 is terminal.
4. Require no physical resurrection of an obsolete secondary cover route after Samsung/native cover has taken authority.
5. If no delayed stale mutation is naturally emitted, record `STALE_COMMAND_NOT_PHYSICALLY_INJECTED`. Do not convert the unit-test stale rejection into a claim that a stale physical command was observed.

The software regression test remains the direct stale-command injection evidence; this phase verifies the real device does not contradict it under natural timing.

## Phase D — strictly newer close cycle C2

1. Open the Fold7 back to a stable inner/native state without restarting the shell service.
2. Verify `shellSession` is still `S`.
3. Close the Fold7 normally again.
4. Identify the next accepted live owner close cycle as `C2`.
5. Require `C2 > C1`.
6. The decisive S1T physical gate is:
   - while the terminal fence still records `C1`, the newer `C2` preparation is accepted rather than rejected as stale;
   - the state is allowed to enter `COVER_PREPARING` and, when successful, `COVER_READY_HIDDEN`;
   - after C2 completes to native cover, `gen4TerminalCloseCycleId == C2`.
7. A result where the device remains stuck in `NATIVE_COVER` solely because C2 cannot prepare is `S1T_FAIL_NEWER_CYCLE_BLOCKED`.

## Phase E — repeated-cycle endurance

Without intentionally restarting the daemon, execute at least five additional open→close cycles.

For each cycle `Cn`:

- retain the full available Gen4 receipt sequence;
- require the accepted close-cycle identity to be strictly greater than the previous accepted close cycle;
- require `shellSession` to remain `S`;
- require `shellRevision` and `gen4IntentSequence` not to move backward;
- require `gen4TerminalCloseCycleId` not to regress;
- require a newer close cycle to remain eligible for preparation;
- record visible panel/continuity behavior and any anomalous frame/route state.

A single failure is retained as evidence and is not erased by later successes.

## Phase F — service/recovery rollover

This phase is separate because S1T intentionally resets its terminal-cycle memory on recovery/service rollover.

1. After the same-lifetime cycle test is complete, intentionally perform one controlled shell/service restart using the normal supported mechanism.
2. Capture the first post-restart Gen4 evidence.
3. Require the new lifetime to be visibly distinguishable by a changed `shellSession` or other explicit service-lifetime evidence.
4. A reset `gen4TerminalCloseCycleId = 0` after a genuine new lifetime is **expected by current S1T design**, not automatically a failure.
5. Execute one new open→close cycle in the new lifetime and verify that the fence is re-established from the new completed cycle.
6. If `gen4TerminalCloseCycleId` resets while `shellSession` did not change and no recovery/rollover occurred, classify `S1T_FAIL_UNEXPECTED_FENCE_RESET`.

This phase evaluates recovery semantics; it does not change the same-lifetime acceptance criteria above.

## Visual continuity observations

For every cycle, record rather than assume:

- starting foreground app/surface;
- whether inner content remains correct while opening;
- whether cover content appears when closing;
- whether Samsung/native cover ownership lands cleanly;
- visible black frame, frozen frame, wrong panel, duplicated content, stretched/cropped content, launcher jump, lock-screen appearance, or unwanted wake;
- whether the next open/close cycle still functions without manual recovery.

Because the current purpose is diagnosis, preserve measured transition timings and frame evidence without inventing a subjective latency threshold after seeing the data.

## Acceptance matrix

S1T may be labeled `PHYSICAL_CYCLE_FENCE_PASS` only if all of the following are true:

- exact frozen artifact identity verified;
- C1 completes and establishes terminal fence C1;
- no same/older cycle naturally resurrects the route after C1 terminal state;
- C2 > C1 prepares successfully in the same shell lifetime;
- C2 completion advances the terminal fence to C2;
- at least five additional same-lifetime cycles do not regress the terminal fence or block a legitimate newer cycle;
- any service restart is separated into a new lifetime and the fence is re-established afterward;
- no telemetry/visible-state contradiction remains unresolved.

Use `PHYSICAL_CYCLE_FENCE_FAIL` for any falsifying observation. Use `PHYSICAL_CYCLE_FENCE_INCOMPLETE` when required evidence was not captured. Do not downgrade a failure to incomplete merely because a rerun later passes.

## Failure codes

Use one or more exact codes:

- `S1T_FAIL_NEWER_CYCLE_BLOCKED`
- `S1T_FAIL_OLD_CYCLE_RESURRECTED`
- `S1T_FAIL_TERMINAL_ID_REGRESSED`
- `S1T_FAIL_UNEXPECTED_FENCE_RESET`
- `S1T_FAIL_RECOVERY_NOT_READY`
- `S1T_FAIL_RELEASE_STUCK`
- `S1T_FAIL_ROUTE_REMAP`
- `S1T_FAIL_PHYSICAL_VISUAL_CONTRADICTION`
- `S1T_INCOMPLETE_MISSING_RECEIPTS`
- `S1T_INCOMPLETE_DAEMON_LIFETIME_AMBIGUOUS`
- `STALE_COMMAND_NOT_PHYSICALLY_INJECTED`

Add a new code only when none of these accurately describes the retained observation.

## Required result record

A completed validation record must include:

- tester/date/time/timezone;
- exact device software build;
- exact APK SHA-256 and GitHub artifact identity;
- raw receipt/log artifact references;
- per-cycle table containing `shellSession`, close-cycle identity, starting/ending phase, terminal-cycle id, decision/error, and visual observation;
- explicit same-lifetime versus new-lifetime boundaries;
- every failure/anomaly, including recovered ones;
- final result: `PHYSICAL_CYCLE_FENCE_PASS`, `PHYSICAL_CYCLE_FENCE_FAIL`, or `PHYSICAL_CYCLE_FENCE_INCOMPLETE`;
- the next single engineering question justified by the evidence.

## Promotion boundary

Passing this protocol validates only S1T's cycle-aware terminal-fence behavior on the tested physical Fold7/software combination. It does not by itself authorize production release, prove every continuity/performance target, or authorize a new architecture stage. Any next implementation change must be based on the retained physical evidence and pass the normal software regression/materialization gates again.
