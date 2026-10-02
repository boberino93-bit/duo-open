# START HERE — Duo Open Gen6 Alpha 1 V2

Import/extract this ZIP at the repository root.

Processing order:

1. Read `GEN6_ALPHA1_DEV_ROUND_V2/README_START_HERE.md`.
2. Run `python3 GEN6_ALPHA1_DEV_ROUND_V2/validate_package.py`.
3. Run `python3 GEN6_ALPHA1_DEV_ROUND_V2/tools/apply_gen6_alpha1.py`.
4. Inspect `git diff` and run `git diff --check`.
5. Run `./gradlew testFullDebugUnitTest assembleFullDebug --stacktrace`.
6. If green, preserve the workflow/build IDs and APK SHA-256.
7. Install that exact APK on the Galaxy Z Fold7 and run the physical acceptance round.

V2 supersedes the previously imported Alpha 1 V1 package for runtime application. The V1 folder can remain in repository history; do not apply both patchers.

The V2 patcher uses exact production-file Git blob gates and will stop instead of patching a drifted runtime.
