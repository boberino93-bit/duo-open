# Duo Open — Transition Lab Batch 4

Vsync + SurfaceControl transaction timing.

Apply by extracting this ZIP into the root of the `duo-open` repository and
allowing the contained files to replace their matching paths.

This batch measures:

- Choreographer FrameTimeline preferred vsync id;
- frame callback time;
- expected presentation time;
- frame deadline;
- app-side `applyTransactionOnDraw()` submission result;
- SurfaceControl transaction committed callback;
- SurfaceFlinger latch timestamp;
- present-fence signal timestamp when immediately available.

Important baseline safeguard:

- the nearest observed vsync id is recorded for correlation;
- `Transaction.setFrameTimeline()` is NOT called;
- therefore the lab does not intentionally change SurfaceFlinger scheduling.

Frame probing is bounded:

- debug/full builds use FULL_LAB;
- FrameTimeline callbacks are armed around real hinge movement, Fold7 state
  activity, and geometry transactions;
- the window expires after 1.5 seconds without renewed activity;
- repeated hinge samples do not enqueue repeated start requests;
- stop/restart is protected against duplicate queued VsyncCallback chains.

Production behavior intentionally remains unchanged:

- Fold7ContinuityController is untouched;
- Fold7ContinuityCoordinator is untouched;
- display power/routing is untouched;
- fold thresholds are untouched;
- mirror crop/geometry is untouched;
- TiltFollower / PanelEngine behavior is untouched.

Expected changed paths:

- app/src/full/java/com/duoopen/lab/TransitionLab.kt
- app/src/full/java/com/duoopen/lab/FrameTimelineProbe.kt
- app/src/full/java/com/duoopen/lab/SurfaceTransactionProbe.kt
- app/src/full/java/com/duoopen/overlay/DisplayMirrorHost.kt
