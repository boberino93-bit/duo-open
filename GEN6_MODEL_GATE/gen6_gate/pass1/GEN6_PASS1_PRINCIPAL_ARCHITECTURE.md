# Duo Open Gen6 — Pass 1 Principal Architecture

Baseline: `boberino93-bit/duo-open@de9eb45086f6eee00dd4e1e01d5e9782e39773d5`, runtime `5.0.0-beta1-zfold7` (42).

## Core boundary
Samsung remains the terminal/steady-state authority. Gen6 owns only a temporary, attempt-scoped continuity presentation between the first corroborated leave-closed wake hint and context-specific native freshness.

Pipeline:

`observations -> WakeHintOwner -> existing semantic hinge/Gen4 panel authority -> OpeningAttemptOwner -> ContentProvenanceOwner -> CanonicalSceneMapper -> PresentationHostLease -> VirtualHingeClock -> Gen6 renderer -> NativeFreshOracle -> Samsung native handoff`

The virtual hinge is visual-only. It cannot fabricate semantic angle, terminal open/closed state, panel route ownership, task migration, or security state.

## Invariants
1. A corroborated Samsung `0->1` or `0->2` transition may start WakeInner and the Gen6 visual attempt immediately, but does not create hinge geometry.
2. `OpeningAttemptId` survives logical-display remap. Display IDs are observations, never physical identity.
3. Host migration is make-before-break: replacement binds, presents, then old host retires. A stale callback cannot clear a newer host or refresh lease.
4. HOME uses only inner x=984..1920 as the canonical right pane. Mapping is uniform 15/13 to 1080x2520. x=1920..1968 is an explicit excluded strip, never stretched into the bridge.
5. GENERAL_APP bridges current same-attempt cover pixels only when capture is permitted and provenance is current. Native inner app re-layout is allowed and expected.
6. SECURE mode never places protected pixels in a content lease/cache/trace. Capture denial selects a content-free visual bridge and native secure-window readiness gate.
7. Cross-attempt content is rejected by default. Pixel leases are attempt + service epoch + generation fenced and short-lived.
8. Wallpaper readiness is separate from launcher/app useful presentation. Wallpaper-only can never release HOME.
9. Terminal release requires measured semantic-open state plus a context-specific NativeFreshOracle PASS.
10. Refresh ownership is `(attemptId, hostId, generation)`. Replacement explicitly clears old owner; stale cleanup is a no-op against a newer owner.
11. Glass and geometry are separate controls. Both are clear/bounded at 0/180; glass peaks at 90; geometry is C1 through 90.
12. Any app/service/Shizuku/host/capture failure cleans overlay, refresh lease, pixel content, and host leases before degrading to Samsung-native behavior.
13. Gen4 close thresholds/choreography remain untouched. Delayed work from a close cycle at or before terminal `NATIVE_COVER` is rejected by cycle/generation fences.
14. MODEL_PASS, CI_PASS, and PHYSICAL_FOLD7_PASS remain separate claims.

## Evidence-driven rationale
The mounted Gen4 field log contains ten leave-closed events. Nine begin as `0->1`; the first nonzero angle follows 380–2484 ms later, median ~810 ms; opening-state transition delays span 1–2487 ms with the same ~810 ms median. This is a software waiting gap, not a reason to synthesize hinge angle. Gen6 starts the wake/presentation attempt from the hint while preserving real measurements as semantic authority.

The final Gen5 peer review also confirmed that production integration must not rely on synthetic `Display.mode` timing, root-only refresh votes, unfenced refresh ownership, coupled glass/geometry, or a 15-minute provenance-free snapshot cache. Pass 1 models these as hard boundaries.

## Pass-1 scope
This model deliberately does not claim Android implementation correctness, real FrameTimeline cadence, secure-window detection correctness, direct diagnostic relay availability, or physical Fold7 visual quality. Those belong to Pass 2 / production slices and must be measured on device.
