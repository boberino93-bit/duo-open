# Fold7 Gen2 Batch C — control-thread confinement

Base requirement: tested Batch B must already be on `main` (`startAnglesSequenced` + shell poll sequence callback present).

This batch intentionally changes only:
- `HingeAngleSource.kt`
- `FoldOverlayService.kt`

It creates exactly one `HandlerThread("duo-fold7-angle-control")` per accessibility-service lifetime and registers production public hinge sensors on that looper using the explicit `SensorManager.registerListener(..., Handler)` overload.

For this migration increment, accepted public sensor values are copied off the SensorEvent and posted back to the existing main handler before they touch source arbitration, `Fold7ContinuityCoordinator`, or `PanelEngine`. This keeps the established controller/render threading contract intact while removing the implicit SensorManager-main-looper dependency.

It does **not** change Samsung polling cadence, Fold7 thresholds, mirror visibility, panel power, logical/physical identity, or early-edge behavior.

The workflow runs `testFullDebugUnitTest` and `assembleFullDebug`; the generated production changes are committed only if both succeed.
