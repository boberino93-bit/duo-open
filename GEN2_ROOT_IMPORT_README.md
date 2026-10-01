# Duo Open 1.3.26 Gen-2 — Root-Ready Import

Baseline audited main SHA: `2f6b27acd31462af6e6f49773391d4770d4b65e3`
Target: Samsung Galaxy Z Fold7 / Android 16 One UI
Intended next version: `1.3.26`

This archive is intentionally rooted at repository-relative paths.
Extract/copy its CONTENTS at the root of the Duo Open fork (the directory that already contains `app/`, `.github/`, `gradlew`, etc.).

## Safe source/test overlay

The `app/` tree adds the tested Gen-2 pure components and their tests:

- `app/src/full/java/com/duoopen/overlay/Fold7EarlyWakeIngress.kt`
- `app/src/full/java/com/duoopen/shell/Fold7AnglePipelineGen2.kt`
- `app/src/test/java/com/duoopen/overlay/Fold7EarlyWakeIngressTest.kt`
- `app/src/test/java/com/duoopen/shell/Fold7AnglePipelineGen2Test.kt`

The underlying standalone/pure models passed 14/14 adversarial tests before packaging.

## Coordinated Android integration

`GEN2_IMPORT_SUPPORT/` contains the master-agent instructions and the WallpaperAngleFeed Gen-2 draft. The draft is NOT a blind replacement file: it depends on coordinated Binder/session/sequence/instrumentation wiring described in the instructions.

The receiving integration agent must compare current `main` to the baseline before applying Android integration. If `main` has moved, rebase/reconcile rather than overwriting newer work.

Do not claim 1.3.26 complete until the coordinated Android changes are integrated and `testFullDebugUnitTest` + `assembleFullDebug` pass from current main-derived source.
