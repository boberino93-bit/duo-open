DUO OPEN GEN3 ALPHA1 V3 — FINAL PRIMARY HANDOFF

This is the deployable corrected Alpha1 package plus complete successor state.

Deploy:
  DEPLOY_GEN3_ALPHA1_V3_FROM_ANYWHERE.sh
or
  DEPLOY_GEN3_ALPHA1_V3_FROM_ANYWHERE.ps1

The workflow is fail-closed:
- verifies production app blobs;
- applies Phase1 V4 CAS;
- applies corrected Alpha1 V2 runtime transforms;
- validates Gen3 invariants;
- runs focused ownership tests;
- runs testFullDebugUnitTest + assembleFullDebug;
- commits app/** only after all gates pass;
- uploads APK only after build success.

V3 does NOT auto-apply unresolved late R&D. Those proposals are bundled and
indexed as ACTIVE_FUTURE_STATE for the successor primary.

Use PRIMARY_MAIN_RESEARCHER_PROMPT_v2.txt.
Use AGENTBUS_HISTORY/ as the canonical lifecycle overlay for the forum.
