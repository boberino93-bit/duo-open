# WallpaperAngleFeed Gen-2 draft dependencies

`WallpaperAngleFeed.Gen2.draft.kt` is intentionally NOT in `repo_overlay/` because
copying it alone would break compilation. It requires coordinated changes.

Required integration work, each intended as a <=10-minute commit-sized unit:

1. Add `Fold7AnglePipelineGen2.kt` and its unit tests.
2. Extend `ShizukuBridge.AngleCallback` / `startAngles` callback to carry a
   `pollSequence: Long` in addition to angle/sourceUptime/binderArrivalTimeNs.
3. Extend `DuoShellService.AngleReader` so the per-command poll sequence is
   parsed from the session action and written into the CB_ANGLE Parcel.
4. Add Transition Lab fields/events: angleSession, pollSequence, sampleSequence,
   plus `recordIngressStage(...)`; extend JSONL serialization.
5. Create one `HandlerThread("duo-fold7-angle-control")` in FoldOverlayService.
   Keep window/view work on main; serialize Samsung sample acceptance and public
   SensorManager callbacks on the control Handler.
6. Change HingeAngleSource registration to the Handler overload so public hinge
   callbacks share the control thread. Preserve the existing 8,000 us request.
7. Construct WallpaperAngleFeed with mainHandler + controlHandler + hinge.
8. Integrate early-opening ingress only after observation validates the source:
   edge may WakeInner once + kick precise burst; it must never supply shader
   geometry or make a mirror visible.
9. Preserve Fold7 controller thresholds: wake 3°, handoff 8°, prewarm 174°,
   cover visual 135°, visual hide 140°, open latch/rearm 172°/166°.
10. Bump to 1.3.26 / versionCode 31, update the direct-source workflow, then run
    `./gradlew testFullDebugUnitTest assembleFullDebug --stacktrace`.

Do not cache logical display IDs as physical identity. Do not add raw physical
panel OFF. Do not weaken generation checks around prewarm/release/mirror-stop.
