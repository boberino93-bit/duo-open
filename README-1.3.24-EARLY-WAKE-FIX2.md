# Duo Open 1.3.24 Early Panel Wake — Fix 2

Supervisor hardening after independent physical-panel lifecycle audit.

This patch is intentionally narrow.

1. Async generation safety
   - beginPrewarm re-checks controller generation inside the IO coroutine
     immediately before touching the privileged shell.
   - ReleaseSecondary rejects stale generations before local/shell work and
     re-checks again inside its IO coroutine.
   - asynchronous stopDisplayMirror also checks generation before touching the
     shell so an old hide cannot tear down a newer mirror generation.

2. Physical-ID priming off the hinge critical path
   - the existing Shizuku-ready resolveCoverDisplay() priming call now resolves
     and caches both validated physical panel ids:
       cover 1080x2520
       inner 1968x2184
   - this uses the existing discovery mechanism outside the real transition,
     avoiding a cold dumpsys lookup during the first 3-degree inner wake where
     possible.
   - logical display ids are NOT cached and remain fresh one-shot routes.

3. Regression coverage
   - adds a 0 -> 15 degree first-sample opening test.
   - verifies WakeInner occurs exactly once and the next sample enters
     INNER_HANDOFF without a second wake.

4. Build identity
   - versionCode 29
   - versionName 1.3.24-zfold7-early-panel-wake-fix2

Not changed:
- inner wake 3 degrees
- inner handoff fallback 8 degrees
- cover prewarm 174 degrees
- cover visual 135 degrees
- reversal visual hide 140 degrees
- 172/166 fully-open latch/rearm
- physical-first cover power ordering
- no raw physical OFF
- no cached logical display ids
- Transition Lab instrumentation
- mirror geometry / renderer behavior

This package must be compiled and unit-tested in the direct-source workflow
before phone installation.
