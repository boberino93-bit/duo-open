# Gen7 SP4 Runtime Regression Beta2 — service-pack report

Baseline Android source: `41c6f20c817226b233eb4cbfb402e879c5e3e3ea`

Target test identity: `5.1.0-beta2-zfold7` / versionCode `43`.

## Why this build exists

Physical Fold7 testing of 5.0.0-beta1 exposed a coupled set of runtime regressions:
inner power calls succeeded without proving useful inner presentation, first-open
visuals could start late and then run synthetic blind geometry, Fold7 snapshot
paths deliberately froze changing content, and portrait-coordinate assumptions
were not safe across rotation. The requested cover-panel power/brightness ramp is
also incorporated into the same authority path rather than added as an unrelated
UI animation.

## Changes

- DeviceState opening edge can recover from stale cover/prewarm states only at a
  confirmed closed endpoint.
- Inner wake now retries and attempts the exact 1968x2184 logical route enable +
  STATE_ON after physical NORMAL, then reports physical/logical readiness
  separately.
- Gen5 holds the closed seed in `AWAIT_PRECISE`; it does not invent opening
  geometry before a measured sample arrives.
- Fold7 snapshot overlays resume live Shizuku recapture.
- Gen3 closing cover continuously refreshes the physical right pane from the
  live inner display. The inner Duo overlay layer is excluded to prevent
  recursive/double application of the fold effect.
- A physical-coordinate transform handles rotations 0/90/180/270 for crop,
  output dimensions, fold axis, hinge edge and moving side.
- Snapshot cache keys include orientation-sized geometry and stale bridges use
  center-crop rather than non-uniform stretch.
- Cover presentation policy is serialized through the shell mutation executor:
  OFF near fully open, ON at 175 degrees closing at minimum brightness, eased
  ramp to the unfolded inner reference by 90 degrees, OFF at 177 degrees while
  opening.

## Validation completed before packaging

- Both supplied field ZIPs passed archive integrity inspection.
- No FATAL/ANR/uncaught-exception marker was found in either retained field log.
- Pure Kotlin presentation-policy and rotation-transform code compiled and ran
  deterministic assertions locally.
- Python patcher compiles and its embedded self-test passes.
- GitHub Actions workflow YAML parses successfully.
- Patch is exact-baseline/fail-closed against known Git blob SHAs, with the
  previously validated Shizuku/onboarding patch accepted only by its explicit
  postcondition markers.

## Validation deliberately not claimed

- Android Gradle compile/unit/build has not been run locally.
- Hidden Samsung/SurfaceControl brightness behavior has not been physically
  validated on the Fold7.
- Physical panel wake, live-content cadence, rotation during an active fold and
  the 175/177 degree brightness/power hysteresis remain NOT_RUN on device.

The included GitHub workflow performs the first Android compile/unit/build gate
and emits the APK, SHA-256, build information and exact applied source diff.


## SP4.1 compiler hotfix

- CI run `37082713549` exposed `Fold7Gen3VisualCoordinator.kt:465:21 Unresolved reference 'scope'`.
- Root cause: the Beta2 transformer added `scope = scope` to the `Fold7CoverVisualHost` call but did not add a `CoroutineScope` dependency to `Fold7Gen3VisualCoordinator` or pass the service-owned scope from `FoldOverlayService`.
- Fix: inject `private val scope: kotlinx.coroutines.CoroutineScope`, pass `scope = scope` from the service, and validate both with transform-level self-test and generated-source postconditions.
- This hotfix does not alter the intended runtime behavior; it repairs dependency wiring required for compilation.
