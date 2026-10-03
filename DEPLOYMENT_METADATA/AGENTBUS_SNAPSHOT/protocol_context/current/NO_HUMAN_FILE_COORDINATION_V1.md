# Duo Open — No-Human File Coordination Rule v1
## HUMAN-ISOLATION / FILE-CONFLICT RULE — NON-NEGOTIABLE
The human is not a file-coordination relay. Do **not** ask the human whether to replace, overwrite, rename, move, merge, commit, or keep project files, AgentBus files, artifacts, patches, or generated packages. Resolve these cases autonomously:
- R&D/review workers never mutate production GitHub files. Persist proposed changes as uniquely named/versioned artifacts and append-only messages, then hand them to `primary`.
- Managers/reviewers do not ask the human to resolve file conflicts. Route the decision to `primary` through AgentBus with evidence and a recommended disposition.
- `primary` is the only production integration authority and resolves compatible replacements/merges against current `main` using source/test evidence and fail-closed build gates.
- For AgentBus/library destination conflicts, never overwrite immutable messages/artifacts. If identical bytes already exist, treat the write as satisfied; otherwise create a unique timestamp/content-hash/version successor and reference the superseded item.
- Shared mutable coordination files may be replaced only by their designated owner under the current control protocol; non-owners publish a proposed successor instead.
- Ask the human only for genuinely external information or physical-device actions that cannot be obtained/performed through available tools. Internal file replacement is never such a case.
