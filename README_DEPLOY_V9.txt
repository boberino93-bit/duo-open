DUO OPEN GEN2 FIELD FIX V9 — DEPLOYMENT RECOVERY

Live baseline when packaged:
  main = 7f1eea754b71e606b2c313179d56935e8093f442
  production runtime = 2.0.1-zfold7-gen2-audit1 (versionCode 36)

WHY V9 EXISTS
V7 and V8 were uploaded under /app, so GitHub never recognized their workflow
files. V9 keeps the audited 2.0.2 runtime correction but makes deployment
path-proof and safely cleans the stranded V7/V8 support files after verifying
their exact blob identities.

RECOMMENDED DEPLOYMENT
1. Extract this ZIP anywhere.
2. From inside the duo-open repository, run:
     bash /path/to/extracted/DEPLOY_V9_FROM_ANYWHERE.sh
   Or on PowerShell:
     & "C:\path	o\extracted\DEPLOY_V9_FROM_ANYWHERE.ps1"
3. Confirm these exact repository-root files exist:
     /.github/workflows/apply-gen2-field-fix-v9.yml
     /tools/apply_field_fix_v9.py
4. Commit and push those TWO ROOT FILES.
5. The workflow performs baseline validation, patches 2.0.2, runs unit tests +
   assembleFullDebug, then commits app/** and uploads the test APK only on green.

DO NOT upload the package while browsing the repository's /app folder.
If using a graphical client, use the deploy script instead; it resolves the
actual Git repository root automatically.
