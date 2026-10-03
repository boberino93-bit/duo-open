# Duo Fold Live -> Duo Open Current Gap Audit V2

**Audit date UTC:** 2026-10-03  
**Duo Open current main checked:** `7127c287a17fd97050c98fbeb05a38f7318f2f64`  
**Donor:** `joeconsorti/duo-fold-live`  
**Donor HEAD checked:** `8ca4371bf4c83ea6c840a2d500325e55635245be`  
**Production Git writes performed by this audit:** NO

## 1. Why this audit was reopened

An earlier donor-adoption policy and expanded research directive exist, but their existence does not prove that donor-derived engineering problems were carried through into the current implementation and validated on current `main` / physical Fold7.

This audit therefore distinguishes four states:
- `PROVEN_CURRENT` — implementation/evidence located against current HEAD;
- `DESIGN_ONLY` — current repo/design material references the concept, but current implementation proof is not established;
- `NOT_PROVEN_CURRENT` — current checks did not locate enough evidence; this is **not** a claim of absence;
- `DEFER` — useful donor idea, but no current product requirement justifies work yet.

## 2. Donor lessons that remain relevant

From donor `docs/FUTURE_WORK.md` and `docs/NEXT-PRIORITIES.md`:
- physical-hardware validation is higher priority than abstraction cleanup;
- additional cover/inner app/task scenarios matter;
- smoothing/curve parameters should be tuned from real behavior;
- orientation/reverse-hinge and task-routing edge cases deserve focused tests;
- diagnostics/tooling should be added when a real bug requires it;
- component extraction should wait until reuse justifies it;
- generalized multi-hinge/external-display work is future work, not automatic core scope.

From donor `docs/FIRMWARE-DISPLAY-FINDINGS.md`:
- Android logical display IDs are not authoritative physical-panel selectors;
- `am start --display <id>` demonstrates task routing, not physical panel ownership;
- display placement can change with fold state;
- device-state/display-shell capabilities must be experimentally verified rather than inferred.

These are engineering constraints, not code-copy mandates.

## 3. Current-repo cross-check result

Searches against Duo Open current `main` found design-era references to concepts such as `AnimationModePolicy` / `FrameSmoothing` in vNext material, but current-repo searches performed in this audit did not establish current implementation parity for donor primitives such as:
- `DeviceStateManager`;
- `TaskDisplayRouter`;
- `WindowManager` hinge provider;
- `SurfaceControl`;
- `FoldInteractive`;
- `AngleLayer`.

Therefore those areas are `NOT_PROVEN_CURRENT` unless a subsequent agent locates current implementation/evidence by path and exact HEAD.

Important: a zero search result is not proof the feature is absent. The promotion criterion below requires concrete source/test/field references.

## 4. Bounded donor-derived research lanes

### R-DONOR-01 — Hinge source fallback, freshness, and failover
**State:** NOT_PROVEN_CURRENT  
**Question:** Does current Duo Open obtain sufficiently fresh hinge/posture data with explicit source identity, retry/failover behavior, and stale demotion?

Cheapest decisive work:
1. map every current angle/posture source in current main;
2. identify source timestamp vs receipt timestamp and stale thresholds;
3. exercise source disappearance/recovery and reversal;
4. verify stale precision never remains semantic authority.

Promotion evidence:
- current source paths/classes;
- deterministic/model test for stale/failover behavior;
- Fold7 trace if behavior depends on Samsung exposure.

Stop/defer trigger: if current architecture intentionally uses only coarse public state for semantics and continuous data is purely visual, narrow the lane to visual interpolation/freshness only.

### R-DONOR-02 — Animation smoothing and physical-response tuning
**State:** DESIGN_ONLY / CURRENT IMPLEMENTATION NOT PROVEN  
**Question:** Did donor-style smoothing/curve lessons survive into the current renderer with measured behavior?

Cheapest decisive work:
- locate current smoothing/interpolation path;
- run synthetic slow/fast/reversal/sign-crossing/end-stop traces;
- measure frame pacing and overshoot/settling;
- compare fold and unfold separately rather than assuming symmetric tuning.

Promotion evidence:
- exact implementation path;
- deterministic trace tests;
- measured Fold7 visual/frame evidence where parameter choice is device dependent.

### R-DONOR-03 — Logical display routing vs physical panel ownership
**State:** HIGH PRIORITY / NOT PROVEN CURRENT  
**Question:** Does any current code or reasoning treat logical display/task routing as proof of physical cover/inner ownership?

Cheapest decisive work:
- enumerate logical display IDs across closed/partial/open transitions;
- launch representative system and third-party tasks to candidate displays;
- correlate logical IDs, visible physical panel, power state, and input/focus;
- explicitly falsify any `displayId == physical panel` assumption.

Promotion rule: task-routing observations may inform routing but must not become physical-panel authority without independent evidence.

