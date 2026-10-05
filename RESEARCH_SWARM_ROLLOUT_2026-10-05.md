# Research Swarm Rollout Overlay — Duo Open

Status: ACTIVE PRE-FIRST-SCHEDULED-RUN
Project ID: `duo-open`
Repository: `boberino93-bit/duo-open`
Project forum authority: `/DuoOpen-AgentBus/messages`
Canonical framework repository: `boberino93-bit/intercommunicationsenhancements`
Canonical framework revision: `db46c9ab0316f5ad1fab38ce6552387d01991842`

This overlay distributes the post-hardening recurring research-swarm launcher into Duo Open without copying the framework implementation into this repository. Duo Open keeps its existing project-local authority, bootstrap, AgentBus, DMSH/3, handoff, review, lease, and production-integration rules. The central framework is consumed by exact revision as a shared protocol dependency; this overlay does not create a second control plane.

Before each scheduled role acts, it must load Duo Open's current `AGENT_BOOTSTRAP.json`, `AGENT_CONTEXT_REFERENCE.md`, `AGENT_DISCOVERY_V7.json`, current accepted AgentBus/handoff state, and any live delta newer than packaged snapshots, then read the applicable central role prompt and storage policy at the canonical revision above.

Canonical central paths include `protocols/primary_recurring_swarm_protocol.md`, `protocols/post_normalization_successor.md`, `research_swarm/five_task_schedule.json`, `research_swarm/STORAGE_HYGIENE_POLICY.md`, `research_swarm/storage_budget.json`, and `research_swarm/prompts/{master,manager,researcher_1,researcher_2,researcher_3}.md`.

## Storage operating boundary

The physical internal Artifactory/account quota is 20 GiB combined across registered projects. The swarm operating cap is 16 GiB combined, preserving 4 GiB / 20% headroom. Duo Open agents must contribute to that portfolio limit by avoiding redundant artifacts, reusing canonical evidence, compacting superseded working data, and performing safe hygiene work whenever storage pressure rises.

At or above 16 GiB measured combined usage, nonessential internal growth stops until cleanup reduces usage. If combined usage cannot be measured, report `STORAGE_USAGE_UNKNOWN`, minimize bulky writes, and do not perform unverified deletion.

Historical Artifactory/message-board material may be pruned only after exact scope review, verification that it is not active/current truth, verification of durable GitHub backup where retention is required, valid project-local destructive authority, and post-delete effect verification. Current handoff, claims/leases/fences, blockers, pending decisions, unresolved contradictions, operative approvals, and evidence supporting active work remain protected.

Duo Open's repository snapshot/backup remains historical/recovery evidence; it does not by itself prove full current AgentBus visibility.

## Hourly behavior

Scheduled wake-ups are opportunities for useful work, not quotas for producing files. When no material research delta exists, useful work can be dedupe, compaction, backup verification, stale cache cleanup, evidence indexing, checkpoint hygiene, or a compact `NO_MATERIAL_DELTA` state update. Never manufacture filler artifacts to justify a run.

The first scheduled invocation must occur only after this overlay is present on the default branch.
