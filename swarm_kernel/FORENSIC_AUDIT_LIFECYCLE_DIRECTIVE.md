# Forensic Audit Standard — Maximum-Detail Evidence and Lifecycle Directive

Applies to PRIMARY, MANAGER, and RESEARCH whenever a debug bundle, crash report, field trace, regression report, implementation candidate, architecture, protocol, workflow, or subsystem is described as being **forensically** audited or analyzed.

## Meaning of “forensic” — HARD REQUIREMENT

Within the requested/relevant scope, **forensic means the most detail-oriented, evidence-first, failure-seeking version of that analysis that can reasonably be performed with the available evidence and tools.**

A forensic task is not satisfied by a normal summary, a likely-cause explanation, a happy-path review, or an audit limited to the most obvious subsystem. The investigator must actively search for hidden contradictions, lifecycle failures, race conditions, stale authority, negative evidence, cross-layer coupling, recovery defects, untested assumptions, and alternative causal explanations.

The required standard is:

- reconstruct before concluding;
- prefer timestamped chronology over narrative intuition;
- distinguish direct observation, derived fact, inference, hypothesis, and unknown;
- test competing hypotheses rather than stopping at the first plausible explanation;
- search for evidence that would falsify the leading hypothesis;
- inspect both positive and negative evidence (what happened and what conspicuously did not happen);
- reconcile logs, source, configuration, persistent state, services, processes, runtime/platform behavior, and user-observed symptoms where applicable;
- inspect boundary conditions, reversals, restarts, failures, timeouts, stale callbacks, partial writes, privilege loss, service death, process death, and recovery paths;
- identify every material assumption and mark it as proven, unsupported, or falsified;
- explicitly document evidence gaps rather than silently converting them into confidence;
- compare BEFORE / AFTER / CURRENT / BASELINE state when temporal evolution matters;
- preserve exact identities, generations, leases, timestamps, versions, branches, devices, environments, and other provenance needed to reproduce the conclusion;
- examine adjacent systems when their shared state, lifecycle, ownership, resources, or authority could affect the reported symptom;
- include implementation and validation implications for every confirmed defect when remediation is requested.

If available evidence or access prevents that standard from being reached, the result must be labeled `PARTIAL_FORENSIC_AUDIT` with the exact missing evidence/tests required to complete it.

## Mandatory forensic reconstruction dimensions

A full forensic analysis must address all materially relevant dimensions below, marking non-applicable ones explicitly rather than silently omitting them:

1. **Chronology** — reconstruct event order with monotonic/wall-clock timing where available; correlate user-visible symptoms with internal state changes.
2. **State / authority** — identify who owned state at every important boundary, including generations, leases, tokens, epochs, process/service ownership, and stale-authority rejection.
3. **Data flow** — trace input → transformation → persistence/cache → consumer → visible/runtime outcome.
4. **Control flow** — trace callbacks, asynchronous work, queues, gates, retries, timeouts, cancellation, and reversal paths.
5. **Concurrency / races** — inspect overlapping tasks, shared mutable state, executor/dispatcher interactions, callbacks during construction/destruction, and out-of-order completion.
6. **Persistence / lifecycle** — apply the lifecycle matrix below to every materially involved stateful feature.
7. **Resource ownership** — inspect bitmap/surface/file/stream/socket/process/coroutine/executor ownership, retention, duplication, recycling, cleanup, and peak-memory amplification.
8. **Error handling** — inspect exceptions, ignored return values, `runCatching` fallbacks, silent defaults, timeout behavior, partial failure, and whether failure is distinguishable from success.
9. **Platform boundary** — distinguish app behavior from Android/Samsung/framework behavior; do not attribute platform latency or hidden-API semantics to app logic without evidence.
10. **Security / privilege** — preserve permission, secure-content, shell/Shizuku, and ownership boundaries; verify no fix weakens an existing security invariant.
11. **Regression surface** — inspect adjacent features that share code/state/process/service/storage/resources with the changed path.
12. **Validation coverage** — map each conclusion and claimed end state to the exact test/evidence that supports it.
13. **Counterfactual / falsifier** — state what evidence would prove the current leading explanation wrong and, where feasible, add instrumentation/tests to obtain it.
14. **Unknowns** — list unresolved questions whose answers could materially alter the conclusion.

## Mandatory lifecycle / persistence matrix

A forensic audit MUST NOT limit itself to the subsystem that produced the most obvious telemetry.

For every user-visible stateful feature touched by the candidate or present in the reported reproduction path, explicitly evaluate the following lifecycle boundaries when applicable:

