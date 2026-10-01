# Duo Open Gen3 — Primary Successor Handoff

## Read this first

This archive is both:

1. a **root-safe deployment package** for the last fully primary-reconciled Gen3 runtime candidate, **3.0.0-alpha1-zfold7 / versionCode 38**; and
2. a **complete successor continuation bundle** containing the significant R&D handoffs that arrived after Alpha1 integration closed.

As of packaging, production `main` is still:

`45bb0d326899c0e08415928224cfea0ff58d2d4e`

Title: `Fix Fold7 Gen2 field transitions and render ownership`

Do **not** assume Alpha1 exists in runtime source until GitHub Actions succeeds and a new runtime commit appears on `main`.

## Deployment boundary

The files at archive root are the deployable, independently reconciled Alpha1 candidate.

Deploy from anywhere inside a `duo-open` Git checkout with:

- Windows: `DEPLOY_GEN3_ALPHA1_FROM_ANYWHERE.ps1`
- macOS/Linux: `DEPLOY_GEN3_ALPHA1_FROM_ANYWHERE.sh`

The deploy script installs these repository-root support files:

- `/.github/workflows/apply-gen3-alpha1-integrated.yml`
- `/tools/apply_gen3_phase1_authority.py`
- `/tools/apply_gen3_alpha1.py`
- `/payload/*`

Commit/push only those support files. The workflow is the integration authority: it verifies the exact baseline blobs, applies Phase1 then Alpha1, runs focused tests plus the full Android unit/build gate, and commits `app/**` only after all gates pass.

## What Alpha1 actually implements

Alpha1 incorporates the last fully primary-reconciled architecture:

1. V4 exact-CAS cover prewarm authority.
2. Service-stable close-cycle continuity-prime ownership.
3. FrameStore newest-STARTED capture fencing.
4. Generic PanelEngine cannot mint privileged continuity frames.
5. Exact cover visual-attempt owner.
6. One dedicated privileged cover shader host.
7. Closing uses exact-cycle frozen canonical RIGHT pane:
   - source x=984..1920
   - source y=0..2184
   - 936x2184 -> 1080x2520, exact 3:7
8. Opening uses immediate live cross-window blur under the same visual ownership model.
9. Samsung logical cover remap does not grant a new visual owner.
10. Shizuku privilege loss revokes active privileged cycle/readiness/visual authority.
11. Sparse exact correlation events for transition/visual/host/content ownership.
12. The experimental WindowArea / “Both screens at once” path is removed entirely.
13. Existing physical-policy thresholds remain unchanged:
   - inner wake 3°
   - inner handoff 8°
   - cover prewarm 174°
   - cover visual 135°
   - opening visual hide 140°
   - open latch 172°
   - rearm 166°
14. No raw physical panel OFF.
15. No Android task migration.
16. Logical display IDs remain disposable observations.

## Alpha1 validation already performed before packaging

- Phase1 pure authority model: PASS.
- Phase1 production-oriented authority tests: PASS.
- Alpha1 pure ownership/integration model: PASS.
- Focused primary integration invariants: 5/5 PASS.
- New host/coordinator type-check against Android stubs: PASS.
- Python patchers compile: PASS.
- Workflow YAML parse: PASS.
- Every Alpha1 production patch anchor audited against baseline and matched exactly once.
- ZIP integrity: PASS.
- Original Alpha1 SHA-256:
  `70cbb13815856b2bb106c6bcd3c0a83037afaf0d55e2a83805269f839a29456d`

The remaining authoritative gate is GitHub CI on the real repository.

## Why late R&D is not auto-applied

Several agents completed additional work after the Alpha1 integration boundary. Their research is valuable and is bundled under `SUCCESSOR_HANDOFF/late_rnd/`, but these changes were explicitly handed off as R&D proposals requiring primary integration and/or Fold7 device validation.

They are therefore **future-state inputs**, not runtime truth.

Do not blindly stack their patch suggestions on Alpha1. Re-fetch the post-Alpha1 `main`, compare source, independently revalidate, and then integrate the compatible parts.

## Successor integration priority after Alpha1

### P0 — App/accessibility process restart recovery

