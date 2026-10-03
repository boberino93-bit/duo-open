# SP4.2 Test-Alignment Hotfix

GitHub Actions run `37083408602` proved the SP4.1 scope fix worked: Kotlin compilation and `assembleFullDebug` completed. CI then failed with exactly one unit test:

`Fold7ContinuityControllerTest > deliberateClosePrewarmsEarlyButStaysHiddenUntil135`

Cause: the test encoded the old `COVER_PREWARM_DEG = 174f` behavior. Beta2 intentionally changes the runtime threshold to `175f` to satisfy the cover-panel presentation contract. On the deliberate-close sequence `177.8 -> 176.3 -> 174.8`, the third sample both proves closing intent and is already below the 175° threshold. The controller's pre-existing fast-close path therefore correctly transitions directly to `COVER_PREWARMING` and returns `BeginPrewarm` on that same sample.

SP4.2:

- adds the exact baseline blob guard for `Fold7ContinuityControllerTest.kt`;
- transforms that test to assert the new 175° behavior;
- adds generated-source postconditions and a patcher self-test for the test alignment;
- keeps the 135° visual-show threshold unchanged;
- adds failure-diagnostic artifact upload to the Beta2 workflow so any later CI failure includes test reports and the applied source diff.

No runtime production logic is relaxed by this hotfix.
