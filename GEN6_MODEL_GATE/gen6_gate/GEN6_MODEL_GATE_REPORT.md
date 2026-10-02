# Duo Open Gen6 Canonical Canvas — Two-Pass Model Gate Report

## Entry baseline

- Repo: `boberino93-bit/duo-open`
- Verified `main`: `de9eb45086f6eee00dd4e1e01d5e9782e39773d5`
- Runtime: `5.0.0-beta1-zfold7` / versionCode 42
- Successful Gen5 Beta1 workflow: `36982521348`
- Artifact: `DuoOpen-ZFold7-5.0.0-beta1`, id `11216201698`
- Downloaded artifact ZIP SHA-256: `5138cea159918cca48457eabbff35ac9183e0262701b386fe1d4f8059a7afcc7`
- Inner APK SHA-256: `bb0747e68c27886e26d47eb56de0fcf86d20e0328797eced711af923a226bc53`
- Artifact BUILD-INFO confirms `diagnosticUploadConfigured=false`.

## Package integrity / old process gates

The supplied Gen6 Primary handoff checksum validation and all bundled process/recursion/manager validators passed. The script-style regression suite passed when executed directly. The current Gen5 Beta1 GitHub build is also a successful CI artifact. These facts establish a clean entry point; they do not prove Gen6 Android integration.

## Pass 1 — PRINCIPAL DESIGN: MODEL_PASS

Result: **PASS**.

- 15/15 tests pass.
- 100,000 randomized lifecycle events with invariant checking after every event.
- 1,000 repeated 30–70° oscillation loops bounded and terminal-clean.
- HOME canonical right-pane geometry: exact `Rect(984,0,1920,2184)` to `1080x2520`, uniform 15/13 scale, excluded 1920..1968 strip not stretched.
- 0→1 / 0→2 wake hints can begin an attempt without fabricating semantic hinge angle.
- Virtual hinge remains visual-only.
- Host migration is generation-fenced; stale callbacks cannot clear current ownership.
- Secure/capture-denied mode owns no protected pixel lease.
- Wallpaper-only never satisfies HOME native freshness.
- Gen4 terminal close reassert fence is explicit.
- Raw Gen4 replay: 10 leave-closed events, 9 `0→1`; first nonzero angle median 810 ms, P95 1761 ms, worst 2484 ms after hint.

## Pass 2 — EXPANSION: MODEL_PASS

Result: **PASS**.

- 23/23 tests pass.
- Three additional 100,000-operation randomized lanes: refresh ownership, host migration and content provenance.
- Real FrameTimeline timing is primary; display-mode Hz is telemetry only.
- Refresh vote ownership includes child View + SurfaceControl with exact attempt/host/generation replacement fencing.
- Same-surface new-generation stale clears are rejected.
- Make-before-break host migration retains old presented host until replacement first-present; early old-host loss degrades to native rather than intentionally blanking.
- Pixel provenance includes attempt/service/generation/user/package/window/task/capture generation.
- Secure transition immediately destroys pixel state.
- NativeFreshOracle is route-generation/presentation fenced; general apps additionally require current layout generation.
- Recovery differentiates wallpaper source loss (non-terminal) from app/accessibility/Shizuku/service/host faults (terminal cleanup + new epoch).
- Typed diagnostics are metadata-only in the model.
- Diagnostic transport model requires HTTPS + key + checksum-matched receipt.
- Raw Transition Lab replay: 6,838 unique FrameTimeline samples, observed 60.32 Hz, expected-presentation lead median 16.667 ms.
- Wake-hint replay: 9/10 recorded hints had an immediate usable frame; median first callback 10.10 ms and median expected-present opportunity 26.35 ms. One event was excluded for an explicit 2.52 s trace-recording gap.

## Gate classification

- `MODEL_PASS`: **YES** — Pass 1 + Pass 2 green.
- `CI_PASS` for **Gen6 production code**: **NO / NOT YET RUN** — no Gen6 Android production source has been integrated in this gate.
- `PHYSICAL_FOLD7_PASS` for Gen6: **NO / NOT YET RUN**.

The correct next step is therefore to define and gate a narrow exact-baseline production slice, starting with Slice A (wake-hint + opening attempt identity + typed telemetry) while keeping existing closing thresholds/visuals and Gen4 panel authority untouched.

## Non-negotiable blockers carried into production integration

1. Do not derive presentation time from `Display.mode`; use FrameTimeline where available.
2. Do not call a root refresh request proof of effective 120 Hz; verify actual child/presentation cadence.
3. Refresh ownership must be fenced by attempt/host/generation and same-surface reuse.
4. Glass optics and geometry must remain independently controlled.
5. No provenance-free stale snapshot cache.
6. No secure/capture-blocked pixel capture/cache/replay.
7. No wallpaper-only native-fresh release.
8. No post-NATIVE_COVER retired close authority re-entry.
9. No physical performance claim until a Fold7 candidate runs the required 30 normal + 20 reversal/endurance gates and same-script Gen5 comparison.
