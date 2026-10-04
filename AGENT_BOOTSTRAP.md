# Agent Bootstrap Contract

Project ID: `duo-open`  
Authorized repository: `boberino93-bit/duo-open`  
Stable GitHub repository ID: `1396743140`  
Internal forum namespace: `duo-open::messages`  
Preferred forum path: `.interagent/messages`

`AGENT_BOOTSTRAP.json` is the machine-readable local routing contract. This Markdown explains the contract but does not override it. If this file, the JSON contract, repository metadata, an identity lock, or the central Intercommunications Enhancements registry disagree, fail closed before mutation.

Before any mutation, a new agent MUST:

1. Determine that it was started for `duo-open` from the project environment or explicit human instruction.
2. Determine its assigned role (`primary`, `manager`, `research`, `recovery`, `qa`, or `build`).
3. Read and validate `AGENT_BOOTSTRAP.json`.
4. Verify the repository full name and, when available, stable GitHub repository ID.
5. Read the project-local internal message/forum state before changing repository state.
6. Read available handoff/state files (`PROJECT_MANIFEST.json`, `START_HERE.md`, and `.interagent/messages` when present).
7. Bind mutation authority only to `boberino93-bit/duo-open`.
8. Emit: `IDENTITY RESOLVED: project=duo-open; role=<role>; forum=duo-open::messages; repositories=boberino93-bit/duo-open; state=<handoff/state ref>`.
9. Only then begin role-specific work.

Fail closed before mutation if project, role, forum, handoff, routing-contract version, or repository identity is missing or conflicting. Never infer another repository from similarity. Cross-project communication or mutation requires explicit human authorization and the Intercommunications Enhancements routing protocol.
