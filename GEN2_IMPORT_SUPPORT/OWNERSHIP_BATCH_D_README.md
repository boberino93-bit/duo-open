# Duo Open — Gen2 Ownership Batch D

This root-ready package adapts the uploaded Mirror Lease and Cover Panel Release Lease R&D into the next Fold7 build.

## Base
- Expected production base: Batch B angle sequence identity is present.
- Batch C control-thread work is intentionally NOT mixed into this build because its Fix 3 still failed compilation and the mirror R&D explicitly recommends separating that work.

## Active production changes
- Mirror V2: shell session, monotonic operation sequence, host lease id, lease-scoped STOP, lifecycle FORCE_STOP, serial shell mutation executor, candidate-first replacement.
- Cover panel V2: shell-owned prewarm/release lease, RELEASE_PENDING semantics, direct IDisplayManager route enumeration/reset when safely validated, subprocess route resolution retained only as fallback.
- Existing fold thresholds, geometry, task placement and no-raw-physical-OFF policy are unchanged.
- Release identity is bumped to versionCode 31 / 1.3.26-zfold7-gen2-ownership.

## Guardrail
The workflow applies the patch in CI, runs testFullDebugUnitTest + assembleFullDebug, commits only on success, and uploads the tested APK.

## Local preflight
The four new pure-Kotlin ownership/test sources compile outside Android, and the packaged ownership tests passed 12/12 in a local lightweight JUnit-compatible runner before export. GitHub CI remains authoritative for the integrated Android build.

## R&D provenance
- Authoritative mirror archive SHA-256: b0044e551896ffa975e9426b5df79ca2389040cc9a453b7d353de24a72902ba8
- Authoritative mirror handoff SHA-256: 5b38befaa9a95cd4cea957ad5ea2caedb04c5cf3e3a27a4ba113b95eecdf6c80
- Cover release archive SHA-256: 55f7088d26fce9c70b4434b224794bf8dac7fa4ef7af8471aeb8afb9fc2b43d5
- Cover release handoff SHA-256: e618d2cfdd773c57fcf992b26340f4b9f4e00271b144b27e0a5ccd9777fbc55a
