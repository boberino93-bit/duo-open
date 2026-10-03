# Duo Open SP5 — Artifactory Capacity Round V1

This is a **root-drop control-plane service pack** pinned to observed GitHub `main` `32b8e44ee12de1c707b21a5c68285edb87cec343`.

## What it changes
- Adds Round Orchestration V2 with a 20-session hard ceiling, nominal 18-session target and useful-parallelism guard.
- Adds the daily STOP_WORK -> pre-test scratch purge -> one 90% adapter calibration -> compact result -> post-test zero-residual purge -> RESUME protocol.
- Adds `MUST_INVOKE_OR_JUSTIFY` so every substantive work unit either requests bounded help or explains why more parallelism would be harmful/duplicative.
- Activates split-plane service publication: DMSH for high-frequency liveness; immutable general messages for material transitions/required ACKs.
- Preserves fail-closed exact-path + readback-hash publication semantics and keeps singleton-Primary CAS blocked.
- Carries only compact capacity evidence into the Git recovery mirror; synthetic calibration probe files are explicitly non-retained scratch data.
- Adds a GitHub workflow which, once this pack is committed/pushed, verifies SP5 and then rebuilds/tests the existing Beta2 APK.

## What it does NOT change
No Android runtime source is changed by this service pack. It does not claim the Fold7 INNER-display/first-open P0 is solved. It does not claim the Library adapter's 20-operation schema limit is Artifactory's physical backend maximum. It does not claim 17 child chats were actually opened; the current host state is `MANUAL_FALLBACK` until `SESSION_STARTED` evidence exists.

## Live calibration captured in this pack
- exposed adapter declared max operations/call: 20
- one controlled 90% batch: 18 writes
- upload results: 18/18 success, zero warnings
- exact requested paths: 18/18
- raw materialized readback SHA-256: 18/18 byte-identical
- total probe payload: 21,681 bytes
- disposition: `PASS_ADAPTER_BATCH_TARGET`; backend physical ceiling remains `UNPROVEN`
- raw calibration probes deleted after verification: 18/18
- residual raw probe objects: 0
- retained capacity evidence: compact aggregate only

## Apply
Extract this ZIP directly into the repository root. It contains root-relative paths and does not replace the project root README or existing `APPLY_AFTER_COPY.py`.

Then run:

```bash
python3 tools/verify_artifactory_capacity_service_pack.py .
python3 DuoOpen-AgentBus/control/round_orchestration/v2/test_capacity_controller.py
```

Commit/push the resulting files. The included `build-sp5-capacity-control-and-beta2-apk.yml` workflow then provides the fresh APK build gate that the current read-only GitHub connector could not dispatch directly.
