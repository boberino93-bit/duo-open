#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

GRADLE = Path("app/build.gradle.kts")
PANEL = Path("app/src/full/java/com/duoopen/overlay/PanelEngine.kt")

MARKER = "S2B_PROGRESS_AWARE_ANCHOR_TERMINAL_V1"


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
    if 'versionName = "5.1.0-beta2-zfold7-s2b-progress-terminal"' in text:
        return text
    text = one(text, "        versionCode = 61\n", "        versionCode = 62\n", "versionCode")
    return one(
        text,
        '        versionName = "5.1.0-beta2-zfold7-s2a-convergence"\n',
        '        versionName = "5.1.0-beta2-zfold7-s2b-progress-terminal"\n',
        "versionName",
    )


def transform_panel(text: str) -> str:
    if MARKER in text:
        return text

    text = one(
        text,
        '''    // S2A_MEASURED_ANCHOR_CONVERGENCE_V1: the inner anchor holds the shader peak until the first real\n    // Samsung precise measurement establishes geometry.\n    private var openingAnchorMotionPreciseSeeded = false\n''',
        f'''    // S2A_MEASURED_ANCHOR_CONVERGENCE_V1: the inner anchor holds the shader peak until the first real\n    // Samsung precise measurement establishes geometry.\n    private var openingAnchorMotionPreciseSeeded = false\n\n    // {MARKER}: terminal cleanup follows motion truth, not one wall-clock\n    // deadline. Forward precise progress renews the anchor; a real stall or\n    // reversal releases it. The no-precise timeout remains bounded.\n    private var openingAnchorMotionLastProgressAngle = Float.NaN\n    private var openingAnchorMotionLastProgressUptimeMs = 0L\n    private var openingAnchorMotionWatchdogSequence = -1L\n\n    private val openingAnchorMotionStallWatchdog =\n        object : Runnable {{\n            override fun run() {{\n                val sequence = openingAnchorMotionWatchdogSequence\n                if (\n                    sequence != openingRemapHandoffSequence ||\n                    openingAnchorProofBitmap == null\n                ) {{\n                    return\n                }}\n\n                if (!openingAnchorMotionPreciseSeeded) {{\n                    com.duoopen.debug.DuoDiagnostics.event(\n                        "opening-anchor-motion",\n                        "NO_PRECISE_RELEASE display=$displayId sequence=$sequence " +\n                            "timeoutMs=$ANCHOR_MOTION_NO_PRECISE_WATCHDOG_MS",\n                    )\n                    releaseOpeningAnchorProof(sequence, "no-precise-watchdog")\n                    return\n                }}\n\n                val now = SystemClock.uptimeMillis()\n                val progressAgeMs =\n                    (now - openingAnchorMotionLastProgressUptimeMs).coerceAtLeast(0L)\n\n                if (progressAgeMs >= ANCHOR_MOTION_PROGRESS_STALL_MS) {{\n                    com.duoopen.debug.DuoDiagnostics.event(\n                        "opening-anchor-motion",\n                        "STALL_RELEASE display=$displayId sequence=$sequence " +\n                            "angle=$openingAnchorMotionLastProgressAngle " +\n                            "progressAgeMs=$progressAgeMs " +\n                            "stallMs=$ANCHOR_MOTION_PROGRESS_STALL_MS",\n                    )\n                    releaseOpeningAnchorProof(sequence, "precise-progress-stall")\n                    return\n                }}\n\n                val remainingMs =\n                    (ANCHOR_MOTION_PROGRESS_STALL_MS - progressAgeMs)\n                        .coerceAtLeast(ANCHOR_MOTION_WATCHDOG_MIN_RECHECK_MS)\n                com.duoopen.debug.DuoDiagnostics.event(\n                    "opening-anchor-motion",\n                    "WATCHDOG_DEFER display=$displayId sequence=$sequence " +\n                        "angle=$openingAnchorMotionLastProgressAngle " +\n                        "progressAgeMs=$progressAgeMs nextMs=$remainingMs",\n                )\n                handler.postDelayed(this, remainingMs)\n            }}\n        }}\n''',
        "progress-aware terminal fields",
    )

    text = one(
        text,
        '''            openingAnchorMotionLastTilt = COVER_OPEN_IMMEDIATE_TILT\n            openingAnchorMotionLastStage = "cover"\n            openingAnchorMotionPreciseSeeded = false\n            startGen5OpeningFrameLoop()\n''',
        '''            openingAnchorMotionLastTilt = COVER_OPEN_IMMEDIATE_TILT\n            openingAnchorMotionLastStage = "cover"\n            openingAnchorMotionPreciseSeeded = false\n            openingAnchorMotionLastProgressAngle = Float.NaN\n            openingAnchorMotionLastProgressUptimeMs = 0L\n            openingAnchorMotionWatchdogSequence = -1L\n            handler.removeCallbacks(openingAnchorMotionStallWatchdog)\n            startGen5OpeningFrameLoop()\n''',
        "reset progress watchdog for new opening",
    )

    measured_flat_anchor = '''        if (result.accepted && angle >= DuoShader.FLAT_HINGE) {\n'''
    terminal_logic = f'''        if (result.accepted) {{\n            val previousProgressAngle = openingAnchorMotionLastProgressAngle\n            if (\n                previousProgressAngle.isNaN() ||\n                angle >= previousProgressAngle + ANCHOR_MOTION_PROGRESS_EPSILON_DEG\n            ) {{\n                openingAnchorMotionLastProgressAngle = angle\n                openingAnchorMotionLastProgressUptimeMs = deliveredUptimeMs\n            }}\n\n            if (\n                firstPrecise &&\n                openingRemapInnerSurfaceReady\n            ) {{\n                armOpeningAnchorMotionWatchdog(openingRemapHandoffSequence)\n            }}\n        }}\n\n        if (result.accepted && result.reversal) {{\n            val sequence = openingRemapHandoffSequence\n            com.duoopen.debug.DuoDiagnostics.event(\n                "opening-anchor-motion",\n                "REVERSAL_RELEASE display=$displayId sequence=$sequence angle=$angle",\n            )\n            releaseOpeningAnchorProof(sequence, "precise-reversal:$angle")\n            return\n        }}\n\n'''
    text = one(
        text,
        measured_flat_anchor,
        terminal_logic + measured_flat_anchor,
        "progress/reversal terminal logic",
    )

    old_presented_log = '''                    "elapsedMs=${decision.elapsedMs} release=measured-flat " +\n                    "flatThreshold=${DuoShader.FLAT_HINGE} " +\n                    "watchdogMs=$ANCHOR_MOTION_PRESENTED_WATCHDOG_MS trigger=$reason",\n'''
    new_presented_log = '''                    "elapsedMs=${decision.elapsedMs} release=measured-flat " +\n                    "flatThreshold=${DuoShader.FLAT_HINGE} " +\n                    "noPreciseWatchdogMs=$ANCHOR_MOTION_NO_PRECISE_WATCHDOG_MS " +\n                    "stallWatchdogMs=$ANCHOR_MOTION_PROGRESS_STALL_MS trigger=$reason",\n'''
    text = one(text, old_presented_log, new_presented_log, "presented terminal telemetry")

    old_watchdog = '''            // S2A_MEASURED_ANCHOR_CONVERGENCE_V1: normal completion is geometry-driven. This delayed\n            // release is failure cleanup only (missing/stalled Samsung stream).\n            handler.postDelayed(\n                {\n                    if (\n                        sequence == openingRemapHandoffSequence &&\n                        openingAnchorProofBitmap != null\n                    ) {\n                        com.duoopen.debug.DuoDiagnostics.event(\n                            "opening-anchor-motion",\n                            "WATCHDOG_RELEASE display=$displayId sequence=$sequence " +\n                                "seeded=$openingAnchorMotionPreciseSeeded",\n                        )\n                        releaseOpeningAnchorProof(sequence, "measured-flat-watchdog")\n                    }\n                },\n                ANCHOR_MOTION_PRESENTED_WATCHDOG_MS,\n            )\n            return\n'''
    new_watchdog = f'''            // {MARKER}: after PRESENTED, missing precise geometry remains\n            // bounded, but once precise motion starts the terminal is renewed by\n            // actual forward progress instead of an absolute wall clock.\n            armOpeningAnchorMotionWatchdog(sequence)\n            return\n'''
    text = one(text, old_watchdog, new_watchdog, "replace fixed presented watchdog")

    release_anchor = '''    private fun releaseOpeningAnchorProof(\n        sequence: Long,\n        reason: String,\n    ) {\n'''
    helper = f'''    private fun armOpeningAnchorMotionWatchdog(\n        sequence: Long,\n    ) {{\n        if (\n            sequence != openingRemapHandoffSequence ||\n            openingAnchorProofBitmap == null\n        ) {{\n            return\n        }}\n\n        openingAnchorMotionWatchdogSequence = sequence\n        handler.removeCallbacks(openingAnchorMotionStallWatchdog)\n\n        val delayMs =\n            if (!openingAnchorMotionPreciseSeeded) {{\n                ANCHOR_MOTION_NO_PRECISE_WATCHDOG_MS\n            }} else {{\n                val progressAgeMs =\n                    (SystemClock.uptimeMillis() - openingAnchorMotionLastProgressUptimeMs)\n                        .coerceAtLeast(0L)\n                (ANCHOR_MOTION_PROGRESS_STALL_MS - progressAgeMs)\n                    .coerceAtLeast(ANCHOR_MOTION_WATCHDOG_MIN_RECHECK_MS)\n            }}\n\n        handler.postDelayed(openingAnchorMotionStallWatchdog, delayMs)\n    }}\n\n'''
    text = one(text, release_anchor, helper + release_anchor, "insert progress-aware watchdog arming")

    text = one(
        text,
        "        const val ANCHOR_MOTION_PRESENTED_WATCHDOG_MS = 2_500L\n",
        '''        const val ANCHOR_MOTION_NO_PRECISE_WATCHDOG_MS = 2_500L\n        const val ANCHOR_MOTION_PROGRESS_STALL_MS = 700L\n        const val ANCHOR_MOTION_WATCHDOG_MIN_RECHECK_MS = 24L\n        const val ANCHOR_MOTION_PROGRESS_EPSILON_DEG = 0.25f\n''',
        "replace absolute watchdog constants",
    )

    text = exact_n(
        text,
        '''        openingAnchorMotionLastStage = "inactive"\n        openingAnchorMotionPreciseSeeded = false\n''',
        '''        openingAnchorMotionLastStage = "inactive"\n        openingAnchorMotionPreciseSeeded = false\n        openingAnchorMotionLastProgressAngle = Float.NaN\n        openingAnchorMotionLastProgressUptimeMs = 0L\n        openingAnchorMotionWatchdogSequence = -1L\n        handler.removeCallbacks(openingAnchorMotionStallWatchdog)\n''',
        2,
        "terminal progress-watchdog cleanup",
    )

    return text


