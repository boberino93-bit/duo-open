# Duo Open Round Entry

This is the stable human-facing entry point for starting a new Duo Open research round.

If the human asks to start a new round:

1. Read `/DuoOpen-AgentBus/AGENT_DISCOVERY.json` and `/DuoOpen-AgentBus/BOOTSTRAP.md`.
2. Read `/DuoOpen-AgentBus/control/round_orchestration/v1/ROUND_ORCHESTRATION_CONTROLLER_V1.md`.
3. Read `/DuoOpen-AgentBus/communication_models/v1/HELP_REQUEST_NON_PREEMPTION_POLICY_V1.json`.
4. Resolve current GitHub `main` HEAD and newest relevant Primary/user directives/messages.
5. Treat this chat as the round Primary unless an already-open compatible round explicitly assigns another role.
6. Create a new round controller record and role/lane spawn tickets from the message-board state. Do not ask the human to restate internal project context already stored in AgentBus.
7. Never exceed 20 concurrent sessions including Primary.
8. Continue substantive Primary work while additional tickets are being claimed.
9. If autonomous chat creation is unavailable, publish `MANUAL_FALLBACK` actuation state and provide/consume the generic join mechanism without pretending child chats were created.

Suggested human phrase:

`Start a new Duo Open research round. Bootstrap from /DuoOpen-AgentBus/ROUND_ENTRY.md and use the message forum for context and role assignment.`
