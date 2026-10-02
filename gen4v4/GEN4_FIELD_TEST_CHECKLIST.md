# Gen4 Alpha1 — Galaxy Z Fold7 field test checklist

Target runtime: `4.0.0-alpha1-zfold7` / versionCode `41`.

## Before testing

- Confirm the dedicated Gen4 Actions run is green.
- Confirm `DuoOpen-ZFold7-4.0.0-alpha1` was produced by that same run.
- Confirm BUILD-INFO commit equals current runtime main.
- Install the Gen4 APK.
- Confirm Shizuku is running and Duo Open is authorised.
- Re-enable the accessibility service if Android disabled it during install/update.
- Capture/export diagnostics for every anomalous sequence rather than repeating it blindly.

## A. Native startup admission

1. Boot/start with the phone fully open on the inner display.
2. Launch Duo Open while Shizuku is already running.
3. Verify continuity does not visibly touch the cover during admission.
4. Repeat with Shizuku stopped, then start Shizuku while Duo Open remains alive.
5. Repeat with Shizuku permission temporarily removed then restored.

Expected:
- no render ownership before actual Shizuku user-service binder readiness;
- `gen4-authority` admission occurs before continuity arm;
- inner display remains native and usable throughout recovery.

## B. Slow close / fast close

Run at least 10 cycles of each:

- very slow 180° -> 0° close;
- normal close;
- fast close.

Watch for:
- early hidden cover preparation near the existing 174° semantic threshold;
- no premature visible cover content during hidden preparation;
- no black/stuck cover at Samsung native landing;
- no duplicate fold visual;
- no touch/task migration to the wrong display.

## C. Slow open / fast open

Run at least 10 cycles of each from fully closed:

- very slow open;
- normal open;
- fast open.

Expected:
- DeviceStateManager early wake remains intact;
- inner physical wake begins before precise angle resumes when appropriate;
- visual opening attempt occurs once;
- native inner landing completes without a persistent cover route.

## D. Reversal stress

Repeat at least 10 times each:

- begin closing, reverse near 170°;
- reverse after cover preparation but before 135° visual threshold;
- reverse during visible cover transition;
- begin opening from closed, reverse back to closed quickly;
- multiple short oscillations around the prewarm region.

Expected:
- latest intent wins;
- stale earlier requests do not reclaim panel authority;
- release either completes immediately or enters bounded RELEASE_PENDING recovery;
- no permanent secondary cover route after the sequence settles open.

## E. App-process death during prepared cover

1. Start a deliberate close far enough to prepare the cover.
2. Before completing the close, kill/restart the Duo Open app/accessibility process while leaving Shizuku alive.
3. Relaunch/re-enable the service.

Expected:
- new serviceEpoch is detected;
- old prepared route is normalized by the daemon before the new service is admitted;
- no inherited old close-cycle ownership;
- continuity remains disarmed until admission succeeds.

## F. Shizuku daemon death/restart

1. Prepare the cover during a close.
2. Kill/restart Shizuku or otherwise force the DuoShellService binder to die.
3. Leave the Duo Open accessibility service alive if possible.
4. Restore Shizuku.

Expected:
- app render authority is revoked immediately on privilege loss;
- the new shellSession performs topology-based startup recovery;
- any observable secondary cover route is normalized before admission;
- no reliance on the old daemon's in-memory lease state;
- continuity re-arms only after binder + recovery readiness.

Also perform a graceful Shizuku stop/restart. The graceful destroy path should attempt normalization before executor shutdown.

## G. Start while natively closed

1. Fully close the Fold7 so the cover is Samsung's native default.
2. Start/restart Duo Open and Shizuku in several orders.
3. Open normally and quickly.

Expected:
- native cover is recognized as safe and is never reset as though it were a secondary route;
- opening early wake and visual continuity still work;
- no forced cover secondary-route mutation while natively closed.

## H. Foreground content matrix

Repeat representative close/open tests from:

- launcher/home;
- a normal app;
- scrolling content;
- video/moving content;
- secure/protected content;
- Duo Open UI itself.

Expected:
- authority behavior is identical regardless of content source;
- secure-content limitations do not change panel ownership semantics;
- no stale frame from a previous close cycle is presented.

## I. Long-run cycle test

Run 30+ mixed open/close cycles with occasional reversals and pauses.

Pass conditions:
- no stuck cover route;
- no persistent black cover;
- no duplicate visual ownership;
- no requirement to manually toggle the accessibility service;
- no monotonic growth of recovery failures;
- no stale serviceEpoch/intentSequence accepted after a newer one.

## Diagnostics to preserve on failure

Capture the debug bundle and note:

- exact physical action performed;
- whether the failure occurred opening or closing;
- approximate hinge angle/direction;
- whether Shizuku/app process had just restarted;
- visible panel(s);
- whether native Samsung content or Duo visual was visible;
- `gen4-authority`, `fold7-state`, `fold7-readiness`, `early-wake`, `hinge-ingress`, and `angle-authority` lines;
- shellSession, serviceEpoch, intentSequence, closeCycleId and transition generation when present.

Do not tune hinge thresholds to hide an ownership/recovery failure. Threshold tuning comes only after authority behavior is proven deterministic.
