# Gen12.4 Angle Authority — Final Design Review

Status: **advanced experimental candidate for physical Fold7 validation**. This is not an approval to merge into `main`.

## Failure domains are now separate

Gen12.4 deliberately avoids treating every missing angle as the same failure.

### Geometry authority

`HingeAngleSource` / `Fold7AngleAuthority` owns whether a precise sample is still fresh enough to drive geometry. Expiry revokes precise authority and allows safe fallback behavior. Geometry staleness alone does not restart infrastructure.

### Wallpaper target authority

`Fold7AngleTargetArbiter` owns which single window/display anchor is allowed to originate the next FoldInteractive poll.

A target becomes proven only when a reply is received for a poll sent exclusively through that target. Target misses cause alternate probing. Reader replacement is subordinate to complete target-round failure.

### Reader transport authority

`Fold7AngleTransportSupervisor` owns direct evidence that the shell/log-reader transport is obsolete or terminal.

It may request recovery for:

- a Shizuku shell `connectionEpoch` change;
- explicit terminal reader states such as `reader error`, `log reader ended`, `callback gone`, `stopped`, or unexpected `not started`.

It does **not** infer transport failure from stale geometry or ordinary poll misses.

A terminal reader state receives one recovery request on an unchanged shell connection. A valid precise sample rearms terminal recovery. A new shell connection epoch also rearms it. This prevents an explicit transport-recovery path from becoming its own restart loop.

## Target recovery circuit breaker

Repeated all-target failure may request one reader replacement for the current target-set failure epoch.

After that request, unchanged dead targets cannot repeatedly restart the reader. Recovery is rearmed only by evidence that the environment changed:

- a valid target acknowledgement; or
- a changed candidate/target set.

This intentionally converts persistent target loss into an observable stale state instead of CPU/Binder/logcat churn.

## Reader replacement transaction

The app does not advance its externally visible reader session before shell `START_ANGLES` has synchronously succeeded.

Recovery sequence:

1. stop issuing new angle polls;
2. allocate a candidate session/prefix;
3. request shell reader replacement;
4. if the transaction fails, preserve the current app-side reader session and retry the replacement transaction at a bounded cadence;
5. only after success, commit the new reader session/prefix;
6. revoke the old precise session, invalidate/reset the poll pipeline, and begin polling the new reader.

Late callbacks from old sessions remain fenced by session identity.

## Single-target attribution

Normal operation sends one `sendWallpaperCommand()` per poll through one selected anchor.

Gen12.3's same-poll fan-out is removed from the Gen12.4 candidate because a reply to a broadcast cannot establish which target was actually command-capable.

Each poll therefore has an attributable target key. The accepted reply promotes/proves exactly that target.

## Anchor retention

One UI topology churn can temporarily remove a display from ordinary inventory. Gen12.4 therefore does not immediately destroy every absent anchor.

- recently observed anchors receive a short retention lease;
- a proven anchor can survive longer while its acknowledgement remains fresh;
- failed/unseen anchors expire;
- stop/disarm removes all anchors immediately.

Display IDs and physical dimensions are discovery hints. Continued acknowledgements are authority.

## Visibility telemetry

Samsung `FoldInteractive` replies are accepted based on exact action identity, poll sequence, reader session, and freshness—not `isVisible=true`.

The shell reader separately counts visible and hidden accepted replies. This lets the physical Fold7 trace tell us whether a working target is the visible cover engine or a hidden inner engine without making visibility itself authoritative.

## Timing policy

The Gen12.4 validation candidate uses a 64 ms per-target timeout instead of the older 96 ms global timeout.

This is intentionally a validation parameter. Previous healthy field data showed FoldInteractive source-to-consumer delivery comfortably below this bound, while a shorter timeout allows an alternate target to be tested quickly after a topology transition.

No claim is made that 64 ms is the final production constant until physical traces confirm scheduler/logcat margin under repeated folding.

## Future direct-sensor source

A separate read-only design specifies how to test whether the Shizuku shell process can directly register a fine Samsung folding-angle sensor using only its existing authority.

That probe is intentionally not combined with this validation build. Doing so would make it impossible to know whether target-attributed FoldInteractive recovery itself works.

If direct fine sensor access is later proven, it should become a separately fenced precise source above FoldInteractive, not an ad-hoc callback into rendering.

## Optional cover FoldInteractive provisioning

Running Samsung's FoldInteractive component on cover HOME is treated only as an explicit compatibility strategy. It is not part of automatic recovery and must never silently replace a user's custom wallpaper.

## Expected physical outcomes

### Best case

The same proven inner target continues to acknowledge polls while the device transitions to native cover. No reader restart occurs.

### Normal failover case

The proven target misses after topology change, an alternate target acknowledges within the bounded probe sequence, and authority is promoted without restarting the reader.

### Reader failure case

Targets are present but the shell reader reports a direct terminal state, or the Shizuku connection epoch changes. Transport recovery runs independently of target recovery.

### No-valid-target case

All available targets fail. One bounded reader replacement may be used to disambiguate target versus reader failure. If the unchanged target set remains dead, recovery latches and geometry stays stale rather than restarting forever.

This outcome is diagnostic evidence that the next experiment must change the source/target strategy, not poll more aggressively.

## Physical acceptance gate

The architecture may be considered ready for merge consideration only after Fold7 traces demonstrate:

1. every accepted FoldInteractive sample can be attributed to one selected target;
2. target failover cannot accept a late reply from an obsolete poll/session;
3. native-cover transition either preserves or promotes a target within the bounded probe window;
4. target loss does not create indefinite reader restarts;
5. explicit reader-terminal and Shizuku-reconnection recovery are independently bounded;
6. hidden/visible reply telemetry is coherent with the working target;
7. retained anchors are eventually retired and are always destroyed on stop/disarm;
8. coarse public 0/90/180 input never regains continuous-animation authority;
9. repeated close/open cycles and rapid reversals do not create stale target, reader, or route ownership.

## Stop condition for software design

Once the exact final candidate passes:

- pure state-machine unit tests;
- full debug unit tests;
- Android lint;
- APK assembly;
- bounded-delta checks proving unrelated runtime files are unchanged;
- static invariants proving one-target dispatch, post-success session commit, target recovery circuit breaking, and explicit transport supervision;

further speculative code changes should stop until physical Fold7 evidence is collected.

At that point the remaining unknown is Samsung/One UI runtime behavior, not a missing software state distinction.
