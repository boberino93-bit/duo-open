# Duo Open Gen6 Alpha 1 — Full Development Round

Repository: `boberino93-bit/duo-open`

Verified runtime baseline before packaging:
`7dd6821cea09559e858cca61579da64a0f14ea71`

This package is intended to produce the first **Gen6 Alpha 1 APK candidate**.

## Included

- Gen6 `0->1` / leave-closed WakeHint attempt identity + telemetry.
- `PUBLIC_GLASS` for ordinary apps.
- `PRIVATE_FROST` for secure/work/private apps.
- Coast Capital explicit private classification via package/label keyword.
- Best-effort managed/work-profile package classification.
- Fail-closed private frost on screenshot rejection.
- Fail-closed private frost when repeated shell capture remains black.
- Procedural opaque frost that never needs protected pixels underneath it.
- Cache / continuity-frame invalidation when privacy becomes private.
- Clearer public-glass tuning on the **opening path only**.
- Version bump: `6.0.0-alpha1-zfold7`, versionCode `43`.

## Preserved

- WakeHint is not hinge geometry.
- Existing semantic opening authority remains separate.
- Ordinary-app close thresholds, geometry, and timing remain unchanged.
- No physical-performance claim is made by this package.

## Apply and build

From repo root:

```bash
python3 GEN6_ALPHA1_DEV_ROUND/validate_package.py
python3 GEN6_ALPHA1_DEV_ROUND/tools/apply_gen6_alpha1.py
git diff --check
./gradlew testFullDebugUnitTest assembleFullDebug --stacktrace
```

The resulting APK is a **candidate** until tested on the Galaxy Z Fold7.
