Duo Open Phase 0 - Batch 3
==============================

Purpose: complete the runtime wiring needed for a direct-source 1.3.23 build.

Apply after Batch 1 and Batch 2.

Replace exactly:
- app/build.gradle.kts
- app/src/full/AndroidManifest.xml
- app/src/main/java/com/duoopen/DuoApplication.kt

These reproduce the 1.3.23 build identity, JUnit dependency, persistent
foreground runtime registration, and process-exit diagnostics from the
materialized build pipeline.

Do not delete the materialized workflow yet.
