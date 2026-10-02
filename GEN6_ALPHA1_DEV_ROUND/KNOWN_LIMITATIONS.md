# Known Limitations / Required Next Gate

This package has passed:

- exact-current-main blob revalidation
- patcher syntax validation
- patcher marker self-test
- package static security/authority checks
- pure-Kotlin WakeHint/privacy/runtime harness

It has **not** been Android-compiled in this sandbox because the full repository/Gradle dependency graph is not locally available here.

After import, the build agent must run:

```bash
git diff --check
./gradlew testFullDebugUnitTest assembleFullDebug --stacktrace
```

The APK remains a candidate until physical Galaxy Z Fold7 testing.

## Physical focus for Alpha 1

- normal app opening: verify clear PUBLIC_GLASS look
- Coast Capital: verify opaque PRIVATE_FROST before any protected capture/cache
- work-profile app: verify PRIVATE_FROST classification when managed-profile discovery is available
- unknown FLAG_SECURE app: verify Accessibility secure-window error resolves to PRIVATE_FROST
- repeated black shell capture: verify one-animation private fallback without permanently misclassifying the app
- reopen/close/reversal: verify ordinary-app close behavior has no regression
