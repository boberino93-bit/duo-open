# Duo Open canonical AgentBus + SP4.2 root-safe overlay

This archive is intended to be **extracted directly into the root** of `boberino93-bit/duo-open` at current main `28842ae4d1c4f907257b24a73012bf5015702f81`. Allow overwrite of existing SP4/SP4.1/SP4.2 files.

It is deliberately root-safe:

- the complete AgentBus is under `DuoOpen-AgentBus/`;
- no generic root `README.md` is included, so the repository README is not replaced;
- the cumulative SP4.2 workflow/patcher/service-pack files are included at their repository paths;
- a new harmless watched-path marker forces a fresh Beta2 workflow run after the overlay commit;
- no transformed Android `app/` source is directly written by this archive. The existing CI patcher performs that transformation in the workflow workspace.

## Snapshot

- AgentBus message JSON files: **594**
- Latest persisted message: `20261003T024651Z__primary__all__root-safe-overlay-export.json`
- Canonical Primary: `DUO_OPEN_PRIMARY_AGENT_V7_POST_APK_ARTIFACTORY_NG.zip`
- Canonical Manager/Reviewer: `DUO_OPEN_GEN7_MANAGER_REVIEWER_AGENT_V5_POST_APK_ARTIFACTORY_NG.zip`
- Canonical Research: `DUO_OPEN_GEN7_RESEARCH_AGENT_V5_POST_APK_ARTIFACTORY_NG.zip`
- Runtime hotfix lineage: SP4 → SP4.1 → SP4.2, with SP4.2 cumulative and the earlier package archives preserved as evidence.
- Successful reference CI run: `37083926151` on `28842ae4d1c4f907257b24a73012bf5015702f81`.
- Physical Fold7 validation remains **NOT_RUN**.

## Apply

1. Extract this ZIP into the repository root.
2. Allow overwrite of existing files.
3. Commit the resulting changes to `main`.
4. The new `service_packs/gen7_runtime_regression_beta2/AGENTBUS_OVERLAY_REVALIDATION_20261003.md` file is under a watched path and should trigger `Build Gen7 Runtime Regression Beta2`.

Run `python DuoOpen-AgentBus/import/VERIFY_ROOT_SAFE_OVERLAY.py .` from the repository root if you want an offline package-integrity check before committing.
