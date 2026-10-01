#!/usr/bin/env python3
from __future__ import annotations
import argparse
import subprocess
from pathlib import Path

REQUIRED = {
    "app/build.gradle.kts": [
        'versionCode = 35',
        'versionName = "2.0.0-zfold7-gen2-ownership"',
    ],
    "app/src/full/java/com/duoopen/shell/ShellProtocol.kt": [
        'COVER_PANEL_LEASE_V3 = 16',
    ],
    "app/src/full/java/com/duoopen/shell/ShizukuBridge.kt": [
        'var connectionEpoch: Long',
        'prewarmSecondaryDisplayV3',
        'ensureSecondaryDisplayHeldV3',
        'releaseSecondaryDisplayV3',
        'reconcileSecondaryDisplayLeaseV3',
    ],
    "app/src/full/java/com/duoopen/shell/DuoShellService.kt": [
        'private val shellSession',
        'coverMutationRevision.incrementAndGet()',
        'ShellProtocol.COVER_PANEL_LEASE_V3',
        'matchesCoverToken',
        'physicalLeaseHeld',
        'routeReady',
    ],
    "app/src/full/java/com/duoopen/shell/WallpaperAngleFeed.kt": [
        'Fold7AnglePipelineGen2',
        'startAnglesSequenced',
        'pollSequence',
        'completePoll',
    ],
    "app/src/main/java/com/duoopen/fold/HingeAngleSource.kt": [
        'callbackHandler: Handler? = null',
        'SAMPLING_PERIOD_US, callbackHandler',
    ],
    "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt": [
        'Fold7Gen2Kernel<Bitmap>',
        'duo-fold7-angle-control',
        'continuity.onTopologyFastLane',
        'continuityFrames = gen2.frames',
    ],
    "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt": [
        'Fold7Gen2Kernel<android.graphics.Bitmap>',
        'fun onTopologyFastLane',
        'Fold7CoverReadiness.Demand',
        'prewarmSecondaryDisplayV3',
        'ensureSecondaryDisplayHeldV3',
        'FROZEN_FRAME_MAX_AGE_MS = 10_000L',
    ],
    "app/src/full/java/com/duoopen/overlay/PanelEngine.kt": [
        'Fold7ContinuityFrameStore<Bitmap>',
        'beginContinuityCapture',
        'continuityFrames.publish',
        'result.timestamp',
    ],
    "app/src/full/java/com/duoopen/overlay/DisplayMirrorHost.kt": [
        'Fold7ContinuityFrameStore.FrameLease<Bitmap>',
        'Fold7PresentationLease()',
        'presentation-frame-commit',
        'presentation-transaction-commit',
        'presentation-presented',
    ],
    "app/src/full/java/com/duoopen/lab/TransitionEvent.kt": [
        'val serviceEpoch: Long?',
        'val closeCycleId: Long?',
        'val shellSession: Long?',
        'val contentLeaseId: Long?',
        'val presentationAttemptSequence: Long?',
    ],
    "app/src/full/java/com/duoopen/lab/TransitionLab.kt": [
        'fun recordIngressStage(',
        'angleSession: Long? = null',
        'pollSequence: Long? = null',
    ],
    "app/src/test/java/com/duoopen/overlay/Fold7Gen2OwnershipTest.kt": [
        'class Fold7Gen2OwnershipTest',
        'frameStore_neverReplaysPriorCycle',
        'presentationLease_rejectsLateOldAttempt',
    ],
}

NEW_OWNERS = [
    "Fold7CycleEnvelope.kt",
    "Fold7CoverLeaseSnapshotGate.kt",
    "Fold7CoverReadiness.kt",
    "Fold7ContinuityFrameStore.kt",
    "Fold7Gen2Kernel.kt",
    "Fold7PresentationLease.kt",
]

FORBIDDEN = {
    "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt": [
        'COVER_ROUTE_REASSERT_SETTLE_MS = 32L',
        'frozenFrameProvider = frozenInnerFrame',
    ],
    "app/src/full/java/com/duoopen/shell/WallpaperAngleFeed.kt": [
        'const val IDLE_POLL_MS = 33L',
    ],
}

def cmd(repo: Path, *args: str) -> str:
    return subprocess.check_output(args, cwd=repo, text=True, stderr=subprocess.STDOUT).strip()

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", type=Path)
    ap.add_argument("--gradle", action="store_true", help="run full debug unit tests and assemble")
    args = ap.parse_args()
    repo = args.repo.resolve()
    failures: list[str] = []

    for rel, needles in REQUIRED.items():
        p = repo / rel
        if not p.is_file():
            failures.append(f"missing {rel}")
            continue
        text = p.read_text()
        for needle in needles:
            if needle not in text:
                failures.append(f"{rel}: missing {needle!r}")

    owner_dir = repo / "app/src/full/java/com/duoopen/overlay"
    for name in NEW_OWNERS:
        if not (owner_dir / name).is_file():
            failures.append(f"missing Gen2 owner {name}")

    for rel, needles in FORBIDDEN.items():
        p = repo / rel
        if not p.is_file():
            continue
        text = p.read_text()
        for needle in needles:
            if needle in text:
                failures.append(f"{rel}: forbidden legacy marker remains {needle!r}")

    try:
        cmd(repo, "git", "diff", "--check")
    except subprocess.CalledProcessError as e:
        failures.append("git diff --check failed:\n" + e.output)

    if failures:
        print("GEN2 POST-APPLY VERIFY: FAIL")
        for f in failures:
            print("-", f)
        raise SystemExit(1)

    print("GEN2 POST-APPLY VERIFY: PASS")
    print(cmd(repo, "git", "status", "--short"))

    if args.gradle:
        print("Running Gradle gates...")
        subprocess.check_call(
            ["./gradlew", "testFullDebugUnitTest", "assembleFullDebug", "--stacktrace"],
            cwd=repo,
        )
        print("GRADLE GATES: PASS")

if __name__ == "__main__":
    main()
