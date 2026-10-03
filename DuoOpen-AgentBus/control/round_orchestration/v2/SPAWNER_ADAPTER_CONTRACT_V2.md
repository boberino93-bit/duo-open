# Duo Open Spawn Adapter Contract V2

V2 adds a host-side declarative browser actuator while preserving the V1 rule that scheduling is not proof of execution.

## Truth separation

- `SPAWN_TICKET` = scheduling intent.
- `HOST_TAB_OPENED` = local actuator observation only.
- `PROMPT_SUBMITTED` = local actuator observation only.
- `SESSION_STARTED` = the first authoritative proof that the child agent joined the round.
- Only the child session may publish its own `SESSION_STARTED` to AgentBus.

Primary MUST NOT count a tab, URL, browser process, prompt submission, or local mapping as an active agent.

## Supported V2 actuator

`DUO_CHAT_SPAWN_ACTUATOR_V1.1` is a user-installed Chrome/Chromium Manifest V3 extension. Its preferred active-session input is a strict machine command emitted by one explicitly armed Primary ChatGPT conversation. It also supports a declarative GitHub desired-state index for durable/recovery control. Both channels contain only bounded ticket metadata; the extension opens/closes ChatGPT tabs and constructs the bootstrap prompt locally.

The actuator is intentionally not an AgentBus authority and does not need access to Artifactory/Library credentials.

## Armed Primary DOM bridge

The user arms exactly one Primary conversation from the extension popup. The extension records that conversation ID and ignores machine commands from every other ChatGPT conversation. A valid assistant message may contain `DUO_ACTUATOR_V1:<base64url-json>:END`, where decoded JSON has schema `duoopen-browser-actuation-command/v1`, `issued_by=primary`, a strict command ID, cap <=19, and the same bounded entries described below. No free-form prompt or URL fields are allowed.

This channel removes repository-write permission as a prerequisite for active Primary control. It still cannot promote a tab to active; child `SESSION_STARTED` remains mandatory.

## Desired-state index (durable/recovery channel)

Canonical repo path:

`/DuoOpen-AgentBus/control/chat_actuation/v1/ACTUATION_INDEX.json`

Allowed remote fields per child are strictly bounded:

- `round_id`
- `ticket_id`
- `role` (`MANAGER_REVIEWER` or `RESEARCH`)
- `generation` (positive integer)
- `desired_state` (`RUNNING` or `STOPPED`)

No arbitrary prompt text, JavaScript, URL, tool instruction, credential, or external destination may be supplied by the desired-state index. The browser actuator constructs the bootstrap prompt from a fixed local template.

## Launch lifecycle

1. Primary verifies an OPEN round and useful independent work.
2. Primary allocates a valid ticket without exceeding the round/session ceiling.
3. Primary updates the desired-state index to `RUNNING` for that ticket/generation.
4. Local actuator opens exactly one ChatGPT tab for the configured Duo Screen project (preferred) or the generic ChatGPT new-chat surface.
5. Content script submits the fixed bootstrap prompt.
6. Child validates AgentBus, claims exactly the requested ticket, then publishes `SESSION_STARTED`.
7. Primary observes `SESSION_STARTED` and only then counts the child as active.
8. If no valid `SESSION_STARTED` arrives before the controller timeout, Primary treats actuation as failed/stale and may set the ticket `STOPPED` or increment generation for a replacement.

## Stop/replacement lifecycle

- `STOPPED` means the local actuator SHOULD close its mapped tab for that ticket/generation.
- A higher generation supersedes an older generation. The local actuator closes the older mapped tab before launching the replacement.
- `STOP_WORK` remains a cooperative AgentBus barrier for agent state integrity; browser-tab closure is an additional host cleanup mechanism, not a substitute for durable handoff.

## Safety and failure rules

- Maximum managed child tabs: 19 by default, leaving the Primary outside the actuator and preserving the 20-session hard ceiling.
- Reject duplicate ticket IDs in one index.
- Reject malformed roles, generations, or desired states.
- Never execute remote arbitrary prompt content.
- Never navigate to remote-provided URLs.
- Never claim `SESSION_STARTED` on behalf of a child.
- Login/CAPTCHA/rate-limit/UI failures remain unproven launches. Primary timeout logic handles them.
- If the exact Duo Screen project URL is configured, prefer it so spawned chats inherit project context. Otherwise child bootstrap must recover from durable AgentBus/Library/GitHub state.

## Capability state

Until the extension is installed and a live child has written `SESSION_STARTED` after autonomous actuation, capability remains `MANUAL_FALLBACK`.

After a successful end-to-end test, capability may be promoted to `LOCAL_BROWSER_ACTUATOR` for that user's configured host. This does not imply a native OpenAI sibling-chat API exists.
