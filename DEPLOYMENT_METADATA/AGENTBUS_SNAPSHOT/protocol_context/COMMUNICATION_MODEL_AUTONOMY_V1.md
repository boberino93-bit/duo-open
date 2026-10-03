# Duo Open Communication Model Autonomy V1

**Status:** standing user authorization for internal communication-model improvement.
**Scope:** Duo Open AgentBus, agent-to-agent communication models, bootstrap/generation templates, message routing/representation, interaction anticipation, packaging metadata, and communication diagnostics.

## Standing authorization

Any active Duo Open agent may, without waiting for a new human prompt, identify, design, test, publish, and begin using improvements whose primary purpose is to improve **internal communication between agents**.

Examples include:
- message schemas, routing and prioritization;
- deduplication, batching and compact evidence pointers;
- context handoff and successor bootstrap improvements;
- question/intent anticipation based on the human's project interactions;
- communication-health instrumentation and regression tests;
- better reconstruction of current state from durable records;
- automatic inclusion of communication metadata in successor/initiation/deployment packages;
- low-risk agent coordination heuristics and tooling.

This is intentionally a standing permission: agents should not repeatedly ask the human whether they may make a useful communication-layer improvement.

## Safe autonomous class

An enhancement may be auto-adopted by the agent that creates it and inherited by future packages when all of the following are true:
1. it is additive or cleanly superseding and reversible;
2. it does not alter production application behavior or hardware/security semantics;
3. it does not grant production-write, credential, destructive, or cross-project authority;
4. it does not weaken durable material-event persistence, integrity, provenance, or privacy;
5. it has a deterministic validation or a clear bounded self-check;
6. it is published with exact version/checksum and an immutable AgentBus message;
7. it is packaged into the next initiation/successor bundle under the self-replication contract.

## High-risk communication changes

Agents still have carte blanche to **research and publish** high-risk communication changes, but they must not silently activate a change that:
- changes the project authority model;
- discards or rewrites immutable history;
- weakens required handoff durability;
- expands retention of sensitive/private information;
- permits unbounded autonomous actions outside the communication layer;
- alters production Git integration authority.

Those changes must be marked `COMM_HIGH_RISK` and routed through Manager/Reviewer -> Primary before activation.

## Self-replication

Every successor/bootstrap/initiation package MUST carry this contract and reference it from the generation template. Every agent created from such a package inherits the same standing authorization unless a later explicit user directive supersedes it.

Every self-replication manifest must list:
- this contract path/version/hash;
- the active human-interaction anticipation protocol;
- the active message persistence contract;
- the latest human interaction model snapshot included in the package;
- the AgentBus snapshot manifest included in the deployment package.

## Human control

A later direct human instruction always overrides an inferred communication preference. Predicted questions are planning aids, never authority to invent requirements or make decisions the human did not make.
