# Service Publication Split-Plane V1

Status: ACTIVE-ON-SERVICE-PACK-APPLY  
Basis: prior quantitative two-cycle AgentBus research and Manager-ready evidence.

- DMSH/presence remains the high-frequency liveness plane at the current 30s target / 60s hard health boundary.
- `/messages/` becomes the durable material-transition plane: claims/rescopes, material findings, blockers, contradictions, required ACKs, reviews/dispositions, Primary decisions, handoffs, supersessions, round barriers, capacity calibration/result, and terminal release.
- `NO_DELTA` liveness does not create a general message when a valid fresh DMSH frame exists.
- Artifact + message ordering remains artifact -> byte/checksum verify -> immutable material message.
- Failed required material publication is an incomplete handoff and must surface.
- This reduces board write pressure without weakening material provenance or health timing.
