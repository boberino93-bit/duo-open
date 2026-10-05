# Research Swarm Rollout Overlay — Duo Open

Status: `CANARY_RECOVERY_ALIGNED_TASKS_DISABLED`
Project ID: `duo-open`
Repository: `boberino93-bit/duo-open`
Project forum authority: `/DuoOpen-AgentBus/messages`
Canonical framework repository: `boberino93-bit/intercommunicationsenhancements`
Canonical serial-pipeline revision inspected: `1eb8e32b936d0fe534f68e26dc2af71f845df1ba`

This overlay binds Duo Open to the current three-stage scheduled design-analysis pipeline without creating a second control plane. Duo Open keeps its existing project-local authority, bootstrap, AgentBus, DMSH/3, handoff, review, lease, production-integration, and exact-action authorization rules.

The failed/timed-out 2026-10-05 canary attempts exposed a handoff mismatch: a Research stage could consume its runtime without a final READY marker, while downstream stages previously treated missing final READY as terminal. The current central contract fixes that cascade by making durable rolling progress checkpoints first-class inputs.

## Current serial schedule

The only active topology defined by the central schedule is:

1. `RESEARCHER_1` — minute `:00` through `:20`
2. `MANAGER` — minute `:20` through `:40`
3. `PRIMARY` — minute `:40` through the next `:00`

`RESEARCHER_2`, `RESEARCHER_3`, and global `MASTER` are not scheduled stages in this serial pipeline. Older five-role/fan-out material is historical and must not be used to infer current timing or handoff requirements.

Scheduled-task enablement is HUMAN-ONLY. A disabled automation is a deliberate control gate, not a failure to repair. Prompt, routing, migration, recovery, or repository changes must preserve the current enabled/disabled state unless Robert Leonard explicitly changes it.

## Mandatory checkpoint contract

Before substantive scheduled work, every stage must load the central `protocols/swarm_checkpoint_bus.md` and `research_swarm/checkpoint_envelope.schema.json` and use append-only comments on `boberino93-bit/intercommunicationsenhancements#25` as the scheduled stage-handoff transport.

For each `America/Vancouver` hourly `cycle_id`:

- Researcher publishes and readback-verifies sequence-0 `RESEARCH_PROGRESS` before expensive work, then higher-sequence progress after meaningful bounded units. `RESEARCH_HANDOFF_READY` is used only when coherently complete.
- Manager accepts the newest valid current-cycle `RESEARCH_PROGRESS` **or** `RESEARCH_HANDOFF_READY`, publishes/readback-verifies `MANAGER_PROGRESS`, and uses `MANAGER_HANDOFF_READY` only when coherently complete.
- Primary accepts the newest valid current-cycle `MANAGER_PROGRESS` **or** `MANAGER_HANDOFF_READY`, publishes/readback-verifies `PRIMARY_PROGRESS`, and uses `PRIMARY_PROPOSAL_READY` only for a durably persisted complete proposal.
- Stale prior-cycle checkpoints are not an implicit fallback.
- Earlier checkpoint comments are never edited or deleted; corrections are higher-sequence comments.
- The checkpoint bus carries coordination state only and grants no production/source mutation authority.

A stage must reserve enough of its 20-minute window to checkpoint and verify persistence. It must not start another bounded work unit when doing so would put the downstream handoff at risk.

## Duo startup / evidence rules

Before each scheduled role acts, load Duo Open's current `AGENT_BOOTSTRAP.json`, `AGENT_CONTEXT_REFERENCE.md`, `AGENT_DISCOVERY_V7.json`, current accepted AgentBus/handoff state when accessible, and live evidence newer than packaged snapshots. A repository snapshot does not prove complete current forum visibility.

Canonical central paths for scheduled work are:

- `research_swarm/five_task_schedule.json`
- `research_swarm/prompts/researcher_1.md`
- `research_swarm/prompts/manager.md`
- `research_swarm/prompts/primary.md`
- `protocols/swarm_checkpoint_bus.md`
- `research_swarm/checkpoint_envelope.schema.json`
- `protocols/primary_recurring_swarm_protocol.md`
- `protocols/post_normalization_successor.md`
- `research_swarm/STORAGE_HYGIENE_POLICY.md`
- `research_swarm/storage_budget.json`

The project-native AgentBus/Library remains authoritative for Duo project evidence where available. Its unavailability does not invalidate the GitHub issue checkpoint transport, but it limits what may be claimed as verified project state.

## Current Duo Fold7 frontier

The repository source tree is not, by itself, the latest materialized Fold7 runtime. Current Fold7 Beta2/S1* validation is reconstructed by pinned transforms and workflows. See `FOLD7_RUNTIME_SOURCE_OF_TRUTH.md` before interpreting `app/build.gradle.kts` or individual runtime source files as the deployable state.

The latest validated S1T materialization remains subject to physical Galaxy Z Fold7 validation. Do not promote build/test success into a physical continuity claim.

## Storage operating boundary

The physical internal Artifactory/account quota is 20 GiB combined across registered projects. The swarm operating cap is 16 GiB combined, preserving 4 GiB / 20% headroom. Avoid redundant artifacts, reuse canonical evidence, compact superseded working data, and perform safe hygiene when storage pressure rises.

At or above 16 GiB measured combined usage, nonessential internal growth stops until cleanup reduces usage. If combined usage cannot be measured, report `STORAGE_USAGE_UNKNOWN`, minimize bulky writes, and do not perform unverified deletion.

Historical Artifactory/message-board material may be pruned only after exact scope review, verification that it is not active/current truth, verification of durable GitHub backup where retention is required, valid project-local destructive authority, and post-delete effect verification. Current handoff, claims/leases/fences, blockers, pending decisions, unresolved contradictions, operative approvals, and evidence supporting active work remain protected.

## Recovery acceptance

The next canary run is acceptable only when it can demonstrate, for one current cycle, a readback-verified Research checkpoint, a Manager checkpoint referencing that Research checkpoint, and a Primary checkpoint referencing that Manager chain, without relying on stale-cycle state. A timeout after useful work is not allowed to erase the latest verified partial checkpoint.
