# Duo Open Gen12 — Engineering / Swarm Decision Log

## Candidate identity

- Version: `5.6.0-gen12-route-lane-resilience-zfold7`
- Version code: `56`
- Baseline: Gen11 `5b43c181faa1a89ee7ee7c0848612033a1545372`
- Target device: Samsung Galaxy Z Fold7 (`SM-F966W`)
- Target runtime: One UI 9 / Android 17 (API 37)

## Physical evidence input

Source field bundle: `duoopen-debug-1791432567831.zip`

The bundle was exported from Gen11 (`5.5.0-gen11-product-ui-zfold7`, code 55) on physical `SM-F966W`, API 37.

Five closing cycles were reconstructed from the diagnostics:

- 4/5 reached the cover visual path.
- 1/5 never reached `COVER_READY_HIDDEN` or `COVER_VISUAL`.
- In that failed close, the hinge began at approximately 175 degrees and progressed to approximately 62 degrees before the initial privileged cover operation returned.
- The corresponding cover-presentation RPC reported approximately 1046 ms.
- Gen4 still reported `PREWARM_IN_FLIGHT`, `routeReady=false` when that delayed operation returned.
- The exact-cycle frame prime had already completed in roughly 69 ms, so capture was not the limiting operation in this cycle.
- Gen10.4 latest-value-wins coalescing was active and replaced eight pending presentation updates; queue growth therefore was not the principal remaining failure.

### Engineering interpretation

The physical evidence supports a narrower bottleneck than earlier generations:

1. Gen10.4 already prevents unbounded presentation-RPC backlog.
2. A single One UI 9 privileged display operation can still occupy the display mutation path for about one second.
3. The service currently starts Gen4 route bootstrap and also allows presentation/brightness traffic to enter the privileged path during `COVER_PREWARMING`.
4. Presentation/brightness cannot produce useful visible output while the cover route is still hidden/not ready.

The next A/B should therefore remove that avoidable contention before considering more invasive mechanisms such as holding the cover powered while the phone is fully open.

## Swarm reconciliation

The research/data-collection swarm was treated as advisory evidence and reconciled against the current Gen11 source rather than applied blindly.

### Findings retained

- Keep Samsung/FoldInteractive precise geometry as the current production authority/fallback transport. The private direct-sensor path is not yet physically proven superior under Shizuku shell identity.
- Keep physical panel power, logical route, and visual/presentation readiness as separate milestones.
- Do not interpret inner physical wake success as proof that useful native pixels are on glass.
- Preserve Gen3/Gen10 lease fencing and secure-content native fail-open.
- For opening readiness, the current research recommendation is a read-only WindowManager/SurfaceFlinger metadata shadow probe before changing release authority.

### Findings already present in Gen11 and therefore NOT reimplemented

Older renderer research recommended:

- `DuoShader.MAX_TILT = 60f` to match the AGSL domain;
- explicit `BitmapShader.FILTER_MODE_LINEAR` for RuntimeShader content.

Current Gen11 source already contains both corrections. Gen12 verifies they remain present but does not claim them as new work.

### Findings deliberately deferred

- No direct private-sensor replacement of FoldInteractive.
- No always-on/fully-open cover pre-power strategy.
- No new SurfaceControl ownership architecture.
- No live blur / recapture expansion.
- No opening `FIRST_USEFUL` authority change. The research lane explicitly requires a shadow metadata experiment first.

## Gen12 implementation

Gen12 adds a two-stage presentation gate:

1. **Bootstrap gate** — while closing is in `CLOSING_INTENT` / `COVER_PREWARMING`, retain only the latest cover presentation intent in-process. No cover presentation RPC is emitted from that deferred intent.
2. **Existing Gen10.4 RPC gate** — after the continuity state reaches `COVER_READY_HIDDEN` or `COVER_VISUAL`, release only the latest retained request into the already validated single-flight latest-value-wins RPC gate.

A deferred closing intent is invalidated rather than replayed when:

- direction reverses;
- Shizuku/privileged authority is lost;
- continuity leaves the eligible closing path;
- the defer window exceeds 1500 ms;
- service teardown occurs.

New field markers:

- `gen12-route-lane presentation deferred ...`
- `gen12-route-lane deferred presentation released ...`
- `gen12-route-lane deferred presentation dropped ...`
- `gen12-route-lane deferred presentation invalidated ...`

## Why the change is bounded

Gen12 does **not**:

- modify Gen4 panel ownership;
- claim route readiness from a timer;
- add another Shizuku cover-presentation RPC source;
- modify the hinge authority;
- bypass `FLAG_SECURE`;
- change the Gen11 product UI;
- change Android manifests;
- change target SDK policy;
- change the renderer.

It changes only when an already-existing closing presentation/brightness intent is allowed to enter the privileged display mutation path.

## Automated validation contract

The Gen12 workflow reconstructs the exact Gen11 predecessor in both candidate and comparison worktrees before applying Gen12.

Protected comparison requires:

- Gen11 product UI parity;
- all `app/src/full/java` runtime code except `FoldOverlayService.kt` to remain hash-identical;
- all main runtime code except the new pure bootstrap gate to remain hash-identical;
- main/full manifests identical;
- resources identical;
- secure fail-open marker retained;
- Gen10.7 angle-authority marker retained;
- existing 60-degree renderer domain retained;
- existing explicit linear bitmap filtering retained.

Build gates:

- Gen12 self-verifier;
- pure bootstrap-gate unit tests;
- full `testFullDebugUnitTest`;
- API-37 `lintFullDebug`;
- `assembleFullDebug`;
- API-35 emulator `connectedFullDebugAndroidTest` for the unchanged Gen11 product shell.

## Physical validation boundary

Automated success does not prove the route-lane hypothesis on Fold7 hardware.

Until a Gen12 debug bundle is captured from the physical Fold7, status must remain:

`BUILD-VERIFIED / EMULATOR-UI-SMOKE-VERIFIED / PHYSICAL-FOLD7-UNVALIDATED`

## Physical falsification plan

The next physical bundle should be evaluated against the Gen11 baseline above.

For at least several full close/open cycles, measure:

- close START -> `COVER_READY_HIDDEN`;
- START -> `COVER_VISUAL`;
- visual -> Gen3 frame commit;
- visual -> presentation commit;
- Gen4 prewarm latency;
- every `cover-presentation rpcMs`;
- every `gen12-route-lane` defer/release/drop marker;
- whether any cover-presentation RPC is emitted before route bootstrap exits prewarm;
- whether a close again reaches native cover without ever reaching cover visual.

### Interpretation

If the former ~1 s outlier disappears or route readiness moves materially earlier while presentation RPCs remain deferred, the contention hypothesis gains physical support.

If Gen4 prewarm still takes approximately one second with no competing presentation RPC, the candidate has falsified the contention hypothesis: the latency is inside Samsung's route/panel operation itself. The next architecture decision should then target earlier safe route preparation or a different Samsung ownership primitive, not more client-side queue tuning.

Opening behavior is intentionally unchanged in Gen12. Opening evidence should continue to be collected, while the swarm's proposed native-presentation metadata receipt remains a separate shadow-probe experiment rather than production authority.
