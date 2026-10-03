# Duo Open Gen7 SP4.2 — Runtime Regression Beta2 Test-Alignment Hotfix

Target production app-source baseline: `41c6f20c817226b233eb4cbfb402e879c5e3e3ea`

Target test build:

- versionCode `43`
- versionName `5.1.0-beta2-zfold7`

## SP4.2 CI hotfix

SP4.1 fixed the missing `CoroutineScope` wiring and Beta2 now compiles and assembles successfully. GitHub Actions run `37083408602` then reached the full unit-test suite and exposed one stale test expectation:

`Fold7ContinuityControllerTest.deliberateClosePrewarmsEarlyButStaysHiddenUntil135`

The test still expected the legacy `174°` prewarm policy. Beta2 intentionally moves cover prewarm/power-on to `175°`, so the third deliberate-close sample at `174.8°` now correctly takes the controller's existing fast-close path directly into `COVER_PREWARMING` and emits `BeginPrewarm` on that same sample.

SP4.2 updates that regression test to the new 175° contract rather than weakening the runtime behavior. The pack also adds a patcher self-test/postcondition for this exact alignment and makes the workflow upload diagnostic test reports/source diffs whenever CI fails.

## Deployment

This archive is root-safe. Extract/copy its contents directly into the root of
`boberino93-bit/duo-open`, allowing it to overwrite the existing SP4/SP4.1 files,
and commit the changed files to `main`.

The workflow `.github/workflows/build-gen7-runtime-regression-beta2.yml` watches
the updated patcher/workflow paths and will run automatically. It:

1. verifies the production source baseline;
2. reapplies the validated Shizuku/onboarding predecessor;
3. validates and applies Beta2 in the CI workspace;
4. runs `testFullDebugUnitTest`;
5. runs `assembleFullDebug`;
6. uploads a tested APK plus SHA-256/build/source-diff evidence on success;
7. uploads failure diagnostics automatically if any later compile/test gate fails.

The workflow does **not** commit transformed Android sources back to production
`main`; the APK remains an isolated service-pack test build until Fold7 field
validation is accepted.

## Runtime corrections covered by Beta2

1. Recover a real DeviceState opening edge even when semantic continuity is
   still stuck in a closing/prewarm/cover-visual state, constrained to confirmed
   closed-endpoint evidence.
2. Retry inner wake and verify physical plus matching logical 1968×2184 route
   activation rather than treating physical power success as useful-pixels proof.
3. Remove blind first-opening geometry; hold until measured hinge data arrives.
4. Restore live Shizuku recapture during Fold7 animation.
5. Continuously recompose the live physical right pane during closing while
   excluding Duo Open's own overlay from recursive capture.
6. Render through rotation-aware physical coordinates for 0/90/180/270°.
7. Isolate portrait/landscape snapshot caches and avoid stretched stale frames.
8. Cover presentation policy: off at open endpoint; closing power-on/prewarm at
   175° at minimum brightness; eased ramp to inner-reference brightness by 90°;
   opening power-off at 177° for hysteresis.

## Validation status before deployment

- SP4.1 scope-wiring compiler regression: resolved; Beta2 Kotlin compilation and
  `assembleFullDebug` completed in run `37083408602`.
- Remaining run failure: one outdated unit-test expectation, corrected by SP4.2.
- SP4.2 Python patcher self-test: PASS.
- Workflow YAML parse: PASS.
- Physical Galaxy Z Fold7 validation: NOT_RUN until a fully passing CI APK is installed.
