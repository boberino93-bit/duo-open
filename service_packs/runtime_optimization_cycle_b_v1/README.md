# Runtime Optimization Cycle B v1

Status: experimental non-production optimization overlay, applied only after validated Cycle A.

## Behavioral freeze

Cycle B inherits Cycle A's hard freeze. It changes no hinge values, authority thresholds, sensor sampling period, shader/render math, visual LUT, continuity state, display ownership, wake behavior, screenshot behavior, or opening/closing threshold.

## Cycle B changes

`tools/apply_runtime_optimization_cycle_b.py` removes two remaining per-hardware-sample costs in `HingeAngleSource`:

1. Build a sensor-to-Stats index once at source construction instead of `firstOrNull` scanning the candidate list for every sensor callback.
2. Replace the remaining all-candidate selector scan with the exact incremental ownership rule already implied by the old implementation: the first reporting source owns; a later source displaces it only when that source has strictly finer resolution. Equal-resolution sources do not displace the current owner.

The transform includes a deterministic model self-test for that promotion rule.

## Acceptance gate

Cycle B is accepted only after reconstructing Beta2, applying validated Cycle A, applying Cycle B, and passing:

- Cycle A self-test + source-shape guard;
- Cycle B selector-model self-test + source-shape guard;
- `git diff --check`;
- `testFullDebugUnitTest`;
- `assembleFullDebug`;
- APK + exact applied Android diff artifact generation.

Physical Fold7 validation remains separate and required before production acceptance. The INNER wake/readiness correctness lane remains intentionally unchanged during both optimization cycles.
