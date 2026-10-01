# Fold7 Gen2 Ownership Batch D Fix 3

Fix 3 addresses both patcher defects exposed by Fixes 1 and 2.

- Fix 1 used a non-unique teardown boundary.
- Fix 2 left the old watchdog/safety-reset field block behind and also used
  removal helpers that duplicated several end anchors.

Fix 3 uses preserve-end removal semantics, explicitly removes the residual
watchdog/mirror/safety-reset fields, and asserts that the surviving boundaries
exist exactly once.

After transformation, FoldOverlayService is forbidden from directly
constructing DisplayMirrorHost, globally stopping the shell mirror, or owning
the retired secondary-display continuity state machine.

Fold7ContinuityCoordinator remains the single production owner of mirror and
cover-panel continuity.

The workflow then runs:
- testFullDebugUnitTest
- assembleFullDebug

It commits and exports the APK only if both succeed.
