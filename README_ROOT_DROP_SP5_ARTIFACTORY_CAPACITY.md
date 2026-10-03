# ROOT DROP — Duo Open SP5 Artifactory Capacity Round V1

Extract directly into the root of `boberino93-bit/duo-open`.

The pack is additive: it does **not** replace root `README.md` or root `APPLY_AFTER_COPY.py`, and it does not modify Android runtime source. It adds the V2 research/control protocol, live daily calibration evidence, current round tickets, deterministic tests, verifier, and a GitHub APK build workflow.

Observed source before packaging: `32b8e44ee12de1c707b21a5c68285edb87cec343`.

Validation after extraction:
`python3 tools/verify_artifactory_capacity_service_pack.py .`


## SP5.1 retention clarification
Artifactory capacity probes are temporary load-test scratch objects. Primary must purge stale probe sets before testing and delete the complete current probe directory after readback verification. Only the compact aggregate planning sample is retained. `RESUME_WORK` is blocked unless post-delete inventory proves zero residual raw calibration objects.
