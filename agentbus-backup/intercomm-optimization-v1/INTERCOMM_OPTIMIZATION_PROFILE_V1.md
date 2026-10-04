# Intercommunication Optimization Profile V1 — Duo Open

**Status:** ACTIVE / SUPERSEDING CONTROL
**Project ID:** `duo-open`
**Canonical live coordination root:** `/DuoOpen-AgentBus`
**Project repository:** `boberino93-bit/duo-open`
**Effective:** `2026-10-04T00:12:30Z`

## 1. Authority and storage separation

The live Library/Artifactory AgentBus is the authoritative operational message board for this project. GitHub is **not** the live message board. Any GitHub copy of AgentBus/forum/message-board material is a downstream backup/recovery mirror only.

This restriction applies to coordination/message-board data. It does **not** demote the project's normal source-code repository: source code, branches, pull requests, releases, and normal project version control continue to use `boberino93-bit/duo-open` according to project governance.

Required backup ordering is:

1. write locally to the canonical AgentBus;
2. read back and validate the local object;
3. only then mirror eligible coordination data to GitHub;
4. record backup status/receipt locally when material.

A GitHub mirror MUST NOT overwrite newer local state, issue live work, acquire locks, decide tasks, or become authoritative merely because it is easier to access. Recovery from a mirror requires an explicit recovery event plus freshness/integrity validation.

## 2. Project identity and fail-closed routing

Before any mutation, bind and verify: project ID, canonical AgentBus root, target repository, intended branch/ref where applicable, active role, and applicable approval gates. Recent conversation context is not sufficient project authority.

Precedence is:

`CURRENT HUMAN INTENT -> PROJECT SCOPE GATE -> PROJECT IDENTITY LOCK -> LOCAL PROJECT STATE -> TASK EXECUTION`

Cross-project ambiguity, repository mismatch, namespace mismatch, stale identity data, or unavailable required authority MUST fail closed. Cross-project writes are denied unless an explicit sanitized bridge contract authorizes them.

## 3. Split-plane communication

Presence/liveness and durable project truth are separate planes.

**Ephemeral/cheap plane:** heartbeat, liveness, active-role presence, polling/service cadence, transient capacity observations. These signals may be refreshed frequently and must not require a durable message or Git commit when nothing material changed.

**Durable AgentBus plane:** material claims, findings, blockers, contradictions, dispositions, decisions, task ownership changes, handoffs, supersessions, release/recovery checkpoints, approval changes, or other events required to reconstruct project truth.

`NO_DELTA`, unchanged heartbeat, unchanged capacity counters, and repeated status prose MUST NOT produce standalone durable records.

## 4. Capacity reserve and UNKNOWN semantics

Capacity evidence is valid only when derived from one of:

- `EXPLICIT_CONFIG`
- `PROVIDER_OBSERVED`
- `ERROR_DERIVED`

If the hard limit or current usage cannot be defensibly verified, capacity state is `UNKNOWN`. Never infer unlimited capacity from absence of an error or documented ceiling.

Reserve fraction is `0.20`; safe operating ceiling is `0.80` of a verified hard limit. State thresholds over verified utilization are:

- `GREEN`: < 60%
- `AMBER`: >= 60% and < 75%
- `PRESERVE`: >= 75% and < 80%
- `RESERVE_ONLY`: >= 80% and below verified hard limit
- `EXHAUSTED`: >= verified hard limit
- `UNKNOWN`: evidence insufficient/stale

At `PRESERVE`, discretionary durable writes are suppressed and related nonurgent work is coalesced. At `RESERVE_ONLY`, only recovery-critical, authority-critical, or otherwise explicitly essential canonical writes are allowed. `UNKNOWN` fails closed for decisions that depend on spare capacity.

## 5. Write classes, coalescing, and deduplication

Every proposed durable write is classified as:

- `ESSENTIAL_CANONICAL` — required for reconstructable truth, authority, safety, recovery, or an explicit human instruction.
- `COALESCED_CHECKPOINT` — useful durable summary that combines multiple related nonurgent changes.
- `DISCRETIONARY` — convenience/diagnostic material that may be deferred or omitted under pressure.

Content-digest deduplication is mandatory for logical artifacts. If the normalized logical content digest is unchanged, disposition is `UNCHANGED_CONTENT` and a duplicate durable object/commit is not created.

Related nonurgent writes SHOULD be batched into one coherent checkpoint. A raw counter change alone is not sufficient reason for a capacity commit; publish when the capacity state or an actionable need changes.

## 6. Cross-project capacity signaling

Projects may expose a sanitized, read-only capacity signal using schema `org-agent-mesh/capacity-signal/v1`. Peer signals are advisory only. They never grant mutation authority in another project.

Permitted high-level needs are limited to:

`REVIEW_REQUIRED`, `PRIMARY_DECISION`, `RELEASE_PENDING`, `CAPACITY_PRESSURE`, `BLOCKED`

No secrets, raw domain data, personal data, unredacted research payloads, credentials, or unrestricted task content may cross this signal boundary.

Freshness MUST be evaluated per consumer. Missing or stale peer capacity data degrades to `UNKNOWN`; stale data may not be silently reused as current.

## 7. Task safety and continuity

Material work claims should use project-scoped identifiers, idempotency keys where applicable, explicit causation/supersession links, and lease/TTL semantics for temporary claims or locks. Expired or structurally invalid coordination objects are quarantined or ignored according to project rules rather than treated as current truth.

Append-only history is preserved. Supersession changes active interpretation; it does not erase historical evidence.

## 8. Role/package propagation

Primary, Manager/Reviewer, Research/Specialist, and successor/continuation packages must carry or reference this active profile. A generated role package that omits the current optimization profile, project identity binding, or backup-only AgentBus rule is stale and must fail package verification.

Package generation should deduplicate unchanged content and avoid generating a new package solely for heartbeat/no-delta state.

## 9. Validation requirements

Implementations enforcing this profile must cover at minimum:

- 20% reserve math and exact boundary behavior;
- `UNKNOWN` when evidence is unavailable or stale;
- `PRESERVE` and `RESERVE_ONLY` write filtering;
- digest deduplication;
- coalesced nonurgent writes;
- no durable heartbeat-only checkpoint;
- allowed high-level cross-project need set;
- peer-signal staleness -> `UNKNOWN`;
- project/repository/root mismatch -> fail closed;
- local-persist/readback before AgentBus backup mirror.


## Project-specific supersession

This profile supersedes the **durable checkpoint frequency requirement** in `ACTIVE_AGENT_SERVICE_INTERVAL_V1.md`. Liveness/presence may still be serviced frequently, but a NO_DELTA/heartbeat-only cycle MUST NOT create a durable AgentBus message or Git commit. Durable writes occur only for material state transitions, decisions, blockers, claims, findings, contradictions, handoffs, supersessions, release checkpoints, or recovery-critical events.

Existing human approval and production-write gates remain unchanged. This profile does not authorize product, device, release, or production actions that were previously gated.

## 10. Supersession rule

Where an older local coordination rule requires more frequent **durable** writes than this profile, this profile governs unless that older rule is explicitly marked safety/recovery-critical and cannot be satisfied through the ephemeral plane. All unrelated project-specific controls continue unchanged.
