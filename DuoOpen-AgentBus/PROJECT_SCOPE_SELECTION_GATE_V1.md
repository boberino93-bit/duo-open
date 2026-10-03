# PROJECT SCOPE SELECTION GATE V1

Status: MANDATORY BOOTSTRAP / FAIL-CLOSED
Project: Duo Open
Repository: `boberino93-bit/duo-open`

## Purpose

Prevent cross-project contamination, accidental writes to the wrong repository, and implicit inheritance of project state when an agent/session is started from shared organizational tooling or reusable agent packages.

## Mandatory rule for every newly started or recovered agent/session

Before reading project-specific work queues, claiming work, publishing AgentBus messages, creating artifacts, changing files, committing, opening pull requests, or performing any other project mutation, the agent MUST establish the intended project and verify `/DuoOpen-AgentBus/REPOSITORY_IDENTITY_LOCK.json`.

1. If the user's current instruction explicitly and unambiguously names the project/repository, the agent may bind to that project without asking a redundant question.
2. If the project is not explicitly and unambiguously specified, the agent MUST ask the user which project it is intended to work on before doing project-specific work.
3. The agent MUST NOT infer the project merely from inherited chat/session context, recent work on another project, the currently open repository, a nearby working tree, a previous agent's task, a default path, memory, or the fact that a bootstrap file was discoverable.
4. Until project identity is resolved and the repository identity lock matches, the agent is READ/WRITE BLOCKED for all project repositories, AgentBus forums, artifact stores, task ledgers, and release outputs.
5. Recovery/handoff does not inherit write authority. A recovered Primary/Manager/Research session must re-run this gate before consuming another project's handoff state as actionable work.

## Duo Open binding

An agent bound to Duo Open MUST verify all of the following before any write:

- `project_id == duo-open`
- repository target is exactly `boberino93-bit/duo-open`
- `/DuoOpen-AgentBus/REPOSITORY_IDENTITY_LOCK.json` exists and matches both values
- AgentBus target is under `/DuoOpen-AgentBus/`
- any artifact/message metadata identifies `duo-open`
- the active task is within Duo Open scope

If any value is missing, conflicting, or points to another project, the operation MUST fail closed.

## Recovery-specific guard

When the user says an agent/session hung, disappeared, or must be replaced, the recovering agent MUST NOT choose a project from whichever prior conversation or project state is most recent. It must first resolve the project from the user's current instruction, then read this gate and `REPOSITORY_IDENTITY_LOCK.json`, and only then inspect that project's handoff/forum state.

A handoff from another project may be read for context only; it cannot become the recovered task unless the user explicitly selected that project.

## Cross-project rule

Shared organizational frameworks may be read or copied under an explicit import/promotion process, but project state MUST remain isolated.

A Duo Open agent MUST NOT write BenefitFlow (`project_id=benefitflow`), Warp Propulsion Lab, or any other project's code, forum messages, research state, artifacts, manifests, or task records into this repository. Likewise, Duo Open-specific state MUST NOT be exported into another project's writable namespace except through an explicit, deliberate transfer artifact that is sanitized for the destination.

Cross-project access is read-only by default. Cross-project writes require a separately authorized transfer with both source and destination named.

## Human interaction requirement

When ambiguity exists, use a concise project-selection question such as:

> Which project should I bind this agent to: Duo Open, BenefitFlow, or another project?

Do not ask this question when the current user instruction already names the project clearly.

## Relationship to NO_NEW_AGENTS_V1

`NO_NEW_AGENTS_V1.md` remains authoritative while its freeze is active. This gate does not authorize spawning a new agent/session. It defines the mandatory scope-resolution behavior for any future new agent after the human explicitly permits new-agent creation and for recovery/rebinding of already-authorized active work.

## Propagation

Every Duo Open successor/bootstrap/initiation/deployment package created after this contract is adopted MUST include this file and `REPOSITORY_IDENTITY_LOCK.json`, and MUST put both in the mandatory bootstrap sequence before any project-specific task execution.

## Failure policy

Unknown project -> ASK USER, DO NOT WRITE.
Conflicting project metadata -> STOP, DO NOT WRITE.
Repository lock mismatch -> STOP, DO NOT WRITE.
Repository mismatch -> STOP, DO NOT WRITE.
AgentBus/artifact namespace mismatch -> STOP, DO NOT WRITE.
Recovered session sees another project's recent handoff -> IGNORE AS WRITE AUTHORITY UNTIL CURRENT PROJECT IS REVALIDATED.

There is no implicit/default writable project.
