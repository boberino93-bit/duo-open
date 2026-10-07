# Validation Claim Gate

Status: project-local hard bootstrap requirement.
Applies to PRIMARY, MANAGER, RESEARCH, and any agent producing, reviewing, handing off, or describing implementation artifacts.

## Purpose

Evidence must bound every implementation claim. Passing source checks, unit tests, lint, CI, packaging, or reproducibility proves only the scope actually exercised. It does not prove device/runtime behavior that was not executed.

This gate exists to prevent an unvalidated build or hypothesis from being presented to a human or another agent as a fix, solution, resolution, working implementation, compatible implementation, recommendation, or production-ready result.

## Mandatory status classes

### 1. BUILD_ARTIFACT

An artifact exists, but its required build/test gates are incomplete or failed.

Permitted wording: artifact, draft build, failed build, partial output.

Forbidden wording: fix, solution, resolved, working, compatible, production-ready, recommended, validated, eligible solution.

### 2. VALIDATION_CANDIDATE

Required source/build/CI/reproducibility gates have passed, but one or more acceptance tests required for the claimed end state have not run in the required environment.

The handoff MUST include a prominent status line naming both proven and unproven scope, for example:

`Validation status: BUILD-VERIFIED / DEVICE-UNVALIDATED`

A validation candidate may be handed to a human when testing or a candidate artifact was requested, but it MUST be described as a test build, validation candidate, or hypothesis-driven validation artifact. It MUST NOT be described as a potential solution, fix, resolved implementation, working implementation, compatible implementation, recommended implementation, or production-ready implementation.

If a prior build failed physical/runtime validation, every successor remains a hypothesis-driven validation candidate until the failed acceptance path and its required regression paths pass.

### 3. VALIDATED_SOLUTION

This status is permitted only when the acceptance criteria necessary to support the claimed end state have actually been executed and passed in the required environment/device scope.

Only this status permits unqualified solution-level wording such as fix, solution, resolved, working, compatible, recommended, ready, or production-ready, and only within the exact scope validated.

Validation of one path does not silently validate adjacent paths, devices, OS versions, secure-content behavior, performance, reliability, or production readiness.

## Claim-to-evidence invariant

Every claim MUST be no stronger than the evidence actually executed and verified.

Examples:

- Compile success proves compilation only.
- Unit-test success proves the covered unit-test assertions only.
- Lint success proves the enabled lint checks only.
- CI success proves the CI workflow completed successfully; it does not prove physical device behavior.
- APK/package integrity proves artifact identity/integrity only.
- Emulator/simulator success does not prove physical-device behavior unless the acceptance contract explicitly says it does.
- A physical Fold7 behavior claim requires the relevant physical Fold7 acceptance path to have been exercised and passed.

Confidence, architectural rationale, forensic evidence, or absence of known errors NEVER substitutes for an acceptance test that the claim logically requires.

## Required pre-handoff reconciliation

Before any implementation handoff or finalization, the agent MUST explicitly reconcile:

1. What exact end state did the human request?
2. What acceptance tests are necessary to prove that end state?
3. Which of those tests were actually executed?
4. What environment/device/OS/version was actually exercised?
5. What remains unvalidated?
6. Is any proposed wording or status stronger than the executed evidence?

If item 6 is yes, the agent MUST downgrade the wording/status before sending the handoff.

## Hard-stop rules

- Missing required validation is a HARD STOP on solution-level claims, regardless of CI confidence or implementation confidence.
- If the required validation cannot be executed with available tools, state the exact validation boundary. Do not imply that the missing test passed and do not promise background validation.
- A request for the "next eligible candidate" authorizes creation of a validation candidate after its applicable pre-device gates pass; it does NOT authorize calling that candidate a fix or solution before required runtime/device acceptance passes.
- Prefer `eligible for device validation` over `eligible candidate` when physical validation remains.
- Never hide the validation gap in a footer after leading with solution language. The status must be clear before or at the first artifact handoff.
- Do not use a filename, link label, release title, or artifact title that calls an unvalidated artifact a fix or solution.

## Required implementation handoff status

Every implementation artifact handoff MUST state one of the following, adjusted to the actual scope:

- `Validation status: BUILD-UNVERIFIED`
- `Validation status: BUILD-VERIFIED / DEVICE-UNVALIDATED`
- `Validation status: DEVICE-VALIDATED — <exact device/environment/path>`
- `Validation status: VALIDATED_SOLUTION — <exact validated scope>`

The status line is mandatory even when the human already knows the history.

## Language control before validation

Before VALIDATED_SOLUTION status, do not use these terms as unqualified descriptions of the artifact or outcome: `fix`, `solution`, `resolved`, `working`, `works`, `compatible`, `recommended`, `production-ready`, `ready`, `successful fix`, `potential solution`.

They may appear only when explicitly scoped to evidence that was actually proven, for example `build-compatible with API 37` after a successful API-37 build, provided that the wording cannot reasonably be mistaken for runtime/device compatibility.

## Failure handling

When physical/runtime validation fails:

1. Mark the tested candidate failed for that acceptance path.
2. Preserve the observed failure evidence.
3. Do not retroactively weaken or reinterpret the acceptance criterion merely to preserve candidate status.
4. Any successor starts again as BUILD_ARTIFACT or VALIDATION_CANDIDATE until the failed path is retested successfully.

This gate is additive to existing security, authorization, production-acceptance, dissent, provenance, and change-control requirements. It never weakens them.
