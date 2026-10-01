DUO OPEN — GEN3 ALPHA1 INTEGRATED

Baseline production main:
  45bb0d326899c0e08415928224cfea0ff58d2d4e
  2.0.2-zfold7-gen2-field1 / versionCode 37

Target:
  Samsung Galaxy Z Fold7 only
  Android 16 / One UI
  INNER 1968×2184
  COVER 1080×2520

This is the first integrated Gen3 field-alpha candidate.

INCLUDED
1. Phase1 V4 exact-CAS cover prewarm authority.
2. Service-stable exact close-cycle continuity prime owner.
3. FrameStore newest-STARTED capture fence.
4. Generic PanelEngine captures cannot mint privileged continuity frames.
5. Pure exact cover-visual attempt owner.
6. One dedicated privileged cover shader host.
7. Closing: exact current-cycle canonical right pane (984..1920 × 0..2184)
   scaled to 1080×2520 and rendered through DuoShader.
8. Opening: immediate live cross-window blur backend, with semantic opening
   demand surviving Samsung logical-cover remaps.
9. Shizuku privilege loss revokes privileged cycle/readiness/visual authority.
10. Sparse exact visual-attempt/host/content correlation in TransitionLab.
11. Experimental WindowArea "Both screens at once" UI and execution path removed.

INTENTIONALLY DEFERRED
- Cold UserService UNKNOWN_RECOVERY blocking: retained as future-state research,
  but it could deadlock legitimate fully-open startup until physical persistence
  is validated on the Fold7.
- Hard present-fence gating: evidence stays diagnostic/causal in Alpha1.
- Threshold tuning: established thresholds remain unchanged.
- Full deletion/renaming of every Gen2-named helper: unreachable legacy helpers
  may remain until field parity is established.

SAFETY INVARIANTS
- no raw physical panel OFF
- no task migration to secondary displays
- logical display IDs remain disposable observations
- Samsung owns steady-state display behavior after handoff
- reversal/stale callbacks are identity-fenced
- right-side portal geometry preserved
- early inner wake preserved

CI
The workflow applies Phase1 then Alpha1, checks invariants, runs focused owner
tests, runs the full testFullDebugUnitTest + assembleFullDebug gate, commits
app/** only on success, and uploads the debug APK.
