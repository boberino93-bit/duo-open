# Forensic Audit Lifecycle / Persistence Directive

Applies to PRIMARY, MANAGER, and RESEARCH whenever a debug bundle, crash report, field trace, regression report, or implementation candidate is being forensically audited.

## HARD REQUIREMENT

A forensic audit MUST NOT limit itself to the subsystem that produced the most obvious telemetry.

For every user-visible stateful feature touched by the candidate or present in the reported reproduction path, the audit MUST explicitly evaluate the following lifecycle boundaries when applicable:

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

For each lifecycle boundary, classify findings as one of:

- `CONFIRMED_PASS`
- `CONFIRMED_FAILURE`
- `NOT_EXERCISED`
- `INSUFFICIENT_EVIDENCE`
- `NOT_APPLICABLE`

`NOT_EXERCISED` and `INSUFFICIENT_EVIDENCE` are not passes.

Absence of an exception in a debug bundle is never proof that persistence/restart behavior is correct. If the bundle does not exercise a boundary, the audit must say so explicitly and either add an automated regression test/probe or require that physical/runtime validation before a solution-level claim.

## Implementation rule

When a forensic audit discovers a persistence or lifecycle defect:

- correct the durable-state transaction first (payload + metadata + commit receipt);
- make rehydration bounded and failure-safe;
- add regression coverage for at least mutation -> reopen/restart -> rehydrate;
- preserve unrelated validated architecture unless evidence requires changing it;
- include the lifecycle result in the engineering decision log and final validation classification.

## Completion gate

A forensic audit is incomplete until it includes a lifecycle/persistence matrix for the stateful features materially involved in the report or candidate. A narrow timing/rendering analysis without that matrix must be labeled `PARTIAL_FORENSIC_AUDIT` and cannot support a full-regression or solution-level claim.
