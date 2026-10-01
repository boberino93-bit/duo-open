# Fold7 1.3.29 — deterministic transition frames + early inner wake

Evidence from the 1.3.28 device bundle:

- Cover prewarm and lease reassert now work.
- The first close can look very good.
- After a full close, the Samsung precise wallpaper feed disappears.
- On reopen, the first precise sample in the captured session does not arrive
  until roughly 81°, so the existing 3° wake rule cannot physically wake the
  inner display at 3°.
- The current Fold7 snapshot renderer also starts a Shizuku live re-capture
  loop after presenting a screenshot. That means the hinge can be stationary
  while the pixels under the fold continue changing.

This batch makes two architectural corrections.

## 1. Deterministic frozen frames

For Fold7 geometries only:

- 1968x2184 inner
- 1080x2520 cover

`PanelEngine` always uses captured snapshot rendering.
Cross-window live blur is disabled for Fold7, and the Shizuku live re-capture
loop is suppressed after the initial frame is captured.

A fresh bridge capture may still replace an old cached bridge once, but after
the transition frame is established it no longer changes underneath a
stationary hinge.

Other device geometries retain the existing behavior.

## 2. Device-state early wake

A new reflection-based `Fold7DeviceStateObserver` listens to Android's
DeviceStateManager callback without hardcoding Samsung state identifiers.

On modern Android it uses the semantic
`PROPERTY_FOLDABLE_DISPLAY_CONFIGURATION_OUTER_PRIMARY` property. If that
property cannot be reflected, an opaque state id is learned as "folded" only
when corroborated by both:

- native cover topology; and
- precise hinge <= 12°.

A folded -> non-folded edge:

- immediately requests physical inner wake through the existing controller /
  coordinator ownership path;
- kicks `WallpaperAngleFeed` into its 8 ms active burst.

It does NOT supply an angle and does NOT control render geometry. Samsung's
precise wallpaper angle remains authoritative for the animation.

## Diagnostics

Adds service lifecycle and Shizuku-state events so the next exported bug bundle
can distinguish a service/process restart from a rendering/topology failure.

Version:
- versionCode 34
- versionName `1.3.29-zfold7-deterministic-early-wake`