### R-DONOR-04 — Physical Fold7 scenario matrix
**State:** REQUIRED FIELD RESEARCH  
**Question:** Which donor assumptions/general Android behaviors actually hold on the target Fold7 / current One UI build?

Minimum matrix:
- closed, crack-open, partial, tabletop, near-flat, flat;
- cover-to-inner and inner-to-cover;
- portrait/landscape/reverse orientation where available;
- repeated oscillation/reversal;
- system app vs third-party app launch;
- foreground/background/restart/recovery;
- secure/private surface cases;
- display-ID topology observed at each state.

Output should be a compact evidence table, not a new framework.

### R-DONOR-05 — Orientation and reverse-hinge cases
**State:** NOT PROVEN CURRENT  
**Question:** Are animation direction, geometry, routing, and cancellation correct under rotations and reversed motion?

Cheapest decisive work: extend the existing deterministic trace/scenario test format rather than creating a new orientation subsystem.

### R-DONOR-06 — Diagnostics only for real data gaps
**State:** CONDITIONAL  
**Rule:** Add instrumentation only when an active bug cannot be distinguished with existing evidence.

For each new diagnostic field/tool, record:
- the exact ambiguity it resolves;
- how it will be removed/downgraded if no longer useful;
- whether it adds material write volume.

No speculative telemetry platform.

### R-DONOR-07 — Reusable component extraction
**State:** DEFER BY DEFAULT  
**Rule:** Do not extract a generalized fold state library, multi-device abstraction, or reusable routing framework until at least two real consumers or a concrete maintenance failure justify it.

This lane exists mainly as a guard against premature abstraction.

### R-DONOR-08 — External display / generalized multi-hinge support
**State:** DEFER  
Useful donor future-work direction, but not current Duo Open core unless a target requirement appears. Do not let this broaden Fold7 continuity work.

### R-DONOR-09 — Per-app profiles / gesture shortcuts
**State:** PRODUCT BACKLOG / DEFER UNTIL CORE PASS  
Potential feature value, but only after continuity, panel authority, privacy, first-useful latency, and regression gates are stable.

## 5. Duo-specific extension that should remain separate from donor claims

Prior internal research has stronger Duo-specific requirements that are not established merely by the donor repository. Keep them as independent evidence lanes:

### R-DUO-01 — FoldInteractive / precise-angle handoff fencing
Verify a bounded handoff between source/topology generations with:
- explicit topology generation;
- receipt-time freshness;
- fast stale demotion;
- exact no-op behavior for cross-generation callbacks;
- explicit `geometry unknown` rather than guessed precision;
- no second top-level semantic state owner.

### R-DUO-02 — Physical wake vs logical readiness vs useful pixels
Measure separately:
- panel physical wake;
- logical display/host readiness;
- `FIRST_PRESENTED`;
- `FIRST_USEFUL`;
- `FIRST_INTERACTIVE`.

This is directly relevant to the observed failure where front animation may begin while the inner/main screen has not powered on quickly enough.

### R-DUO-03 — Predictive prewarm without ownership promotion
Test whether hinge kinematics can safely prewarm inner resources earlier while ensuring prediction never becomes physical ownership authority and reversal cancels cleanly.

Required evidence:
- physical-edge-to-first-useful latency before/after;
- false-positive rate/cost;
- cancellation latency;
- stale/timebase fencing;
- power/thermal impact.

## 6. Research ordering

Recommended order based on current user-observed pain and donor lessons:

1. `R-DUO-02` wake/readiness/useful-pixel timeline.
2. `R-DONOR-03` display routing vs physical panel authority.
3. `R-DONOR-01` hinge source/freshness/failover mapping.
4. `R-DUO-01` precise-angle/topology-fenced handoff.
5. `R-DONOR-02` smoothing/tuning against physical traces.
6. `R-DUO-03` predictive prewarm measured against the baseline.
7. `R-DONOR-04/05` broader physical/orientation matrix.
8. Conditional/backlog lanes only after core evidence stabilizes.

This ordering prioritizes the actual latency/power-on problem over protocol or abstraction work.

## 7. Required lane handoff format

Each lane should answer only:
- exact current Git HEAD;
- hypothesis;
- cheapest decisive test performed;
- SOURCE / MODEL / CI / FIELD evidence refs;
- result: CONFIRMED / FALSIFIED / UNKNOWN / PHYSICAL_TEST_REQUIRED;
- current implementation path if found;
- specific integration implication;
- unresolved risk;
- whether any proposed control-plane change passed `ANTI_OVERENGINEERING_GATE_V1`.

Do not create a new subsystem merely to report the lane.

## 8. Bottom line

The donor was partially *learned from*, but current adoption is not proven merely because donor policies/design documents exist. The next round should recover the donor's practical engineering questions as bounded current-HEAD research and physical Fold7 tests, with special emphasis on display-routing semantics, hinge freshness/failover, smoothing, and real hardware scenarios.

The donor's own prioritization also supports simplifying the agent system: validate hardware and solve real bugs before extracting components or building tooling that no measured problem requires.
