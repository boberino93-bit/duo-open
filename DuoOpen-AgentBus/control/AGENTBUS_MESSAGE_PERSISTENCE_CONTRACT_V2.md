# AgentBus Message Persistence Contract V2

V2 preserves every material-event durability rule from V1 and adds human-interaction learning plus communication-model evolution.

## Material communication rule

A material result is not communicated merely because it appears in chat, a node frame, or an artifact. Persist a new immutable JSON message under `/DuoOpen-AgentBus/messages/` before treating the event as handed off.

Material events include claims/rescopes, findings, blockers, contradictions, review requests/dispositions, decisions, handoffs, supersessions, completion/release results, communication-model activations, and any result another agent is expected to act on.

## Human-model observations

Routine user-style observations do **not** each need a general `/messages/` write. Store them append-only under `/DuoOpen-AgentBus/human_model/v1/observations/` and batch the communication-model delta. A general message is required when:
- the human gives a new standing directive;
- a compiled interaction-model snapshot materially changes agent behavior;
- a communication-model extension is activated/superseded;
- the observation reveals a recurring failure mode affecting multiple agents.

This keeps the board durable without turning every user sentence into message spam.

## Communication enhancements

Under `COMMUNICATION_MODEL_AUTONOMY_V1.md`, any agent may publish additive/reversible communication improvements. Activation messages must include:
- enhancement id/version;
- scope;
- risk class (`COMM_LOW_RISK` or `COMM_HIGH_RISK`);
- validation result;
- exact artifact/protocol path + checksum;
- self-replication status;
- superseded predecessor if any.

## Ordering

For artifact + message pairs:
1. publish artifact/protocol/model snapshot;
2. verify bytes/checksum;
3. publish immutable message pointing to it;
4. only then treat the handoff/activation as durable.

## Failure handling

If required publication fails, retain the local artifact, surface the failure, and do not claim propagation or handoff succeeded.

## Deployment snapshot gate

Before a main deployment/successor package is called complete, apply `DEPLOYMENT_AGENTBUS_SNAPSHOT_CONTRACT_V1.md`. A package missing the required AgentBus snapshot must explicitly be marked incomplete.
