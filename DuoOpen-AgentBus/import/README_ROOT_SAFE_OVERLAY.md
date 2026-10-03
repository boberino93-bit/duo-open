# Duo Open AgentBus Round Orchestration + SP4.2 root-safe overlay

Extract this archive **directly into the repository root** of `boberino93-bit/duo-open`. It is based on current main/application baseline `1cf46d7505ee74a8f4434be6d77a890ddce57ac1`.

## What is included

- Full current `DuoOpen-AgentBus/` mirror carried forward from the previous canonical overlay plus all live deltas through the canonical round-orchestration refresh.
- Complete message-forum backup: **699 files** (**698 JSON + 1 historical Markdown handoff**).
- Latest forum record: `20261003T040500Z__primary__all__canonical-round-orchestration-refresh-complete.json`.
- Canonical role packages:
  - Primary V8 `DUO_OPEN_PRIMARY_AGENT_V8_ROUND_ORCHESTRATION.zip`
  - Manager/Reviewer V6 `DUO_OPEN_GEN7_MANAGER_REVIEWER_AGENT_V6_ROUND_ORCHESTRATION.zip`
  - Research V6 `DUO_OPEN_GEN7_RESEARCH_AGENT_V6_ROUND_ORCHESTRATION.zip`
- Round Orchestration V1 controller, schemas, stable `ROUND_ENTRY.md` / `JOIN_ROUND.md`, role bootstrap prompts, and non-preemptive help policy.
- Hard orchestration ceiling: **20 concurrent sessions**, including Primary.
- Physical chat-spawn adapter state: **MANUAL_FALLBACK** until a native/host adapter is actually validated.
- Existing cumulative SP4.2 workflow, service-pack, patcher and hotfix lineage.

## Current engineering priority

The INNER-screen issue remains P0. Field evidence is that the inner panel stays dark until roughly 50-60 degrees, the first opening animation crashes/recoveries, and later animations become smooth once the inner display/system is established. This package does **not** claim that physical problem is solved.

## GitHub write status

A direct GitHub push was attempted from the connected integration and returned `403 Resource not accessible by integration`. No GitHub write is claimed. This archive is therefore the complete root-safe publication vehicle: extract it, review, then commit the resulting changes to `main`.

## Apply

1. Extract into repository root.
2. Allow overwrite of existing AgentBus/SP4.2 paths.
3. Your existing root `README.md` is not included or replaced.
4. Run `python DuoOpen-AgentBus/import/VERIFY_ROOT_SAFE_OVERLAY.py .`.
5. Commit/push the resulting changes.

The archive preserves old canonical role ZIPs for lineage but the new registry marks V8/V6/V6 as canonical.
