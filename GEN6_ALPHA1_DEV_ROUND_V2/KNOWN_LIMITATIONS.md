# Gen6 Alpha 1 V2 — Known Limitations / Required Next Gate

## Passed before packaging

- current-main recheck
- exact runtime blob revalidation
- patcher Python syntax validation
- patcher transformation self-test
- static security/authority gate
- pure-Kotlin deterministic checks
- 100,000-cycle opening-attempt lifecycle fuzz
- 100,000-case privacy-invariant fuzz
- Gen4 raw-field WakeHint replay
- clean final-ZIP extraction/checksum/package revalidation (recorded in `TEST_STATUS_V2.md`)

## Not yet proven

### Android compile / CI
The complete Android repository and Gradle dependency graph are not available in this execution container, so V2 is **not** marked `CI_PASS` until the imported package is applied in the repo and this succeeds:

```bash
./gradlew testFullDebugUnitTest assembleFullDebug --stacktrace
```

### Physical Fold7 behavior
No V2 APK has run on the Galaxy Z Fold7 yet. `PHYSICAL_FOLD7_PASS` remains false.

### Managed/work-profile discovery
The current work-profile detector is best effort because Accessibility window-state events provide a package name but not a stable public per-event user/profile identity. Physical testing must verify the intended managed-profile apps on the target Fold7. The security fallback still treats secure-layer/capture-denied cases as private.

### Unknown secure apps before first secure signal
Explicit private apps (including Coast Capital) and detected work-profile apps are private before capture. An unknown app that is only discoverable as secure through platform capture metadata/error becomes private when that signal is received. Secure shell captures are rejected before Bitmap materialization.

## Physical focus after APK build

- ordinary app open: transparent `PUBLIC_GLASS` appears immediately on leave-closed WakeHint
- verify inner panel wakes from the early WakeHint rather than waiting for precise hinge
- Coast Capital: opaque `PRIVATE_FROST`, no visible stale frame during open/close/reversal
- work-profile app: same opaque behavior
- unknown `FLAG_SECURE`/secure-layer app: fail closed without protected Bitmap materialization
- public -> private -> public app switching while partially folded
- repeated 30–70° reversals
- at least 30 normal open/close cycles
- compare ordinary closing behavior against Gen5 Beta1 for regressions
