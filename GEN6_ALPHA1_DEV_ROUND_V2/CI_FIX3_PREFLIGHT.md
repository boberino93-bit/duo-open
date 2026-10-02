# Gen6 Alpha 1 V2 — CI Fix 3 Proactive Preflight

Baseline checked immediately before packaging:

- `main`: `c8421905578b354f400014979feb789358d073d8`
- all 10 production blob gates still match the V2 patcher exactly

## Compiler correction

Run #3 reached `:app:compileFullDebugKotlin` and exposed one remaining error:

- `PanelEngine` needed access to the PUBLIC_GLASS view for the refresh-rate lease,
  while `PublicGlassSurface.view` had been made private in Fix 2.

Fix 3 keeps the material view private and exposes only a `View`-typed
`refreshView` handle. `PanelEngine` now uses that handle.

## Additional proactive corrections

The rest of the Gen6 V2 touched paths were reviewed before another CI run.

1. **Continuity-prime secure capture**
   - Uses `ShizukuBridge.captureResult(...)`.
   - A secure-layer result is preserved as a security signal.
   - No protected bitmap is admitted into the continuity frame store.

2. **Live recapture secure transition**
   - Uses `captureResult(...)` instead of collapsing secure capture to `null`.
   - Secure-layer discovery triggers the private path instead of leaving the
     previous public snapshot visible.

3. **Secure metadata fail-closed**
   - If `containsSecureLayers` cannot be queried, the shell capture is treated
     as secure and is not materialized.

4. **Cross-app stale-frame invalidation**
   - Snapshot and continuity-frame references are cleared on every foreground
     package change, not only when the destination is already classified
     PRIVATE_FROST.

5. **Stale in-flight shell frame cleanup**
   - A bitmap returned after the capture attempt became stale is recycled before
     the callback exits.

## Local gates

- patcher Python compile: PASS
- patcher self-test: PASS
- package static gate: PASS
- pure Kotlin Gen6 harness: 17/17 PASS
- opening-attempt fuzz: 100,000 iterations PASS
- privacy invariant fuzz: 100,000 iterations PASS
- Gen4 WakeHint raw-log replay regenerated: 9 usable `0→1` events
- current-main marker revalidation: PASS
- 10/10 production blob hashes: PASS

Android CI / APK status remains **not passed until the next GitHub Actions run**.
