# Duo Open User Interaction Prediction Model Protocol V1

Status: MANDATORY FOR FUTURE AGENT/BOOTSTRAP PACKAGES ONCE ADOPTED
Scope: project-local Duo Open coordination only
Authority: advisory context only; never production authority

## Purpose

Duo Open agents may learn from the user's own project interactions so future agents can anticipate likely follow-up questions, preferred handoff formats, and recurring workflow expectations without requiring the user to repeat them.

This is a project workflow model, not a psychological profile. Predictions are hypotheses, never facts about the user and never permission to act beyond the user's actual request.

## Durable locations

When the live AgentBus is available, use append-only records under:

- `/DuoOpen-AgentBus/user-model/v1/events/`
- `/DuoOpen-AgentBus/user-model/v1/models/`
- `/DuoOpen-AgentBus/user-model/v1/predictions/`

Do not overwrite prior events or model snapshots. The newest valid model is the lexicographically newest immutable model snapshot whose referenced event digests validate.

## What to record

Record only user-provided project interaction evidence that helps future work, such as:

- exact or lightly normalized project questions and directives;
- recurring request forms (for example: verify integrity, implement rather than only describe, produce a root-safe package, confirm whether something is actually committed/applied);
- terminology the user consistently uses for project components;
- preferred output/handoff mechanics;
- corrections the user makes to agent assumptions;
- likely next-question candidates derived from repeated interaction patterns.

## What not to infer or store

Do not infer sensitive traits, diagnoses, politics, health, identity categories, or private-life attributes from wording. Do not store credentials, secrets, tokens, personal account identifiers, or unrelated private data. If a project message includes such material, redact it from the user-model event and retain only the non-sensitive workflow signal.

Do not model persuasion susceptibility or use predictions to manipulate the user. The model exists to reduce repetition and prepare useful evidence.

## Event schema

Each immutable event should contain at least:

```json
{
  "schema": "duoopen-user-interaction-event/v1",
  "id": "<unique>",
  "timestamp_utc": "<ISO8601>",
  "agent_instance_id": "<agent>",
  "source": "USER_MESSAGE",
  "user_text": "<project-scoped text or redacted excerpt>",
  "intent_tags": ["IMPLEMENT", "VERIFY", "PACKAGE"],
  "mannerism_features": {
    "brevity": "HIGH|MEDIUM|LOW",
    "action_bias": "HIGH|MEDIUM|LOW",
    "prefers_direct_answer": true,
    "spelling_normalization_needed": false
  },
  "workflow_preferences": ["ROOT_SAFE_PACKAGE"],
  "candidate_followups": [
    {"question": "<candidate>", "confidence": 0.0}
  ],
  "sensitive_redaction_applied": false
}
```

## Model snapshots

A model snapshot is derived, inspectable, and append-only. It should contain:

- source event ids/digests;
- recurring intent frequencies;
- stable workflow preferences with evidence counts;
- recurring linguistic markers useful to interpretation;
- a ranked set of possible next questions with confidence and evidence refs;
- contradictions/decay notes so older habits do not become permanent assumptions.

Confidence must fall when later behavior contradicts an older pattern.

## Runtime behavior

At startup, every generated Primary, Manager/Reviewer, and Research package must:

1. look for `/DuoOpen-AgentBus/user-model/v1/models/`;
2. load the newest valid model snapshot if present;
3. treat it as advisory context beneath the user's current message and current project evidence;
4. record new material user interaction events during the active work unit;
5. generate a new model snapshot when material interaction evidence changes the model;
6. use likely-question predictions to prefetch or preserve useful evidence, not to answer questions the user did not ask;
7. never let a prediction override an explicit current instruction.

## Self-replication rule

Every successor ZIP, bootstrap bundle, or agent-generation package must include this protocol or a newer superseding version and must include the user-model lookup step in its startup sequence. If a package cannot access the live database, it may carry the newest validated snapshot as a cache, clearly labeled with its timestamp and source digests.

## User control

The model must remain inspectable. If the user asks what it thinks they may ask next, show the current predictions and why. If the user asks to stop using this project model, agents must stop consulting it. Deleting or rewriting immutable live records is a separate storage-administration action; agents should instead publish a superseding disable/ignore directive unless the backing system supports explicit deletion by the user.
