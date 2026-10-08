# Gen12.4 — Angle Authority Architecture

Status: experimental design / validation branch only. Not adopted into `main`.

## Why Gen12.3 is not sufficient

The 5.6.2 Fold7 field capture proves that Duo Open can continue issuing `WallpaperManager.sendWallpaperCommand()` calls after the Samsung precise-angle stream stops, but a successful call return is not proof that Samsung's `FoldInteractive` engine received the command. Android WindowManager only forwards wallpaper commands from a window that is the display's current/previous wallpaper target unless the calling process has the privileged `ALWAYS_UPDATE_WALLPAPER` capability.

The final failure in `duoopen-debug-1791442095112.zip` is tightly correlated with native-cover handoff:

- FoldInteractive was live and precise samples were accepted before native-cover authority.
- State reached `NATIVE_COVER` with cover logical 0 / inner logical 1.
- Last Samsung precise sample was 4.0 degrees, poll 5807.
- Poll dispatch continued afterward and timed out repeatedly.
- Wallpaper metadata subsequently reported `none` on the active/default cover context.

This supports **target/source loss** as the leading explanation. It does not distinguish, by itself, between:

1. the command window no longer being an eligible wallpaper target;
2. the active cover HOME not hosting FoldInteractive;
3. the hidden inner FoldInteractive engine no longer accepting command traffic;
4. the log reader itself failing.

Gen12.3 broadcasted the same action through every discovered Fold7 display anchor and restarted the reader after timeout streaks. That is useful diagnostically, but it has two architectural weaknesses:

- the same poll can be sent through multiple anchors, so a reply does not prove which anchor was effective;
- reader restart is attempted before distinguishing **target failure** from **reader failure**.

## Gen12.4 design goals

### 1. Target attribution, not broadcast

Every Samsung wallpaper poll is sent through exactly **one** command anchor.

A reply to that uniquely sequenced poll proves that the selected anchor was able to reach a FoldInteractive engine. That anchor becomes the current **proven target**.

No same-poll fan-out is used in normal operation.

### 2. Explicit target arbiter

A pure state machine owns target selection:

- preserve a proven target while it continues to acknowledge polls;
- after a timeout, probe another available target before blaming the reader;
- preserve target proof across candidate list reordering;
- require all available candidates to miss before counting an exhausted target round;
- request a reader restart only after repeated exhausted rounds;
- rate-limit reader restart requests;
- promote an alternate immediately when it produces a valid reply.

This makes target health and reader health separate concepts.

### 3. Anchor retention across display churn

One UI changes logical-display topology during folding. An anchor that temporarily disappears from `DisplayManager` inventory must not be destroyed immediately.

Anchors therefore receive a bounded retention lease:

- recently seen non-proven anchors survive a short topology gap;
- the currently proven anchor survives longer;
- no anchor is retained indefinitely;
- stop/disarm still removes every anchor immediately.

A retained anchor is only useful if it continues to acknowledge unique polls; proof, not display-ID assumptions, determines authority.

### 4. Reader restart becomes secondary recovery

A timeout means: **the selected target did not produce a valid reply for this poll**.

It does not automatically mean the log reader is broken.

Gen12.4 first rotates through target candidates. Only repeated all-target failure permits reader replacement. The new reader session remains fenced from old callbacks exactly as in Gen12.3.

### 5. Visibility is telemetry, not authority

`isVisible=false` cannot be a hard reject because the inner FoldInteractive engine can be hidden while the cover is active.

The shell reader should instead record visible/hidden reply counts and last reply visibility. Exact action identity, freshness, reader session, and poll sequence remain the acceptance boundary.

### 6. Direct Samsung sensor is a preferred future source

A Samsung-specific high-resolution `Folding Angle` sensor is known to exist on current foldables with much finer resolution than the public Android `hinge_angle` sensor. Access is permission-gated on at least some Samsung builds.

The architecture therefore defines source priority as:

1. direct fine Samsung sensor, **only if a read-only shell-side registration probe proves it works**;
2. proven FoldInteractive wallpaper target;
3. public 0/90/180 hinge sensor as posture/endpoint input only.

No permission changes, settings changes, or root assumptions are permitted merely to make source 1 work.

