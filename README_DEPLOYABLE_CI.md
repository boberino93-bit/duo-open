# Deployable CI addition

This SP3 root-drop adds a dedicated GitHub Actions workflow:

`.github/workflows/build-gen7-service-pack.yml`

After these files are copied into the repository root and committed to `main`, the workflow is designed to start automatically because its own workflow path is included in the `push.paths` trigger.

The workflow:

1. checks that the fail-closed Shizuku/onboarding patch still matches the expected Android source;
2. applies the patch only inside the CI checkout;
3. runs `testFullDebugUnitTest` and `assembleFullDebug`;
4. uploads the resulting full debug APK plus its SHA-256, build metadata, and the exact Android-source diff applied in CI.

The artifact name is:

`DuoOpen-ZFold7-Gen7-ServicePack-Shizuku-Onboarding`

This does **not** claim a successful APK build until GitHub Actions actually completes successfully. It also does not claim physical Fold7 validation.
