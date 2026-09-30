# Duo Open — Samsung Galaxy Z Fold7 Generated Baseline

## Trusted source

Baseline commit:

`1a8787c5727be47f40d77ca9258e1cadb56fa1a4`

Version:

`1.3.16-zfold7-motion-power`

Version code:

`20`

## Target hardware

Samsung Galaxy Z Fold7.

Physically verified panel geometry:

- Inner: `1968 x 2184`
- Cover: `1080 x 2520`

Logical Android display IDs are not treated as permanent physical
panel identities. Samsung may remap the physical panels between
logical routes during topology transitions.

## Preserved continuity architecture

The 1.3.16 baseline uses:

- live SurfaceControl display mirroring
- explicit source/destination geometry
- the left pane of the inner display as continuity content
- Shizuku-assisted privileged operations
- the existing glass/frost rendering system
- motion-gated cover activation
- cover power hold during the transition
- Samsung native display handoff

The Android application/task remains the actual source of truth.

The continuity implementation does not move the application task to
a secondary display.

## Purpose of this branch

Historical Duo Open Fold7 builds reconstructed large portions of the
final source inside GitHub Actions.

This branch materializes the effective 1.3.16 source into ordinary
repository files so future engineering can work from a stable source
tree instead of repeatedly replaying multiple generations of workflow
transformations.

## Validation status

Creation of this branch means the source reconstruction compiled and
passed the existing Full debug unit tests.

It does not establish new physical Fold7 behavior.

Any future behavioral or performance change must still be physically
tested on the target Galaxy Z Fold7.
