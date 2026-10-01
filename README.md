# Duo Open Gen2 production workflow V4

V3 eliminated the previous visibility errors, but its constructor reorder caused
one remaining compatibility error in `DuoWallpaperService`:

`No value passed for parameter 'onAngle'`

V4 takes the safer approach:

- keep HingeAngleSource as `(context, onAngle, callbackHandler = null)`;
- keep existing positional callers such as DuoWallpaperService working;
- convert DuoApp's trailing-lambda construction to explicit named `onAngle`;
- retain the successful V3 visibility fixes;
- retain the installer shell-capture anchor fix.

The workflow remains fail-closed. It commits/pushes only after structural checks,
unit tests, and APK assembly all pass.
