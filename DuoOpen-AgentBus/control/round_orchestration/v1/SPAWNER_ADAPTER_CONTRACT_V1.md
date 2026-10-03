# Duo Open Spawn Adapter Contract V1

The AgentBus controls orchestration. A Spawn Adapter performs host-specific creation of independent ChatGPT conversations.

## Important separation

A `SPAWN_TICKET` is a scheduling decision, not proof that a chat exists. Only a successfully observed `SESSION_STARTED` from the child session proves successful actuation.

## Current default capability

Normal ChatGPT conversation tools do not expose a supported primitive for creating arbitrary sibling conversations. Therefore the default capability is `MANUAL_FALLBACK` until a specific browser/desktop/Work/native adapter is validated.

## Adapter input

- round_id
- ticket_id
- role
- assignment/context refs
- requested bootstrap prompt
- slot reservation
- expiration

## Required adapter behavior

1. Verify the round is OPEN and total active sessions will remain <= 20.
2. Reserve one controller slot.
3. Create one new independent chat/session.
4. Submit either the generic join prompt or a deterministic prompt containing round_id + ticket_id.
5. Wait for the child to write `SESSION_STARTED`.
6. Record `SPAWN_ACTUATION` success only after that evidence is visible.
7. On timeout/failure, release the reservation and publish failure; never fabricate success.

## Adapter candidates

- Official/native chat-session creation capability, if OpenAI exposes one.
- ChatGPT Work/desktop/browser computer-use automation, only after tested against the current UI/account behavior.
- Local browser automation/extension under explicit user control.
- Manual fallback: user opens additional chats and pastes the same JOIN_ROUND prompt.

The orchestration protocol must not depend on which adapter is used.
