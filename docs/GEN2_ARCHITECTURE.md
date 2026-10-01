# Duo Open Gen2 continuity architecture

## Top-level pipeline

`Angle/Device State -> Transition Policy -> Physical Cycle Envelope -> Cover Lease Authority -> Cover Readiness -> Frame Provenance -> Host/Render -> Presentation Evidence -> Samsung Native Handoff`

## Identity hierarchy

### Service lifetime
`serviceEpoch`

Created once for each accessibility-service lifetime. It is not persisted and does not need to survive process death; its purpose is to make in-memory stale work non-authoritative.

### Physical close cycle
`closeCycleId`

Created when deliberate closing is accepted. Stable through:
`CLOSING_INTENT -> COVER_PREWARMING -> COVER_READY_HIDDEN -> COVER_VISUAL`.
Invalidated on reversal, native-cover takeover, destroy/restart.

### Transition policy
`transitionGeneration`

Existing controller generation remains unchanged. It identifies one policy transition/action and is deliberately not reused as the close cycle ID.

### Shell cover authority
`connectionEpoch + shellSession + shellRevision + leaseId + leaseEpoch + ownerGeneration + physicalDisplayId`

The app accepts only monotonic current-session V3 snapshots. Reassert/release use the exact accepted token.

### Readiness
`serviceEpoch + closeCycleId + transitionGeneration + exact lease token + current target logical route`

Logical ID remains disposable. It is accepted only while current geometry/topology agrees with the shell's fresh route observation.

### Frame content
`serviceEpoch + closeCycleId + captureSequence + contentLeaseId`

A current-cycle frame is never inferred from age alone.

### Presentation
`serviceEpoch + closeCycleId + contentLeaseId + hostEpoch + presentationAttemptSequence + renderPath`

Every draw/commit/present callback is accepted only by this exact attempt.

## Threading

- Shell cover mutations: existing single-thread executor.
- Shell mirror mutations: existing single-thread executor.
- Samsung/public angle acceptance: one Fold7 control HandlerThread.
- Window/View/DisplayMirrorHost operations: main thread.
- Capture: existing coroutine/IO behavior, but publication is token-gated.
- Transition Lab writer: existing async writer.

## Readiness fast lane

DisplayManager callbacks must synchronously/cheaply tell the continuity coordinator that topology changed before the 24 ms coalesced heavy engine sync. Heavy engine creation/evaluation may remain debounced.

## Failure behavior

- No current V3 cover authority -> fail closed and wait/reacquire.
- Physical cover held but logical route late -> remain PREWARMING/WAITING_ROUTE; do not classify as generic failure.
- Current-cycle capture unavailable -> live mirror/native fallback, never prior-cycle deterministic frame.
- Stale callback -> record rejection and do nothing.
- Shizuku disconnect -> invalidate app cover authority and mirror session immediately.
- Native cover takeover -> hide/release local continuity and let Samsung own the endpoint.

## Non-goals

Gen2 does not redesign the shader, move the real Android task, add raw physical OFF, change fold thresholds, or force the Lite flavor through privileged machinery.
