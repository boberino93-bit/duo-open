# Two-cycle hardening notes

## Cycle 1
The initial reference model implemented the 20-session hard ceiling, 18-session target, 14–20 tolerance band, 18-of-20 calibration probe and ticket-vs-session distinction. The first test execution exposed a Python 3.13 dynamic-loader harness incompatibility; the harness was corrected and the 8-test Cycle-1 suite then passed.

## Adversarial strengthening after Cycle 1
A manual failure-mode review found that a bare 90% rule could still be misused in four ways even with green unit tests:
1. treating an 18-write adapter batch as proof of Artifactory backend throughput or simultaneous-agent safety;
2. filling unused capacity with duplicate/busywork lanes;
3. treating a STOP_WORK message as proof every running/dormant agent actually stopped;
4. accepting Library auto-renamed collision writes as successful idempotent publication.

V2 therefore separates batch and session capacity, gates allocation by useful independent work, adds safe-checkpoint barrier states, requires exact-path+readback-hash publication ACK, preserves CAS blocking, and adds MUST_INVOKE_OR_JUSTIFY rather than compulsory pointless spawning.

## Cycle 2
The strengthened model adds deterministic failure-mode tests plus a 50,000-operation randomized session reducer. Packaging verification separately checks required files, JSON validity and SHA-256 manifest integrity.


## SP5.1 — calibration retention hardening
- Synthetic Artifactory load-test objects are EPHEMERAL, not engineering evidence.
- Primary purges stale calibration scratch before a run.
- Primary compacts measurement data, then deletes the entire run scratch directory.
- `RESUME_WORK` requires a zero-residual post-delete inventory.
- Longitudinal probabilistic planning retains aggregate samples, never raw probe payloads.
