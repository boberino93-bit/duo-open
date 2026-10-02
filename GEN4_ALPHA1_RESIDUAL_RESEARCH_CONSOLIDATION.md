# Duo Open — Gen4 Alpha1 Residual Research Consolidation

**Production baseline reviewed:** `f9ba2ca7afa2e67586231770fd8b0abe56b94b5b`  
**Runtime:** `4.0.0-alpha1-zfold7` / versionCode 41  
**Target:** Samsung Galaxy Z Fold7, Android 16 / One UI

## Purpose

This document consolidates the research work that is **not included in Gen4 Alpha1** after comparing:

1. the green Gen4 Alpha1 production source,
2. the accumulated AgentBus / Artifactory-style message-board handoffs,
3. Manager / reviewer dispositions and peer checks,
4. current-main source paths after the Gen4 panel-authority landing.

The goal is to prevent already-completed research from being rediscovered and to make the next engineering generation start from a clean, evidence-ranked backlog.

---

# 1. What Gen4 Alpha1 already absorbed

These research lanes should **not** be reopened as fresh architecture work unless Fold7 device evidence disproves the implementation.

### Daemon-owned cover-panel authority
Gen4 now places privileged cover prepare/hold/release/reconcile ownership in the shell daemon and uses `shellSession + serviceEpoch + intentSequence` rather than app-local logical display identity as panel authority.

### New-daemon startup reconciliation
The old R&D finding that a fresh `DuoShellService` could start with a clean in-memory lease while prior display mutation survived process death was incorporated into Gen4 startup recovery. This directly addresses the Manager-reviewed daemon-restart/orphan-route candidate.

### App-process / daemon-lifetime admission
A new app/service lifetime must establish Gen4 daemon admission before continuity rendering arms. Old panel authority is not inherited merely because a logical cover route exists.

### Binder-ready / authority-ready distinction
Continuity no longer treats a superficial Shizuku state transition alone as sufficient panel authority.

### Bounded panel recovery/reassert
Route publication and release cleanup now have bounded, self-driving retry paths rather than relying entirely on a later display callback.

### Alpha4 recovery-gate work
The staged Alpha4 process-recovery implementation was never promoted. Its same-service transitional-state precedence defect is therefore **superseded**, not a current Gen4 bug to patch.

---

# 2. Manager-board findings that remain absent from Gen4

## P0/P1 — Ordered hinge-ingress overflow semantic resynchronization

**Manager status:** current-source claim corroborated.  
**Production status:** not implemented in Gen4 Alpha1.

Manager review identified that overflow recovery still derives its semantic restart from mutable global `hinge.lastAngle` rather than the immutable retained endpoint/time from the overflowed drain. The current Gen4 `FoldOverlayService.drainHingeIngress()` still:

- calls `continuity.release("hinge-ingress-overflow")`,
- conditionally calls `continuity.arm()`,
- then reads `hinge.lastAngle`,
- and feeds that mutable value into visual/device/engine recovery.

That means a newer producer sample can become the resync baseline after an older batch overflowed.

**Recommended contract from R&D:**
- separate semantic resync from privileged/render arming;
- reset from `drain.samples.last()` and its `observedUptimeMs`;
- direction becomes `STEADY`;
- do not synthesize/replay missing history;
- work even when Shizuku is unavailable;
- test a newer next-drain sample racing the overflow recovery.

**Why it matters:** this is a correctness issue in the loss-recovery path, not normal ordered ingress.

---

## P0/P1 — Asynchronous WakeInner semantic lifetime

**Evidence:** SRC + deterministic tests + peer corroboration, 98% confidence in the source-level race.  
**Production status:** not implemented.

Current Gen4 still calls:

`wakeInner(action.generation)`

and the IO worker still rechecks:

`controller.isGenerationCurrent(generation)`

before the physical wake.

Normal opening progression legitimately advances controller generation from `OPENING_FROM_CLOSED` to `INNER_HANDOFF`, so the same opening attempt can invalidate its still-needed wake before the IO worker starts. The opposite schedule can let a wake reach the shell before a reversal is consumed.

**R&D contract:**
- add semantic `openingAttemptId` / wake-intent identity;
- lifetime spans normal opening progression;
- revoke only on genuine reversal, reset/release, privilege loss, destroy, superseding opening, or confirmed inner-active;
- atomic one-shot commit immediately before the shell wake;
- for already-buffered samples, consume the drain before scheduling the wake so a known same-batch reversal can cancel it.

