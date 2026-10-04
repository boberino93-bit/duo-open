# AgentBus Backup Mirror Notice

Project: **Duo Open**  
Repository: `boberino93-bit/duo-open`  
Canonical live AgentBus: `/DuoOpen-AgentBus`

This directory is a **downstream recovery-only mirror** of selected message-board / AgentBus coordination artifacts. It is **not authoritative operational state**.

Rules:

- The live Library/Artifactory AgentBus at `/DuoOpen-AgentBus` is the source of truth for current coordination state.
- Do not use this GitHub mirror as live task, decision, lock, research, heartbeat, capacity, or message-board state.
- The GitHub repository itself remains normal version control for the actual project source code and project artifacts. This backup-only rule applies to the mirrored AgentBus/message-board data in this directory, not to project code.
- Restore from this mirror only during a verified recovery event, then reconcile restored state back into the canonical live AgentBus before normal coordination resumes.
- No project-specific approval, safety, validation, financial, disclosure, booking, research, release, or human-decision gates are changed by this mirror.
- Mirrored files must be copied only after canonical local persistence and readback validation.

Profile: `INTERCOMM_OPTIMIZATION_PROFILE_V1`  
Mirror role: `NON_AUTHORITATIVE_RECOVERY_ONLY`
