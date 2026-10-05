# Fold7 Runtime Source of Truth

Status: `ACTIVE`
Date: 2026-10-05
Target: Samsung Galaxy Z Fold7

## Why this file exists

Duo Open currently uses a **baseline-plus-transforms** build model for the advanced Fold7 continuity stack. The checked-in `app/**` tree on `main` is an input baseline and does not, by itself, represent the newest validated materialized runtime.

This distinction matters because reading `app/build.gradle.kts` directly currently shows `versionCode = 42` and `versionName = "5.0.0-beta1-zfold7"`, while the latest validated S1T build reconstructs the full Beta2/S1 stack and produces `versionCode = 54`, `versionName = "5.1.0-beta2-zfold7-s1t"`.

Do not treat that difference as evidence that S1T was reverted unless the materialization chain itself has changed or failed.

## Current latest validated materialization

Latest validated stage: `S1T_CYCLE_AWARE_NATIVE_COVER_V1`

Validation workflow:

- `.github/workflows/s1t-cycle-aware-terminal-fence-v1.yml`

Materialization transform:

- `tools/apply_s1t_cycle_aware_terminal_fence_v1.py`

Known successful GitHub Actions run:

- run id: `37194318911`
- result: `success`
- validated head: `8babfad6b4abf46d4dc4107a64126ce710113168`
- artifact: `DuoOpen-S1T-Cycle-Aware-Terminal-Fence-V1`
- artifact id: `11299804391`
- artifact digest: `sha256:1b85c8b5f225dedf8de0227d3217ee18657e23c77cab9569fa45fc762e233b69`
- artifact expiry recorded by GitHub: 2026-11-03

The S1T run reconstructs the validated Beta2 wake stack, reapplies S1 through S1S, applies S1T, executes the full unit-test/build gate, and packages the physical-validation APK.

## What S1T changes

S1T preserves the stale-cycle safety behavior while making the terminal native-cover fence close-cycle aware:

- a delayed prepare from a completed or older close cycle remains rejected;
- a strictly newer legitimate close cycle may prepare again after `NATIVE_COVER`;
- the terminal native-cover close-cycle identity is retained for the current service lifetime;
- regression coverage includes both stale-cycle rejection and repeat-close acceptance.

This addresses the failure mode where a phase-only terminal fence could prevent all later legitimate close cycles after the first completed native-cover transition.

## Canonical interpretation rules

When determining the current Fold7 runtime state:

1. Treat `main` as the canonical repository for source inputs, transform implementations, workflow definitions, governance, tests, and project history.
2. Treat the latest **successful, exact-revision materialization workflow** as the authoritative statement of what advanced runtime source and APK were actually reconstructed and tested.
3. Do not infer the materialized version from baseline `app/build.gradle.kts` alone.
4. Do not infer physical device correctness from CI success alone.
5. Preserve exact workflow run, head SHA, transform chain, artifact digest, and physical-test status in every release/handoff claim.
6. If the transform chain changes, invalidate older materialized-runtime claims until the new exact chain passes build/tests.
7. If a materialized runtime source snapshot is packaged, treat it as derived evidence tied to its workflow run, not as an independent competing source tree.

## Current validation boundary

`S1T_CYCLE_AWARE_NATIVE_COVER_V1` is software-regression/build validated but **physical Galaxy Z Fold7 validation remains required**.

Do not claim that repeat close/open continuity, presentation timing, cover readiness, wake behavior, or Samsung/native-cover landing is physically proven until device evidence is captured against the exact S1T artifact.

## Next bounded engineering frontier

The next safe work should improve evidence and close the physical-validation gap rather than inventing a new architectural generation prematurely:

- make the latest materialized build artifact self-describing and include hashes/source snapshots for the runtime-critical reconstructed files;
- capture exact-current presentation/readiness and close-cycle telemetry on the Fold7;
- verify repeated close/open cycles, stale-work rejection, native-cover landing, and recovery after service/process restart;
- only after those observations are reconciled should a new implementation stage be proposed.