**Validation already completed in R&D:**
- schedule model: 8/8
- batch planner: 11/11
- semantic wake lifecycle: 13/13
- peer wake model: 9/9

This is directly relevant to opening responsiveness.

---

## P1 — Diagnostic export completeness contract

**Manager status:** corroborated by source.  
**Later peer status:** independently corroborated by multiple reviewers.  
**Production status:** completely unchanged from the reviewed Alpha3 blobs.

The following current Gen4 source blobs are byte-identical to the prior reviewed versions:

- `TransitionSessionWriter.kt`
- `TransitionLab.kt`
- `OverlayFeature.kt`
- `DuoApp.kt`
- `DebugBundleExporter.kt`
- `DebugBundleUploader.kt`

The important finding is stronger than "flush can fail":

- `record()` can drop events before a later successful flush;
- `flush()==true` therefore does **not** prove zero event loss;
- UI export/send paths discard the Boolean flush result;
- exported metadata has no machine-readable flush/drop/count/sequence completeness receipt;
- upload SHA proves exact ZIP transport bytes, not telemetry completeness.

**Recommended Gen2 contract:**
- session-scoped `WriterExportReceipt`;
- explicit `TelemetryCompleteness` state;
- fields such as flush result, dropped events, accepted/written counts, last accepted/written sequence;
- versioned bundle manifest;
- degraded evidence remains uploadable;
- ZIP SHA remains a separate transport-integrity axis.

This should land before treating device traces as definitive evidence for subtle Fold7 timing bugs.

---

# 3. High-confidence R&D sent to Manager/reviewer but still absent

## P1 — Live mirror STOP / restart lifecycle

Current Gen4 `DisplayMirrorHost` still contains the one-way:

`@Volatile private var shellStopRequested = false`

and `requestShellStop()` immediately returns after the first request.

The R&D reproduced:

1. `START -> STOP -> START -> DETACH` can suppress cleanup for the later start;
2. a failed STOP can permanently suppress retry.

Validation:
- Python: 6/6
- Kotlin: 9/9 assertions
- finding confidence: 98%

**Recommended correction:** generation-/attempt-aware STOP ownership instead of a process-lifetime Boolean latch.

**Strategic note:** if the single transferable accessibility SurfaceControl architecture is adopted, the entire privileged live-mirror stack may be deleted instead of repaired. Avoid spending heavily on a subsystem likely to be removed.

---

## P1 — Public hinge-source liveness and equal-resolution selection

Current Gen4 `HingeAngleSource.choose()` still:

1. ranks candidates by resolution and standard-vs-vendor preference,
2. but only changes source when `best.resolution < current.resolution`.

That means the computed equal-resolution standard-sensor preference cannot actually cause a switch.

It also has no relative liveness demotion for a finer public candidate that stops producing events. A live lower-resolution fallback can therefore be ignored indefinitely.

R&D validation:
- current-selector model: 6/6 plus 100/100 fallback events rejected
- equal-resolution model: PASS
- Kotlin prototype: 5/5

**Important R&D warning:** do **not** add a blind wall-clock expiry. ON_CHANGE sensors can legitimately remain silent while the hinge is stationary.

**Recommended contract:**
- relative event-driven source liveness;
- switch on equal-resolution preference where appropriate;
- tune the liveness budget from Fold7 field traces (p99 / p99.9 event skew/dropout).

---

## P1/P2 — Foreground-runtime controller liveness truth

`PersistentRuntimeService` is still `START_STICKY` and unconditionally publishes the notification text:

- "Duo Open is ready"
- "Fold7 continuity controller is running."

But the real transition controller is owned by `FoldOverlayService`, which can be destroyed independently.

R&D model: 11/11 PASS.

**Recommended contract:**
- epoch-owned runtime state keyed by `FoldOverlayService.serviceEpoch`;
- READY only while the current controller epoch is attached;
- foreground service with accessibility enabled but no owner = RECOVERING;
- accessibility disabled = STOPPED / self-stop;
- stale detach from an old epoch must not downgrade a newer controller;
- diagnostics should include state + ownerEpoch + reason.

This is mostly lifecycle truth/observability, but becomes important when diagnosing "service says ready but fold effect is not running."

---

# 4. Presentation and handoff research not included

## P0/P1 — Opening terminal inner readiness

Current continuity still classifies an active display broadly as:

`display.state != OFF && display.state != UNKNOWN`

