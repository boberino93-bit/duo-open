# Duo Open Gen6 Pass 2 — Expansion Plan From Pass 1 Evidence Gaps

Baseline: `boberino93-bit/duo-open@de9eb45086f6eee00dd4e1e01d5e9782e39773d5`.

Pass 1 produced a green architecture/lifecycle model, but intentionally did not claim Android integration or physical correctness. Pass 2 therefore expands only the boundaries that remained evidence gaps rather than changing the principal architecture.

## Expansion work

1. **Presentation-time truth** — consume real FrameTimeline `vsyncId`, `frameTimeNs`, `deadlineNs`, and `expectedPresentNs`. Treat display mode refresh as diagnostic metadata only. Derive observed cadence from unique frame timestamps and never classify a 120 Hz request as effective without direct ~8.33 ms cadence evidence.
2. **Refresh ownership** — model both the actual invalidating child View vote and seamless SurfaceControl vote. Lease ownership is exact `(attempt, host, generation)`; replacement clears the previous View and SurfaceControl votes before requesting the successor. A stale generation cannot clear the current owner, including same-surface reuse.
3. **Zero-gap host migration** — keep the old presented host alive until the replacement reports its first presentation. If the old host dies before replacement readiness, abandon Gen6 ownership to deterministic native fallback rather than intentionally exposing a blank interval.
4. **Content provenance** — bind reusable pixels to attempt, service epoch, visual generation, user, package, window, task and capture generation. Any mismatch or age violation rejects the lease. Transition to a secure/capture-denied window immediately destroys the pixel lease.
5. **Native freshness** — require route-generation-matched presentation evidence after the attempt began. HOME still rejects wallpaper-only; ordinary apps additionally require current app-layout generation; secure windows require native protected-window readiness.
6. **Recovery** — wallpaper source loss is non-terminal. App/accessibility/Shizuku/service/host failures retire all owned visual/refresh/content resources and move to native fallback with a new service epoch before another attempt.
7. **Diagnostics/transport** — use typed metadata-only events carrying attempt/epoch/generation/host, frame timeline, physical/visual angle, display-mode vs observed cadence, native freshness and recovery reason. Diagnostic upload requires configured HTTPS transport plus checksum-matched receipt.
8. **Replay** — use the raw Gen4 Transition Lab JSONL to prove real FrameTimeline availability/cadence behaviour, and preserve the raw leave-closed replay as a model-vs-current waiting comparison.

## Still deferred after Pass 2

A green Pass 2 is a **MODEL_PASS**, not an Android implementation, CI pass, or Fold7 physical pass. Exact source slices are allowed only after both passes remain green together. Physical claims remain blocked until an APK is built and tested on the Fold7.
