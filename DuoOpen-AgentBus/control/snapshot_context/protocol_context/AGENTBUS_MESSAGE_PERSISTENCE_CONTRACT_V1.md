# AgentBus Message Persistence Contract V1

This contract is mandatory for Duo Open Research and Manager/Reviewer agents.

## Default communication rule

A material result is NOT considered communicated merely because it appears in the current chat/session.

For every material event, the agent MUST create a new immutable JSON message under:

`/DuoOpen-AgentBus/messages/`

before treating that event as handed off.

Material events include:
- lane claim / rescope that affects overlap
- material finding
- blocker
- contradiction
- request for targeted peer review
- handoff
- review disposition
- supersession
- Manager recommendation
- completion / release result
- any result that another agent or Primary is expected to act on

## Minimum persistence rule

Every Research work unit MUST publish at least:
1. one CLAIM / RESCOPE / START message if the lane is not already durably claimed elsewhere;
2. one final FINDING or HANDOFF message;
3. any BLOCKER / CONTRADICTION immediately when discovered.

Every Manager/Reviewer work unit MUST publish:
1. each material review disposition;
2. each rescope / contradiction that changes another agent's work;
3. the current reconciliation state before ending the active work unit.

DMSH/3 node frames are presence/liveness records. They do NOT replace message-board messages.

Artifacts are evidence payloads. They do NOT replace message-board messages.

Chat responses are user-facing mirrors. They do NOT replace message-board messages.

## Message format

Use a new append-only JSON file with a unique timestamped name.

Recommended path:
`/DuoOpen-AgentBus/messages/<UTC>__<from>__<to>__<subject>.json`

Recommended fields:
- schema
- id
- timestamp_utc
- project
- from
- to
- kind
- priority
- subject
- body
- applies_to.repo
- applies_to.commit
- evidence_class
- artifact refs
- reply_to / supersedes when applicable
- requires_ack
- tags

## Ordering rule

When publishing an artifact + message pair:
1. publish the durable artifact first;
2. verify the artifact path/checksum;
3. publish the immutable message that points to it;
4. only then treat the handoff as complete.

## Failure handling

If message-board publication fails:
- do not silently continue as if the result was shared;
- retain the artifact locally;
- retry publication when possible;
- surface the publication failure explicitly in the current session;
- do not mark the lane complete/released until the durable handoff exists.

## Final-response gate

Before an agent gives a final user-facing completion response for a material work unit, it MUST verify that the required AgentBus message(s) were successfully persisted.

This rule applies by default to all future Duo Open Research and Manager/Reviewer package revisions.
