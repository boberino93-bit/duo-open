# Duo Open Gen2 — Post-Audit Corrections V6

Audited baseline: `4aa953925bf3aa2ac3f09d9c80b6653c6dfb058a`

This pass corrects three issues found before Fold7 field testing:

1. **Right-side portal geometry.** Both frozen and live continuity paths are
   changed from the integrated left-pane crop to the intended right inner pane,
   preserving the hinge edge. Fold7 source geometry becomes x=984..1920
   (936x2184) -> 1080x2520.

2. **No older same-cycle frame after a newer capture begins.** Starting a new
   capture immediately revokes the prior continuity frame. If the newer attempt
   fails, the frozen-frame lookup returns nothing rather than replaying the old
   image. A unit regression test is added.

3. **Serialized V3 revision authority.** If the serialized cover mutation
   throws or times out, the Binder-thread catch no longer stamps a new
   authoritative shell revision. The unstamped failure is rejected by the
   app-side gate until a later serialized reconcile/status result arrives.

The app is bumped to:
- versionCode 36
- versionName `2.0.1-zfold7-gen2-audit1`

The workflow verifies the exact audited blobs, applies the patch, runs
`testFullDebugUnitTest` and `assembleFullDebug`, commits only `app/**` on
success, and uploads a Fold7 field-test APK.

Still tracked separately:
- the frozen presentation path currently has View draw + frame-commit evidence,
  but not the stronger inert SurfaceControl presented/completed marker proof;
- legacy GitHub build workflows are stale and will be cleaned up after the
  runtime correction lands.
