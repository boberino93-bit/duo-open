# Duo Open Agent Registry

This file defines stable logical agent IDs. Individual chat sessions may come and go; the logical role name remains stable.

| Agent ID | Role | Authority / responsibility |
|---|---|---|
| `primary` | Production owner | Architecture, integration, production file changes, final implementation decisions |
| `performance-rd` | Performance / measurement R&D | Latency, frame pacing, transition timing, instrumentation |
| `display-rd` | Display / SurfaceControl R&D | Physical panels, cover/inner behavior, mirroring, prewarm, geometry |
| `state-rd` | State-machine R&D | Fold posture, continuity state machine, arbitration, race analysis |
| `reviewer` | Independent reviewer | Cross-checks proposed fixes against current main/HEAD and looks for regressions |
| `all` | Broadcast pseudo-recipient | Any participating agent should read |

Agents should identify themselves using one stable ID. If a new role is needed, post a `request` to `primary` proposing an ID before relying on it for routing.
