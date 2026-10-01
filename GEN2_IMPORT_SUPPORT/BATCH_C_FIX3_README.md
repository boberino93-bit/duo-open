# Duo Open Gen-2 Batch C Fix 3

Fix 2 reached compilation and exposed a second existing call style:

- `DuoWallpaperService`: `HingeAngleSource(context, ::onHingeAngle)`
- `DuoApp`: `HingeAngleSource(context.applicationContext) { ... }`

Fix 3 preserves both using constructor overloads. Existing callers are left
unchanged. Only `FoldOverlayService` uses the new control-thread constructor.

The workflow runs `testFullDebugUnitTest` and `assembleFullDebug` and commits
the two production files only if both pass.