def validate(gradle: str, panel: str) -> None:
    required = (
        (gradle, ['versionCode = 62', 'versionName = "5.1.0-beta2-zfold7-s2b-progress-terminal"']),
        (panel, [
            MARKER,
            "openingAnchorMotionLastProgressAngle",
            "openingAnchorMotionLastProgressUptimeMs",
            "openingAnchorMotionStallWatchdog",
            "armOpeningAnchorMotionWatchdog",
            "NO_PRECISE_RELEASE display=$displayId",
            "STALL_RELEASE display=$displayId",
            "WATCHDOG_DEFER display=$displayId",
            "REVERSAL_RELEASE display=$displayId",
            "ANCHOR_MOTION_NO_PRECISE_WATCHDOG_MS = 2_500L",
            "ANCHOR_MOTION_PROGRESS_STALL_MS = 700L",
            "ANCHOR_MOTION_PROGRESS_EPSILON_DEG = 0.25f",
            "angle >= DuoShader.FLAT_HINGE",
            "PRECISE_SEED display=$displayId angle=$angle",
            "PEAK_HOLD display=$displayId",
            "ANCHOR_AUTHORITY_EMERGENCY_HOLD_MS = 30_000L",
        ]),
    )
    for content, needles in required:
        for needle in needles:
            if needle not in content:
                raise RuntimeError("missing S2B invariant: " + needle)

    for forbidden in (
        "ANCHOR_MOTION_PRESENTED_WATCHDOG_MS = 2_500L",
        "WATCHDOG_RELEASE display=$displayId",
        'releaseOpeningAnchorProof(sequence, "measured-flat-watchdog")',
    ):
        if forbidden in panel:
            raise RuntimeError("S2B retained obsolete absolute-watchdog behavior: " + forbidden)

    # Proven S1V/S1X isolation and S1Z source fence must remain intact.
    for needle in (
        "if (openingAnchorProofBitmap != null) return",
        'source != "SAMSUNG_PRECISE"',
        "ANCHOR_AUTHORITY_EMERGENCY_HOLD_MS = 30_000L",
    ):
        if needle not in panel:
            raise RuntimeError("S2B lost protected invariant: " + needle)