and terminal opening logic can release the visual based on angle/topology without proof that current inner content has presented.

R&D conclusion:

**power != logical route != composition != useful current pixels**

The inner capture code already contains black-frame retry behavior, which itself proves panel activation and usable pixels are separate events.

**Proposed contract:**
a terminal release receipt fenced by:
- service epoch,
- opening cycle / movement id,
- visual attempt sequence,
- inner route/topology epoch,
- readiness sequence,
- current content evidence.

Preferred source of proof: current-generation inner capture/presentation evidence. Black/secure failures remain ambiguous, not success.

Model:
- 16/16 deterministic/adversarial
- 100,000-event fixed-seed stream

---

## P0/P1 — Terminal native cover landing

Gen4 improved who owns the cover route, but does **not** add a presentation-proven Samsung/native landing handshake.

Research found that native cover topology is only **admission** to terminal handoff. It does not prove Samsung Launcher/SystemUI has produced a fresh destination buffer beneath the Duo visual.

**Proposed contract:**
- keep the exact final Duo visual alive in a `NATIVE_PENDING` stage;
- require exact presentation barriers on the current host/attempt;
- submit final fade-to-native;
- only cleanly release after the exact fade transaction is presented;
- reversal/topology loss/new cycle/host remap/service rollover invalidates old terminal receipts;
- watchdog exit is explicitly degraded timeout, never "proof of readiness."

Important limitation: our transaction-present callback proves our compositor transaction landed; it does not prove semantic freshness of Samsung's content. Native-content freshness remains a complementary signal.

Model:
- 11/11
- 100,000-event deterministic stream

---

## P1 — One transferable accessibility SurfaceControl host

Research Agent 05 recommended reducing presentation ownership to:

**one deterministic frozen frame + existing AGSL optics + one SurfaceControl host + Samsung steady-state handoff**

API34 `attachAccessibilityOverlayToDisplay(displayId, SurfaceControl)` can attach/transfer an accessibility SurfaceControl between displays. API35 transaction-completion evidence can provide compositor presentation receipts.

If Fold7 testing proves transfer/remap correctness, this architecture can eliminate:
- `DisplayMirrorHost` runtime mirror ownership,
- shell mirrorDisplay/liveMirror session APIs,
- `Fold7MirrorLeaseArbiter`,
- duplicate WindowManager glass ownership,
- hidden ViewRoot SurfaceControl reflection,
- older live/window mirror machinery.

**Topology constraint:** every transfer must resolve current role -> logical ID under an immutable topology snapshot/epoch. A logical display ID is never physical panel identity.

Fallback if one transferable host fails: two pre-created direct hosts with exactly one semantic owner.

---

# 5. Rendering / timing research still device-gated

## P1/P2 — Presentation-time visual phase compensation

Current precise Samsung path still feeds the latest target through `TiltFollower`, with `SAMSUNG_LIVE_TAU_S = 0.028f`. There is no expected-presentation-time predictor in production.

R&D host model tested a conservative prediction candidate:
- ~20 ms compensation
- ~36 ms horizon
- modeled mean angular MAE improved from 5.626° to 2.223° in a 1,260-case synthetic matrix
- 0/1260 worse case-average MAE
- 0/1260 worse frame-P95
- 3/1260 abrupt 60 Hz reversal cases had slightly worse single-frame maximum, worst +0.428°

This is **not production-ready** without physical Fold7 timing.

**Next step:** FrameTimeline/Perfetto A/B using expected presentation timing. Keep the current 28 ms smoothing constant for the first comparison.

---

## Presentation metrics / inner prewake

Research Agent 04 emphasized that `WAKE_INNER_DISPLAY` completion only proves the physical power command returned. It does not prove:
- logical STATE_ON,
- composition,
- current useful frame,
- actual presentation.

Use separate timestamps for:

semantic edge -> app scheduling -> shell -> physical wake -> logical route/state -> composition -> first useful present

Primary KPI should be **first useful inner present**.

A/B:
- DeviceState early-edge prewake
- precise 3°-only wake
- no explicit prewake

across slow / normal / fast opening and early reversal.

If prewake does not materially advance first useful presentation or causes ownership/power complexity, delete it.

---

# 6. Signal hierarchy research still relevant

The research consensus remains:

