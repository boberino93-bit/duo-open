# Duo Open Chat Spawn Actuator V1

This is the first concrete host actuator for turning AgentBus `SPAWN_TICKET` intent into real ChatGPT browser tabs while preserving fail-closed child acknowledgement.

## Why a browser actuator

As of the implementation date, there is no supported ChatGPT sibling-conversation creation API exposed to this chat. ChatGPT's web UI can start new conversations and current URL surfaces can carry prompt/query state, but Duo Open does not treat those UI details as authoritative. The local browser extension owns only host actuation; AgentBus remains the coordination truth.

## One-time user setup

1. Extract the root-drop package into the Duo Open repo and push it.
2. In Chrome/Chromium open `chrome://extensions`, enable Developer mode, choose **Load unpacked**, and select `tools/chat_spawn_actuator/chrome_extension/`.
3. Open the extension Options page.
4. Paste the exact Duo Screen ChatGPT Project URL into **Duo Screen project URL**. This is strongly preferred over the generic fallback because it gives spawned chats the same Project context.
5. Confirm the desired-state URL points at the raw `ACTUATION_INDEX.json` on the intended branch.
6. Enable autonomous reconciliation.
7. Keep ChatGPT signed in in that browser profile.

## Primary control channels

### Preferred active-session channel: armed Primary DOM bridge

Click the extension icon while viewing the intended Primary conversation and choose **Arm current tab as Primary**. The extension stores that exact ChatGPT conversation URL. It will only accept strict `DUO_ACTUATOR_V1:<base64url-json>:END` command markers found in assistant-authored messages from that armed conversation. Research/Manager child tabs cannot actuate siblings.

This removes GitHub repository-write scope as a prerequisite while the Primary conversation is open in the browser. Commands still contain only bounded desired state; prompts are built locally.

### Durable/recovery channel: GitHub desired-state index

The existing raw GitHub index remains supported for recovery, browser restarts, and future background operation once repository content-write scope is available.

## Primary behavior

Primary modifies only `ACTUATION_INDEX.json` desired state. It never places free-form prompt text into the index. A ticket is counted active only after the child writes `SESSION_STARTED` into AgentBus. If no acknowledgement appears by timeout, Primary may stop/retry using a new generation.

## Current unavoidable dependency

The ChatGPT GitHub connection currently reads the repository but returns HTTP 403 for repository writes. This blocks the durable GitHub feed but no longer blocks active-session DOM actuation. The remaining mandatory live gates are extension installation/configuration, arming the Primary conversation, and observing a child-authored SESSION_STARTED.
