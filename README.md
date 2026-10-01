# Duo Open Gen2 production workflow V5

V4 proved the Gen2 runtime is buildable:

- structural verification passed;
- `testFullDebugUnitTest` passed;
- `assembleFullDebug` passed;
- Gradle reported `BUILD SUCCESSFUL`.

The only V4 failure happened after the successful build. GitHub rejected the
push because the installer had modified `.github/workflows/build-direct-fold7.yml`
and the GitHub Actions token does not have the separate `workflows` permission.

V5 keeps the exact runtime code and build gates that already passed, but stages
and commits **only `app/**`**. The refreshed direct-build workflow remains
runner-local and is not included in the pushed commit.

This preserves the validated Gen2 app runtime while avoiding an unrelated
GitHub workflow-permission restriction.