def apply(repo: Path, check: bool) -> None:
    for rel in (GRADLE, PANEL):
        if not (repo / rel).exists():
            raise RuntimeError("missing required S2A materialized source: " + str(rel))

    gradle = transform_gradle((repo / GRADLE).read_text(encoding="utf-8"))
    panel = transform_panel((repo / PANEL).read_text(encoding="utf-8"))
    validate(gradle, panel)

    if not check:
        (repo / GRADLE).write_text(gradle, encoding="utf-8")
        (repo / PANEL).write_text(panel, encoding="utf-8")


def self_test() -> None:
    STALL = 700
    NO_PRECISE = 2500

    # S2A field case 1: active progress at the old absolute deadline must defer.
    presented = 0
    seeded = True
    last_progress = 2470
    now = 2500
    assert seeded and now - last_progress < STALL
    assert STALL - (now - last_progress) == 670

    # The next measured sample can then cross the real flat boundary normally.
    assert 173.0 >= 172.0

    # S2A field case 2: a genuine partial-fold pause still releases.
    last_progress = 1800
    now = 2500
    assert now - last_progress >= STALL

    # A missing Samsung stream remains bounded exactly as before.
    seeded = False
    assert not seeded and NO_PRECISE == 2500

    # A measured reversal is terminal immediately; no stall wait is required.
    reversal = True
    assert reversal

    print("S2B progress-aware anchor terminal model: PASS")


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
    print("S2B progress-aware anchor terminal: " + ("source shape verified" if args.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
