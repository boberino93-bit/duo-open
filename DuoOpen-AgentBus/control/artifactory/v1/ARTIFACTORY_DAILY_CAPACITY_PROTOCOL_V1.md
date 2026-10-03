# Artifactory Daily Capacity Protocol V1.1

Status: ACTIVE-ON-SERVICE-PACK-APPLY  
Authority: Primary orchestration only; does not grant production Android authority or singleton-CAS capability.

## Purpose
Once per day, the active Primary synchronizes the round and runs a **temporary load test** against the exposed Artifactory/Library adapter. The test exists only to build probabilistic performance expectations for product/project planning: how much coordination/write load appears safe, and therefore how many genuinely useful agents the plan can reasonably engage.

The calibration namespace is **scratch space, not project evidence storage**. Raw probe files, duplicate aliases, intermediate payloads, and prior calibration directories MUST NOT accumulate in the local Artifactory/Library database.

## Retention classes
Primary MUST distinguish two classes:

1. **EPHEMERAL LOAD-TEST OBJECTS** — synthetic probe files, temporary batches, collision probes, retry aliases, intermediate readback files and stale calibration directories. These MUST be deleted.
2. **COMPACT PLANNING EVIDENCE** — one small aggregate result per run containing only measurements needed for longitudinal probability estimates: timestamp, tested batch size, payload bytes, elapsed/latency measurements when observable, successes/failures/warnings, exact-path/readback status, cleanup result, adapter/version identity, and the derived planning recommendation/confidence. These MAY be retained append-only.

Never retain raw synthetic probe payloads merely to prove that the test happened. The compact result is the evidence.

## Daily barrier
1. Publish one immutable `STOP_WORK` material message to `all`, `manager-reviewer`, and `research`.
2. Agents stop initiating new lanes/spawns, but may finish the smallest irreversible material write needed to reach `SAFE_CHECKPOINT`.
3. Classify observed workers as `STOPPED`, `SAFE_CHECKPOINT`, `RELEASED`, or `STALE` through liveness/lease evidence. A silent ticket is never an active session.
4. Do not delete ordinary engineering evidence or another agent's work. Cleanup authority in this protocol applies only to the dedicated synthetic calibration scratch namespace.
5. Calibrate only after the barrier is safe or unresolved workers are explicitly blockers.

## Mandatory pre-test garbage collection
Before creating a new probe batch, Primary MUST recursively delete every prior synthetic calibration scratch directory/object from the designated calibration namespace.

- Old probe sets are not version history.
- Auto-renamed aliases such as `(1)` copies are scratch garbage after their result is summarized.
- A previous run's raw files MUST NOT be used as the next run's baseline.
- If stale scratch cleanup cannot be verified, the new calibration is `CLEANUP_BLOCKED` and MUST NOT start.

The retained compact result/history lives outside the scratch namespace.

## Exactly one controlled calibration
- Read the adapter's declared per-call operation ceiling from the actual tool/schema available to Primary.
- Probe `floor(0.90 * declared_ceiling)` unique calibration objects in **one** batch. With the currently exposed `maxItems=20`, the nominal probe is 18 writes.
- Use one run-scoped scratch directory only.
- Every write uses a unique path and a small deterministic payload.
- For a measurement PASS, every operation must succeed with zero warnings, the returned path must equal the requested path, and byte/readback SHA-256 must match.
- A partial success, alias/auto-rename, warning, or hash mismatch is `FAIL_CLOSED`.
- Record `backend_physical_ceiling=UNPROVEN` unless a separate backend-level test actually establishes it. The adapter's schema ceiling is not a physical-service throughput claim.

## Mandatory post-test compaction and deletion
Immediately after readback verification, and before `RESUME_WORK`:

1. Compute the compact planning sample/result.
2. Persist and verify that compact result.
3. Recursively delete the entire current run scratch directory, including successful probes, failed probes, aliases, retry files and intermediate objects.
4. Re-list/re-read the scratch namespace and prove the run left **zero raw calibration objects**.
5. Record `raw_probe_files_created`, `raw_probe_files_deleted`, `residual_raw_probe_files`, and `cleanup_status` in the compact result.
6. Only `cleanup_status=PASS_ZERO_RESIDUAL` permits the run to become an accepted planning sample and permits `RESUME_WORK`.

Deletion failure is not cosmetic. It is `CALIBRATION_CLEANUP_BLOCKED`; Primary surfaces the blocker and does not claim a clean sample.

## Probabilistic planning model
The purpose of repeated calibration is planning, not maximizing writes for its own sake. Primary should use the retained compact sample history to estimate a conservative operating envelope. At minimum track:

- sample count and recency;
- tested operation batch size;
- clean-pass rate;
- failure/warning/collision rate;
- readback-integrity pass rate;
- elapsed time / throughput / p50-p95 latency when observable;
- adapter/schema/version changes;
- cleanup success rate;
- confidence/uncertainty.

Agent-count planning MUST remain separate from write-batch capacity. The session controller hard ceiling remains 20. The nominal 18-session target is usable only when both (a) enough independent work exists and (b) the current planning model does not indicate that coordination/write pressure requires a lower target.

Primary may lower the planned agent count based on observed performance. A load-test PASS never requires filling unused slots with duplicate work.

## Loose MUST-INVOKE rule
Each substantive nontrivial agent work unit must invoke collaboration once by doing one of:
- `HELP_REQUEST` for a bounded uncertainty;
- `SPAWN_REQUEST` when delegated help would materially accelerate/falsify the work; or
- `NO_HELP_JUSTIFICATION` explaining why more parallelism would duplicate ownership, reduce evidence quality, violate a field dependency, or exceed the current capacity plan.

## Resume gate
Primary publishes one material capacity result / `RESUME_WORK` message only after:
- the measurement result is computed;
- the compact result is durably persisted;
- current-run scratch deletion is complete;
- stale scratch deletion is complete; and
- a post-delete inventory confirms zero residual raw probe objects.

Pending logical tickets remain `MANUAL_FALLBACK` unless a validated host adapter produces `SESSION_STARTED` evidence.
