# Gen12.3 — Fold7 Precise-Angle Poll Preemption / Reacquisition Instrumentation

## Scope

Gen12.3 is a bounded hardening layer on top of the Gen12.2 route-retention candidate. It addresses a separate latency component in Samsung FoldInteractive precise-angle reacquisition and does **not** replace the Gen12.2 cover-route fence.

Field source: `duoopen-debug-1791438725678.zip`  
Field build: `5.6.1-gen12-1-wallpaper-lifecycle-zfold7` / versionCode 57  
Target: Samsung Galaxy Z Fold7 (`SM-F966W`, q7q), API 37.

## Corrected transport interpretation

The earlier Gen12.2 route-retention note described the authoritative source as approximately 25 Hz. The deeper sequence-correlated transport audit supersedes that interpretation as a general transport ceiling.

Measured from the physical trace:

- poll due: 9,127;
- successful poll completions: 8,556;
- poll timeouts: 560;
- healthy successful RTT: p50 2 ms, p95 16 ms, p99 approximately 33 ms;
- while Samsung `FoldInteractive` was active: 8,231 successes / 8,241 polls and only 7 timeouts (~0.085%);
- while `DuoWallpaperService` was the observed wallpaper owner: 543 timeouts / 875 polls (~62.06%);
- 543 of 560 total timeouts (96.96%) occurred during Duo wallpaper ownership;
- FoldInteractive-active accepted throughput was about 95.6 samples/s, with stable short windows around 110–120/s;
- seven closed-to-open cycles reached first accepted Samsung precise angle at median 416.8 ms, p95 1110.6 ms, max 1357.7 ms.

Therefore the healthy transport is already capable of near-100 Hz delivery. The dominant defect is target availability / reacquisition when Duo wallpaper ownership displaces the Samsung FoldInteractive command path. A stale UI `25 Hz` value must not be treated as the hardware or transport ceiling.

## Why preemption still matters

`Fold7AnglePipelineGen2` correctly enforces one poll in flight, but `WallpaperAngleFeed.kickBurst()` previously did nothing when a poll was already outstanding. A strong device-state opening edge could therefore remain head-of-line blocked until the nominal 96 ms timeout even after the topology had become capable of answering a new probe.

The existing reader-session + poll-sequence identity already supplies the safety fence needed for same-session retirement:

1. retire only the current poll token;
2. preserve the reader session;
3. start a replacement with a strictly larger poll sequence;
4. reject late old-sequence samples;
5. reject late old-sequence completion/timeouts;
6. preserve the one-current-poll invariant.

Preemption can remove only the residual blocked-poll component. It cannot make FoldInteractive available before Samsung/topology exposes the correct wallpaper target.

## Additional command-dispatch fence

A poll can be retired after its control-thread token was created but before its main-thread `sendWallpaperCommand()` runnable begins. Gen12.3 therefore keeps a volatile same-session retirement watermark. If cancellation wins before command dispatch, the old command is skipped and logged as `poll-command-skip-preempted`.

If `sendWallpaperCommand()` has already begun, it is not synchronously cancelled. Its eventual callback remains harmless because the replacement poll owns a higher sequence and the existing callback fence rejects the retired sequence.

## Trigger scope

The runtime lineage has one `kickBurst()` caller: the independent Fold7 device-state opening-edge callback. Gen12.3 does not preempt on ordinary hinge samples or steady-state display callbacks.

## Added observability

Gen12.3 records:

- `poll-kick` — strong reacquisition request;
- `poll-preempt` — exact retired poll sequence;
- `poll-command-skip-preempted` — retired sequence suppressed before main-thread dispatch;
- `poll-reacquire-target` — one wallpaper identity observation per strong reacquisition edge.

Existing sequence-correlated `poll-due`, `poll-command-start`, `poll-command-return`, Samsung callback, and `control-accept` stages remain unchanged.

## Explicit non-goals

Gen12.3 does **not**:

- globally reduce `POLL_TIMEOUT_MS = 96`;
- increase polling to 4 ms;
- restore dynamic persistent anchors on every display;
- invent/interpolate visual hinge geometry;
- weaken one-poll ownership;
- change hinge thresholds or rendering geometry;
- assume Shizuku shell UID can access Samsung private hinge sensors;
- claim to solve the P0 wallpaper-target availability conflict.

## Deterministic contract

Unit validation must prove:

1. poll A starts;
2. A is preempted without session invalidation;
3. poll B starts in the same session with `B.sequence > A.sequence`;
4. A sample is rejected;
5. A completion is rejected;
6. A timeout is rejected;
7. B sample is accepted;
8. a third simultaneous poll cannot start while B is current.

## Physical Fold7 acceptance gate

Run at least 10 closed-to-open cycles with Duo wallpaper active and compare against the Gen12.1 baseline:

- opening edge -> first precise: median 416.8 ms / p95 1110.6 ms;
- FoldInteractive-active timeout rate: ~0.085%;
- Duo-wallpaper-active timeout rate: ~62.06%;
- healthy successful RTT: p50 2 ms / p95 16 ms / p99 ~33 ms.

A preemption pass is successful only if it reduces the blocked-poll component without introducing wrong-sequence acceptance, multiple in-flight ownership, extra false timeouts, or wallpaper visual regression.

The next architectural layer remains topology-fenced target activation / bounded candidate-token handoff if first-precise reacquisition is still dominated by hundreds of milliseconds of Duo wallpaper ownership.
