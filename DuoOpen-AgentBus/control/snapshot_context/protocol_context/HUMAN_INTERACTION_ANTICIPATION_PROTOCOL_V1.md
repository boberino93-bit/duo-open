# Duo Open Human Interaction Anticipation Protocol V1

## Purpose

Build a project-scoped model of how the human asks questions, adds requirements, corrects agents, and verifies work so agents can prepare likely follow-up information and reduce repetitive clarification.

This is **not** a personality diagnosis and must not infer sensitive personal traits. It is a communication/workflow model for the Duo Open project.

## What to record

During an active Duo Open work unit, agents SHOULD convert material human inputs into append-only observations containing:
- request type: question / directive / correction / enhancement / verification / packaging / handoff / autonomy;
- normalized intent;
- project-specific vocabulary and recurring referents;
- interaction style signals useful to communication (for example: direct imperative, rapid additive follow-up, expects action rather than a proposal, typo-tolerant semantic interpretation);
- whether the request corrected an agent assumption;
- whether the human asked for proof, integrity checks, persistence, packaging, or autonomous continuation;
- the next question/request archetype that actually followed when known;
- optional short raw excerpt when needed for evidence.

Do NOT store passwords, credentials, unrelated private app content, health details, financial details, or other sensitive personal information in this model. When a user input contains both project direction and sensitive content, retain only the project-relevant normalized directive.

## Observation storage

Append-only observations live under:

`/DuoOpen-AgentBus/human_model/v1/observations/`

Recommended filename:

`<UTC>__<agentInstanceId>__human-input.json`

Observations are evidence. Do not overwrite prior observations.

## Compiled model

A compiled model snapshot lives under:

`/DuoOpen-AgentBus/human_model/v1/snapshots/<UTC>__interaction-model.json`

Each snapshot contains:
- evidence observation refs;
- stable communication preferences;
- recurring request/question archetypes;
- likely next-question candidates with bounded confidence labels (`LOW`, `MEDIUM`, `HIGH`);
- common failure modes that trigger human correction;
- recommended agent behavior;
- superseded snapshot refs.

Do not use fake numerical probabilities unless they are actually measured from observations.

## Runtime use

At bootstrap, every agent reads the latest interaction-model snapshot referenced by discovery/its package. During work it uses the model to:
- interpret terse/typo-heavy input semantically rather than pedantically;
- prepare proof for likely verification questions;
- preserve requested packaging/persistence automatically;
- avoid asking the human to repeat known project context;
- answer the current request first, while pre-validating likely next questions when inexpensive;
- notice when a new human directive should update the model.

Predictions must never be treated as user decisions. An agent may prepare evidence for a likely question, but it must not claim the human asked it or silently change production scope because of a prediction.

## Feedback loop

When the human corrects an agent, treat the correction as high-value evidence. Record:
- what assumption failed;
- what the human expected instead;
- how future agents should change communication or packaging behavior.

When a predicted follow-up is wrong, lower or retire that archetype in the next compiled snapshot.

## Self-replication requirement

Every agent initiation/successor package MUST include:
1. this protocol;
2. the latest compiled interaction-model snapshot available at packaging time;
3. the observation schema/compiler used to update it;
4. a self-replication manifest instructing the new agent to continue the loop;
5. the deployment AgentBus snapshot required by `DEPLOYMENT_AGENTBUS_SNAPSHOT_CONTRACT_V1.md`.
