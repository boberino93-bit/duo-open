# Duo Open Deployment AgentBus Snapshot Contract V1

Status: MANDATORY / FAIL-CLOSED  
Project: `duo-open` / Duo Open / Duo Screen  
Writable repository: exactly `boberino93-bit/duo-open`

## Purpose

Prevent deployment, successor, bootstrap, initiation, recovery, or role packages from losing the project-identity safeguards that protect Duo Open from cross-project misbinding.

This contract exists because a recovery attempt on 2026-10-03 followed recent context from another project before revalidating Duo Open. Live-repo protection is insufficient if a newly generated package omits the protection.

## Mandatory identity payload

Every newly generated PRIMARY, MANAGER/REVIEWER, RESEARCH/SPECIALIST, successor, bootstrap, initiation, recovery, or main-deployment package MUST contain, from the exact source revision used to build that package:

1. `DuoOpen-AgentBus/PROJECT_SCOPE_SELECTION_GATE_V1.md`
2. `DuoOpen-AgentBus/REPOSITORY_IDENTITY_LOCK.json`
3. `DuoOpen-AgentBus/AGENT_DISCOVERY.json`
4. `DuoOpen-AgentBus/BOOTSTRAP.md`
5. `DuoOpen-AgentBus/NO_NEW_AGENTS_V1.md` while that human freeze remains active
6. the applicable AgentBus `/messages/` snapshot required by the package

The package must preserve the bootstrap order in `AGENT_DISCOVERY.json`: project scope gate first, repository identity lock second, before project-specific handoff/task state is treated as actionable.

## Required package metadata

The deployment metadata/checksum manifest MUST record at minimum:

- `project_id=duo-open`
- `repository=boberino93-bit/duo-open`
- `agentbus_root=DuoOpen-AgentBus/`
- exact source Git revision/HEAD
- SHA-256 or equivalent integrity digest for every required identity artifact included in the package
- package role/type
- current human agent-spawn/freeze state

## Fail-closed validation

A package is INVALID and MUST NOT be presented as ready when any of the following is true:

- a mandatory identity artifact is missing;
- the package's project id, repository, or AgentBus namespace differs from `REPOSITORY_IDENTITY_LOCK.json`;
- `PROJECT_SCOPE_SELECTION_GATE_V1.md` or `REPOSITORY_IDENTITY_LOCK.json` is ordered after project-specific handoff/task state in the effective bootstrap sequence;
- artifact contents do not match the exact declared source revision;
- checksum/readback verification fails;
- another project's accepted state, task queue, handoff, credentials, private data, or writable namespace has been imported as Duo Open authority;
- the package would instantiate a new agent/session while `NO_NEW_AGENTS_V1.md` remains active.

## Recovery rule

A packaged recovering agent does not inherit writable scope from the most recent chat, memory, previous project, prior handoff, current working directory, neighboring repository, or whatever project was touched last.

Recovery order is:

`CURRENT USER PROJECT INTENT -> PROJECT_SCOPE_SELECTION_GATE -> REPOSITORY_IDENTITY_LOCK -> LOCAL AGENTBUS/HANDOFF -> TASK EXECUTION`

If current project intent is ambiguous, the agent asks the user and writes nowhere until resolved.

## Cross-project boundary

Other repositories may be consulted read-only when separately permitted, but their state cannot become Duo Open write authority merely because it is recent, accessible, or included in context. Any cross-project transfer must be explicitly authorized and name both source and destination.

## Verification requirement

After any package builder or packaging workflow is changed, perform readback verification on the resulting package contents. Confirm all required identity artifacts are present, internally consistent, and checksum-covered before marking packaging complete.

If no dedicated package builder exists for a package type, the agent assembling it manually is responsible for the same validation. Documentation-only compliance is not sufficient.

## Non-expansion rule

This is a minimal safeguard for a witnessed failure. It does not create a new controller, daemon, lease system, authority hierarchy, agent-spawn permission, or background process.
