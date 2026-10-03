# Primary Review of Manager-Organized Research — 2026-10-03

Baseline audited main: `7127c287a17fd97050c98fbeb05a38f7318f2f64`  
Round: `round-20261003T064442Z-gen7-p0-expanded-r2`

## Primary disposition from the organized round

### Integrate next as one bounded P0 runtime candidate (not included as Android source changes in this process-delta ZIP)
- **02 — INNER wake causal chain:** source-confirmed async lifetime race. A valid opening wake can be queued under controller generation G, ordinary handoff advances to G+1, and the delayed worker can self-cancel before Binder wake. Required identity is `(serviceEpoch, openingAttemptSequence)`, not transient controller generation.
- **03 — presentation readiness cold race:** add exact-current same-attempt evidence through physical wake -> logical route -> FIRST_PRESENTED -> FIRST_USEFUL -> FIRST_INTERACTIVE. Physical wake success is not useful-pixel success.
- **04 — terminal cover-route fencing:** mandatory addendum. True terminal/native-cover/supersession authority must revoke or fence stale wake/route/mirror work exactly; eventual return to native cover is insufficient.
- **Manager disposition:** READY_FOR_PRIMARY runtime candidate, but CI and physical Fold7 attempt-correlated validation remain hard acceptance gates.

### Preserve but do not implement independently yet
- **05 — 120 Hz:** model target is sound, current implementation proof absent. Keep refresh lease strictly orthogonal to wake/readiness/panel authority. Do not let request success mean actual 120 Hz delivery.
- **09 — predictive prewarm:** useful follow-on optimization only after correctness. Prediction may prepare resources but never grant panel ownership or semantic hinge authority.

### Research complete but still physical-evidence gated
- **06 — hinge telemetry / micro-gestures:** current evidence supports ~111–112 accepted samples/s when Samsung precise telemetry is available, but topology blackout/timeout exists; no production micro-gesture threshold is justified without the physical measurement matrix.
- **07 — dual-panel / secondary input:** Manager observer disposition is `READY_FOR_PRIMARY_PHYSICAL_EXPERIMENT_PLAN_ONLY / DEFER_RUNTIME_ADOPTION`. Public Android primitives exist, but Samsung concurrent inner+cover publication/power/composition/input is not proven. Historical device evidence does prove a temporary dual-active *cover-secondary* bridge window; the inverse (cover default + early INNER secondary) remains the decisive P0 experiment.
- **08 — universal Flex Deck:** Manager observer disposition is `READY_FOR_PRIMARY_ISOLATED_PROTOTYPE_PLAN / DEFER_UNIVERSAL_FLEX_REPLACEMENT`. Bounded companion controls are plausible; universal native-like replacement is unproven and can duplicate Samsung Flex Mode. Keep any prototype isolated; no automatic Shizuku/raw-input escalation.

### Process/control-plane
- **10 — AgentBus write pressure:** unlike speculative protocol growth, this lane has witnessed failures (durable write pressure and live claim collisions) plus manager-revalidated models. It can pass `ANTI_OVERENGINEERING_GATE_V1` in principle, but activation still requires implementation/compatibility/claim-fence/discovery/integrity regression gates. Do not mix it into the P0 Android runtime correction.
- **11 — independent INNER peer check:** Manager observer disposition is `CORROBORATED_SUBSUMED_IN_P0_DOSSIER_WITH_IDENTITY_CORRECTION`. It corroborates the generation race and corrects identity semantics: `presentationAttemptSequence` is not a stable per-opening semantic key. Supports a new opening-attempt identity.

## Newly reconciled historical field evidence
A 2026-09-30 Fold7 trace demonstrated a temporary dual-active window while INNER remained default and cover was enabled as a secondary route. Both internal physical display devices reported ON and both internal viewports active. This is useful evidence that a bounded secondary bridge may be feasible, but it is not proof of simultaneous visible pixels and does not prove the inverse operation required for early INNER activation on opening.

## Integration order
1. Implement attempt-scoped wake lifetime and one-shot `WAKE_COMMITTED`.
2. Add exact-current readiness/presentation ledger and bounded opening prelude/bridge gating.
3. Add terminal/native-cover exact-no-op fences from ticket04.
4. Run CI/model/regression matrix, preserving smooth closing and 30–70° oscillation coverage.
5. Run physical Fold7 attempt-correlated timing from opening edge through FIRST_INTERACTIVE.
6. If residual delay remains, run the gated post-correctness early-INNER secondary-bridge experiment: Stage 0 read-only enumeration under the exact opening key; Stage 1 only if a 1968x2184 route exists early enough, retaining COVER default/task/input ownership and requiring external-camera visible-pixel proof. Rebind by physical identity after every topology mutation; never trust numeric display IDs.
7. Only after correctness, evaluate dedicated low-jitter wake executor, predictive prewarm and refresh/cadence optimization.

## Not promoted
Tickets 06/07/08 are not runtime-ready from research alone. Missing physical evidence should result in experiments, not new generalized infrastructure.
