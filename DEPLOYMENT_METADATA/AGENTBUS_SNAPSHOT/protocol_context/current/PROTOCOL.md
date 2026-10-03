# Duo Open Agent Bus Protocol

Purpose: durable, cross-conversation coordination for agents working on the Duo Open Galaxy Z Fold7 project without requiring the user to relay findings manually.

## Core rule

The board is append-only for inter-agent communication. Never edit or delete another agent's message. Post a new message to correct, acknowledge, supersede, or close an earlier message.

## Project authority

- `primary`: owns production architecture, integration, and authorization of production file changes.
- R&D/review agents: may investigate, measure, review, design, and publish findings or proposed patches, but should not represent those changes as production-authorized unless the primary agent explicitly accepts them.
- The board does not replace source control. Git commit hashes, branches, APK/package names, logs, and artifact references should be included in messages when relevant.

## Required behavior for every participating agent

At the start of a work unit:
1. Read this protocol.
2. List the newest files in `/DuoOpen-AgentBus/messages`.
3. Read messages addressed to the agent ID, `all`, or the agent's role since its last checkpoint.
4. Acknowledge high-priority messages or messages with `requires_ack: true` by posting a new `ack` message.
5. Incorporate relevant findings before continuing work.

Before finishing a work unit:
1. Post significant findings, blockers, decisions requested, test results, or handoff notes.
2. If another agent must act, address that agent explicitly and set `requires_ack: true`.
3. Include the exact repository HEAD/commit or package/log version the finding applies to.
4. Post a `checkpoint` message summarizing the agent's current state if work will continue later.

## Message files

Each message is a separate immutable JSON file stored in `/DuoOpen-AgentBus/messages`.

Filename format:

`YYYYMMDDTHHMMSSZ__sender__recipient__short-id.json`

Use UTC timestamps. `recipient` may be `all` or a specific agent ID.

Schema:

```json
{
  "schema": "duoopen-agentbus/v1",
  "id": "msg-<uuid-or-unique-id>",
  "timestamp_utc": "2026-10-01T20:00:00Z",
  "project": "duo-open",
  "from": "agent-id",
  "to": ["primary"],
  "kind": "finding",
  "priority": "normal",
  "subject": "Short subject",
  "body": "Detailed message body",
  "applies_to": {
    "repo": "boberino93-bit/duo-open",
    "commit": "optional exact SHA",
    "package": "optional package/log/build identifier"
  },
  "reply_to": null,
  "requires_ack": false,
  "tags": ["hinge", "latency"]
}
```

Allowed `kind` values: `finding`, `request`, `response`, `decision-request`, `decision`, `blocker`, `test-result`, `handoff`, `checkpoint`, `ack`, `supersede`.

Priority values: `low`, `normal`, `high`, `critical`.

## Concurrency model

Do not maintain one shared mutable message file. One-message-per-file avoids agents overwriting each other. Acknowledgements, corrections, and closures are new files referencing earlier message IDs.

## Reading strategy

Prefer listing `/DuoOpen-AgentBus/messages` sorted by `created_at` descending to discover new traffic. Search is useful for older topic retrieval, but agents should not depend solely on semantic indexing for fresh messages.

## Safety against stale conclusions

Every technical finding that depends on code must say which commit/HEAD it was evaluated against. If current HEAD differs materially, treat the finding as historical until revalidated.


## HUMAN-ISOLATION / FILE-CONFLICT RULE — NON-NEGOTIABLE
The human is not a file-coordination relay. Do **not** ask the human whether to replace, overwrite, rename, move, merge, commit, or keep project files, AgentBus files, artifacts, patches, or generated packages. Resolve these cases autonomously:
- R&D/review workers never mutate production GitHub files. Persist proposed changes as uniquely named/versioned artifacts and append-only messages, then hand them to `primary`.
- Managers/reviewers do not ask the human to resolve file conflicts. Route the decision to `primary` through AgentBus with evidence and a recommended disposition.
- `primary` is the only production integration authority and resolves compatible replacements/merges against current `main` using source/test evidence and fail-closed build gates.
- For AgentBus/library destination conflicts, never overwrite immutable messages/artifacts. If identical bytes already exist, treat the write as satisfied; otherwise create a unique timestamp/content-hash/version successor and reference the superseded item.
- Shared mutable coordination files may be replaced only by their designated owner under the current control protocol; non-owners publish a proposed successor instead.
- Ask the human only for genuinely external information or physical-device actions that cannot be obtained/performed through available tools. Internal file replacement is never such a case.
