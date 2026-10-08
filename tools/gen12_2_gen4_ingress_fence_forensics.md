# Gen12.2 Gen4 Binder-Ingress Fence — Forensic Engineering Note

## Source field evidence

Source bundle: `duoopen-debug-1791438725678.zip`

Source build: `5.6.1-gen12-1-wallpaper-lifecycle-zfold7` (`versionCode 57`).

The field capture demonstrates that the authoritative Samsung FoldInteractive hinge source is not the primary latency bottleneck. The material failure is privileged cover-route mutation ordering.

A representative failure sequence showed a newer close transition entering `CLOSING_INTENT` / `COVER_PREWARMING` while an older `secondary-release` operation was still pending in the shell-side cover mutation lane. When that older release finally executed, it normalized the cover route to `IDLE`, clearing the prepared route that the newer close needed. The newer close then had to reacquire the route and deferred presentation for hundreds of milliseconds.

## Why Gen4 sequence rejection was insufficient

Gen4 already carries `serviceEpoch` and monotonically increasing `intentSequence` values. However, the authoritative sequence was advanced inside the same single-threaded `coverMutationExecutor` that performed the hardware operation.

That creates a serialization paradox:

1. old release enters or waits in the mutation lane;
2. new prepare arrives at Binder with a higher intent sequence;
3. new prepare cannot update `Fold7PanelAuthorityGen4.lastIntentSequence` until it reaches the same lane;
4. old release therefore still appears current while it executes destructive normalization;
5. only afterward can the newer prepare execute.

The sequence guard was correct *inside* the lane but too late to reject obsolete work already ahead of the new intent.

## Gen12.2 design

Gen12.2 adds `Fold7Gen4IngressFence`, a very small synchronized ordering object owned by `DuoShellService`.

The fence observes `(serviceEpoch, intentSequence)` immediately when `COVER_PANEL_GEN4` reaches Binder, before the request blocks on `coverMutationExecutor`.

Ordering is lexicographic:

- higher `serviceEpoch` supersedes all work from an older app-service lifetime;
- within the same service epoch, higher `intentSequence` supersedes lower sequence work;
- late arrival of an older epoch or lower sequence can never move the watermark backward.

The daemon remains a single hardware writer. Gen12.2 does **not** create a second route/power executor and does not allow concurrent physical route mutations.

## Release hardening

`returnCoverPanelGen4()` now checks the ingress fence:

1. before entering release state;
2. again immediately before route cleanup;
3. during route-normalization retries;
4. immediately before the destructive secondary-display reset.

If a newer intent has already reached Binder, the old release returns a stale/superseded receipt and skips destructive cleanup.

This directly addresses the observed stale-release race while preserving Gen4's serialized hardware mutation invariant.

## Why the earlier 750 ms retention experiment was superseded

A first experiment delayed normal transition release for 750 ms. That covered common rapid reversals but did not cover the worst observed sequence: one problematic native-cover/opening release had already been outstanding long enough that a fixed 750 ms grace could expire before the next close arrived.

Increasing the timer further would trade correctness for hidden-route lifetime and could delay legitimate native ownership restoration. The Binder-ingress fence instead invalidates stale work based on semantic ownership, not elapsed time.

## Safety invariants preserved

Gen12.2 does not change:

- hinge-angle authority or sampling;
- controller thresholds;
- Samsung display topology inference;
- Gen12 presentation deferral behavior;
- secure-content fail-open behavior;
- live-mirror geometry;
- renderer behavior;
- Shizuku protocol layout;
- wallpaper lifecycle behavior from Gen12.1.

`coverMutationExecutor` remains the sole serialized route/panel authority lane.

## Automated validation

The candidate workflow must reconstruct the exact Gen12.1 lineage first, then apply only the Gen12.2 overlay.

Required checks:

- old queued intent is invalidated as soon as a newer intent is observed;
- an older late-arriving sequence cannot move the fence backward;
- a new service epoch supersedes an old service even though its sequence restarts;
- an old service epoch cannot supersede the new service;
- protected app/runtime files remain byte-identical to Gen12.1 except `DuoShellService` plus the new pure fence/test;
- `testFullDebugUnitTest`, `lintFullDebug`, and `assembleFullDebug` pass.

## Physical Fold7 acceptance criteria

On a rapid OPEN → CLOSE reversal that previously reproduced the defect:

1. the newer Gen4 prepare must be visible at Binder ingress before the older release executes;
2. the old release must return `stale=true` with an `ingress-superseded` / `return-superseded` operation rather than resetting the route;
3. the route must not transiently fall to `IDLE` because of that older release;
4. `physicalLeaseHeld` / `routeReady` for the new close must become ready without the former reacquisition penalty;
5. stable opening, native-cover handoff, service re-arm, and Shizuku reconnect must still normalize safely;
6. no legacy cover mutation path may regain authority.

If latency remains after stale releases are eliminated, the next target is queue residency caused by `COVER_PRESENTATION_V1`; that should be solved only with an explicit power-ownership refactor, not by unsafely running physical panel writes concurrently.
