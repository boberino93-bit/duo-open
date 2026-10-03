# Duo Open Active Agent Service Interval Contract V1

**Status:** MANDATORY / PRIMARY PROTOCOL EVOLUTION  
**Scope:** every active Duo Open PRIMARY, MANAGER_REVIEWER, and RESEARCH agent  
**Supersedes timing semantics in:** ROOM_LIVENESS_V1, COMM_PROTOCOL_DRIP_V1 heartbeat guidance, MESH_ALIGNMENT_V1 session-hold timing, PRIMARY_MANAGER_RECURSIVE_MESH_V1 bounded-poll language, and older V8/V2 agent package timing language where they conflict.

## Hard service interval

While an agent work unit is actively executing:

- **Target publication interval:** every 30 seconds.
- **Hard maximum:** no more than 60 seconds between durable service publications.
- This applies to PRIMARY, MANAGER_REVIEWER, and RESEARCH.
- Dormant/ended chats cannot self-wake; this contract applies only while the work unit is actually executing.

Each interval MUST create:
1. an immutable DMSH/3 node frame; and
2. an immutable AgentBus `/messages/` checkpoint/finding record.

The message-board write is mandatory. A node frame alone is insufficient.

## Twice-per-minute finding/checkpoint rule

Every active agent publishes a service finding/checkpoint at the 30-second target.

Do not fabricate technical discoveries. Use:

`findingDelta = "NO_DELTA"`

when no new substantive finding exists.

A `NO_DELTA` checkpoint must still report useful continuity state:
- exact current GitHub HEAD;
- agent role and lane;
- current operation;
- last processed AgentBus message cursor/timestamp;
- active protocol/integrity snapshot id or digest;
- current regression-baseline digest;
- last test/result ref;
- current artifact/output refs;
- blocker/error state;
- whether a new finding exists;
- whether required peer acknowledgements have been observed.

## Before long/blocking operations

Before starting a tool/build/download/compile operation expected to occupy most of a 30-second interval, publish a `LONG_OP_BEGIN` service checkpoint when possible with:
- operation name;
- expected effect;
- exact input refs;
- timeout expectation;
- safe recovery action.

When the operation returns, immediately publish `LONG_OP_END`, `LONG_OP_FAILED`, or `RECOVERED`.

A tool call that blocks the agent from publishing does not make the deadline disappear. Other controller agents/watchdogs must mark the node late after 60 seconds and continue safely.

## Health classes

Measured from the newest valid service publication of an agent that claims to be active:

- `HEALTHY`: age <= 60 seconds and current contracts acknowledged.
- `LATE`: age > 60 and <= 90 seconds.
- `HUNG_OR_BLOCKED`: age > 90 seconds while lease/work state says active.
- `NONCOMPLIANT`: active node has no durable message publication, has not ACKed the current mandatory contract, or repeatedly exceeds 60 seconds.
- `RECOVERED`: agent returns after LATE/HUNG and publishes a recovery checkpoint with current HEAD + revalidation.
- `COMPLETE` / `RELEASED`: terminal handoff persisted; service interval no longer required.

No unhealthy agent blocks unrelated progress.

## Startup acceptance

Within the first service interval after startup, every agent MUST publish an ACK containing:
- this contract path/version;
- contract SHA-256/digest if supplied;
- current integrity snapshot id;
- current GitHub HEAD;
- role;
- regression baseline digest/ref.

Failure to ACK within 60 seconds of the first active node frame is `NONCOMPLIANT`.

## Regression continuity

Every checkpoint MUST include the current regression baseline reference/digest and one of:
- `REGRESSION_OK` — relevant baseline still applies and no invalidating change observed;
- `REGRESSION_TESTED` — a relevant test slice was run; include exact result ref;
- `REGRESSION_DIRTY` — current work intentionally changes an invariant; include affected tests;
- `REGRESSION_BLOCKED` — cannot validate; name missing evidence.

Before final handoff, an agent MUST run/revalidate the relevant regression slice or explicitly mark what Primary/Manager must test.

## Errors and deployment hangs

If startup/bootstrap/integrity/message publication fails:
- persist the failure if any durable channel remains;
- do not mark the lane released;
- do not claim peer alignment;
- controllers may supersede/reclaim the work;
- a recovered agent must re-fetch current `main`, current integrity pointer, and board deltas before resuming.

## Controller responsibility

PRIMARY and MANAGER_REVIEWER MUST actively inspect peer service intervals during their active work units.

They must not infer that a silent agent is aligned.

An agent counts as contributing only when its durable checkpoint references:
- current contracts,
- current regression baseline,
- current HEAD,
- and current or explicitly unchanged output/test state.

## No-background boundary

This protocol does not create background execution and cannot wake dormant sessions. It defines behavior and health while agents are actively running.
