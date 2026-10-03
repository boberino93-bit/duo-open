# Duo Fold Live Gap Audit V2 — Live Board Reconciliation Delta

**UTC:** 2026-10-03T07:58Z  
**Base audit:** `DUO_FOLD_LIVE_CURRENT_GAP_AUDIT_V2.md`  
**Current Duo Open HEAD:** `7127c287a17fd97050c98fbeb05a38f7318f2f64`

This is a narrow delta, not a replacement audit. It reconciles material research that arrived on AgentBus after the base audit was drafted.

## 1. R-DUO-02 is no longer merely an open measurement lane

Fresh current-main research reports a **source-confirmed intermittent opening race**:
- accepted opening emits `WakeInner` under controller generation G;
- privileged wake work is queued asynchronously;
- cover opening visuals can start immediately without waiting for wake worker start, physical wake, logical INNER activation, or first useful presentation;
- state can advance to `INNER_HANDOFF`, incrementing controller generation to G+1;
- if the queued wake worker then re-checks generation G, it can reject the still-valid opening wake as stale before issuing the privileged wake.

This matches the observed symptom: cover/front animation begins while INNER remains dark.

The stronger current fix direction is therefore attempt-scoped wake lifetime (`openingAttemptId`/sequence) rather than transient controller generation, plus a same-attempt `WAKE_COMMITTED` milestone and stronger readiness/presentation fencing before substantial bridge/final handoff.

Physical wake, logical activation, `FIRST_PRESENTED`, `FIRST_USEFUL`, and `FIRST_INTERACTIVE` remain distinct evidence stages.

**Audit state update:** `R-DUO-02 = SOURCE_CONFIRMED_DEFECT / IMPLEMENTATION+FIELD_VALIDATION REQUIRED`.

## 2. R-DONOR-03 / R-DONOR-04 are reinforced by current research

Fresh dual-panel/input research confirms public Android primitives can target suitable logical displays, but does **not** establish that Samsung concurrently publishes, powers, composites, or routes touch for both Fold7 internal panels.

This reinforces the donor rule that logical display/task-routing observations are not physical panel ownership proof.

**Audit state update:** keep physical Fold7 topology/publication/composition/input matrix as a hard evidence gate.

## 3. Expanded Flex Deck work supports the anti-overengineering gate

Fresh two-cycle Flex Deck research found a bounded companion-control design plausible but a universal/native-like replacement unproven. It explicitly advises against automatic Shizuku/raw-input escalation and notes a generic touchpad can duplicate Samsung's native Flex Mode capability.

**Process implication:** isolate a small prototype only if product value remains compelling; do not build a generalized control/input framework from speculative capability.

## 4. Revised immediate order

1. Correct the source-confirmed opening wake-intent lifetime race without regressing smooth closing.
2. Add attempt-correlated `WAKE_COMMITTED` and readiness/presentation evidence.
3. Physically validate Fold7 timing: wake request -> physical panel -> logical INNER -> presented/useful/interactive.
4. Only then measure residual scheduler/OEM policy latency and consider narrow executor/logical-activation experiments.
5. Continue physical display-routing/topology/input matrix.
6. Keep generalized Flex Deck/input infrastructure isolated and evidence-gated.

No new controller or protocol mechanism is needed for any of these product fixes.
