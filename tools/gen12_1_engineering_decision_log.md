# Duo Open Gen12.1 — Wallpaper Persistence / Lifecycle Forensic Log

## Status at authoring

This document describes the evidence and implementation intent for the Gen12.1 validation candidate. It does **not** claim physical Fold7 validation.

## Trigger

User report on Gen11/Gen12 lineage:

- setting a wallpaper does not reliably persist when the app is reopened;
- reopening can freeze and crash the app.

The earlier forensic pass of `duoopen-debug-1791432567831.zip` focused on fold-transition timing and missed the wallpaper persistence/lifecycle surface. The project bootstrap has since been updated on `main` so future forensic audits require maximum-detail cross-layer analysis plus an explicit lifecycle/persistence matrix.

## Evidence inventory

### Physical debug bundle

`duoopen-debug-1791432567831.zip`

- build: `5.5.0-gen11-product-ui-zfold7` / code 55
- device: Samsung `SM-F966W`
- API: 37
- generated: `2026-10-08T04:09:27.832873Z`

### Source lineage

Gen12 baseline head:

`ada974eb9a9bebb19fa0a669278fa250889d976a`

Gen12.1 is a post-lineage overlay and must preserve Gen12 route-lane behavior.

## Reconstructed forensic findings

### 1. Exact crash mechanism is not present in the supplied bundle

The persistent field log contains one prior-process-exit record:

- reason `10`
- description `[REMOVE TASK] remove task`

On Android this is a user-requested/task-removal style exit, not evidence of Java crash, native crash, ANR, or low-memory kill.

The bundle contains no `AndroidRuntime`, `FATAL`, `OutOfMemory`, or ANR record.

**Classification:** `INSUFFICIENT_EVIDENCE` for the exact reported crash mechanism.

The implementation therefore must not claim a confirmed OOM or exception root cause.

### 2. Wallpaper payload/version transaction is unsafe

Current `WallpaperImage.import`:

1. decodes the picked image;
2. writes `wallpaper.jpg.tmp`;
3. calls `tmp.renameTo(wallpaper.jpg)` without checking the result;
4. advances `imageVersion` unconditionally.

A failed replacement can therefore produce metadata/payload divergence: consumers are told a new image version exists even if the durable payload did not change.

**Classification:** `DIRECTLY_CONFIRMED` source defect.

### 3. Imported bitmap is decoded again immediately

After import advances `imageVersion`, both app preview and live wallpaper can react to the new state. `WallpaperImage.load` does not reuse the just-decoded imported bitmap for the new version, so it can decode the newly-written JPEG again.

Because app UI and `DuoWallpaperService` run in the same process, the transition can temporarily retain:

- imported decoded bitmap;
- previous cached bitmap;
- previous wallpaper-service bitmap/shader references;
- freshly decoded replacement bitmap;
- Compose/GPU texture state.

This is a credible peak-memory amplification path. It is consistent with a freeze/crash report but not proven as the physical crash cause by the supplied bundle.

**Classification:** `DERIVED_CONFIRMED` for redundant decode/resource amplification; `SUPPORTED_HYPOTHESIS` for relation to the physical crash.

### 4. Corrupt persisted payload silently degrades

Current load behavior falls back to a generated default if persisted decode fails but does not produce persistent diagnostics explaining the failure. A corrupt payload can therefore appear as “wallpaper not retained” without an explicit storage receipt.

**Classification:** `DIRECTLY_CONFIRMED` observability/recovery defect.

### 5. Duo live wallpaper conflicts with Samsung wallpaper-backed precise-angle transport

The physical bundle repeatedly records transitions such as:

- `wallpaper changed from=live/FoldInteractive to=duoopen/DuoWallpaperService`
- shortly afterward `readerFresh=false`
- when `live/FoldInteractive` returns, the reader becomes fresh again.

The UI simultaneously presents Duo wallpaper mode while documenting Samsung Fold interactive as the temporary precise-angle fallback.

This is a cross-feature compatibility conflict: both wallpaper ownership modes cannot be assumed simultaneously authoritative on the active wallpaper target.

**Classification:** `DIRECTLY_CONFIRMED` from physical field logs + current UI/transport design.

Gen12.1 does not replace the angle transport. It adds an explicit Fold7 compatibility warning and preserves the existing fallback architecture.

### 6. Prior-exit diagnostics are too narrow

`DuoApplication` currently logs only the newest historical process exit. A user/task removal can therefore hide a crash/OOM/ANR immediately before it.

**Classification:** `DIRECTLY_CONFIRMED` forensic observability defect.

### 7. Default-image reset performs durable storage work on the Compose/main thread

The Gen11/Gen12 `DuoApp` callback for `Use default` calls `WallpaperImage.reset(context.applicationContext)` directly from the Compose click handler. Gen12.1 intentionally makes reset a checked durable transaction, so leaving that caller synchronous would permit storage latency/failure to block the UI thread and would make a thrown reset failure an activity-level crash path.

