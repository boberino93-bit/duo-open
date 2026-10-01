# Duo Open 1.3.24 — Early Panel Wake Experiment

This package is a targeted Fold7 wake-timing adjustment based on physical
device feedback.

Changes:

- CLOSED -> OPEN:
  - ignore tiny <3° movement;
  - at ~3° real opening, emit WakeInner;
  - Shizuku powers the stable physical 1968x2184 inner panel directly;
  - no cached logical inner display id is introduced;
  - INNER_HANDOFF fallback moves from 20° to 8°.

- OPEN -> CLOSED:
  - deliberate-close intent detector is preserved;
  - cover prewarm moves from 150° to 174°;
  - the physical 1080x2520 cover panel is powered BEFORE requiring a logical
    1080x2520 route;
  - if the logical route does not exist yet, successful physical wake is still
    treated as a successful hidden prewarm;
  - logical display ids are still re-resolved and revalidated for every
    logical operation.

Not changed:

- 135° cover visual threshold;
- 140° reversal hide threshold;
- 172°/166° fully-open latch/rearm;
- mirror crop/geometry;
- renderer/TiltFollower tuning;
- Transition Lab instrumentation.

Important experimental limitation:

A physical-only cover wake that is immediately reversed before Samsung creates
a logical cover route cannot yet be explicitly power-reset by logical id. We
intentionally do NOT issue a raw physical OFF command in this experiment,
because forcing OFF at the wrong native handoff moment is riskier than allowing
Samsung to reclaim the panel. Transition Lab should reveal whether that case
needs a dedicated safe release design.

Apply by extracting into the root of the duo-open repository and replacing the
matching files.