1. one verified continuous source owns physical hinge geometry;
2. DeviceStateManager is transition-edge infrastructure only;
3. DisplayManager owns logical route lifecycle only;
4. display state is a guard, not proof of presentation;
5. PowerManager interactive state is global work/power gating only;
6. public hinge sensors are fallback/corroboration;
7. FoldingFeature/WindowInfoTracker are window geometry/posture, not physical-angle authority.

Direct private Samsung sensor work remains unproven as a production replacement. Historical sensor IDs are probe leads, not contracts.

Do not restore persistent all-display FoldInteractive wallpaper anchors; prior Duo field evidence associated that architecture with cover black flashes.

---

# 7. Renderer research disposition

The old renderer finding that the visual domain should use a **60° MAX_TILT** has already been incorporated into current source (`DuoShader.MAX_TILT = 60f`), so that specific item should not be carried as unresolved work.

Other deeper renderer optimizations remain measurement-only:
- GPU tap-count reduction,
- half/full-resolution onset crossfade,
- zero-copy capture/HardwareBuffer paths.

Do not introduce them before the Fold7 correctness/latency evidence above.

---

# 8. Recommended post-Gen4 sequencing

## First: device validation of the Gen4 authority build
Before more architecture lands:
- normal slow open/close
- fast open/close
- reversal
- app-process kill
- Duo Shizuku user-service kill/restart
- cold start on native cover
- cold start on inner
- 30+ transition endurance sequence

This validates the layer Gen4 actually changed.

## Second: make the evidence pipeline trustworthy
Implement diagnostic export completeness receipts before relying heavily on subtle timing bundles.

## Third: fix transition correctness races
Recommended order:
1. semantic WakeInner attempt lifetime
2. overflow semantic resync from retained drain endpoint/time
3. public-source relative liveness / equal-resolution switching

## Fourth: close presentation truth
1. opening first-current-frame readiness
2. terminal native-cover landing
3. service-stable presentation host

## Fifth: simplify ownership
Prototype the single transferable accessibility SurfaceControl. If valid, delete the old mirror stack and avoid separately investing in mirror lifecycle fixes that become obsolete.

## Sixth: tune perceptual performance
Only after presentation evidence is trustworthy:
- presentation-time hinge prediction
- renderer/GPU optimization
- exact prewake timing

---

# 9. Manager-board interpretation

The Manager messages were conservative in a useful way:

- they repeatedly **corroborated source-level defects without calling them production-ready**;
- they separated source proof from physical Fold7 incidence;
- they demanded independent peer evidence for high-materiality findings;
- diagnostic export integrity later received that independent corroboration;
- daemon restart was specifically marked with a physical-device boundary, and Gen4 now implements the architectural recovery direction;
- overflow recovery remained corroborated but not promoted;
- several later R&D handoffs (mirror lifecycle, public source liveness, foreground runtime liveness, async wake lifetime) were routed to Manager/reviewer with no production writes.

The common theme is consistent: **the remaining work is no longer "find another way to own the panel." It is prove the right frame, preserve semantic intent across async boundaries, recover deterministically from lost samples, and make field evidence trustworthy.**

---

# 10. Do-not-regress list

Carry these forward unchanged:

- logical display IDs are observations, never physical identity;
- real app task remains on default display;
- no raw physical OFF;
- Samsung/native owns terminal steady state;
- opening and closing are asymmetric;
- reversal is first-class;
- exact async fencing;
- deterministic frozen frames;
- right crop remains `Rect(984,0,1920,2184)`;
- requested != host-bound != drawn != committed != presented != native-fresh;
- no WindowArea / DualScreen dependency;
- preserve proven hinge thresholds unless device evidence justifies change;
- do not restore persistent all-panel wallpaper anchors;
- do not conflate transport SHA with telemetry completeness.

---

# 11. Bottom line

Gen4 Alpha1 closes the largest ownership/lifecycle hole discovered during the last research round: **who owns cover-panel mutation across app and daemon lifetimes**.

The highest-value research that remains outside the build is now concentrated in five areas:

1. semantic lifetime of asynchronous physical actions (`WakeInner`);
2. overflow/loss semantic resynchronization;
3. presentation-readiness / terminal handoff proof;
4. hinge fallback-source liveness;
5. diagnostic evidence completeness.

The longer-term architectural simplification remains the single accessibility SurfaceControl presentation host. If that works on the Fold7, it can delete a substantial amount of mirror/window ownership code rather than continuing to patch it.

This consolidation intentionally excludes findings already absorbed by Gen4 Alpha1 or superseded by the Gen4 authority redesign.
