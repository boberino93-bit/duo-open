DUO OPEN — GEN3 ALPHA3 INPUT TRUTH + GLASS CORRECTNESS

Target: Samsung Galaxy Z Fold7 only
Required production baseline: 413d4a722fe8193f15ff086595f10d1464505ace

PURPOSE
Alpha3 corrects the input-truth boundary before deeper presentation work:
- one service-owned Fold7 hinge authority;
- Samsung/FoldInteractive precise samples have a finite freshness lease;
- public 0/90/180 sensor remains a timestamped shadow fallback;
- precise loss without a fresh fallback becomes GEOMETRY UNKNOWN (NaN), never a held fake-current angle;
- bounded ordered source-time mailbox preserves reversals/semantic samples;
- mailbox overflow fails closed and rearms continuity from current evidence;
- full UI reads the service authority instead of constructing a second hinge source;
- Fold7 Shizuku capture + angle transport become required infrastructure when Shizuku is ready;
- obsolete Fold7 Live Blur / capture / continuous-angle switches are removed from production UI;
- shader producer and AGSL use the same 60-degree optical domain;
- BitmapShader input to RuntimeShader uses explicit linear sampling.

UNCHANGED INTENTIONALLY
- 3/8/174/135/140/172/166 degree continuity thresholds.
- physical inner prewake experiment.
- Samsung/native steady-state ownership.
- FoldInteractive remains a temporary precise transport until a direct sensor is physically proven.
- no raw physical panel OFF.
- no task migration.

DEPLOYMENT
1. Extract this ZIP directly into the ROOT of the GitHub repository.
2. Do not upload the containing folder as one directory.
3. Commit/push the support files to main.
4. The workflow .github/workflows/apply-gen3-alpha3-input-truth.yml triggers on that push.
5. It verifies the exact Alpha2 production blob set, verifies this package's checksums, applies Alpha3, runs focused tests, runs the full unit/build gate, then commits app/** only if all gates pass.
6. The validated APK artifact will be named DuoOpen-ZFold7-3.0.0-alpha3.

FIELD TEST AFTER SUCCESSFUL BUILD
- Slow open: 0 -> 30 -> 60 -> 90 -> 120 -> 150 -> open.
- Slow close in reverse.
- Reversal around ~30, ~90, and ~140 degrees.
- Watch the app's authoritative angle/status: it should show the service source, not an independent 0/90/180 UI sensor.
- If precise FoldInteractive disappears, status should demote quickly to a fresh public shadow or Geometry unknown; it must not silently claim a stale precise angle.
- After 5-10 folds/reversals, use Send diagnostic data and retain the returned diagnostic ID/checksum.