Artifacts:
- `DUO_OPEN_APP_PROCESS_RECOVERY_GEN3_RND_HANDOFF.txt`
- `DUO_OPEN_APP_PROCESS_RECOVERY_GEN3_RND_PROPOSAL.zip`

Finding:
Shizuku UserService can outlive the app process. A fresh accessibility service gets a new `serviceEpoch`, while a previous service's shell lease may remain HELD. Phase1 CAS prevents that old token from becoming the new cycle owner, but startup reconcile can still accept the resident shell snapshot before normal auto-arm.

Recommendation:
Add a service-start recovery gate before visual/content/presentation owners arm. A non-IDLE lease owned by a different `ownerServiceEpoch` is `FOREIGN_PRIOR_SERVICE`: exact-release/reconcile it and remain disarmed until clean. If startup occurs mid-transition after provenance loss, wait for a fresh semantic edge instead of joining the dead process's attempt.

Do not use raw physical OFF.

### P0/P1 — Service-stable presentation owner

Artifacts:
- `DUO_OPEN_PRESENTATION_OWNER_GEN3_RND_HANDOFF.txt`
- `DUO_OPEN_PRESENTATION_OWNER_GEN3_PROPOSAL.zip`

Reason:
Current presentation proof is still too host-local. The final Gen3 presentation layer should use service-stable host lease identity + global visual attempt identity and reject all late draw/commit/present callbacks from superseded host/content bindings.

This is a dependency for the terminal opening/closing handoff work below.

### P1 — Opening terminal inner readiness

Artifacts:
- `DUO_OPEN_OPENING_TERMINAL_INNER_HANDOFF_GEN2_RND_HANDOFF.txt`
- `DUO_OPEN_OPENING_TERMINAL_INNER_HANDOFF_GEN2_PROPOSAL.zip`

Goal:
Do not equate logical inner availability with completed opening visual/native handoff. Bind terminal opening completion to the exact movement/visual/presentation identities and preserve visual demand across transient route remap.

### P1 — Terminal Samsung/native cover landing owner

Artifacts:
- `DUO_OPEN_TERMINAL_NATIVE_HANDOFF_GEN2_RND_HANDOFF.txt`
- `DUO_OPEN_TERMINAL_NATIVE_HANDOFF_GEN2_PROPOSAL.zip`
- `DUO_OPEN_TERMINAL_HANDOFF_BUDGET_GEN3_RND_HANDOFF.txt`
- `DUO_OPEN_TERMINAL_HANDOFF_BUDGET_GEN3_RND_PROPOSAL.zip`

Finding:
`nativeCover` topology is admission evidence, not proof that Samsung Launcher/SystemUI has delivered a matching fresh buffer. Immediate teardown can expose a black/stale landing.

Recommendation:
After exact visual/presentation ownership is stable, add a terminal native-handoff owner:
- freeze the accepted Duo terminal image;
- stop visual mutation;
- enter NATIVE_PENDING;
- release on the first of:
  - genuine exact native-content-present evidence, if a trustworthy OEM/privileged signal is found;
  - a bounded refresh-relative fallback deadline;
  - owner-scoped semantic/authority cancellation.
- A Duo-owned transaction-complete callback proves Duo's transaction, not fresh Samsung content underneath.
- Performance R&D suggests sweeping 1/2/3 frames; **2 frames is only a field-test starting point**, not a production constant.

### P1 — Semantic launcher/content freshness

Artifacts:
- `DUO_OPEN_LAUNCHER_CONTENT_CONTINUITY_GEN2_RND_HANDOFF_V2.txt`
- `DUO_OPEN_LAUNCHER_CONTENT_CONTINUITY_GEN2_PROPOSAL_V2.zip`

Goal:
Separate “technically current bitmap” from semantically current content. Do not silently reuse a stale launcher/page frame merely because dimensions/cycle IDs pass. Model explicit semantic freshness/degraded fallback so home-screen continuity cannot replay the wrong page/content without telemetry.

### P1/P2 — Precise-angle authority/failover

Artifacts:
- `DUO_OPEN_ANGLE_AUTHORITY_GEN2_RND_HANDOFF.txt`
- `DUO_OPEN_ANGLE_AUTHORITY_GEN2_PROPOSAL.zip`

