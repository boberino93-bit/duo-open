# Duo Open Minimal Controller Succession V1

**Status:** PROPOSED HIGH-IMPACT PROCESS CHANGE — REVIEW REQUIRED BEFORE MANDATORY ACTIVATION  
**Scope:** Primary/Manager controller succession only  
**New service/daemon:** NONE  
**Authority granted:** NONE

## 1. Goal

Allow one active controller chat/session to hand responsibility to a successor without inventing a new leader-election system, mutable controller database, background scheduler, or autonomous production authority.

Succession is a **revalidation handoff over the existing append-only event stream**.

## 2. Minimal FSM

`ACTIVE`
→ `HANDOFF_REQUESTED`
→ `SUCCESSOR_REVALIDATING`
→ (`SUCCESSOR_READY` | `BLOCKED_REVALIDATION`)
→ `OLD_CONTROLLER_RELEASED`
→ `ACTIVE_SUCCESSOR`

If the old controller disappears after `HANDOFF_REQUESTED`, a candidate successor may begin `SUCCESSOR_REVALIDATING`, but it cannot claim current alignment until every revalidation item below has been checked from authoritative sources.

## 3. Handoff record

Use an ordinary immutable AgentBus message. Do not create a parallel state service.

Minimum handoff payload:
- `fromController`
- `toController` or `candidateRole`
- `controllerEpoch`
- `githubHeadObserved`
- `protocolLockRefOrDigest`
- `lastBoardCursorOrTimestamp`
- `unresolvedLaneRefs[]`
- `openContradictionRefs[]`
- `managerDispositionRefs[]`
- `regressionBaselineRefOrDigest`
- `integritySnapshotRefOrDigest`
- `pendingHumanCommitState`
- `pendingArtifactRefs[]`
- `knownBlockedExternalActions[]`

`controllerEpoch` is continuity metadata only. It grants no capability and is not a production-write token.

## 4. Successor revalidation gate

Before `SUCCESSOR_READY`, the successor must independently:

1. fetch current GitHub `main` and record exact HEAD;
2. compare it with the handoff HEAD and mark drift explicitly;
3. load current discovery/protocol lock and mandatory contracts;
4. read durable AgentBus events newer than the handoff cursor/timestamp;
5. enumerate unresolved/closed research lanes relevant to the active campaign;
6. read current Manager/Reviewer dispositions and unresolved contradictions;
7. load the current regression baseline and identify invalidated/unknown rows;
8. verify current integrity/freshness state rather than assuming an old valid snapshot is current;
9. reconstruct any pending final-reconciliation/packaging state;
10. verify the human-controlled production boundary state.

If any required item cannot be established, state is `BLOCKED_REVALIDATION`, not assumed alignment.

## 5. Production boundary

Succession changes who coordinates the work; it does not change who may mutate production.

`SUCCESSOR_READY` does not imply:
- `PRIMARY_ACCEPTED`;
- `FINAL_RECONCILIATION_PASS`;
- `HUMAN_COMMIT_AUTHORIZATION`;
- Git write permission;
- production acceptance.

The human remains the explicit production mutation interlock. A production commit occurs only through the single designated commit-capable agent after human authorization.

## 6. Failure/recovery

### Stale handoff
If Git HEAD/protocol state/board state drifted, successor records the drift, consumes the delta, and revalidates. It does not force the room back to the older snapshot.

### Duplicate successors
Two candidates do not elect themselves via another service. They publish their revalidation records. Primary/Manager role rules plus newest valid explicit handoff/decision resolve ownership. If ambiguity remains material, work may continue in bounded research lanes while production finalization stays blocked.

### Missing old controller
No waiting indefinitely. Persisted evidence survives. Successor reconstructs from source truth + board + regression/integrity records.

### Pending human commit
A handoff must preserve whether a commit package exists, whether human authorization has actually occurred, and whether a designated single writer has acted. These are distinct states.

## 7. Anti-overengineering constraints

This succession design MUST NOT be expanded into a new leader-election daemon, distributed consensus protocol, mutable ROOM owner, lock server, or autonomous scheduler unless `ANTI_OVERENGINEERING_GATE_V1.md` Level-2 evidence is satisfied by a concrete observed failure.

Use the existing message stream and existing role authority first.

## 8. Adoption

Because controller succession touches continuity/authority interpretation, this file is a reviewed proposal rather than a silently activated high-risk rule. Manager/Reviewer should check it against current DMSH/3, discovery, integrity, regression, and human-interaction contracts; Primary may then accept/supersede it.
