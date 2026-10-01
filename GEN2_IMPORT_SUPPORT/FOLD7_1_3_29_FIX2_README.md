# Fold7 1.3.29 Fix 2 — deterministic continuity + early inner wake

Use this package instead of the earlier 1.3.29 / Fix 1 packages.

The first 1.3.29 attempt froze only PanelEngine's live re-capture loop.
`DisplayMirrorHost` still contained a live SurfaceControl mirror, so live source
pixels could continue changing underneath a stationary hinge.

Fix 2 addresses both live-pixel paths.

## Rendering

- Fold7 live blur is disabled.
- Fold7 Shizuku live re-capture is suppressed after the snapshot is established.
- `DisplayMirrorHost` prefers a recent inner-panel snapshot already captured by
  `PanelEngine`.
- That bitmap is drawn with the exact existing canonical left-pane crop into the
  1080x2520 cover.
- The old live SurfaceControl mirror remains only as a compatibility fallback
  when no recent valid snapshot exists.

## Opening wake

The 1.3.28 bug log showed the precise Samsung angle did not return until about
81 degrees during reopen.

Fix 2 observes Android DeviceState semantics without Samsung state IDs:

- `PROPERTY_FOLDABLE_HARDWARE_CONFIGURATION_FOLD_IN_CLOSED`
- `PROPERTY_FOLDABLE_HARDWARE_CONFIGURATION_FOLD_IN_HALF_OPEN`
- `PROPERTY_FOLDABLE_HARDWARE_CONFIGURATION_FOLD_IN_OPEN`

A physical CLOSED -> HALF_OPEN/OPEN edge can therefore wake the stable inner
physical panel before the wallpaper angle returns.

DeviceState never supplies animation geometry. Samsung's precise angle remains
authoritative.

Version:
- versionCode 34
- versionName `1.3.29-zfold7-deterministic-early-wake`