Finding:
Current `HingeAngleSource` can suppress a public sensor event while precise/external authority is fresh and then lose that fallback when precise callbacks expire. On an on-change/coarse sensor, geometry can remain stale until another physical movement.

Recommendation:
Introduce one control-thread Fold7 angle authority:
- immutable source/session/sequence/source-time envelopes;
- precise source age is part of lease validity;
- always retain the latest fresh public candidate;
- atomically promote buffered public fallback on precise expiry/revocation;
- keep DeviceState wake-only;
- scope synthetic endpoints to exact precise session/generation.
Do not copy the R&D model's 96 ms lease as a production constant without Fold7 fault-injection measurements.

## Corroborating R&D already represented in Alpha1

These artifacts are also included for recovery/provenance even though Alpha1 has already incorporated their central findings:

- `DUO_OPEN_CLOSE_CYCLE_PRIME_GEN2_*`
- `DUO_OPEN_SHIZUKU_RECOVERY_GEN2_*`
- `DUO_OPEN_OPENING_OWNER_GEN3_*`

Their central rules remain:
- all privileged continuity capture admission must be service/cycle stable;
- old capture publish after a newer START must be inert;
- privilege loss revokes privileged visual/cycle ownership;
- opening visual intent must survive logical-host remap under the same attempt identity.

## First action for successor agent

1. Fetch actual current `main`; do not trust this document as current state.
2. Check for workflow `Apply Duo Open Gen3 Alpha1 Integrated`.
3. If it ran:
   - inspect run/jobs/logs;
   - verify full test/build gate;
   - verify runtime commit;
   - verify `3.0.0-alpha1-zfold7`, versionCode 38;
   - verify uploaded APK artifact.
4. If the workflow failed, diagnose and repair the exact failure before incorporating any late R&D.
5. Only after Alpha1 is green, rebase/revalidate the late R&D against the new main.
6. Preserve AgentBus future-state/current-state distinction and keep posting primary checkpoints.

## First Alpha1 Fold7 field-test matrix

After CI succeeds:
1. fully closed -> slow open
2. fully closed -> fast open
3. normal slow close
4. normal fast close
5. close -> immediate open reversal
6. open -> close -> open
7. close -> open -> close
8. pause mid-fold then resume
9. rapid movement with sparse samples
10. repeated logical cover remaps
11. Shizuku loss/recovery
12. service restart at rest
13. launcher/home screen
14. ordinary app
15. secure/capture-blocked content
16. 10+ repeated cycles

Observe/export:
- inner wake latency
- cover authority token transitions
- prime attempt count per close cycle
- visual attempt ID
- host binding/rebinding
- content lease ID
- shader start/stop
- requested/drawn/committed/presented evidence
- fallback/degraded reason
- wrong-side crop
- blackout
- jitter
- stale/lingering overlay
- Samsung native landing

## Non-negotiable invariants for successor

- Physical panel identity must never be permanently bound to logical display ID.
- Real Android task remains on the normal/default display.
- Never raw physical panel OFF.
- Opening/closing are asymmetric.
- Reversal is first-class.
- Duplicate input/callbacks are expected.
- Every async result must be fenced by exact identity.
- Frozen-frame behavior remains deterministic; no live recapture while stationary.
- Preserve early inner wake unless device evidence disproves it.
- Preserve canonical RIGHT-side portal.
- “Requested” != “committed” != “presented” != “fresh native content”.
- Secondary AgentBus R&D is future-state evidence, never production truth until independently integrated.

## AgentBus recovery locations

Primary reconciliation:
`/DuoOpen-AgentBus/artifacts/primary/20261001T211847Z/`

Primary Alpha1:
`/DuoOpen-AgentBus/artifacts/primary/20261001T232455Z/`

Late R&D remains under:
- `/DuoOpen-AgentBus/artifacts/state-rd/`
- `/DuoOpen-AgentBus/artifacts/display-rd/`
- `/DuoOpen-AgentBus/artifacts/reviewer/`
- `/DuoOpen-AgentBus/artifacts/performance-rd/`

The immutable board remains:
`/DuoOpen-AgentBus/messages/`

END OF PRIMARY SUCCESSOR HANDOFF
