# Duo Open R&D Handoff — Alpha3 Shizuku Capture Bitmap Lifetime

Agent: `rnd-5da10562da90496f`  
Repository: `boberino93-bit/duo-open`  
Evaluated HEAD: `98a7c1cde9fd36d47562b40fa25ed0b094038e70`  
Production GitHub writes: **NONE**

## Executive finding

Current Alpha3 has a narrow, source-confirmed bitmap lifetime asymmetry in `app/src/full/java/com/duoopen/overlay/PanelEngine.kt`.

The Shizuku general-capture coroutine can obtain a full-resolution bitmap and then discard it through **three** branches without eager `Bitmap.recycle()`:

1. generation/phase is already stale immediately after capture returns;
2. generation/phase becomes stale while the bitmap is being classified as mostly black;
3. the bitmap is black during a post-panel-swap attempt, so a retry is scheduled and the current bitmap is abandoned.

The equivalent accessibility screenshot discard branches explicitly recycle. The dedicated exact-cycle continuity-prime path also recycles a captured bitmap when authority is stale or publication is rejected. Therefore this is a local implementation gap, not evidence of an intentional global ownership policy.

## Evidence

### Current source

`PanelEngine.capture()` Shizuku path:

- `val bitmap = ... ShizukuBridge.capture(...)`
- `if (stale()) return@launch` — bitmap not recycled.
- after `isMostlyBlack(bitmap)`, `if (stale()) return@launch` — bitmap not recycled.
- black-retry branch schedules `capture(...attempt + 1...)` then `return@launch` — bitmap not recycled.

In the accessibility path in the same file:

- stale callback: `bitmap?.recycle()` before return.
- black retry: `bitmap.recycle()` before retry.

`DuoShellService.capture()` confirms that the shell-side hardware result is copied to `Bitmap.Config.ARGB_8888`; its temporary hardware bitmap is recycled and the HardwareBuffer is closed. `PanelEngine` requests `INITIAL_SHELL_SCALE = 1f` for the initial capture.

### Deterministic probes

`panelengine_bitmap_ownership_probe.py` checks the exact source excerpt and passes 5/5 assertions:

- first Shizuku stale return lacks recycle;
- post-black-check Shizuku stale return lacks recycle;
- Shizuku black retry lacks recycle;
- accessibility stale discard recycles;
- accessibility black retry recycles.

`OwnershipModel.kt` compiles and runs as a pure ownership model. It proves the proposed contract:

- stale-early, stale-after-black-check, and black-retry outcomes recycle and never hand off;
- accepted capture hands off and is not recycled;
- null fallback has no bitmap to recycle.

Result: `OWNERSHIP_MODEL=PASS`.

## Resource scale

ARGB_8888 raw pixel storage is 4 bytes/pixel.

- Inner 1968×2184: 17,192,448 bytes ≈ **16.40 MiB** per full-resolution bitmap.
- Cover 1080×2520: 10,886,400 bytes ≈ **10.38 MiB** per full-resolution bitmap.
- With `MAX_CAPTURE_ATTEMPTS = 3`, two black frames can be discarded before the final attempt: ≈ **32.79 MiB** inner or **20.76 MiB** cover of raw pixel backing that could be released immediately instead of awaiting later reclamation.

These numbers are raw pixel backing only. They are not a claim that the app permanently leaks that amount or that all backing remains resident for a specific duration. Device profiling is required to quantify actual peak native/shared memory pressure and frame-time impact.

## Platform evidence

Android's current `Bitmap.recycle()` API contract says it immediately releases pixel data for a bitmap that is certainly no longer needed, instead of waiting for a future garbage collection. Modern Android bitmap pixel data resides in native heap, and bitmap transfers through Binder may involve shared-memory backing.

Official references:

- https://developer.android.com/reference/android/graphics/Bitmap#recycle()
- https://developer.android.com/topic/performance/graphics/manage-memory
- https://developer.android.com/topic/performance/memory/guide/bitmaps

The proposed three recycle sites satisfy the safety precondition because each branch exits before the bitmap is cached, presented, published to the continuity frame store, or handed to a View.

## Minimal Gen2 recommendation

Apply only the three eager-release operations:

```kotlin
if (stale()) {
    bitmap?.recycle()
    return@launch
}
...
if (stale()) {
    bitmap.recycle()
    return@launch
}
if (black && !demoRunning) {
    bitmap.recycle()
    ...schedule retry...
    return@launch
}
```

Do **not** recycle accepted captures here; their ownership transfers to `onCaptured()` / cache / renderer. Do not combine this narrow correction with a SnapshotCache ownership rewrite until that broader lifecycle is separately modeled.

## Why the change is low-risk

- No state-machine behavior changes.
- No hinge/arbitration behavior changes.
- No timing/backoff changes.
- No capture API changes.
- No renderer changes.
- The branches already terminate immediately and have no downstream consumer for that bitmap.
- The patch mirrors existing behavior in the accessibility capture path.

## Recommended validation after production integration

1. Compile `testFullDebugUnitTest` and `assembleFullDebug`.
2. On Fold7, record baseline and patched `dumpsys meminfo` / Memory Profiler during repeated close/open sequences that trigger waking-panel black retries.
3. Confirm retry/capture behavior is unchanged and no `Canvas: trying to use a recycled bitmap` appears.
4. Exercise rapid reversals to hit stale-generation branches; verify no crash and unchanged continuity semantics.
5. Compare native/shared bitmap pressure and frame-time outliers; treat memory/jank improvement as device-measured only after this step.

## Confidence

- **High / source-confirmed:** three Shizuku discard branches lack eager recycle; equivalent accessibility discard branches recycle; shell capture creates full-scale ARGB_8888 bitmap.
- **High / deterministic model:** proposed discard-only recycling preserves the intended ownership partition.
- **Medium / platform-backed:** eager release should reduce transient bitmap backing lifetime.
- **Unmeasured:** magnitude of real Fold7 memory/jank improvement.

## Primary-agent action

Review `PROPOSED_RND_PATCH.diff` against current `main`. If accepted, the primary agent can integrate the three-line ownership correction and run normal build + physical Fold7 validation. This R&D session did not alter GitHub production files.
