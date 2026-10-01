# Duo Open — Whole-Application Gen2 Audit

Baseline: `586c308649258145b3da9b5ea27b726a6fb3647a`
Target: Samsung Galaxy Z Fold7, INNER 1968×2184, COVER 1080×2520
Audit date: 2026-10-01

## Executive finding

The current app is not fundamentally missing a renderer; it is missing one coherent ownership model across the lifetime of a physical fold. The current runtime contains several individually reasonable generations/tokens, but they are not carried end-to-end across the same physical transition:

- `Fold7ContinuityController.generation` owns policy transitions.
- `PanelEngine.captureGen` owns one engine's capture attempts.
- `Fold7CoverPanelLease` owns shell-side cover prewarm/release.
- `Fold7MirrorLeaseArbiter` owns shell-side mirror replacement.
- `DisplayMirrorHost.generation` owns a host's async mirror binding.
- `SnapshotCache` owns only age/geometry, not transition provenance.
- Samsung angle input has session/poll scaffolding in R&D/import files but production still runs the older adaptive feed.
- Transition Lab timestamps many stages but often correlates late callbacks against mutable latest state rather than immutable operation identity.

The Gen2 direction is therefore: **one physical-cycle envelope, separate typed child authorities**. Do not replace all IDs with a single global generation.

## 1. Shared app / Lite / wallpaper path

### Stable and worth preserving
- `DuoApplication`, `MainActivity`, Compose UI and `DuoSettings` are structurally independent of the Fold7 privileged runtime.
- The Lite flavor remains wallpaper-only and should not inherit Shizuku/Fold7 privileged machinery.
- `DuoShader`, wallpaper rendering and user tuning are not the source of the current continuity races.

### Gen2 rule
Keep Fold7 privileged ownership classes in `src/full`. Shared rendering/settings stay shared unless a measured visual requirement demands otherwise.

## 2. Hinge ingress

### Current strengths
- `HingeAngleSource` rejects implausible/non-angle vendor sensors.
- Samsung continuous angle can override the coarse public sensor.
- Public midpoint callbacks are suppressed after a continuous endpoint.
- Endpoint bridge exists for Samsung feed gaps.
- A pure `Fold7AnglePipelineGen2` model and tests already exist.

### Current weakness
Production `WallpaperAngleFeed` still schedules adaptive wallpaper commands independently of an explicit per-poll ownership pipeline. `ShizukuBridge` and the shell reader already carry optional poll sequence support, but active production does not consume it end-to-end.

### Gen2 direction
- one reader session;
- one poll in flight;
- exact poll sequence in wallpaper action -> shell parse -> Binder callback;
- completion-paced scheduling;
- latest-only delivery toward main/render thread;
- stale session/poll callbacks inert.

## 3. Transition policy

### Current strengths
`Fold7ContinuityController` has an explicit asymmetric state machine with reversal handling:
- OPEN_INNER
- CLOSING_INTENT
- COVER_PREWARMING
- COVER_READY_HIDDEN
- COVER_VISUAL
- NATIVE_COVER
- OPENING_FROM_CLOSED
- INNER_HANDOFF

Established Fold7 calibration should remain unchanged absent device evidence:
- inner wake 3°
- inner handoff 8°
- cover prewarm 174°
- cover visual 135°
- visual hide 140°
- open latch / rearm 172° / 166°

### Current weakness
`generation` increments on every state transition. It is correct for policy action freshness but cannot also represent an entire close-cycle provenance identity.

### Gen2 direction
Add a separate stable close-cycle envelope that begins once deliberate closing is accepted and remains stable through prewarm/readiness/visual. Invalidate on reversal, Samsung native takeover, service destruction/restart.

## 4. Cover power / privileged ownership

### Current strengths
- stable physical display geometry is used to identify Fold7 panels;
- logical display IDs are re-resolved and revalidated;
- raw physical OFF is not used;
- mutation executors serialize shell-side cover and mirror work;
- `Fold7CoverPanelLease` already uses leaseId + epoch internally.

### Current weakness
The app-facing `COVER_PANEL_LEASE_V2` protocol primarily carries `ownerGeneration`. App-side state can therefore accept a later Bundle without an explicit shell-process session/revision gate. Reconnect/restart authority is not represented as a complete immutable token.

