# Duo Open — Transition Lab Batch 2

Observation-only Samsung angle-path instrumentation.

Apply by extracting this ZIP into the root of the `duo-open` repository and
allowing the contained files to merge/replace their matching paths.

This batch:

- adds `TransitionLab.kt`;
- starts BASIC lab recording automatically in debug full builds;
- records Samsung FoldInteractive source time separately from Binder arrival
  and main/consumer delivery;
- labels endpoint-bridge samples as synthetic;
- preserves signed clock residuals instead of clamping them to zero;
- adds pure JVM tests for the timing model.

Production fold behavior is intentionally unchanged:

- no physical controller thresholds are changed;
- no display power logic is changed;
- no mirror geometry is changed;
- no renderer tuning is changed;
- `hinge.feedExternal(...)` remains the production delivery path.

Expected changed paths:

- app/src/full/java/com/duoopen/lab/TransitionLab.kt
- app/src/full/java/com/duoopen/lab/TransitionModel.kt
- app/src/full/java/com/duoopen/overlay/OverlayFeature.kt
- app/src/full/java/com/duoopen/shell/ShizukuBridge.kt
- app/src/full/java/com/duoopen/shell/WallpaperAngleFeed.kt
- app/src/test/java/com/duoopen/lab/TransitionModelTest.kt
