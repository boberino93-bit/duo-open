# Duo Open Gen-2 Batch C Fix 1

The previous Batch C generated patch did not commit.

Its only compile failure was caused by changing `HingeAngleSource` constructor
ordering, which broke the existing positional call in `DuoWallpaperService`.

Fix 1 preserves the original positional contract:

`HingeAngleSource(context, onAngle, ...)`

and appends `sensorHandler` / `deliveryHandler` as optional parameters.

The workflow applies the corrected two-file production patch, validates the
existing wallpaper-service call remains source-compatible, runs
`testFullDebugUnitTest` and `assembleFullDebug`, and commits only if both pass.
