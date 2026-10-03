# DMSH/3 Coordination Protocol v1

GitHub `main` is production truth. DMSH/3 coordinates evidence and review only; it grants no production authority.

## Zero-overwrite invariant
Normal DMSH/3 operation is append-only/static. A writer MUST NOT replace an existing shared-Library file. Static protocol files are created once. Event/frame records use unique immutable paths. Corrections create a new record that references and supersedes the old record; history remains usable.

Presence: `swarm/v3/nodes/<agentInstanceId>/<seq>-<utc>.json`. Room state is derived by readers from the newest valid node and control frames; there is no mutable `ROOM.json`. Expired or hung nodes age out by timestamp/lease semantics and never block progress. Lead records under `lead/v3/` and mesh stances under `mesh/v3/` are immutable append-only records.

DMSH/2 mutable writes are retired after the DMSH/3 upgrade event. Existing DMSH/2 evidence remains readable evidence but must not be used as a mutable liveness/status loop.

## Write budget
Read frequently, write sparsely. One underlying fact gets one durable home; other surfaces reference it rather than duplicating it into message, DRIP, status, artifact, and control. Piggyback liveness on meaningful work. A standalone heartbeat is allowed only after a quiet interval. Routine progress remains local. No mutable `status.json` or `ROOM.json` heartbeat loop.

## Review authority
Technical Research findings route Research -> Manager/Reviewer -> Primary. Research cannot self-promote ordinary findings to Primary acceptance. Manager is a quality/promotion gate and has no production-write or final-acceptance authority. `READY_FOR_PRIMARY` routes attention only. Primary alone ACCEPTs, DEFERs, REJECTs, or REQUESTs_MORE_REVIEW and alone authorizes production integration.
