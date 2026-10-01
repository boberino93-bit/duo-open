# Duo Open Gen2 — exact-baseline apply package

This package implements the whole-system Gen2 continuity architecture against:

`586c308649258145b3da9b5ea27b726a6fb3647a`

It does **not** push, commit, or modify GitHub by itself. The production/root agent remains the merge authority.

## Architecture delivered

`Angle/Device State -> Transition Policy -> Physical Cycle Envelope -> Cover Lease Authority -> Cover Readiness -> Frame Provenance -> Host/Render -> Presentation Evidence -> Samsung Native Handoff`

The design uses one physical-cycle envelope with typed child authorities. It does **not** collapse every subsystem into one global generation counter.

## Main changes

- Gen2 Samsung angle ingress: explicit reader/poll identity, one poll in flight, completion-paced polling, latest-only main delivery.
- One Fold7 control HandlerThread for angle acceptance/public hinge callbacks.
- Cover lease protocol V3: shell process session + monotonic shell revision + exact lease token validation.
- Immediate cheap DisplayManager topology/readiness fast lane; heavy PanelEngine synchronization remains debounced.
- Exact current-cycle frame provenance separate from generic SnapshotCache bridge semantics.
- Exact presentation-attempt ownership for frozen View and live SurfaceControl paths.
- Transition Lab identity expansion and stale-callback rejection telemetry.
- Version target `2.0.0-zfold7-gen2-ownership`, versionCode 35.
- Build workflow assertions updated for Gen2.

## Preserved invariants

- Samsung Galaxy Z Fold7 only for privileged continuity behavior.
- INNER 1968x2184, COVER 1080x2520.
- Real Android task remains on normal/default display.
- Logical display IDs are disposable observations, never physical identity.
- No raw physical-panel OFF is added.
- Samsung native endpoint handoff remains authoritative.
- Existing Fold7 thresholds are preserved.
- Deterministic frozen-frame intent is preserved.
- Lite/wallpaper flavor is not forced through Fold7 privileged ownership machinery.
- Transition Lab remains part of the architecture.

## Apply

From an exact checkout of the baseline SHA:

```bash
python3 /path/to/DUO_OPEN_GEN2_FULL_SYSTEM_DEPLOY/tools/apply_gen2.py /path/to/duo-open
```

The installer verifies `HEAD` and every high-risk source blob before changing anything. It makes no commit.

Then inspect:

```bash
git diff --check
git status --short
git diff
```

Run structural verification:

```bash
python3 /path/to/DUO_OPEN_GEN2_FULL_SYSTEM_DEPLOY/tools/verify_gen2_postapply.py /path/to/duo-open
```

Run the mandatory repository gates:

```bash
python3 /path/to/DUO_OPEN_GEN2_FULL_SYSTEM_DEPLOY/tools/verify_gen2_postapply.py /path/to/duo-open --gradle
```

Equivalent Gradle command:

```bash
./gradlew testFullDebugUnitTest assembleFullDebug --stacktrace
```

## Baseline drift

If `main` is no longer `586c308649258145b3da9b5ea27b726a6fb3647a`, do **not** blindly apply. Reconcile the changed files first. `--force` only relaxes the HEAD check; the installer still refuses to modify any guarded production file whose blob differs from the audited source.

## Merge stop conditions

Do not merge if any of these occur:

- stale cycle/frame/presentation callback changes current visible state;
- old shell session/revision is accepted;
- duplicate inner wake per opening cycle;
- cover visible before readiness/current visual demand converge;
- prior-cycle frozen frame becomes current continuity content;
- logical display ID becomes cached physical identity;
- raw physical OFF is introduced;
- Samsung native cover takeover is weakened;
- Gradle unit tests or fullDebug assembly fail;
- direct-source workflow checks fail.

## Device validation

After build, validate slow/moderate/fast close, opening from native cover, reversals at every major phase, close-open-close before async completions, Shizuku disconnect/reconnect, route remap/late publication, capture failure/secure content, service restart, repeated closes, and native takeover. Export Transition Lab bundles for comparison.
