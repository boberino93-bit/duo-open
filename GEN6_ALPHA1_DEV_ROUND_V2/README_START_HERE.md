# Duo Open Gen6 Alpha 1 V2 — Full Development Round

Repository: `boberino93-bit/duo-open`

Current `main` observed during final validation:
`12c8f2530afb0523d8d2f83af3c62c1dca8c11b8`

That commit contains the imported V1 handoff package only. The production runtime files patched by V2 remain byte-for-byte equal to their exact gated baselines, so V2 gates the individual Git blob SHAs rather than trusting a repository commit label.

This package is intended to produce the first **Gen6 Alpha 1 APK candidate** after a real Android/Gradle build.

## What V2 fixes before APK compilation

The deeper pre-build test pass rejected V1 for two reasons and V2 fixes both:

1. **WakeHint was telemetry-only.** V2 uses the learned Samsung `0 -> 1` leave-closed WakeHint to start opening visual material immediately and queue the existing physical-inner wake command. It still does **not** make WakeHint semantic hinge geometry or continuity authority.
2. **A private transition could retain an already-presented public frame.** V2 revokes Gen3 pixel rendering in `PRIVATE_FROST`, clears reusable pixel leases, detaches stale pixel hosts, and replaces them with procedural opaque frost in the same control turn.

## Included runtime work

- Gen6 `0 -> 1` WakeHint attempt identity and typed telemetry.
- Early `ShizukuBridge.wakeInnerDisplay()` dispatch from WakeHint when privileged access is ready.
- Early opening material from WakeHint without waiting for a precise hinge sample.
- `PUBLIC_GLASS` for ordinary apps using a transparent procedural material over the live app; no cached previous-app frame is required for the opening bootstrap.
- `PRIVATE_FROST` for secure/work/private apps using a fully opaque procedural material.
- Coast Capital explicit private classification via label/package keyword.
- Best-effort managed/work-profile package classification.
- Accessibility secure-window failure -> fail-closed `PRIVATE_FROST`.
- Shell `containsSecureLayers` is checked **before** HardwareBuffer/Bitmap materialization.
- Secure-layer metadata is preserved through `ShizukuBridge.captureResult()`.
- Reusable snapshot and continuity leases are cleared when private mode becomes active.
- Existing Gen3 frozen-frame host is revoked when entering private mode.
- Repeated terminal black shell capture degrades to procedural frost for that transition.
- Version target: `6.0.0-alpha1-zfold7`, versionCode `43`.

## Preserved authority boundaries

- WakeHint can prepare infrastructure and visual material only.
- WakeHint never becomes measured hinge geometry.
- Existing semantic continuity state remains authoritative.
- Normal-app Gen4/Gen5 closing thresholds and geometry are not intentionally changed.
- `PRIVATE_FROST` must never capture/cache protected pixels merely to blur them.
- `MODEL_PASS`, Android `CI_PASS`, and `PHYSICAL_FOLD7_PASS` remain separate claims.

## Apply and build

From repository root:

```bash
python3 GEN6_ALPHA1_DEV_ROUND_V2/validate_package.py
python3 GEN6_ALPHA1_DEV_ROUND_V2/tools/apply_gen6_alpha1.py
git diff --check
./gradlew testFullDebugUnitTest assembleFullDebug --stacktrace
```

The patcher refuses to touch the runtime if any exact gated source blob has drifted.

## Pre-build evidence included

- Pure Kotlin harness: two independent 100,000-iteration fuzz lanes plus deterministic unit-style gates.
- Gen4 field replay: Samsung `0 -> 1` WakeHint to next authoritative hinge sample was 401–2484 ms across nine usable events, median 910 ms. V2 dispatches wake/material directly from the earlier WakeHint. This is **replay/model evidence**, not a physical Gen6 timing measurement.
- Package static/security gate verifies the no-protected-pixel and authority invariants.

## Required next gate

The first real Android result must come from:

```bash
./gradlew testFullDebugUnitTest assembleFullDebug --stacktrace
```

Only after that succeeds should the APK be installed on the Galaxy Z Fold7 for the physical acceptance round.
