# Duo Open Gen5 Beta1 — Principal Virtual Hinge Implementation Plan

Baseline runtime: `f9ba2ca7afa2e67586231770fd8b0abe56b94b5b`
Current repository HEAD at packaging: `bfbf5d68fc84cab62cadcbc0b6bc5eefbc7ba5ea`
Target: Samsung Galaxy Z Fold7 / Android 16 / One UI

## Goal

Move the opening experience from delayed sample-following to a visual-only, presentation-oriented virtual hinge while preserving the now-smooth Gen4 closing path and daemon-owned panel authority.

## Gen5 opening pipeline

1. A trusted CLOSED -> OPEN edge starts a visual-only virtual hinge immediately.
2. Before Samsung continuous angle truth returns, the visual clock advances conservatively from the closed seed toward a bounded ~92 degree blind cap.
3. The opening visual runs directly at display vsync instead of feeding predicted state back through the legacy 28 ms TiltFollower.
4. When real angle samples return, the virtual hinge reconciles through a hard slew-rate cap rather than snapping.
5. Reversals disable extrapolation; repeated 30-70 degree oscillation enters a measured-angle guard mode.
6. Visual state uses a 0 -> 1 -> 0 glass envelope with maximum glass at 90 degrees and clear endpoints at 0/180.
7. The preferred opening bootstrap content is the canonical right pane of the most recent inner capture: crop Rect(984,0,1920,2184), scaled to 1080x2520.
8. The active opening overlay requests 120 Hz using seamless-only SurfaceControl frame-rate policy. Actual refresh remains system-authoritative and is logged.
9. The virtual hinge remains visual-only. It cannot drive panel power, continuity semantic state, route mutation, native handoff, or cycle identity.

## Beta1 scope

This build intentionally limits runtime integration to the existing cover-hosted opening renderer. It does not yet move the right-pane bridge onto a dedicated inner-display split-pane SurfaceControl. That larger presentation migration remains the next Gen5 iteration after hardware evidence from this build.

## Preserved invariants

- Gen4 daemon owns privileged cover-panel mutation.
- Real app task stays on default display.
- No raw physical OFF.
- Samsung/native owns terminal steady state.
- Existing Gen3/Gen4 close thresholds are unchanged.
- Closing frozen-frame/canonical-right-pane path is unchanged.
- Reversal remains first-class.
- Logical display IDs remain observations, not physical identity.

## App productization included

- Main app surface simplified to status + Test fold + Settings.
- Existing tuning, simulator and engineering controls remain in the settings sheet.
- Diagnostics action remains usable when no upload endpoint is configured: it falls back to Android sharing instead of being greyed out.
- Gen5 logs requested/effective refresh rate, physical/virtual angle, confidence, correction, slew limiting and mode.

## Acceptance gate

CI must pass:

- exact baseline blob checks;
- package support-file checksum validation;
- patcher syntax;
- Gen5 invariant checks;
- `Fold7VirtualHingeGen5Test`;
- Gen4 panel-authority regression test;
- continuity-controller regression test;
- hinge-ingress regression test;
- visual-attempt-owner regression test;
- full `testFullDebugUnitTest assembleFullDebug`.

Only then does CI commit runtime files and publish the Beta1 APK.

V3 CI PERMISSION FIX
--------------------
V2 run 36981573600 passed focused Gen5/Gen4 regressions and the full testFullDebugUnitTest + assembleFullDebug gate. The only failure was the final push because GitHub Actions cannot update another workflow file without workflows permission. V3 therefore human-commits the legacy build-shizuku workflow as manual-only during package import; the validated CI runtime commit stages only app/**. Runtime payload is unchanged from V2.
