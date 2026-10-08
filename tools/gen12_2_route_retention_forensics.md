# Gen12.2 Route Retention Fence — Forensic Basis

## Source evidence

Field bundle: `duoopen-debug-1791438725678.zip`

Source build: `5.6.1-gen12-1-wallpaper-lifecycle-zfold7` (versionCode 57)

The capture demonstrates that Samsung FoldInteractive angle acquisition is not the dominant latency source. Successful authoritative angle delivery is generally low-single-digit milliseconds, while cover-route availability can be delayed by hundreds of milliseconds.

Observed characteristics from the supplied field trace:

- Samsung authoritative source approximately 25 Hz.
- Successful source-to-consumer delivery generally ~1–4 ms, with no hinge-ingress drops or overflows observed.
- Display mode in the capture: 60 Hz, so one physical frame quantum is ~16.67 ms.
- Closing intent to usable/HELD cover route: roughly 226 ms median, ~319 ms p90, and ~676 ms worst observed.
- Deferred-presentation waits reached ~677 ms.
- Opening presentation operations exhibited a severe long tail; one representative stale opening operation took ~622 ms and the trace contained still larger presentation RPC outliers.

## Confirmed race

A representative failure sequence occurred around 05:51:35 in the field report:

1. A new close generation entered `CLOSING_INTENT` and then `COVER_PREWARMING`.
2. An asynchronous `gen4-return:secondary-release` belonging to an older generation completed afterward.
3. That return normalized the cover route to `IDLE`, clearing `physicalLeaseHeld` and `routeReady` while the newer close was already attempting to prepare the cover.
4. The newer close therefore waited for route reacquisition and deferred presentation, producing a ~677 ms readiness delay.

The existing Gen4 `intentSequence` checks do not fully prevent this class of failure because privileged cover mutations execute through one serialized mutation lane. Once an older release has begun executing, a newer prepare cannot advance daemon-side sequencing until the older call leaves that lane.

## Gen12.2 mitigation

Gen12.2 changes only transition-time cover release behavior.

Normal state-machine release reasons beginning with `secondary-release:` no longer immediately invoke the destructive Gen4 route return. Instead, the coordinator retains the already-prepared hidden route for 750 ms and issues a release ticket containing:

- the current continuity generation;
- the current Shizuku connection epoch;
- a monotonically superseding local fence serial;
- a due uptime.

The release is allowed to proceed only if all of those identities are still current when the grace period expires.

A new valid cover prewarm explicitly cancels the pending release before issuing privileged route work. Generation changes and Shizuku reconnections independently invalidate the ticket even if explicit cancellation is missed.

Explicit/non-transition release paths remain immediate. The existing destroy-time direct Gen4 return remains unchanged.

## Why 750 ms

The supplied trace shows an opening-side operation taking approximately 622 ms while a newer close was already waiting. A 750 ms retention window is intentionally larger than that observed representative tail and therefore prevents the stale teardown from even starting during common rapid OPEN→CLOSE reversals.

This is a bounded retention experiment, not a claim that 750 ms is globally optimal. Physical Fold7 validation should determine whether the value can be reduced without reintroducing route churn.

## Safety properties

The patch deliberately does **not** change:

- Samsung precise-angle authority;
- display-angle thresholds;
- secure fail-open behavior;
- DuoShellService physical mutation implementation;
- Shizuku protocol layout;
- renderer geometry;
- wallpaper lifecycle behavior from Gen12.1.

The route remains visually hidden while retained. Only the timing of normal transition teardown changes.

## CI tests

The Gen12.2 workflow reconstructs the exact Gen12.1 lineage first, applies the new overlay, and then requires:

- pure JVM tests for retention timing, cancellation, generation fencing, connection fencing, and ticket supersession;
- a forensic timing replay asserting that the 750 ms window exceeds the representative ~622 ms stale-opening tail;
- `testFullDebugUnitTest`;
- `lintFullDebug`;
- `assembleFullDebug`;
- byte-for-byte parity with Gen12.1 for protected runtime files including `DuoShellService`, `ShizukuBridge`, `FoldOverlayService`, `PanelEngine`, and `Fold7ContinuityController`.

## Physical Fold7 acceptance criteria

A device run should be considered successful only if rapid fold reversals show all of the following:

1. A pending `secondary-release` is logged as retained rather than immediately returning the cover route.
2. A new close logs `cancel ... prewarm:generation=...` before destructive return begins.
3. The old retained release subsequently logs `drop`, not an accepted Gen4 return that clears the newer route.
4. Closing intent to `HELD/routeReady=true` no longer exhibits the prior 200–700 ms reacquisition penalty during rapid reversals.
5. There are no new route leaks after stable-open, disarm, service destruction, or Shizuku reconnection.
6. Existing secure fail-open and native panel restoration behavior remains intact.

If the field trace still shows stale destructive release after this change, the next escalation is daemon-side ingress watermarking / cancellable route return rather than increasing sensor polling frequency.
