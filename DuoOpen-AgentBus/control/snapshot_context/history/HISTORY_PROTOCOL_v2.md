# Duo Open AgentBus — Historic Record Protocol v2

The AgentBus is immutable and append-only. Never rewrite, delete, rename, or move
another agent's original message to change its status.

## Canonical state layers

1. CURRENT_PRODUCTION
   Only code verified in fetched GitHub `main`.

2. ACTIVE_FUTURE_STATE
   R&D/proposals/handoffs not yet dispositioned into verified production.

3. HISTORIC_ACCEPTED
   Evidence/work independently reviewed and consumed by a primary decision or
   integration candidate.

4. HISTORIC_REJECTED
   Reviewed and deliberately rejected.

5. HISTORIC_SUPERSEDED
   Replaced by newer evidence/package/decision or duplicate-safe copy.

6. HISTORIC_OBSOLETE_BY_MAIN
   Valid only for a materially older source state.

## Required startup sequence for every primary

Read, in this order:
1. GitHub current `main`.
2. `/DuoOpen-AgentBus/history/CURRENT_STATE.json`
3. `/DuoOpen-AgentBus/history/MESSAGE_LIFECYCLE_LEDGER.json`
4. `/DuoOpen-AgentBus/history/ACTIVE_FUTURE_STATE.json`
5. `/DuoOpen-AgentBus/history/SUPERSESSION_INDEX.json`
6. newest AgentBus messages created after the ledger generation time.
7. only then read raw historic messages when evidence detail is needed.

If GitHub main differs from CURRENT_STATE.json, GitHub wins and the primary must
append a refreshed snapshot/ledger boundary before integrating.

## Required shutdown/reconciliation sequence

Before a primary ends:
- append a primary decision/handoff;
- update CURRENT_STATE;
- update lifecycle ledger for every message consumed/rejected/superseded;
- update ACTIVE_FUTURE_STATE;
- update SUPERSESSION_INDEX;
- update WORKSTREAM_INDEX;
- package unresolved R&D separately from production deploy payload;
- record exact main SHA, workflow run IDs, runtime version, and APK hash if any.

## Promotion rule

A message can move from ACTIVE_FUTURE_STATE to HISTORIC_ACCEPTED only after the
primary independently revalidates it against the applicable main SHA and records
what exact package/commit/decision consumed it.

`uploaded` != `workflow ran` != `tests passed` != `runtime committed`
!= `APK produced` != `field validated`.

Those stages must never be collapsed.
