# PROJECT SCOPE SELECTION GATE V1

Status: MANDATORY BOOTSTRAP / FAIL-CLOSED
Project: Duo Open
Repository: `boberino93-bit/duo-open`

## Purpose

Prevent cross-project contamination, accidental writes to the wrong repository, and implicit inheritance of project state when an agent/session is started from shared organizational tooling or reusable agent packages.

## Mandatory rule for every newly started agent/session

Before reading project-specific work queues, claiming work, publishing AgentBus messages, creating artifacts, changing files, committing, opening pull requests, or performing any other project mutation, the agent MUST establish the intended project.

1. If the user's current instruction explicitly and unambiguously names the project/repository, the agent may bind to that project without asking a redundant question.
2. If the project is not explicitly and unambiguously specified, the agent MUST ask the user which project it is intended to work on before doing project-specific work.
3. The agent MUST NOT infer the project merely from the currently open repository, inherited chat/session context, a nearby working tree, a previous agent's task, a default path, or the fact that this bootstrap file was discoverable.
4. Until project identity is resolved, the agent is READ/WRITE BLOCKED for all project repositories, AgentBus forums, artifact stores, task ledgers, and release outputs.

## Duo Open binding

An agent bound to Duo Open MUST verify all of the following before any write:

- `project_id == duo-open`
- repository target is exactly `boberino93-bit/duo-open`
- AgentBus target is under `/DuoOpen-AgentBus/`
- any artifact/message metadata identifies `duo-open`
- the active task is within Duo Open scope

If any value is missing, conflicting, or points to another project, the operation MUST fail closed.

## Cross-project rule

Shared organizational frameworks may be read or copied under an explicit import/promotion process, but project state MUST remain isolated.

A Duo Open agent MUST NOT write Benefits Maximizer, Warp Propulsion Lab, or any other project's code, forum messages, research state, artifacts, manifests, or task records into this repository. Likewise, Duo Open-specific state MUST NOT be exported into another project's writable namespace except through an explicit, deliberate transfer artifact that is sanitized for the destination.

Cross-project access is read-only by default. Cross-project writes require a separately authorized transfer with both source and destination named.

## Human interaction requirement

When ambiguity exists, use a concise project-selection question such as:

> Which project should I bind this agent to: Duo Open, Benefits Maximizer, or another project?

Do not ask this question when the current user instruction already names the project clearly.

## Relationship to NO_NEW_AGENTS_V1

`NO_NEW_AGENTS_V1.md` remains authoritative while its freeze is active. This gate does not authorize spawning a new agent/session. It defines the mandatory scope-resolution behavior for any future new agent after the human explicitly permits new-agent creation.

## Propagation

Every Duo Open successor/bootstrap/initiation/deployment package created after this contract is adopted MUST include this file and MUST put it in the mandatory bootstrap sequence before any project-specific task execution.

## Failure policy

Unknown project -> ASK USER, DO NOT WRITE.
Conflicting project metadata -> STOP, DO NOT WRITE.
Repository mismatch -> STOP, DO NOT WRITE.
AgentBus/artifact namespace mismatch -> STOP, DO NOT WRITE.

There is no implicit/default writable project.
