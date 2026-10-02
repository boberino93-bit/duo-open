DUO OPEN — GEN4 ALPHA1 PANEL AUTHORITY
======================================

BASELINE
--------
Live runtime baseline when this package was built:
  main: 44f6d52abbf5de4cad36b0309b4d923d70f83d78
  versionCode: 40
  versionName: 3.0.0-alpha3-zfold7

Gen3 Alpha4 never changed app/**; its workflow failed before runtime patching.

WHY GEN4
--------
The repeated Fold7 failures now resolve into two independent timing domains:

1. geometry/input timing — already substantially solved by Gen3 ordered precise-angle authority,
   DeviceStateManager early opening edge, source-time replay, and stale-callback fencing;
2. panel ownership/lifetime — app process, AccessibilityService, Shizuku binder, Shizuku daemon,
   physical cover and logical cover route do not share the same lifetime.

Gen4 keeps the proven Gen3 geometry + renderer behavior and moves cover-panel mutation authority
into DuoShellService. The app sends semantic intents. It no longer owns a privileged cover lease.

GEN4 ALPHA1 AUTHORITY MODEL
---------------------------
  shellSession      = one DuoShellService daemon lifetime
  serviceEpoch      = one AccessibilityService/app lifetime
  intentSequence    = strict ordering for privileged intents inside that service lifetime
  closeCycleId      = one deliberate close cycle
  transitionGeneration = semantic controller generation

The shell daemon is the only writer of cover power/route state.

STARTUP / RECOVERY
------------------
Before the app can arm continuity, the daemon examines ACTUAL Fold7 topology.

- native cover default -> safe, admit
- inner default + no secondary cover route -> safe, admit
- inner default + secondary 1080x2520 route -> normalize it with the existing validated
  logical power-reset primitive, then admit
- ambiguous topology -> remain fail-closed and retry boundedly

A newer serviceEpoch cannot inherit a prepared route from an older app process. The daemon
normalizes it before admitting the replacement service.

Shizuku State.Ready is no longer enough by itself: the AccessibilityService also requires an
actually connected Shizuku user-service binder and a clean Gen4 admission receipt.

COVER PREPARE
-------------
The existing field-proven physical-first Fold7 path is retained:
  physical cover NORMAL -> bounded fresh logical-route discovery -> enable route -> logical ON

The route remains a hidden readiness resource until the existing semantic controller reaches its
visual threshold. Gen4 does not change these measured thresholds:
  INNER_WAKE_MIN_DEG      3
  INNER_HANDOFF_MIN_DEG   8
  COVER_PREWARM_DEG       174
  COVER_VISUAL_START_DEG  135
  OPEN_LATCH_DEG          172
  OPEN_REARM_DEG          166

If Samsung publishes the logical route late, Gen4 performs bounded self-driving reasserts instead
of waiting indefinitely for another Android display callback.

RELEASE
-------
Return-to-inner is daemon-owned and uses the existing validated logical power-reset mechanism.
Failed cleanup remains RELEASE_PENDING and is retried boundedly. Raw physical OFF and task
migration are not introduced.

GRACEFUL DAEMON EXIT
--------------------
SHIZUKU_DESTROY now attempts cover-route normalization before shutting down the cover mutation
executor. A crash still cannot run cleanup, so the next daemon lifetime performs topology-based
startup recovery before accepting panel intents.

LEGACY MUTATION FENCE
---------------------
The Gen4 DuoShellService rejects the old direct secondary-display and cover-lease V2/V3/V4
mutation transactions. The constants/methods remain in source for historical compatibility, but
they are no longer an authority path in the Gen4 binary.

DEPLOYMENT
----------
Do NOT copy individual app/** files manually.

1. Put every support file from this package at repository root, preserving directories.
2. Verify GEN4-SUPPORT-SHA256.txt.
3. Commit/push all files EXCEPT APPLY_GEN4_ALPHA1_NOW.txt first.
4. Commit/push APPLY_GEN4_ALPHA1_NOW.txt LAST.
5. The workflow checks exact Alpha3 runtime blob hashes before touching app/**.
6. It applies the patch, checks architecture invariants, runs focused tests, then the full
   testFullDebugUnitTest + assembleFullDebug gate.
7. Only after all gates pass does Actions commit app/** to main and publish the APK.

If any baseline blob changed, STOP and rebase this package. Do not weaken the checks.

TARGET OUTPUT
-------------
  versionCode: 41
  versionName: 4.0.0-alpha1-zfold7
  artifact: DuoOpen-ZFold7-4.0.0-alpha1

LEGACY WORKFLOW NOTE
--------------------
The repository's generic "Build Z Fold 7 Motion-Gated Cover Power 1.3.16" workflow currently fails
while replaying historical pre-Gen3 steps before compilation. It is not the Gen4 acceptance gate.
Use the dedicated "Apply Duo Open Gen4 Alpha1 Panel Authority" run: it performs focused unit tests,
the full FullDebug unit suite, and assembleFullDebug before committing or publishing an APK.

REVISION 2 NOTE
The first deployment attempt reached the patcher final safety check and failed only because the validator treated the existing Display.STATE_OFF topology read as if it were a power-off mutation. V2 narrows that assertion. Runtime design and payload are unchanged.

REVISION 3 NOTE
The second deployment reached Kotlin compilation and exposed missing retry declarations in the patcher. V3 adds those declarations and explicit postconditions so this cannot recur. Gen4 panel-authority behavior is otherwise unchanged.
