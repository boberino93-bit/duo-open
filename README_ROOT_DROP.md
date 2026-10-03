# Duo Open Gen7 SP4 — Runtime Regression Beta2

Target baseline: `main` app source from commit `41c6f20c817226b233eb4cbfb402e879c5e3e3ea`

Target test build:

- versionCode `43`
- versionName `5.1.0-beta2-zfold7`

## Deployment

This archive is root-safe. Extract/copy its contents directly into the root of
`boberino93-bit/duo-open` and commit them to `main`.

The new workflow `.github/workflows/build-gen7-runtime-regression-beta2.yml`
will trigger from that commit. It reapplies the already-validated
Shizuku/onboarding predecessor in the CI workspace, applies this Beta2 runtime
pack, runs `testFullDebugUnitTest`, builds `assembleFullDebug`, and uploads the
APK plus the exact applied source diff.

The workflow does **not** commit generated Android source changes back to main.
This keeps the next device test isolated. Once field behavior is accepted, the
same patch can be promoted into a production commit.

## Runtime corrections in this pass

1. Recover a real DeviceState opening edge even when the semantic controller is
   still stuck in a closing/prewarm/cover-visual state, but only with confirmed
   closed-endpoint topology/geometry.
2. Retry inner wake on a bounded cadence and, after physical power, attempt the
   matching 1968×2184 logical route enable + `STATE_ON` sequence. Physical
   `setDisplayPowerMode()` success alone is no longer treated as useful-pixels
   proof.
3. Stop Gen5 blind-bootstrap geometry. Opening visuals hold the closed seed
   until measured geometry arrives.
4. Restore live Shizuku recapture while Fold7 snapshot overlays are active.
5. During closing, continuously recapture the live inner display and compose
   its physical right pane onto the cover instead of holding one frozen frame.
   The inner Duo overlay layer is explicitly excluded from that cross-display
   capture so the fold effect is not recursively applied twice.
6. Add rotation-aware physical-coordinate transforms for 0/90/180/270 degrees,
   including right-pane crop, fold axis and cover hinge edge.
7. Cache portrait and landscape snapshots separately and center-crop stale
   bridges rather than non-uniformly stretching them after rotation.
8. Add serialized physical cover power/brightness presentation:
   - open endpoint: cover off;
   - closing at 175°: cover on at minimum usable brightness;
   - 175° -> 90°: eased brightness ramp toward the unfolded inner reference;
   - <=90°: cover matches the captured inner reference;
   - opening at 177°: cover off, providing endpoint hysteresis.

## Physical-device status

Android compile/unit/build validation is delegated to GitHub Actions after the
root drop is committed. Physical Galaxy Z Fold7 validation remains NOT_RUN
until the resulting APK is installed and exercised on device.
