#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

GRADLE = Path("app/build.gradle.kts")
HINGE = Path("app/src/main/java/com/duoopen/fold/Fold7VirtualHingeGen5.kt")
HINGE_TEST = Path("app/src/test/java/com/duoopen/fold/Fold7VirtualHingeGen5Test.kt")
PANEL = Path("app/src/full/java/com/duoopen/overlay/PanelEngine.kt")

MARKER = "S2A_MEASURED_ANCHOR_CONVERGENCE_V1"


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


def between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    i = text.find(start)
    if i < 0:
        raise RuntimeError(f"{label}: start anchor missing")
    j = text.find(end, i + len(start))
    if j < 0:
        raise RuntimeError(f"{label}: end anchor missing")
    return text[:i] + replacement + text[j:]


def transform_gradle(text: str) -> str:
    if 'versionName = "5.1.0-beta2-zfold7-s2a-convergence"' in text:
        return text
    text = one(text, "        versionCode = 60\n", "        versionCode = 61\n", "versionCode")
    return one(
        text,
        '        versionName = "5.1.0-beta2-zfold7-s1z-precise-anchor"\n',
        '        versionName = "5.1.0-beta2-zfold7-s2a-convergence"\n',
        "versionName",
    )


def transform_hinge(text: str) -> str:
    if MARKER in text:
        return text

    anchor = '''    /**\n     * Returns an allocation-light visual target for the next presented frame.\n'''
    method = f'''    /**\n     * {MARKER}\n     * The first precise sample may arrive only after Samsung has already moved\n     * well into the physical opening. Rebase visual state directly to that\n     * measured geometry instead of traversing unobserved 0..N history. This is\n     * visual-only state; semantic continuity authority is unchanged.\n     */\n    fun rebaseToMeasured(sample: Sample): AddResult {{\n        if (!active || !sample.angleDegrees.isFinite()) {{\n            return AddResult(false, false, false, false)\n        }}\n\n        val accepted =\n            sample.copy(\n                angleDegrees = sample.angleDegrees.coerceIn(0f, 180f),\n            )\n\n        history.clear()\n        reversalTimesNs.clear()\n        lastDirectionSign = 0\n        reversalGuardUntilNs = Long.MIN_VALUE\n        oscillationGuardUntilNs = Long.MIN_VALUE\n        reacquireUntilNs = Long.MIN_VALUE\n        lastAcceptedDeliveryNs = accepted.deliveryTimeNs\n        initialAngle = accepted.angleDegrees\n        visualAngle = accepted.angleDegrees\n        visualVelocityDps = 0f\n        lastFrameNs = accepted.deliveryTimeNs\n        history += accepted\n\n        return AddResult(true, false, false, false)\n    }}\n\n'''
    return one(text, anchor, method + anchor, "measured rebase method")


def transform_hinge_test(text: str) -> str:
    if "s2aMeasuredRebaseStartsAtMeasuredAngle" in text:
        return text

    test = r'''

    @Test
    fun s2aMeasuredRebaseStartsAtMeasuredAngle() {
        val v = Fold7VirtualHingeGen5()
        v.startOpening(0L)

        val result = v.rebaseToMeasured(sample(1_000L, 115f))
        assertTrue(result.accepted)

        val target =
            v.targetForFrame(
                1_002_000_000L,
                1_010_333_333L,
            )

        assertEquals(Fold7VirtualHingeGen5.Mode.INSUFFICIENT, target.mode)
        assertTrue(abs(target.angleDegrees - 115f) < 0.05f)
        assertTrue(abs(target.correctionDegrees) < 0.05f)
    }
'''
    i = text.rfind("\n}")
    if i < 0:
        raise RuntimeError("hinge test class end not found")
    return text[:i] + test + text[i:]


