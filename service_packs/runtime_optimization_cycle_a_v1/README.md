# Runtime Optimization Cycle A v1

Status: experimental non-production optimization overlay.

Base Android source lineage: `fc44280d5162c58aefbc2c210ea8496f9f2c3719` (Android runtime unchanged from the prior Beta2 build lineage).

## Behavioral freeze

This cycle MUST NOT change:

- hinge/angle authority semantics, source ranking, thresholds, geometry, or angle values;
- shader equations, fold transforms, tilt math, visual LUTs, animation phase semantics, or frame geometry;
- privacy/security render classification;
- display ownership, continuity states, generation semantics, wake policy, or opening/closing thresholds;
- screenshot selection/crop semantics;
- the known INNER wake/readiness investigation. That correctness lane resumes only after optimization deployment and field regression testing.

## Cycle A changes

`tools/apply_runtime_optimization_cycle_a.py` applies four mechanical reductions:

1. Remove the duplicate `PersistentRuntimeService.ensureRunning(this)` invocation during accessibility-service connection.
2. Iterate the existing `engines.values` view directly instead of allocating temporary `toList()` snapshots in main-thread hinge/render loops that do not mutate the map.
3. Replace `HingeAngleSource.choose()`'s per-sample `filter()` + comparator/min traversal with a single allocation-free loop preserving the exact ranking rule: lowest resolution first, standard hinge sensor wins an equal-resolution tie.
4. Preserve every `DuoDiagnostics` event while batching asynchronous file persistence into bounded groups of 64 lines. In-memory recording, observer callbacks, Logcat emission, ordering, and line payloads remain intact; this removes one executor task and one file append syscall per event during bursts.
5. Reuse the identical per-hinge-drain reason string rather than allocating it twice.

## Required validation

Cycle A is accepted only if all of the following pass after the existing Shizuku onboarding + Gen7 Runtime Regression Beta2 overlays are applied:

- optimization transformer self-test;
- source-shape guard/check;
- `git diff --check`;
- `testFullDebugUnitTest`;
- `assembleFullDebug`;
- artifact packaging with the applied Android-source diff and hashes.

Passing CI is not physical Fold7 validation. After Cycle B and final regression CI, the optimized APK still requires device regression testing before this work can be merged/deployed as accepted production behavior.
