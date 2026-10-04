#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

GRADLE = Path("app/build.gradle.kts")
SHELL = Path("app/src/full/java/com/duoopen/shell/DuoShellService.kt")
SERVICE = Path("app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt")
PANEL = Path("app/src/full/java/com/duoopen/overlay/PanelEngine.kt")
VISUAL = Path("app/src/full/java/com/duoopen/debug/VisualForensics.kt")
EXPORTER = Path("app/src/main/java/com/duoopen/debug/DebugBundleExporter.kt")

MARKER = "STABILIZATION_S1J_OPENING_HANDOFF_TRUTH_V1"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_gradle(text: str) -> str:
    if 'versionName = "5.1.0-beta2-zfold7-s1j"' in text:
        return text
    text = one(text, "        versionCode = 43\n", "        versionCode = 44\n", "versionCode")
    text = one(
        text,
        '        versionName = "5.1.0-beta2-zfold7"\n',
        '        versionName = "5.1.0-beta2-zfold7-s1j"\n',
        "versionName",
    )
    return text


def transform_shell(text: str) -> str:
    if "S1J_WAKE_CRITICAL_S1G_DEFERRED" in text:
        return text
    if "STABILIZATION_S1G_FORENSIC_SUPERSET_V1" not in text:
        raise RuntimeError("S1G must be applied before S1J")
    old = '''        // S1G begins only after all pre-existing wake/route/SF/layout decisions.\n        val forensicTruth =\n            probeForensicTruth(\n                openingAttempt = openingAttempt,\n                wakeStartedMs = t0,\n            )\n'''
    new = '''        // S1J_WAKE_CRITICAL_S1G_DEFERRED: Fold7 field evidence showed this\n        // broad dumpsys sweep taking ~4.8s inside WAKE_INNER_DISPLAY. Keep its\n        // schema for compatibility, but do not run it on the wake-critical path.\n        val forensicTruth =\n            probeForensicTruth(\n                openingAttempt = -1L,\n                wakeStartedMs = t0,\n            )\n'''
    return one(text, old, new, "defer S1G wake-critical probe")


def transform_panel(text: str) -> str:
    if "fun openingHandoffDiagnosticState()" in text:
        return text
    helper = r'''    // STABILIZATION_S1J_OPENING_HANDOFF_TRUTH_V1: cheap app-side state only.
    // No Binder, dumpsys, screenshot or display mutation is performed here.
    fun openingHandoffDiagnosticState(): String {
        val mode = runCatching { display.mode }.getOrNull()
        return "id=$displayId state=${display.state} " +
            "mode=${mode?.physicalWidth ?: -1}x${mode?.physicalHeight ?: -1}@${mode?.refreshRate ?: -1f} " +
            "innerPanel=$innerPanel coverGeom=${isFold7CoverGeometryNow()} innerGeom=${isFold7InnerGeometryNow()} " +
            "phase=$phase showing=$showing coverOwned=$continuityCoverOwned " +
            "openingVisual=$continuityOpeningVisual surface=${surface != null}"
    }

'''
    return one(
        text,
        "    fun setContinuityCoverOwned(\n",
        helper + "    fun setContinuityCoverOwned(\n",
        "panel opening diagnostic state",
    )