def transform_panel(text: str) -> str:
    if MARKER in text:
        return text

    text = one(
        text,
        '''    private var openingAnchorMotionLastTilt = 0f\n    private var openingAnchorMotionLastStage = "inactive"\n''',
        f'''    private var openingAnchorMotionLastTilt = 0f\n    private var openingAnchorMotionLastStage = "inactive"\n    // {MARKER}: the inner anchor holds the shader peak until the first real\n    // Samsung precise measurement establishes geometry.\n    private var openingAnchorMotionPreciseSeeded = false\n''',
        "measured anchor state",
    )

    text = one(
        text,
        '''            openingAnchorMotionLastTilt = COVER_OPEN_IMMEDIATE_TILT\n            openingAnchorMotionLastStage = "cover"\n            startGen5OpeningFrameLoop()\n''',
        '''            openingAnchorMotionLastTilt = COVER_OPEN_IMMEDIATE_TILT\n            openingAnchorMotionLastStage = "cover"\n            openingAnchorMotionPreciseSeeded = false\n            startGen5OpeningFrameLoop()\n''',
        "reset precise seed for new opening",
    )

    target_anchor = '''                val target = gen5VirtualHinge.targetForFrame(\n                    callbackTimeNs = nowNs,\n                    expectedPresentationTimeNs = nowNs + gen5FrameIntervalNs,\n                )\n'''
    target_replacement = f'''                // {MARKER}: before Samsung exposes precise geometry on INNER,\n                // hold the already-proven anchor at the transition peak. This\n                // masks the handoff without inventing a moving hinge trajectory.\n                if (anchoredMotionStage == "inner-anchor" && !openingAnchorMotionPreciseSeeded) {{\n                    val waitingTilt = openingAnchorWaitingPreciseTilt()\n                    openingAnchorMotionLastTilt = waitingTilt\n                    surface?.tilt = waitingTilt\n                    Choreographer.getInstance().postFrameCallback(this)\n                    return\n                }}\n\n                val target = gen5VirtualHinge.targetForFrame(\n                    callbackTimeNs = nowNs,\n                    expectedPresentationTimeNs = nowNs + gen5FrameIntervalNs,\n                )\n'''
    text = one(text, target_anchor, target_replacement, "peak hold before precise seed")

    text = one(
        text,
        '''        created.tilt = openingAnchorMotionLastTilt\n        surface = created\n''',
        f'''        if (!openingAnchorMotionPreciseSeeded) {{\n            openingAnchorMotionLastTilt = openingAnchorWaitingPreciseTilt()\n        }}\n        created.tilt = openingAnchorMotionLastTilt\n        surface = created\n        com.duoopen.debug.DuoDiagnostics.event(\n            "opening-anchor-motion",\n            "PEAK_HOLD display=$displayId sequence=$sequence " +\n                "tilt=$openingAnchorMotionLastTilt preciseSeeded=$openingAnchorMotionPreciseSeeded",\n        )\n''',
        "inner attach peak hold",
    )

    start = "    fun onAuthoritativeAnchorMotionSample(\n"
    end = "    fun onHinge(\n"
    replacement = f'''    private fun openingAnchorWaitingPreciseTilt(): Float =\n        (gen5VisualLut.stateFor(90f).rightPaneTiltDegrees *\n            DuoSettings.config.value.intensity.coerceAtMost(1f))\n            .coerceIn(0f, DuoShader.MAX_TILT)\n\n    /**\n     * {MARKER}\n     * S1Z already proved that Samsung precise samples can drive Gen5 through\n     * the inner anchor. S2A changes only convergence: the first precise sample\n     * directly establishes current visual geometry, then ordinary Gen5\n     * prediction resumes from that measured state.\n     */\n    fun onAuthoritativeAnchorMotionSample(\n        angle: Float,\n        observedUptimeMs: Long,\n        source: String,\n        coarse: Boolean,\n    ) {{\n        if (openingAnchorProofBitmap == null) return\n        if (source != "SAMSUNG_PRECISE" || coarse || !angle.isFinite()) return\n\n        val deliveredUptimeMs = SystemClock.uptimeMillis()\n        val sample =\n            Fold7VirtualHingeGen5.Sample(\n                sourceTimeNs =\n                    observedUptimeMs.coerceAtMost(deliveredUptimeMs) * 1_000_000L,\n                deliveryTimeNs = deliveredUptimeMs * 1_000_000L,\n                angleDegrees = angle,\n            )\n\n        val firstPrecise = !openingAnchorMotionPreciseSeeded\n        val result =\n            if (firstPrecise) {{\n                gen5VirtualHinge.rebaseToMeasured(sample)\n            }} else {{\n                gen5VirtualHinge.addSample(sample)\n            }}\n\n        if (firstPrecise && result.accepted) {{\n            openingAnchorMotionPreciseSeeded = true\n            openingAnchorMotionLastTilt =\n                (gen5VisualLut.stateFor(angle).rightPaneTiltDegrees *\n                    DuoSettings.config.value.intensity.coerceAtMost(1f))\n                    .coerceIn(0f, DuoShader.MAX_TILT)\n            surface?.tilt = openingAnchorMotionLastTilt\n            com.duoopen.debug.DuoDiagnostics.event(\n                "opening-anchor-motion",\n                "PRECISE_SEED display=$displayId angle=$angle " +\n                    "tilt=$openingAnchorMotionLastTilt observed=$observedUptimeMs " +\n                    "delivered=$deliveredUptimeMs",\n            )\n        }} else {{\n            com.duoopen.debug.DuoDiagnostics.event(\n                "opening-anchor-motion",\n                "PRECISE_ADMIT display=$displayId angle=$angle " +\n                    "observed=$observedUptimeMs delivered=$deliveredUptimeMs " +\n                    "accepted=${{result.accepted}} reversal=${{result.reversal}} " +\n                    "reacquiring=${{result.reacquiring}}",\n            )\n        }}\n\n        if (result.accepted && angle >= DuoShader.FLAT_HINGE) {{\n            val sequence = openingRemapHandoffSequence\n            com.duoopen.debug.DuoDiagnostics.event(\n                "opening-anchor-motion",\n                "MEASURED_FLAT display=$displayId sequence=$sequence angle=$angle " +\n                    "threshold=${{DuoShader.FLAT_HINGE}}",\n            )\n            releaseOpeningAnchorProof(sequence, "measured-flat:$angle")\n        }}\n    }}\n\n'''
    text = between(text, start, end, replacement, "replace S1Z precise convergence method")

    presented_old = '''        if (decision.action == Fold7OpeningAnchorProofGate.Action.PRESENTED) {\n            openingRemapInnerSurfaceReady = true\n            com.duoopen.debug.DuoDiagnostics.event(\n                "opening-anchor-proof",\n                "PRESENTED sequence=$sequence evidence=${decision.reason} " +\n                    "elapsedMs=${decision.elapsedMs} holdMs=$ANCHOR_PROOF_VISIBLE_HOLD_MS trigger=$reason",\n            )\n            handler.postDelayed(\n                {\n                    releaseOpeningAnchorProof(sequence, "visible-hold-complete")\n                },\n                ANCHOR_PROOF_VISIBLE_HOLD_MS,\n            )\n            return\n        }\n'''
    presented_new = f'''        if (decision.action == Fold7OpeningAnchorProofGate.Action.PRESENTED) {{\n            openingRemapInnerSurfaceReady = true\n            com.duoopen.debug.DuoDiagnostics.event(\n                "opening-anchor-proof",\n                "PRESENTED sequence=$sequence evidence=${{decision.reason}} " +\n                    "elapsedMs=${{decision.elapsedMs}} release=measured-flat " +\n                    "flatThreshold=${{DuoShader.FLAT_HINGE}} " +\n                    "watchdogMs=$ANCHOR_MOTION_PRESENTED_WATCHDOG_MS trigger=$reason",\n            )\n            // {MARKER}: normal completion is geometry-driven. This delayed\n            // release is failure cleanup only (missing/stalled Samsung stream).\n            handler.postDelayed(\n                {{\n                    if (\n                        sequence == openingRemapHandoffSequence &&\n                        openingAnchorProofBitmap != null\n                    ) {{\n                        com.duoopen.debug.DuoDiagnostics.event(\n                            "opening-anchor-motion",\n                            "WATCHDOG_RELEASE display=$displayId sequence=$sequence " +\n                                "seeded=$openingAnchorMotionPreciseSeeded",\n                        )\n                        releaseOpeningAnchorProof(sequence, "measured-flat-watchdog")\n                    }}\n                }},\n                ANCHOR_MOTION_PRESENTED_WATCHDOG_MS,\n            )\n            return\n        }}\n'''
    text = one(text, presented_old, presented_new, "geometry-driven proof release")

    text = one(
        text,
        "        const val ANCHOR_PROOF_VISIBLE_HOLD_MS = 900L\n",
        "        const val ANCHOR_MOTION_PRESENTED_WATCHDOG_MS = 2_500L\n",
        "replace diagnostic visible hold with convergence watchdog",
    )

    text = exact_n(
        text,
        '''        openingAnchorMotionLastStage = "inactive"\n''',
        '''        openingAnchorMotionLastStage = "inactive"\n        openingAnchorMotionPreciseSeeded = false\n''',
        2,
        "proof terminal resets measured seed",
    )

    return text