**Classification:** `DIRECTLY_CONFIRMED` caller/lifecycle hazard from source inspection. It is not proven to be the exact historical crash reported by the user.

Gen12.1 moves reset onto `Dispatchers.IO`, wraps it in `runCatching`, and reports failure to the UI rather than allowing the storage operation to take down the activity.

## Gen12.1 implementation

### Durable wallpaper transaction

- Replace unchecked temp-file rename with Android `AtomicFile`.
- Sync the output descriptor before `finishWrite`.
- Verify committed payload existence/length.
- Synchronously commit `imageVersion` metadata and check the SharedPreferences commit receipt.
- Publish the new StateFlow version only after metadata commit succeeds.
- Publish the already-decoded imported bitmap as the cache entry for that exact version.

### Rehydration / failure safety

- Use `AtomicFile.openRead()` to recover interrupted writes.
- Persist diagnostics for open/decode/corruption/OOM outcomes.
- Delete corrupt committed payload before falling back to the generated default.
- Use a small low-memory fallback if a persisted decode hits `OutOfMemoryError`.

### Resource envelope

- Cap custom-image decode to `MAX_DIM=2600` and `MAX_PIXELS=5,000,000`.
- Avoid immediate second decode after import.
- Do not recycle the previous shared bitmap from the store because UI/wallpaper consumers may still reference it; let ownership drain naturally.

### UI mutation threading

- Keep image import on `Dispatchers.IO`.
- Move `Use default` / wallpaper reset to `Dispatchers.IO`.
- Catch reset failures and surface them with a user-visible error instead of blocking/crashing the Compose activity.

### Service lifecycle diagnostics

Persist bounded events for:

- wallpaper engine create/destroy;
- visibility changes;
- surface changes/destruction;
- image load success/failure/stale result;
- load duration/dimensions/version.

### Process-exit forensics

Log up to five recent `ApplicationExitInfo` records with:

- rank;
- numeric + named reason;
- status;
- importance;
- PSS/RSS;
- age;
- description.

### Fold7 wallpaper/angle compatibility warning

When Shizuku/Fold7 mode is available, settings explicitly warn that Duo wallpaper can displace Samsung Fold interactive and force the temporary angle path onto coarse fallback.

No new sensor authority is introduced.

## Lifecycle / persistence matrix

| Boundary | Pre-Gen12.1 evidence | Gen12.1 automated acceptance |
|---|---|---|
| Immediate import | payload write present, replacement receipt unchecked | atomic commit + metadata receipt |
| Second replacement | unsafe rename replacement | instrumentation performs two replacements |
| Activity/background resume | not specifically exercised in bundle | unchanged UI smoke + persistent version state |
| Default/reset mutation threading | synchronous durable mutation from Compose click | reset dispatched to IO and failures contained |
| In-memory cache loss | not exercised | test explicitly clears wallpaper cache |
| Settings reinitialization / process rehydrate simulation | not exercised | test re-runs `DuoSettings.init` and reloads persisted image |
| Corrupt payload | not exercised | instrumentation corrupts payload and verifies responsive fallback/quarantine |
| Service coexistence | same-process architecture confirmed | existing wallpaper service retained + lifecycle diagnostics |
| Peak resource ownership | redundant decode confirmed by source | imported bitmap reused; pixel budget unit-tested |
| Exact crash reason | missing from supplied bundle | expanded exit-reason instrumentation for next physical reproduction |
| FoldInteractive coexistence | conflict directly visible in field logs | explicit product warning; authority unchanged |
| Physical Fold7 reopen/crash behavior | not exercised after patch | **required physical validation; not an automated pass** |

## Invariants preserved

- Gen12 route-lane resilience remains present.
- Gen10.7 angle authority remains present.
- Gen10.2 secure native fail-open remains present.
- targetSdk remains 35 while compileSdk remains 37.
- no `FLAG_SECURE` bypass.
- no new private-sensor authority.
- no change to Gen4 panel ownership.

## Physical falsification plan

After installing Gen12.1 on the Fold7:

1. choose custom image A;
2. leave/reopen app;
3. choose image B over A;
4. leave/reopen app;
5. choose `Default`, leave/reopen again;
6. activate/deactivate Duo wallpaper mode if intentionally testing wallpaper-only behavior;
7. repeat at least several app opens and fold transitions;
8. export a debug bundle immediately after any freeze/crash or state loss.

Expected new receipts include `wallpaper-store`, `wallpaper-lifecycle`, and multi-ranked `process-exit` events.

If image persistence still fails despite `payload-commit-ok`, the next audit can distinguish disk commit, metadata rehydrate, service load, UI cache, and process-exit cause independently.