def transform_service(text: str) -> str:
    if MARKER in text:
        return text
    if "VisualForensics.beginOpeningBurst" not in text:
        raise RuntimeError("S1H/S1I visual forensics must be present before S1J")

    direct = '''            // STABILIZATION_S1H_VISUAL_FORENSICS_V1: diagnostic-only sparse screenshot burst.\n            val forensicExclusions = engines.values.flatMap { engine ->\n                runCatching { engine.captureExclusionLayers() }.getOrDefault(emptyList())\n            }\n            VisualForensics.beginOpeningBurst(\n                context = applicationContext,\n                displayManager = displayManager,\n                scope = scope,\n                openingGeneration = continuity.generation,\n                reason = reason,\n                excludedLayers = forensicExclusions,\n            )\n'''
    text = one(
        text,
        direct,
        '''            startOpeningForensics(reason)\n''',
        "centralize existing S1H trigger",
    )

    helper = r'''    // STABILIZATION_S1J_OPENING_HANDOFF_TRUTH_V1: one trigger used by
    // every accepted opening path. VisualForensics de-dupes by continuity generation.
    private fun startOpeningForensics(reason: String) {
        val forensicExclusions = engines.values.flatMap { engine ->
            runCatching { engine.captureExclusionLayers() }.getOrDefault(emptyList())
        }
        DuoDiagnostics.event(
            "opening-handoff-truth",
            "forensics-trigger generation=${continuity.generation} reason=$reason exclusions=${forensicExclusions.size}",
        )
        VisualForensics.beginOpeningBurst(
            context = applicationContext,
            displayManager = displayManager,
            scope = scope,
            openingGeneration = continuity.generation,
            reason = reason,
            excludedLayers = forensicExclusions,
        )
    }

    private fun traceOpeningHandoff(phase: String, reason: String) {
        if (!::continuity.isInitialized || !::gen3Visual.isInitialized) return
        val state = continuity.state
        val active =
            state == Fold7ContinuityController.State.OPENING_FROM_CLOSED ||
                state == Fold7ContinuityController.State.INNER_HANDOFF ||
                gen3Visual.openingVisualDemandActive
        if (!active || reason.startsWith("hinge:")) return

        val displays = displayManager.displays.joinToString(" | ") { display ->
            val mode = runCatching { display.mode }.getOrNull()
            "id=${display.displayId}:state=${display.state}:" +
                "${mode?.physicalWidth ?: -1}x${mode?.physicalHeight ?: -1}@${mode?.refreshRate ?: -1f}"
        }
        val engineState = engines.values.joinToString(" || ") { it.openingHandoffDiagnosticState() }
        DuoDiagnostics.event(
            "opening-handoff-truth",
            "$phase reason=$reason state=$state generation=${continuity.generation} " +
                "demand=${gen3Visual.openingVisualDemandActive} host=${gen3Visual.openingHostDisplayId} " +
                "displays=[$displays] engines=[$engineState]",
        )
    }

'''
    text = one(
        text,
        "    // HALL_OPEN_LATCH_V3\n    private fun startLidEventsIfNeeded() {\n",
        helper + "    // HALL_OPEN_LATCH_V3\n    private fun startLidEventsIfNeeded() {\n",
        "S1J helper insertion",
    )

    device_call = '''                    gen3Visual.beginOpening(\n                        generation = continuity.generation,\n                        reason = "device-state:$reason",\n                    )\n'''
    text = one(
        text,
        device_call,
        device_call + '''                    startOpeningForensics("device-state:$reason")\n''',
        "device-state opening forensic trigger",
    )

    hinge_call = '''                gen3Visual.beginOpening(\n                    generation = continuity.generation,\n                    reason = "authoritative-hinge-opening-edge",\n                )\n'''
    text = one(
        text,
        hinge_call,
        hinge_call + '''                startOpeningForensics("authoritative-hinge-opening-edge")\n''',
        "hinge opening forensic trigger",
    )

    start = '''    private fun reconcileContinuityCoverRendering(\n        reason: String,\n    ) {\n        if (!::continuity.isInitialized) {\n            return\n        }\n\n        val privilegedReady =\n'''
    text = one(
        text,
        start,
        '''    private fun reconcileContinuityCoverRendering(\n        reason: String,\n    ) {\n        if (!::continuity.isInitialized) {\n            return\n        }\n\n        traceOpeningHandoff("BEFORE", reason)\n\n        val privilegedReady =\n''',
        "opening handoff trace before reconcile",
    )

    end = '''            } else {\n                engine.endContinuityOpeningVisual(\n                    "gen3-opening-not-owner:$reason"\n                )\n            }\n        }\n    }\n\n    /** Samsung continuous angle via Shizuku + fold wallpaper, when everything lines up. */\n'''
    text = one(
        text,
        end,
        '''            } else {\n                engine.endContinuityOpeningVisual(\n                    "gen3-opening-not-owner:$reason"\n                )\n            }\n        }\n\n        traceOpeningHandoff("AFTER", reason)\n    }\n\n    /** Samsung continuous angle via Shizuku + fold wallpaper, when everything lines up. */\n''',
        "opening handoff trace after reconcile",
    )

    return text


def transform_visual(text: str) -> str:
    if "S1J_FINAL_SAMPLE_SHELL_PROBE_ONLY" in text:
        return text
    if "STABILIZATION_S1I_CORRELATED_FORENSICS_V1" not in text:
        raise RuntimeError("S1I must be applied before S1J")

    text = one(
        text,
        "    private val OFFSETS_MS = longArrayOf(0L, 500L, 1_200L, 2_500L)\n",
        "    // S1J: let the ownership handoff occur before the first screenshot call.\n"
        "    private val OFFSETS_MS = longArrayOf(120L, 350L, 900L, 1_800L)\n",
        "S1J visual offsets",
    )

    text = one(
        text,
        '''        val shell = runCatching { ShizukuBridge.renderTimelineProbe() }.getOrNull()\n''',
        '''        // S1J_FINAL_SAMPLE_SHELL_PROBE_ONLY: repeated dumpsys calls can take\n        // seconds on Fold7. Early samples keep only app DisplayManager + pixel truth.\n        val shell = if (sample == OFFSETS_MS.lastIndex) {\n            runCatching { ShizukuBridge.renderTimelineProbe() }.getOrNull()\n        } else {\n            null\n        }\n''',
        "final-sample-only shell render probe",
    )

    text = one(
        text,
        '''                appendLine("probeWallMs=${probeWallFinished - probeWallStarted}")\n                appendLine("shellProbeOk=${shell?.getBoolean("ok", false) == true}")\n''',
        '''                appendLine("probeWallMs=${probeWallFinished - probeWallStarted}")\n                appendLine("shellProbePolicy=S1J_FINAL_SAMPLE_ONLY")\n                appendLine("shellProbeOk=${shell?.getBoolean("ok", false) == true}")\n''',
        "S1J context policy marker",
    )
    return text


