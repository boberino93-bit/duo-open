# Duo Open 1.3.25 — Debug Export + Crash-Resistant Transition Logs

This build intentionally does not retune panel or animation behavior.

It exists so the next physical Fold7 failure produces usable evidence.

Changes:

- Adds `Debug logs -> Export debug bundle` to the in-app Control Sheet.
- Creates one shareable ZIP in app cache.
- ZIP includes:
  - `field-report.txt` from DuoDiagnostics' in-memory ring buffer;
  - `duoopen-field-debug.log` when present;
  - up to the newest 8 Transition Lab JSONL sessions;
  - build/export metadata.
- Uses FileProvider for secure one-time sharing.
- Transition Lab now flushes:
  - after at most 250 ms of writer idle time;
  - every 64 rows during sustained activity;
  - explicitly before a user-triggered export.
- This materially reduces the amount of timing evidence lost if the app process
  crashes during repeated folding.

Preserved from 1.3.24 Fix2:

- inner physical wake ~3 degrees;
- inner handoff fallback ~8 degrees;
- cover physical-first prewarm ~174 degrees;
- cover visual gate ~135 degrees;
- async generation guards;
- pre-resolved/cached physical IDs only;
- no cached logical display IDs;
- no unconditional physical OFF;
- Transition Lab vsync/SurfaceControl timing probes.

Version:
- versionCode 30
- versionName 1.3.25-zfold7-debug-export

The direct-source CI workflow must pass before installation.
