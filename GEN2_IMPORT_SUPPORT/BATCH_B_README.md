# Duo Open Gen-2 — Batch B: shell sequence identity

Base verified before packaging: `642719f226da7a440fd0f611aeb8f011a7656afc`.

This is intentionally backward-compatible. It does **not** switch production polling yet.
It only establishes the transport contract required by the next batch:

- shell `AngleReader` accepts the existing exact action (sequence 0);
- it also accepts `<session-prefix>:<poll-sequence>` actions;
- parsed poll sequence is returned in `CB_ANGLE` after source uptime;
- `ShizukuBridge.startAngles(...)` remains available for the existing feed;
- new `startAnglesSequenced(...)` exposes sequence identity to Gen-2 callers;
- angle status reports the latest poll sequence.

The included workflow applies this patch, runs `testFullDebugUnitTest` and
`assembleFullDebug`, and commits only if those checks pass.


## Fix 1
The first apply attempt correctly refused to commit after Kotlin compilation failed.
The only compiler error was the compatibility wrapper calling `startAnglesSequenced`
with the obsolete named argument `action=` after the callee parameter became
`actionPrefix`. This package corrects it to `actionPrefix = action` and adds a
workflow/postcondition assertion for that exact call shape.