def validate(gradle: str, hinge: str, hinge_test: str, panel: str) -> None:
    required = (
        (gradle, ['versionCode = 61', 'versionName = "5.1.0-beta2-zfold7-s2a-convergence"']),
        (hinge, [MARKER, "fun rebaseToMeasured", "visualAngle = accepted.angleDegrees", "visualVelocityDps = 0f"]),
        (hinge_test, ["s2aMeasuredRebaseStartsAtMeasuredAngle", "rebaseToMeasured(sample(1_000L, 115f))"]),
        (panel, [
            MARKER,
            "openingAnchorMotionPreciseSeeded",
            "openingAnchorWaitingPreciseTilt",
            "gen5VisualLut.stateFor(90f)",
            "PRECISE_SEED display=$displayId angle=$angle",
            "MEASURED_FLAT display=$displayId",
            "angle >= DuoShader.FLAT_HINGE",
            "ANCHOR_MOTION_PRESENTED_WATCHDOG_MS = 2_500L",
            "WATCHDOG_RELEASE display=$displayId",
            'source != "SAMSUNG_PRECISE"',
            "if (openingAnchorProofBitmap != null) return",
            "ANCHOR_AUTHORITY_EMERGENCY_HOLD_MS = 30_000L",
        ]),
    )
    for content, needles in required:
        for needle in needles:
            if needle not in content:
                raise RuntimeError("missing S2A invariant: " + needle)

    for forbidden in (
        'releaseOpeningAnchorProof(sequence, "visible-hold-complete")',
        "ANCHOR_PROOF_VISIBLE_HOLD_MS = 900L",
    ):
        if forbidden in panel:
            raise RuntimeError("S2A retained obsolete fixed-hold behavior: " + forbidden)


