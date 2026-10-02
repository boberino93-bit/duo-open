# Gen5 Beta1 Fold7 field test checklist

Remove the Photos widget during continuity testing so launcher/widget content changes do not confound the visual assessment.

## Normal use
- 10 slow closes and opens.
- 10 normal-speed closes and opens.
- 10 fast closes and opens.
- Confirm closing remains as smooth as Gen4 Alpha1.
- Opening should visibly begin immediately from the leave-closed edge rather than waiting for the first coarse 90 degree sample.
- At roughly 90 degrees the glass effect should be at its visual maximum.
- As the device approaches fully open, glass should resolve toward clear.

## Opening latency
- Note time/feel from first physical opening motion to first visible continuity motion.
- Note time to inner panel illumination.
- Note any wallpaper-only interval before icons/widgets appear.
- Do not classify wallpaper-only as first-useful launcher presentation.

## Reversal / oscillation
- Repeat 30 -> 70 -> close -> 30 -> 70 degree cycles at least 30 times.
- Perform single rapid reversals at 20, 45, 70, 100 and 130 degrees.
- Look for snap-back, runaway animation, stale direction, process/service crash, wallpaper fallback, black cover, or stuck route.

## Angle blackout / reacquisition
- Open from fully closed several times without pausing.
- Watch for a sudden visual jump when precise Samsung angle resumes.
- Gen5 should reconcile gradually; no giant one-frame snap.

## 120 Hz
- Export diagnostics after a clean sequence.
- Check `gen5-refresh` for requested=120 and actual effective refresh.
- A request being refused by Samsung/Android is not itself a failure; it must be recorded accurately.
- No black flash is acceptable from refresh-rate switching.

## Failure recovery
- Kill/restart Duo app process while Shizuku survives.
- Restart Duo Shizuku user service while on cover and mid-open.
- Run 50+ mixed open/close/reversal cycles.
- After any anomaly, stop and export diagnostics immediately.

## Diagnostics
Expected Gen5 events include:
- `gen5-virtual-hinge`
- `gen5-split-pane`
- `gen5-refresh`
- existing `early-wake`, `hinge-ingress`, `gen3-visual`, `display-probe`, `cover-opening-visual`