### 7. Optional dual-FoldInteractive provisioning is explicit

Another Fold7 implementation has demonstrated that Samsung's stock FoldInteractive component can be configured on the cover HOME using the inner wallpaper's stock service settings. This can remove the hidden-inner targeting dependency because the active cover display then hosts an angle-aware engine.

Duo Open must **not** silently change a user's wallpaper to obtain this behavior.

If later adopted, this is an explicit compatibility option with these rules:

- inspect first;
- do nothing if the cover wallpaper is not a known-safe stock state or already FoldInteractive;
- require explicit user action to apply;
- verify the exact component/settings after apply;
- support a bounded, exact restoration path only when the previous state is known and reproducible;
- never overwrite an arbitrary custom wallpaper.

## State model

### Target candidate

Identity should include at least:

- logical display ID;
- observed panel geometry;
- anchor generation/key;
- inner/cover preference hint.

Geometry and display ID are hints, not authority.

### Target states

- `UNKNOWN`: anchor exists but has not acknowledged a poll.
- `PROVEN`: latest valid replies came from polls sent only through this anchor.
- `PROBING`: selected after another target missed.
- `RETIRED`: anchor aged out or was physically removed.

### Recovery sequence

Healthy:

`PROVEN target -> poll -> reply -> PROVEN target`

Single miss:

`PROVEN target -> timeout -> alternate PROBING target`

Alternate succeeds:

`alternate reply -> promote alternate PROVEN`

All targets fail:

`all candidates timeout -> exhausted round -> retry candidates`

Repeated all-target failure:

`exhausted threshold -> replace reader session once -> continue target probes`

Persistent no-target condition:

`source stale -> preserve endpoint/posture safety -> no restart storm`

## Timing

Healthy FoldInteractive transport in the first field capture was normally a few milliseconds and had a worst observed source-to-consumer delay below the existing 96 ms poll timeout. Gen12.4 can therefore use a shorter target-probe timeout (initial validation target: 64 ms) so two targets can be checked within roughly one eighth of a second while retaining margin for scheduler/logcat jitter.

This value is a validation parameter, not a permanent contract.

## Required telemetry

Status/UI:

- current source class;
- proven target key;
- current in-flight target key;
- target candidate count;
- target exhausted-round count;
- target promotions/failovers;
- reader restart success/failure counts;
- visible/hidden FoldInteractive reply counts;
- age of last proven target acknowledgement.

Transition trace:

- `angle-target-select`;
- `angle-target-ack`;
- `angle-target-timeout`;
- `angle-target-promote`;
- `angle-target-round-exhausted`;
- `angle-target-retire`;
- `angle-reader-restart`.

## Physical validation matrix

At minimum:

1. inner open -> slow close -> native cover -> remain closed -> reopen;
2. rapid reversal before native-cover handoff;
3. rapid reversal immediately after native-cover handoff;
4. repeated close/open cycles without leaving Duo Open;
5. remain closed for at least 10 seconds;
6. remain open for at least 10 seconds.

For each case record:

- which anchor is proven before and after topology change;
- whether a hidden reply is accepted;
- whether the alternate anchor can be promoted without reader restart;
- whether restart occurs only after all target candidates fail;
- whether precise angle reacquires before visual safety timeout.

## Acceptance gate for architecture adoption

Gen12.4 is not ready for merge merely because it compiles.

The angle architecture is sufficiently validated only when a physical Fold7 trace demonstrates all of the following:

- target attribution is deterministic;
- no duplicate same-poll source ambiguity;
- no stale reader session can mutate the current session;
- native-cover handoff either preserves a proven target or fails over within the bounded target-probe window;
- no persistent reader-restart loop occurs when no valid FoldInteractive target exists;
- public coarse angles never drive continuous animation;
- stop/disarm tears down retained anchors and reader state;
- the behavior survives repeated close/open and reversal cycles.

## Current conclusion

The next design step is **not** faster polling. It is explicit source and target authority.

Gen12.3 remains useful as a diagnostic fallback build. Gen12.4 should replace broadcast polling with target-attributed polling and make reader restart subordinate to target arbitration. Direct Samsung-sensor access and explicit cover FoldInteractive provisioning remain separately testable source strategies, not assumptions baked into the core state machine.
