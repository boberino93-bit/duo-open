# `.swarm/` Project-Local Runtime Namespace

Reserved for Swarm Launch Kernel coordination records. Use immutable/per-task records where possible; do not create a global mutable `state.json` hotspot.

All records are scoped to this repository's configured `project_id` and `global_run_id`. Other projects may read health telemetry where policy allows, but they may not write here or issue commands through telemetry.

GitHub writers use create-if-absent for new claim/idempotency records and current blob SHA plus expected lease version for updates. Stale writes reread/reconcile/back off; never force-push.
