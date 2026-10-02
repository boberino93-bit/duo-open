# START HERE — Duo Open Primary Successor V3

This archive is the final primary handoff.

## Production truth at packaging
- main: `7a612a0fe3181768f548a1ec78d2c3ee5938a339`
- runtime: versionCode 37 / `2.0.2-zfold7-gen2-field1`
- Gen3 runtime is NOT yet committed.
- Alpha1 V1 run `36941681407` failed safely; no runtime commit/APK.

## Deploy candidate
Run `DEPLOY_GEN3_ALPHA1_V3_FROM_ANYWHERE.sh` or `.ps1` from inside the repo.
Commit/push the root support files it installs.
The workflow applies corrected Phase1 + Alpha1 and commits `app/**` only after
focused tests and full Android test/build pass.

## Primary successor
Use `PRIMARY_MAIN_RESEARCHER_PROMPT_v2.txt`.

## History
Read `AGENTBUS_HISTORY/` before raw forum messages. It contains the full
retroactive lifecycle ledger for all 70 pre-handoff messages and the exact
ACTIVE_FUTURE_STATE queue.

## Critical rule
Do not treat Alpha1 as CURRENT_PRODUCTION until GitHub proves the runtime commit
and the APK exists.
