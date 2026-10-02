DUO OPEN — GEN3 ALPHA4 PROCESS RECOVERY
========================================

TARGET
------
Samsung Galaxy Z Fold7 only.

PURPOSE
-------
Fix the P0 app-process / surviving Shizuku daemon cover-lease recovery race
without changing the Alpha3 transition thresholds, visual architecture, or
hinge-authority model.

VERIFIED PRODUCTION BASELINE
----------------------------
Repository: boberino93-bit/duo-open
Alpha3 baseline commit:
  98a7c1cde9fd36d47562b40fa25ed0b094038e70
  "Make Fold7 hinge authority explicit and ordered"

Exact baseline Git blob SHAs checked by the workflow:
  app/build.gradle.kts
    ad3d7e60b427ed9b2de51d0e94944f600363f345
  app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt
    22426e1f24b51d4a921b7d565ac811ee7fbfb050
  app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt
    e759bb85726a489959bf03248d3ae454d5cd3985

SOURCE-CONFIRMED FAILURE
------------------------
Alpha3 does this when Shizuku becomes Ready:
  1. continuity.onPrivilegedReady()
  2. coordinator starts asynchronous V3 lease reconciliation
  3. FoldOverlayService immediately calls continuity.arm()
  4. arm() sets renderOwnershipArmed=true before reconciliation completes

The daemon-side Fold7CoverPanelLease can survive a fresh app/accessibility
process because DuoShellService is bound as a daemon UserService. A surviving
HELD lease is not cleared by Fold7CoverPanelLease.onTopology(); only
RELEASE_PENDING / UNKNOWN_RECOVERY are reconciled there.

Alpha3 already carries the exact identity needed for a safe fix:
  shellSession + leaseId + leaseEpoch + ownerGeneration
and the V4 owner identity:
  ownerServiceEpoch + ownerCloseCycleId

ALPHA4 FIX
----------
Alpha4 adds one narrow startup-admission owner:
  Fold7ProcessRecoveryGate

A fresh app process starts RECOVERING and privileged continuity stays disarmed.
Accepted shell snapshots are classified as follows:

  IDLE
    -> startup authority is clean; allow arm.

  Non-IDLE token with ownerServiceEpoch == current serviceEpoch
    -> same app-service lifetime; allow resume/arm.

  Non-IDLE foreign or legacy token
    -> issue ONE exact V3 token release; stay disarmed.

  RELEASE_PENDING / RELEASING / UNKNOWN_RECOVERY
    -> stay disarmed and wait for safe topology/reconciliation evidence.

  Invalid non-IDLE snapshot without an exact token
    -> fail closed; do not arm.

Controller hinge/topology/early-opening ingress is ignored while recovery is
not READY or continuity is manually disarmed. The latest authoritative hinge
source continues to run independently; when recovery completes, the existing
controller is reset from current hinge + topology instead of reconstructing a
stale semantic attempt.

UNCHANGED BY ALPHA4
-------------------
- Alpha3 angle-authority architecture.
- Ordered hinge ingress mailbox.
- Gen3 visual coordinator.
- V4 exact-CAS prewarm/adoption protocol.
- Fold7 transition thresholds.
- No raw display OFF commands are introduced.
- No task migration is introduced.

VERSION
-------
versionCode: 41
versionName: 3.0.0-alpha4-zfold7

HOW TO APPLY
------------
This package is intentionally a fail-closed deployment bundle. Do NOT manually
copy payload_alpha4 files into app/** and commit them untested.

1. CHECK ACTUAL CURRENT main FIRST.
2. If any of the three app blob hashes above changed, STOP. Rebase/rebuild this
   Alpha4 patch against current main instead of bypassing the baseline gate.
3. Upload this package at repository root, preserving paths.
4. Upload/create the workflow file LAST:
     .github/workflows/apply-gen3-alpha4-process-recovery.yml
   Its push event starts deployment after support files are present.
5. The workflow verifies baseline + support hashes, applies the patch, runs:
     *Fold7ProcessRecoveryGateTest
     *Fold7CoverPanelLeaseV4Test
     testFullDebugUnitTest
     assembleFullDebug
6. Only after all gates pass does GitHub Actions commit app/** to main.
7. The workflow then uploads:
     DuoOpen-ZFold7-3.0.0-alpha4

If the workflow fails at any gate, runtime app/** is not committed by this
workflow. Diagnose and rebuild against actual main; do not weaken the checks.

CURRENT SESSION WRITE STATUS
----------------------------
The connected GitHub integration used to produce this handoff had read access
but returned HTTP 403 for branch creation and repository content writes. No
repository mutation from this package-building session succeeded. This is why
Alpha4 is delivered as an importable fail-closed deployment package.
