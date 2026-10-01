# Duo Open 1.3.26 Gen-2 ingress import instructions

You are integrating this package into `boberino93-bit/duo-open` as the production
supervisor/master agent.

## Baseline discipline

1. Resolve live `main` before touching files.
2. This package was prepared against:
   `2f6b27acd31462af6e6f49773391d4770d4b65e3`.
3. If live `main` differs, compare every affected file and re-derive the patch;
   do not blindly overwrite newer work.
4. Preserve any newer fixes unless they conflict with a measured Gen-2 invariant.

## <=10-minute integration batches

Batch A — pure scaffolding/tests
- Copy the four files under `repo_overlay/`.
- Run unit tests.

Batch B — shell sequence identity
- Add pollSequence to the FoldInteractive action/callback protocol.
- Reject stale/mismatched sequence completions.
- Tests/compile.

Batch C — control HandlerThread
- Add exactly one Fold7 angle/control HandlerThread.
- Register public sensors onto it.
- Route Samsung Binder samples onto it.
- Keep View/Window operations on main.

Batch D — completion-paced 8 ms acquisition
- Integrate the draft WallpaperAngleFeed behavior.
- One poll in flight.
- Next poll only after response/timeout.
- 8 ms target while interactive; 1 ms minimum yield; no catch-up burst.

Batch E — latest-only presentation
- Do not enqueue one main runnable per angle.
- Coalesce to newest accepted sample.
- Preserve reversal delivery.

Batch F — Transition Lab timing
- Add poll due/command/return, shell parse/Binder, control accept, controller
  decision, privileged enqueue/start/return, main post/run and presentation timing.

Batch G — early-edge observation
- Add DeviceState observation first.
- Learn opaque folded-state identity only at independently confirmed native-cover
  closed rest.
- Record timing; do not wake from it until field evidence proves it leads the
  precise path reliably.

Batch H — early-wake action (only after evidence)
- Shared one-shot opening lease.
- Allowed: WakeInner + kick precise poll burst + telemetry.
- Forbidden: inferred visual angle, mirror visibility, task migration.

Batch I — release identity/workflow
- versionCode 31
- versionName `1.3.26-zfold7-gen2-ingress`
- update direct-source workflow assertions/artifact naming.
- compile/tests/build.

Batch J — Fold7 device validation
- slow/moderate/fast open matrix + no-motion + reversal sequences.
- Export Transition Lab bundle.
- Compare T0..T10 timings from the R&D handoffs.

## Stop conditions

Do not merge if any of these occur:
- duplicate WakeInner per opening generation;
- mirror visible before existing visual gate;
- logical-id physical ownership regression;
- old reader session can mutate current state;
- unbounded main queue growth from angle samples;
- direct-source unit/build workflow fails.
