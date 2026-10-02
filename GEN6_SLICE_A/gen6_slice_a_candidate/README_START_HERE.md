# Duo Open Gen6 Slice A — WakeHint + Attempt Identity + Telemetry Candidate

Exact baseline: `de9eb45086f6eee00dd4e1e01d5e9782e39773d5` (`5.0.0-beta1-zfold7`, 42).

This is a **candidate/import package**, not a production commit. GitHub write access for the creating Primary session returned HTTP 403, so `main` was not modified.

## Scope

- Observe departure from an independently corroborated closed-rest Samsung device-state id. On the Fold7 field trace this exposes `0->1` immediately even though Samsung still labels state 1 `folded=true`.
- Assign a stable Gen6 opening attempt id and emit typed diagnostic ingress.
- Attach the existing semantic controller generation later, when the existing controller independently accepts opening.
- Abort/rearm attempt identity after independently corroborated native-cover precise <=12° or service teardown.

## Explicit non-scope

Slice A does **not** use the hint as hinge geometry, does not call `continuity.onEarlyOpeningEdge`, does not wake or mutate a panel, does not migrate tasks, does not change Gen4 close thresholds/visuals, does not alter Gen5 rendering, and does not claim CI or physical Fold7 acceptance.

## Exact-baseline gate

`tools/apply_gen6_slice_a.py` refuses to patch unless these baseline blob SHAs match:
- `Fold7DeviceStateObserver.kt`: `760d075332740e5ee0d73766766175b17e6f9122`
- `FoldOverlayService.kt`: `cfc4706458e1da197e0e86ce74dc80c83489a2e6`

## Intended authorized-primary procedure

1. Fetch exact `main`; require the SHA above or rebase/re-review.
2. Extract this package at repository root.
3. Run `python3 validate_slice_a.py`.
4. Run `python3 tools/apply_gen6_slice_a.py`.
5. Inspect diff; allow only the two existing files plus the new owner/test files.
6. Run focused tests plus the mandatory existing regression suite.
7. Run `./gradlew testFullDebugUnitTest assembleFullDebug --stacktrace`.
8. Route the evidence through the Manager/peer review gate before production acceptance.
9. Only Primary may integrate to production; fetch `main` afterward to prove it.