### Gen2 direction
Versioned V3 snapshot identity:
`connectionEpoch + shellSession + shellRevision + leaseId + leaseEpoch + ownerGeneration + physicalDisplayId`.

App accepts only monotonic snapshots from the current connection/session. Ensure/release require the exact accepted token.

## 5. Cover readiness

### Current weakness
A successful prewarm currently transitions the controller to `COVER_READY_HIDDEN`, even though shell mutation completion and app-visible destination readiness are different facts. Display callbacks are also routed through a resettable 24 ms debounce, and route reassert uses a fixed 32 ms delayed mirror sync.

### Gen2 direction
Create a readiness owner that consumes:
- current close cycle;
- exact accepted cover lease token;
- shell route-ready observation;
- current app DisplayManager topology.

Split DisplayManager ingress into:
1. immediate cheap continuity/readiness observation;
2. existing 24 ms debounced heavy engine synchronization.

Do not use a fixed success timer as readiness proof.

## 6. Capture / frame provenance

### Current strengths
- per-engine `captureGen` prevents many late screenshot callbacks from mutating a newer local phase;
- Fold7 deterministic frozen-frame mode suppresses live recapture;
- generic SnapshotCache gives useful visual bridging on other paths.

### Current weakness
The continuity host asks for any inner `SnapshotCache` entry with matching geometry and age <=10 seconds. It cannot prove that the bitmap belongs to the current deliberate close cycle. A failed current-cycle capture can therefore leave a prior-cycle frame eligible.

### Gen2 direction
Keep `SnapshotCache` for generic PanelEngine bridge behavior. Add a separate continuity-specific frame store with:
`serviceEpoch + closeCycleId + captureSequence + contentLeaseId + source + request/capture/completion timing`.

Accessibility screenshots should preserve the framework screenshot timestamp. Shizuku captures without an exact capture timestamp are request-bounded and must have begun after cycle start.

## 7. Mirror / rendering / presentation

### Current strengths
- canonical geometry is explicit;
- live mirror uses `applyTransactionOnDraw`;
- SurfaceControl transactions are instrumented by Transition Lab;
- mirror shell singleton has explicit session/sequence/lease arbitration.

### Current weakness
Frozen-frame binding reports success after `VISIBLE + invalidate()` without immutable draw/frame-commit/present identity. Live-mirror transaction callbacks also lack the full physical-cycle/content attempt identity.

### Gen2 direction
Add exact presentation identity:
`serviceEpoch + closeCycleId + contentLeaseId + hostEpoch + attemptSequence + renderPath`.

Frozen path: record exact content draw, View frame commit, and an identity-bearing transaction marker applied on draw. Live mirror: stamp geometry transaction instrumentation with the same immutable presentation attempt.

Initial Gen2 behavior remains observation-first: do not block visibility on telemetry callbacks.

## 8. Service lifecycle

### Current strengths
- foreground service keeps continuity runtime alive;
- accessibility destruction invalidates capture generation and releases surfaces;
- Shizuku daemon/session cleanup exists.

### Current weakness
Service, Shizuku connection, shell process, close cycle and host lifetimes are not represented in one correlation envelope.

### Gen2 direction
Every asynchronous child owner must be invalidated at its actual lifetime boundary. A service restart must make old frame/presentation identities impossible to accept even when wall-clock freshness would otherwise pass.

## 9. Diagnostics / Transition Lab

### Current strengths
Transition Lab is already a first-class architecture component and has frame/surface timing probes.

### Gen2 direction
Extend rather than replace it. Record immutable identity fields and rejection reasons:
- serviceEpoch
- closeCycleId
- angleSession / pollSequence / sampleSequence
- shellSession / shellRevision / leaseId / leaseEpoch
- contentLeaseId / captureSequence
- hostEpoch / presentationAttemptSequence / renderPath
- staleAtCallback / rejectionReason

Never use `latestHingeSample` or another mutable latest value as ownership; it is correlation only.

## 10. Build / workflow

The checked-in workflow still contains historical 1.3.25 source assertions while the app is 1.3.29. Gen2 should update workflow version assertions and validate the new owners/tests directly.

## Gen2 architectural invariant

A callback is allowed to mutate visible Fold7 continuity state only when the exact owner for that callback still recognizes its immutable identity. Timing alone is never ownership when an explicit token can exist.
