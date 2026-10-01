# Duo Open — Transition Lab Batch 3

Observation-only public hinge + Fold7 state timing.

Apply by extracting this ZIP into the root of the `duo-open` repository and
allowing the contained files to merge/replace their matching paths.

This batch:

- adds an independent read-only `PublicHingeProbe`;
- records `SensorEvent.timestamp` without changing production HingeAngleSource;
- converts the sensor timestamp from elapsedRealtimeNanos into the lab's
  monotonic comparison domain using an explicit sampled anchor;
- retains conversion uncertainty;
- observes all accepted public fold/hinge sensor candidates, including coarse
  0/90/180 callbacks;
- keeps fresh Samsung samples authoritative for controller-event correlation;
- adds a safe observation tap to existing DuoDiagnostics;
- mirrors existing `fold7-state` diagnostics into Transition Lab JSONL with a
  monotonic timestamp and the latest authoritative hinge sample sequence.

Production fold behavior remains unchanged:

- Fold7ContinuityController is untouched;
- Fold7ContinuityCoordinator is untouched;
- HingeAngleSource is untouched;
- thresholds are untouched;
- display power/routing is untouched;
- mirror lifecycle/geometry is untouched;
- renderer behavior is untouched.

Expected changed paths:

- app/src/main/java/com/duoopen/debug/DuoDiagnostics.kt
- app/src/full/java/com/duoopen/lab/TransitionLab.kt

Expected new path:

- app/src/full/java/com/duoopen/lab/PublicHingeProbe.kt
