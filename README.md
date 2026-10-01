# Duo Open Gen2 production workflow V2

The first real CI execution reached the installer and failed safely at:

`PanelEngine.kt:shell publish: expected anchor exactly once, found 3`

Cause: the installer used a generic `onCaptured(...)` text anchor before
distinguishing the shell path from two accessibility paths.

This workflow fixes only that installer anchor in the ephemeral GitHub Actions
runner. It does not commit the installer modification.

Execution order:

1. verify all audited production blobs with the original installer;
2. patch the ambiguous installer anchor in the runner;
3. run the installer against the still-audited production source;
4. run `verify_gen2_postapply.py`;
5. run `git diff --check`;
6. run `testFullDebugUnitTest assembleFullDebug --stacktrace`;
7. commit only `app/**` and the existing direct-build workflow;
8. push the Gen2 production commit only when every prior gate succeeds.

If a later source/compiler issue appears, the workflow stops before commit and
the job log becomes the authoritative next diagnostic.