1. **Immediate use** — feature works directly after mutation/setup.
2. **Activity recreation** — state survives recomposition/configuration/activity recreation where product semantics require it.
3. **App background/resume** — state remains valid after leaving and returning to the app.
4. **App process restart** — durable state can be reconstructed after process death/relaunch.
5. **Service coexistence/restart** — app UI and long-lived services do not corrupt, race, or retain incompatible copies of the same state.
6. **Device/runtime restart where relevant** — persistent configuration and storage are not incorrectly treated as in-memory authority.
7. **Storage mutation integrity** — writes are checked for success; replacement/rename/copy operations are atomic or explicitly recoverable; temporary files cannot be promoted as success without a durable commit receipt.
8. **State-version integrity** — version counters/metadata must advance only after the durable payload mutation succeeds. Metadata and payload may never be allowed to diverge silently.
9. **Rehydration failure handling** — missing, corrupt, revoked, stale, or incompatible persisted data must fail safely, remain responsive, and produce diagnostics rather than freezing or crashing the app.
10. **Memory/resource ownership** — large bitmaps, surfaces, file handles, coroutine jobs, and service/UI shared objects must be checked for duplicate ownership, leaks, stale references, and restart-time amplification.
11. **Crash/freeze evidence** — prior-process exit reason, ANR/OOM evidence, uncaught exceptions, and lifecycle timing must be reviewed whenever a user reports a freeze, crash, restart, or state loss.
12. **Cross-feature regression** — a subsystem-specific candidate is not cleared merely because its own telemetry is healthy; adjacent persistent UI/configuration flows must be checked if the candidate preserves or reuses them.

## Evidence classification

For each material finding and each lifecycle boundary, classify the evidence as one of:

- `DIRECTLY_CONFIRMED`
- `DERIVED_CONFIRMED`
- `SUPPORTED_HYPOTHESIS`
- `FALSIFIED_HYPOTHESIS`
- `CONFIRMED_PASS`
- `CONFIRMED_FAILURE`
- `NOT_EXERCISED`
- `INSUFFICIENT_EVIDENCE`
- `NOT_APPLICABLE`
- `UNKNOWN`

`NOT_EXERCISED`, `INSUFFICIENT_EVIDENCE`, and `UNKNOWN` are never passes.

Absence of an exception in a debug bundle is never proof that persistence/restart behavior is correct. Absence of a telemetry marker is only meaningful when the instrumentation contract proves the marker should have been emitted under the tested condition.

## Required output structure for forensic work

Unless a stricter project-local format exists, a forensic result should preserve this minimum structure:

1. **Scope and evidence inventory** — exact artifacts, versions, hashes, devices/environments, source refs, and missing evidence.
2. **Reconstructed chronology** — timestamped/ordered sequence of material events.
3. **Confirmed findings** — direct and derived facts only.
4. **Competing hypotheses** — including evidence for/against each and explicit falsifiers.
5. **Lifecycle/persistence matrix** — all materially involved stateful features.
6. **Cross-layer / adjacent-system findings** — shared resources, state, services, platform boundaries, and regressions.
7. **Root-cause assessment** — strongest supported causal chain, with confidence constrained by evidence class.
8. **Implementation implications** — minimal safe remediation, invariants to preserve, and risks.
9. **Validation plan / results** — automated, emulator, device, restart, recovery, and negative tests mapped to claims.
10. **Residual unknowns** — exact gaps that prevent stronger claims.

## Implementation rule

When a forensic audit discovers a persistence or lifecycle defect:

- correct the durable-state transaction first (payload + metadata + commit receipt);
- make rehydration bounded and failure-safe;
- add regression coverage for at least mutation -> reopen/restart -> rehydrate;
- test failure injection for corrupt/missing/failed replacement state where practical;
- check service/UI coexistence and peak resource use;
- preserve unrelated validated architecture unless evidence requires changing it;
- add diagnostic receipts where the prior evidence was insufficient to distinguish success from failure;
- include the lifecycle result in the engineering decision log and final validation classification.

## Completion gate

A forensic audit is incomplete until all materially relevant reconstruction dimensions above have either been examined or explicitly marked `NOT_APPLICABLE`, and every materially involved stateful feature has a lifecycle/persistence matrix.

A narrow timing/rendering/source review that omits relevant lifecycle, resource, concurrency, failure, or adjacent-system analysis must be labeled `PARTIAL_FORENSIC_AUDIT` and cannot support a full-regression, root-cause-complete, or solution-level claim.
