DUO OPEN — GEN3 ALPHA2 FIELD FIX

Target baseline:
  production main = 179e688e234fd54cedf99aa7792c86de00bba947
  version = 3.0.0-alpha1-zfold7 / code 38

Why Alpha2 exists:
1. Physical Fold7 field diagnostics show Gen3 Alpha1 OPENING selecting GEN3_LIVE_BLUR and failing attachment on every captured opening attempt.
2. The prior validated Fold7 renderer explicitly disabled live blur and used the snapshot + fold shader path.
3. Early inner wake is still issued successfully, but Alpha1 field timing needs finer causal instrumentation before changing wake thresholds/policy.
4. Diagnostics currently export locally only. Alpha2 adds a receipt-verified HTTPS uploader client while preserving manual export.

What the workflow does:
- verifies exact Alpha1 production blobs before touching app source;
- restores the proven Fold7 opening snapshot/shader renderer UNDER the Gen3 exact visual-attempt owner;
- leaves closing Gen3 frozen-right-pane composition intact;
- does NOT change hinge thresholds;
- adds queue/shell/total timings to inner-wake diagnostics;
- adds Send diagnostic data + local receipt persistence;
- requires the phone to verify diagnosticId + artifactPath + matching SHA-256 before showing Diagnostic received;
- runs focused tests and full testFullDebugUnitTest + assembleFullDebug;
- commits only app/** if all gates pass;
- publishes DuoOpen-ZFold7-3.0.0-alpha2-debug.apk.

Diagnostic relay configuration:
The APK never receives the Artifactory token. Configure a relay endpoint separately from diagnostics-relay/.

Optional GitHub repository settings used by the build:
  Variable: DUO_DIAGNOSTIC_UPLOAD_URL
    Example: https://your-relay.example/v1/diagnostics

  Secret: DUO_DIAGNOSTIC_INGEST_KEY
    Optional relay ingest key. This is NOT an Artifactory credential.

If DUO_DIAGNOSTIC_UPLOAD_URL is empty, Alpha2 still builds and all rendering/wake changes work. The Send diagnostic data button is disabled and manual Export debug bundle remains available.

Upload this package over the REPOSITORY ROOT and commit/push it. The workflow file itself triggers the Alpha2 gated build.
