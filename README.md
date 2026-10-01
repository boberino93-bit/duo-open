# Duo Open Gen2 production workflow V3

V2 successfully applied and structurally verified the Gen2 runtime, then Gradle
found four compile-surface issues:

- DisplayMirrorHost public constructor exposed internal Gen2 types.
- PanelEngine public constructor exposed internal Gen2 types.
- Two ShizukuBridge V3 token methods exposed an internal lease-token type.
- HingeAngleSource placed `callbackHandler` after the lambda parameter, breaking
  existing trailing-lambda call sites such as DuoApp.

V3 fixes those exact integration issues in the ephemeral runner after applying
Gen2, then repeats structural verification and the complete Gradle gates.

No runtime commit is pushed unless:
- audited production blob verification passes;
- Gen2 applies;
- structural verification passes;
- `git diff --check` passes;
- `testFullDebugUnitTest` passes;
- `assembleFullDebug` passes.

If Gradle exposes another issue, the workflow stops before commit and the job
log becomes the next diagnostic input.