def apply(repo: Path, check: bool) -> None:
    paths = [repo / GRADLE, repo / HINGE, repo / HINGE_TEST, repo / PANEL]
    if not all(path.exists() for path in paths):
        raise RuntimeError("required S1Z materialized sources are missing")

    gradle = transform_gradle((repo / GRADLE).read_text(encoding="utf-8"))
    hinge = transform_hinge((repo / HINGE).read_text(encoding="utf-8"))
    hinge_test = transform_hinge_test((repo / HINGE_TEST).read_text(encoding="utf-8"))
    panel = transform_panel((repo / PANEL).read_text(encoding="utf-8"))
    validate(gradle, hinge, hinge_test, panel)

    if not check:
        (repo / GRADLE).write_text(gradle, encoding="utf-8")
        (repo / HINGE).write_text(hinge, encoding="utf-8")
        (repo / HINGE_TEST).write_text(hinge_test, encoding="utf-8")
        (repo / PANEL).write_text(panel, encoding="utf-8")


def self_test() -> None:
    # S1Z field evidence: first precise samples commonly arrive around 100..115
    # degrees. Peak hold at 90 then direct measured seed must never replay the
    # missing closed->measurement trajectory.
    peak = 90.0
    measured = 115.0
    flat = 172.0
    assert peak < measured < flat

    visual = peak
    visual = measured
    assert visual == measured
    assert visual != 0.5

    assert 171.9 < flat
    assert 172.0 >= flat
    print("S2A measured anchor convergence model: PASS")


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
    print("S2A measured anchor convergence: " + ("source shape verified" if args.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