def transform_exporter(text: str) -> str:
    if "openingHandoffTruth=STABILIZATION_S1J_OPENING_HANDOFF_TRUTH_V1" in text:
        return text
    old = '''                        appendLine(\n                            "visualForensics=ENABLED_IN_S1H_EXPERIMENTAL_BUILD"\n                        )\n'''
    new = old + '''                        appendLine(\n                            "openingHandoffTruth=STABILIZATION_S1J_OPENING_HANDOFF_TRUTH_V1"\n                        )\n                        appendLine(\n                            "wakeCriticalS1GProbe=DEFERRED_IN_S1J"\n                        )\n                        appendLine(\n                            "visualShellProbePolicy=FINAL_SAMPLE_ONLY"\n                        )\n'''
    return one(text, old, new, "export S1J identity")


def validate(g: str, s: str, f: str, p: str, v: str, e: str) -> None:
    requirements = (
        (g, ['versionCode = 44', 'versionName = "5.1.0-beta2-zfold7-s1j"']),
        (s, ["S1J_WAKE_CRITICAL_S1G_DEFERRED", "openingAttempt = -1L"]),
        (p, [MARKER, "openingHandoffDiagnosticState", "openingVisual=$continuityOpeningVisual"]),
        (f, [MARKER, "startOpeningForensics", "opening-handoff-truth", 'startOpeningForensics("device-state:$reason")', 'startOpeningForensics("authoritative-hinge-opening-edge")', 'traceOpeningHandoff("BEFORE", reason)', 'traceOpeningHandoff("AFTER", reason)']),
        (v, ["S1J_FINAL_SAMPLE_SHELL_PROBE_ONLY", "longArrayOf(120L, 350L, 900L, 1_800L)", "shellProbePolicy=S1J_FINAL_SAMPLE_ONLY"]),
        (e, ["openingHandoffTruth=STABILIZATION_S1J_OPENING_HANDOFF_TRUTH_V1", "wakeCriticalS1GProbe=DEFERRED_IN_S1J"]),
    )
    for text, needles in requirements:
        for needle in needles:
            if needle not in text:
                raise RuntimeError("missing S1J invariant: " + needle)

    if f.count("VisualForensics.beginOpeningBurst(") != 1:
        raise RuntimeError("S1J must centralize VisualForensics.beginOpeningBurst to exactly one helper")

    for forbidden in (
        "STABILIZATION_S1C_ACTIVE_TRANSFER_V1",
        "STABILIZATION_S1D_REAL_INNER_EDGE_V1",
        "cmd device_state state 4",
        "cmd device_state state 5",
    ):
        if forbidden in s:
            raise RuntimeError("S1J unexpectedly contains behavior mutation: " + forbidden)


def apply(repo: Path, check: bool) -> None:
    paths = (GRADLE, SHELL, SERVICE, PANEL, VISUAL, EXPORTER)
    for path in paths:
        if not (repo / path).exists():
            raise RuntimeError("missing " + str(path))

    g = transform_gradle((repo / GRADLE).read_text())
    s = transform_shell((repo / SHELL).read_text())
    f = transform_service((repo / SERVICE).read_text())
    p = transform_panel((repo / PANEL).read_text())
    v = transform_visual((repo / VISUAL).read_text())
    e = transform_exporter((repo / EXPORTER).read_text())
    validate(g, s, f, p, v, e)

    if not check:
        for path, text in ((GRADLE, g), (SHELL, s), (SERVICE, f), (PANEL, p), (VISUAL, v), (EXPORTER, e)):
            (repo / path).write_text(text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        gradle = '        versionCode = 43\n        versionName = "5.1.0-beta2-zfold7"\n'
        out = transform_gradle(gradle)
        assert "versionCode = 44" in out
        assert "zfold7-s1j" in out
        print("stabilization S1J opening handoff truth transformer self-test: PASS")
        if not args.check:
            return 0

    apply(Path(args.repo).resolve(), args.check)
    print("stabilization S1J opening handoff truth: " + ("source shape verified" if args.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
