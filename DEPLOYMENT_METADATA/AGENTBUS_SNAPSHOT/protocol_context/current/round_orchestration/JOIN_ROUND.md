# Duo Open Join Current Round

This is the stable entry point for an additional Duo Open chat joining an existing round.

1. Read `/DuoOpen-AgentBus/AGENT_DISCOVERY.json` and `/DuoOpen-AgentBus/BOOTSTRAP.md`.
2. Read `/DuoOpen-AgentBus/control/round_orchestration/v1/ROUND_ORCHESTRATION_CONTROLLER_V1.md`.
3. Find the newest OPEN round and its unclaimed valid SPAWN_TICKETs.
4. Generate a unique session/agent identity and claim exactly one compatible ticket using the controller's slot/claim rules.
5. Your role and assignment come from the claimed ticket.
6. Publish `SESSION_STARTED`, fetch current GitHub main, then begin work.
7. Continue your own assignment even when requesting or providing bounded help unless explicitly rescheduled.
8. On completion, publish durable handoff + `SESSION_RELEASED`, then release the ephemeral slot lock.

Suggested generic prompt:

`Join the current Duo Open research round. Bootstrap from /DuoOpen-AgentBus/JOIN_ROUND.md and claim one valid open launch ticket.`
