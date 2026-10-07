#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

GRADLE = Path("app/build.gradle.kts")
PANEL = Path("app/src/full/java/com/duoopen/overlay/PanelEngine.kt")

MARKER = "S1Y_ANCHORED_GEN5_MOTION_V1"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def exact_n(text: str, old: str, new: str, expected: int, label: str) -> str:
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} matches, found {count}")
    return text.replace(old, new, expected)


def transform_gradle(text: str) -> str:
    if 'versionName = "5.1.0-beta2-zfold7-s1y-motion"' in text:
        return text
    text = one(text, "        versionCode = 58\n", "        versionCode = 59\n", "versionCode")
    return one(
        text,
        '        versionName = "5.1.0-beta2-zfold7-s1x-lifecycle"\n',
        '        versionName = "5.1.0-beta2-zfold7-s1y-motion"\n',
        "versionName",
    )


def transform_panel(text: str) -> str:
    if MARKER in text:
        return text

    # Motion state is visual-only. The S1W/S1X immutable authority and proof
    # objects remain the source/lifetime/presentation authority.
    text = one(
        text,
        '''    private var openingAnchorProofDrawSeen = false\n''',
        f'''    private var openingAnchorProofDrawSeen = false\n    // {MARKER}: Gen5 may animate the already-proven frame, but never owns it.\n    private var openingAnchorMotionLastTilt = 0f\n    private var openingAnchorMotionLastStage = "inactive"\n''',
        "anchored motion state",
    )

    # The original Gen5 callback was cover-only. S1Y keeps that same predictor
    # alive while an S1X proof bitmap exists, so the SAME visual trajectory can
    # cross the Samsung cover -> inner remap without reopening generic engine
    # evaluation inside the proof window.
    old_guard = '''                if (\n                    !continuityOpeningVisual ||\n                    phase != Phase.SHOWING ||\n                    !isFold7CoverGeometryNow()\n                ) {\n                    gen5FramePosted = false\n                    return\n                }\n'''
    new_guard = f'''                val anchoredMotionStage =\n                    when {{\n                        continuityOpeningVisual -> "cover"\n                        openingAnchorProofBitmap != null -> "inner-anchor"\n                        else -> "inactive"\n                    }}\n                if (\n                    phase != Phase.SHOWING ||\n                    anchoredMotionStage == "inactive"\n                ) {{\n                    gen5FramePosted = false\n                    return\n                }}\n\n                if (anchoredMotionStage != openingAnchorMotionLastStage) {{\n                    openingAnchorMotionLastStage = anchoredMotionStage\n                    com.duoopen.debug.DuoDiagnostics.event(\n                        "opening-anchor-motion",\n                        "STAGE display=$displayId stage=$anchoredMotionStage " +\n                            "tilt=$openingAnchorMotionLastTilt",\n                    )\n                }}\n'''
    text = one(text, old_guard, new_guard, "extend Gen5 callback through anchor proof")

    text = one(
        text,
        '''                surface?.tilt = tilt\n                gen5FrameCount++\n''',
        '''                openingAnchorMotionLastTilt = tilt\n                surface?.tilt = tilt\n                gen5FrameCount++\n''',
        "retain last Gen5 tilt across remap",
    )

    # S1V deliberately disabled motion for the binary anchor experiment. S1X
    # physically reached PRESENTED, so S1Y re-enables only the existing Gen5
    # loop and its cover refresh-rate lease. Capture authority remains immutable.
    static_block = '''            // S1V diagnostic: no hinge animation or refresh-rate lease.\n            // The cover frame must remain motionless so physical anchoring is binary.\n            com.duoopen.debug.DuoDiagnostics.event(\n                "opening-anchor-proof",\n                "COVER_STATIC display=$displayId animation=disabled",\n            )\n'''
    motion_block = f'''            // {MARKER}: S1X established the stationary anchor path. Restore\n            // ONLY Gen5 visual motion; authority/lifetime/proof remain unchanged.\n            openingAnchorMotionLastTilt = COVER_OPEN_IMMEDIATE_TILT\n            openingAnchorMotionLastStage = "cover"\n            startGen5OpeningFrameLoop()\n            (created as? SnapshotSurface)?.let(::requestGen5RefreshRate)\n            com.duoopen.debug.DuoDiagnostics.event(\n                "opening-anchor-motion",\n                "START display=$displayId stage=cover tilt=$openingAnchorMotionLastTilt",\n            )\n'''
    text = one(text, static_block, motion_block, "restore Gen5 cover motion")

    # S1V stopped Gen5 at the handoff because its inner frame had to remain
    # static. S1Y intentionally preserves the clock until proof release/abort.
    text = one(
        text,
        '''        continuityOpeningVisual = false\n        stopGen5OpeningClock()\n        captureGen++\n        openingRemapInnerSurfaceReady = false\n''',
        f'''        continuityOpeningVisual = false\n        // {MARKER}: keep Gen5 alive while the S1X proof bitmap crosses to INNER.\n        captureGen++\n        openingRemapInnerSurfaceReady = false\n''',
        "continue motion clock across successful handoff",
    )

    # Avoid even a one-frame visual reset when the inner SnapshotSurface is
    # created. The callback can update it on subsequent vsyncs.
    text = one(
        text,
        '''        created.tilt = 0f\n        surface = created\n''',
        '''        created.tilt = openingAnchorMotionLastTilt\n        surface = created\n''',
        "attach inner anchor at continuous Gen5 tilt",
    )

    # Now that the Gen5 clock survives handoff, release and cancellation own its
    # terminal cleanup. These two identical proof cleanup sites are release and
    # abort; both must stop the virtual clock and clear any frame-rate lease.
    cleanup = '''        openingRemapInnerSurfaceReady = false\n\n        if (surface != null) removeOverlay()\n'''
    cleanup_motion = f'''        openingRemapInnerSurfaceReady = false\n        // {MARKER}: proof terminal owns Gen5 cleanup after cross-display motion.\n        stopGen5OpeningClock()\n        openingAnchorMotionLastStage = "inactive"\n\n        if (surface != null) removeOverlay()\n'''
    text = exact_n(text, cleanup, cleanup_motion, 2, "release/abort Gen5 cleanup")

    return text


