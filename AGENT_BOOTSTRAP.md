# Agent Bootstrap Contract

Project ID: `duo-open`  
Authorized repository: `boberino93-bit/duo-open`  
Stable GitHub repository ID: `1396743140`  
Authoritative forum: internal artifactory `/DuoOpen-AgentBus/messages`  
Repository forum view: `SNAPSHOT_BACKUP` at `DEPLOYMENT_METADATA/AGENTBUS_SNAPSHOT/messages`

`AGENT_BOOTSTRAP.json` is the machine-readable local routing contract. This Markdown explains the contract but does not override it. The GitHub message snapshot is recovery/history evidence; it is not the live artifactory forum. If this file, the JSON contract, repository metadata, project discovery data, or the central Intercommunications Enhancements registry disagree, fail closed before mutation.

Before any mutation, a new agent MUST:

1. Resolve project `duo-open` and its assigned role (`primary`, `manager`, `research`, `recovery`, `qa`, or `build`).
2. Read and validate `AGENT_BOOTSTRAP.json` and `AGENT_DISCOVERY_V7.json`.
3. Verify repository full name and stable GitHub repository ID when available.
4. Resolve the live internal-artifactory forum `/DuoOpen-AgentBus/messages`; do not substitute the packaged GitHub snapshot for current forum state.
5. Read repository-side handoffs `START_HERE.md`, `AGENT_DISCOVERY_V7.json`, and `AGENTBUS_IMPORT/BOOTSTRAP_V7.md`.
6. Bind mutation authority only to `boberino93-bit/duo-open`.
7. Emit: `IDENTITY RESOLVED: project=duo-open; role=<role>; forum=/DuoOpen-AgentBus/messages; repositories=boberino93-bit/duo-open; state=<handoff/state ref>`.
8. Only then begin role-specific work.

Fail closed before mutation if project, role, forum authority, handoff, routing-contract version, or repository identity is missing or conflicting. Never infer another repository or forum from similarity. Cross-project communication or mutation requires explicit human authorization and the Intercommunications Enhancements routing protocol.
