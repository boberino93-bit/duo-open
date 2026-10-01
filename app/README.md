# Duo Open Gen2 Field Fix V7 — final pre-apply revision

Baseline: `813b2ac2fa44edc3e69a7f534ad01dd79e45fa25`
(`2.0.1-zfold7-gen2-audit1`)

This pass is driven by the first real Fold7 2.0.1 field logs.

## Changes

- Starts an explicit cover opening visual from the semantic DeviceState opening edge instead of waiting for Samsung's precise FoldInteractive stream to resume.
- Keeps that opening visual latched across topology-only `INNER_HANDOFF`, because the logs show inner topology can become active roughly a hundred milliseconds after the opening edge while precise hinge data may resume hundreds of milliseconds later.
- Uses a service-owned 2.5 s safety timeout so a missing precise-angle recovery cannot leave the opening visual stuck. The timeout clears the semantic latch, so later callbacks cannot restart the same opening animation.
- Clears the opening latch on route loss/remap, Shizuku/ownership loss, manual stop, true open/native/closing states, or service destruction.
- Primes a capture-only Gen2 continuity frame as soon as a stable close cycle exists; ordinary inner shader capture cannot supersede that primed cycle unless the prime fails.
- Makes privileged Gen2 the sole autonomous Fold7 cover renderer during closing. The generic cover `PanelEngine` is suppressed while Gen2 owns the cover.
- Uses fresh 1968x2184 / 1080x2520 geometry for render ownership and frame priming rather than treating logical display IDs or cached panel role as physical identity.
- Immediately reconciles render ownership when the user manually Arms or Stops continuity.
- Preserves V6 right-pane portal geometry and frozen-frame provenance.
- Leaves the established 3° / 8° / 174° / 135° / 140° / 172° / 166° thresholds unchanged.

## Validation strategy

The workflow fails closed unless the exact V6 production blobs match. It then applies the patch, validates source invariants, runs:

`./gradlew testFullDebugUnitTest assembleFullDebug --stacktrace`

Only after those gates succeed does it commit `app/**` and upload:

`DuoOpen-ZFold7-2.0.2-gen2-field1-debug.apk`