def validate(gradle: str, panel: str) -> None:
    required = (
        (gradle, ['versionCode = 59', 'versionName = "5.1.0-beta2-zfold7-s1y-motion"']),
        (panel, [
            MARKER,
            "openingAnchorMotionLastTilt",
            'anchoredMotionStage == "inactive"',
            '"opening-anchor-motion"',
            '"inner-anchor"',
            "startGen5OpeningFrameLoop()",
            "requestGen5RefreshRate",
            "created.tilt = openingAnchorMotionLastTilt",
            "ANCHOR_PROOF_VISIBLE_HOLD_MS = 900L",
            "ANCHOR_AUTHORITY_EMERGENCY_HOLD_MS = 30_000L",
            '"immutable-cover-authority"',
        ]),
    )
    for content, needles in required:
        for needle in needles:
            if needle not in content:
                raise RuntimeError("missing S1Y invariant: " + needle)

    if "COVER_STATIC display=$displayId animation=disabled" in panel:
        raise RuntimeError("S1Y must not leave S1V static-cover diagnostic active")

    # The S1V/S1X safety isolation remains: generic evaluate and hinge rendering
    # do not reclaim authority while an opening proof bitmap is active.
    for needle in (
        "if (openingAnchorProofBitmap != null) return",
        "if (openingAnchorProofBitmap != null) {",
    ):
        if needle not in panel:
            raise RuntimeError("S1Y lost proof-window isolation: " + needle)


def apply(repo: Path, check: bool) -> None:
    paths = [repo / GRADLE, repo / PANEL]
    if not all(path.exists() for path in paths):
        raise RuntimeError("required S1X materialized sources are missing")

    gradle = transform_gradle((repo / GRADLE).read_text(encoding="utf-8"))
    panel = transform_panel((repo / PANEL).read_text(encoding="utf-8"))
    validate(gradle, panel)

    if not check:
        (repo / GRADLE).write_text(gradle, encoding="utf-8")
        (repo / PANEL).write_text(panel, encoding="utf-8")


def self_test() -> None:
    # Model the only ownership change S1Y is allowed to make: visual motion
    # remains active from cover rendering into the existing anchor proof, and
    # ends when that proof ends. Authority itself is outside this model.
    def active(cover_visual: bool, proof_bitmap: bool, showing: bool) -> bool:
        stage = "cover" if cover_visual else "inner-anchor" if proof_bitmap else "inactive"
        return showing and stage != "inactive"

    assert active(True, False, True)
    assert active(False, True, True)
    assert not active(False, False, True)
    assert not active(True, False, False)
    print("S1Y anchored Gen5 motion model: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        if not args.check:
            return 0

    apply(Path(args.repo).resolve(), args.check)
    print("S1Y anchored Gen5 motion: " + ("source shape verified" if args.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
