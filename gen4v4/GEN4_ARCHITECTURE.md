# Duo Open Gen4 Alpha1 — Fold7 Panel Authority

## Ownership boundary

Gen4 separates semantic fold policy from privileged panel mutation.

`ordered geometry -> Fold7ContinuityController -> semantic panel intent -> DuoShellService Gen4 authority -> physical/logical panel transaction -> receipt -> render readiness`

The AccessibilityService owns **intent** and rendering policy. `DuoShellService` owns **panel mutation**.

## Identity hierarchy

- `shellSession`: invalidates all authority when the Shizuku user-service process changes.
- `serviceEpoch`: invalidates authority when the app/AccessibilityService lifetime changes.
- `intentSequence`: total order for privileged requests within one service lifetime.
- `closeCycleId`: stable identity for one deliberate closing cycle.
- `transitionGeneration`: state-machine generation; never substituted for close-cycle identity.

## Recovery invariants

1. No continuity arm before real Shizuku binder readiness.
2. No continuity arm before daemon topology reconciliation.
3. No new app service may inherit an older prepared cover route.
4. A daemon restart trusts physical topology, not old in-memory state.
5. Ambiguous topology is fail-closed.
6. Logical display IDs are resolved fresh immediately before mutation.
7. A stale serviceEpoch or intentSequence cannot mutate the cover.
8. Failed route publication and release are boundedly retried.
9. Native-cover topology is never reset as though it were a secondary cover route.
10. No new raw physical OFF or task migration path is introduced.

## Preserved Gen3 mechanisms

- ordered precise/public hinge authority;
- source-observation timestamps;
- DeviceStateManager early opening wake;
- 174° hidden prewarm intent;
- 135° visible cover transition threshold;
- frozen-frame continuity + deterministic Fold7 shader;
- close-cycle identity and stale frame/visual callback fencing;
- mirror session ordering;
- secure-content behavior and diagnostics.

## Alpha1 scope

This is deliberately an authority/recovery generation, not a renderer rewrite. Once field traces
confirm that cover preparation/release and daemon/app restarts are deterministic, later Gen4 work
can tune presentation timing using measured Fold7 data without reopening privileged ownership.
