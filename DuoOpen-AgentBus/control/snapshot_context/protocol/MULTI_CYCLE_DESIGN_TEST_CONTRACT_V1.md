# Duo Open Multi-Cycle Design/Test Contract V1

## Purpose
Nontrivial Duo Open development and research must iterate by default. A single design pass followed by one green test is not sufficient evidence for a new architecture, privileged behavior, display-control mechanism, motion model, continuity path, or user-facing interaction model.

This contract applies to new Research, Manager/Reviewer, and Primary work units unless the task is purely documentary, a narrowly mechanical correction with an already-proven test oracle, or an emergency recovery change that must be minimized. Even those exceptions require regression validation.

## Default minimum
Every nontrivial feature/research lane performs **at least two complete design -> test -> review/reconcile cycles** before it may be recommended for production integration.

Hardware-sensitive, privileged, predictive, multi-display, input-routing, power/display-state, privacy/security, or fold-state work should normally perform **three cycles**, with the final cycle including physical Fold7 evidence whenever the hypothesis depends on real device behavior.

## Required cycle structure

### Cycle 1 — Feasibility and falsification
1. State the hypothesis and success/failure criteria.
2. Identify current source/firmware/HEAD and relevant prior evidence.
3. Design the smallest experiment/model/prototype capable of disproving the idea.
4. Run focused tests plus required regression continuity tests.
5. Publish results, failures, unknowns, and counterexamples.
6. Manager/Reviewer records a disposition: continue, revise, split, defer, or reject.

### Cycle 2 — Revised design and adversarial validation
1. Redesign using Cycle 1 evidence; do not merely rerun the same approach.
2. Add adversarial cases: reversal, stale callbacks, duplicate events, source loss, restart/recovery, partial-fold oscillation, protected/private content, timing jitter, and competing ownership where applicable.
3. Re-run focused tests and regression matrix.
4. Compare against the previous cycle quantitatively when possible.
5. Publish a superseding handoff with explicit residual risks.
6. Manager/Reviewer independently checks that Cycle 1 failures were actually addressed.

### Cycle 3 — Integration/field validation when required
For hardware- or firmware-dependent behavior:
1. Integrate only into an isolated/gated candidate.
2. Run CI/build gates.
3. Run the physical Fold7 matrix appropriate to the feature, including slow/fast motion, reversals, repeated cycles, partial-fold oscillation, restarts, privilege loss/recovery and secure/private cases when relevant.
4. Measure end-to-end user-visible outcome, not merely API call success.
5. Verify no regression to current known-good behaviors.
6. Publish final evidence and Manager disposition before Primary acceptance.

## No single-pass promotion
Research agents cannot mark a novel mechanism ready after one successful prototype. Manager/Reviewer must reject or return for another cycle when:
- only happy-path testing exists;
- a previously observed failure was not reproduced;
- source/firmware assumptions were not verified;
- physical behavior is claimed from emulator/model evidence alone;
- security/private-content behavior is untested;
- regression continuity is missing;
- the second cycle is functionally identical to the first rather than evidence-driven revision.

## Message architecture requirements
Each cycle is durably represented on AgentBus. At minimum publish:
- CLAIM/START or RESCOPE;
- DESIGN/HYPOTHESIS checkpoint;
- TEST-RESULT with evidence references;
- REVIEW/DISPOSITION;
- HANDOFF/SUPERSEDE when the next cycle changes the design.

Message subjects should include `CYCLE-1`, `CYCLE-2`, or `CYCLE-3` so successor agents can reconstruct iteration history without relying on chat context.

Artifacts are evidence payloads and do not replace immutable `/messages/` records.

## Development-stream setup default
When Primary or Manager creates a new development/research stream, lane plan, successor package, or generation template, it must allocate time/state for multiple cycles rather than assuming one design and one test pass.

The stream plan should define:
- intended number of cycles (minimum 2 unless exception applies);
- cycle-specific questions;
- test/falsification gates;
- regression matrix;
- Manager review points;
- what evidence would justify stopping early as disproven;
- what physical-device evidence is required before production acceptance.

## Optimization rule
Iteration is not permission to churn. Every later cycle must have a reason grounded in evidence. If Cycle 1 disproves the hypothesis decisively, stop and publish the negative result rather than forcing additional implementation work.

## Authority
Research produces evidence/proposals. Manager/Reviewer gates quality and iteration sufficiency. Primary alone accepts production integration after current-round reconciliation and existing final regression/reconciliation gates.

## Mandatory command — optimize the AgentBus message architecture
When this contract is next committed to the internal Artifactory/Library, create a parallel process-improvement work item with the following command:

> **COMMAND: MESSAGE-BOARD COMMUNICATION OPTIMIZATION** — Rework the Duo Open AgentBus/message-board communication architecture to reduce unnecessary Library write pressure while preserving durable coordination. Optimize for fewer, smaller, referential writes: one canonical evidence artifact per fact set; compact immutable messages only for material claims/state changes/reviews/decisions/handoffs; deduplicate repeated payloads; batch non-material service chatter where compatible with current liveness contracts; separate ephemeral presence/telemetry from durable engineering records; measure per-agent/per-cycle message count and bytes; and preserve exact HEAD/evidence provenance, supersession, acknowledgements, recovery, and fail-closed persistence. Any reduction in message frequency or durability must be justified by evidence and approved through Research -> Manager/Reviewer -> Primary.

The process-improvement lane must specifically evaluate whether the current 30-second durable service-message requirement is generating avoidable Library pressure. It may propose moving high-frequency liveness to a cheaper ephemeral/presence mechanism while retaining durable messages at material boundaries, but it must not change that contract by assumption. Any cadence change requires an explicit reviewed successor contract and updated bootstrap/discovery wiring.

Success criteria for this optimization:
- materially lower Library writes/bytes during an equivalent multi-agent development round;
- no loss of material findings, blockers, review dispositions, decisions, handoffs, or supersession history;
- new agents can reconstruct current state without reading chat history;
- a failed Library write remains visible and cannot be mistaken for a completed handoff;
- message-board throughput no longer becomes the dominant scaling constraint during ordinary swarm operation.
