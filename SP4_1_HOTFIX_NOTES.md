# SP4.1 Scope Wiring Hotfix

Observed in GitHub Actions run `37082713549`:

`Fold7Gen3VisualCoordinator.kt:465:21 Unresolved reference 'scope'`

Correction:

- `Fold7Gen3VisualCoordinator` now explicitly owns the accessibility-service `CoroutineScope`.
- `FoldOverlayService` passes its existing lifecycle-bound `scope` into the coordinator.
- `Fold7CoverVisualHost` receives that same scope for live closing-content capture.
- The pack self-test and generated-source postconditions now assert this wiring so the same omission fails before Gradle.

Copy this archive into repository root and overwrite the existing SP4 files. The changed patcher path is already watched by `build-gen7-runtime-regression-beta2.yml`, so committing it to `main` retriggers CI.
