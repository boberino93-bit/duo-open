#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

P = Path("app/src/full/java/com/duoopen/shell/ShellProtocol.kt")
S = Path("app/src/full/java/com/duoopen/shell/DuoShellService.kt")
B = Path("app/src/full/java/com/duoopen/shell/ShizukuBridge.kt")
V = Path("app/src/full/java/com/duoopen/debug/VisualForensics.kt")

M = "STABILIZATION_S1I_CORRELATED_FORENSICS_V1"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def protocol(text: str) -> str:
    if "RENDER_TIMELINE_PROBE = 20" in text:
        return text
    if "CAPTURE_PHYSICAL_FORENSIC = 19" not in text:
        raise RuntimeError("S1H protocol must be applied first")
    return one(
        text,
        "    const val CAPTURE_PHYSICAL_FORENSIC = 19\n\n    const val CB_ANGLE = 1\n",
        "    const val CAPTURE_PHYSICAL_FORENSIC = 19\n"
        "    // STABILIZATION_S1I_CORRELATED_FORENSICS_V1: read-only dynamic render timeline probe.\n"
        "    const val RENDER_TIMELINE_PROBE = 20\n\n"
        "    const val CB_ANGLE = 1\n",
        "protocol timeline code",
    )


def shell(text: str) -> str:
    if M in text:
        return text
    if "STABILIZATION_S1H_VISUAL_FORENSICS_V1" not in text:
        raise RuntimeError("S1H shell diagnostics must be applied first")

    transaction = r'''            ShellProtocol.RENDER_TIMELINE_PROBE -> {
                // STABILIZATION_S1I_CORRELATED_FORENSICS_V1: read-only only.
                val identity = clearCallingIdentity()
                val result = try {
                    renderTimelineProbe()
                } catch (error: Throwable) {
                    Bundle().apply {
                        putBoolean("ok", false)
                        putString("error", "${error.javaClass.simpleName}: ${error.message}")
                    }
                } finally {
                    restoreCallingIdentity(identity)
                }
                out.writeNoException()
                out.writeBundle(result)
            }
'''
    text = one(
        text,
        "            ShellProtocol.START_ANGLES -> {\n",
        transaction + "            ShellProtocol.START_ANGLES -> {\n",
        "timeline transaction",
    )

    helper = r'''    // STABILIZATION_S1I_CORRELATED_FORENSICS_V1: compact dynamic state
    // sampled beside the visual burst. This intentionally avoids the broad S1G
    // forensic sweep so the repeated samples remain bounded and measurable.
    private fun renderTimelineProbe(): Bundle {
        val started = SystemClock.elapsedRealtime()
        val timings = mutableListOf<String>()

        fun snap(label: String, command: String): String {
            val t0 = SystemClock.elapsedRealtime()
            val value = runCatching { runProbe(command) }
                .getOrElse { error -> "probe-error=${error.javaClass.simpleName}:${error.message}" }
                .lineSequence()
                .map { it.trim() }
                .filter { it.isNotBlank() }
                .take(180)
                .joinToString("\n")
                .take(12000)
            timings += "$label=${SystemClock.elapsedRealtime() - t0}ms"
            return value
        }

        val deviceState = snap(
            "device-state",
            "cmd device_state state 2>/dev/null",
        )
        val displayFramework = snap(
            "display-framework",
            "dumpsys display 2>/dev/null | " +
                "grep -E -i 'LogicalDisplayMapper:|mCurrentLayout=|mDeviceState=|" +
                "mPendingDeviceState=|Logical Displays:|^[[:space:]]*Display [0-9]+:|" +
                "mIsEnabled=|mPrimaryDisplayDevice=|DisplayDeviceInfo|uniqueId=|address|" +
                "DisplayPowerController|mDisplayReadyLocked=|mPendingRequestLocked=|" +
                "mPendingUpdatePowerStateLocked=|mDisplayEnabled=|mIsInTransition=|" +
                "mScreenState=|mState=|mCommittedState=|mBrightnessState=' | head -n 220",
        )
        val windowDisplays = snap(
            "window-displays",
            "dumpsys window displays 2>/dev/null | " +
                "grep -E -i 'Display: mDisplayId=|DisplayContent|mCurrentFocus|mFocusedApp|" +
                "mWaitingForConfig|mDisplayReady|mOpeningApps|mClosingApps|" +
                "mChangingContainers|mTransition|collecting|waitingForRemoteDisplayChange|" +
                "init=|cur=|app=|Wallpaper|Launcher|SystemUI|AppWidget' | head -n 220",
        )
        val activityTasks = snap(
            "activity-tasks",
            "dumpsys activity activities 2>/dev/null | " +
                "grep -E -i 'Display #[0-9]+|RootTask|mResumedActivity|topResumedActivity|" +
                "mLastPausedActivity|realActivity=|homeActivity|launcher|systemui|AppWidget' | head -n 180",
        )
        val wallpaper = snap(
            "wallpaper",
            "dumpsys wallpaper 2>/dev/null | " +
                "grep -E -i 'mWallpaper|Wallpaper|visible|mVisible|Engine|mEngine|display|" +
                "surface|shown|draw|offset|connection|component' | head -n 160",
        )
        val surfaceLayers = snap(
            "surface-layers",
            "dumpsys SurfaceFlinger --list 2>/dev/null | " +
                "grep -E -i 'Launcher|Wallpaper|SystemUI|AppWidget|duoopen|Duo Open|SurfaceView|Task' | head -n 180",
        )

        return Bundle().apply {
            putBoolean("ok", true)
            putLong("probeStartedElapsedMs", started)
            putLong("probeMs", SystemClock.elapsedRealtime() - started)
            putString("probeTimings", timings.joinToString(","))
            putString("deviceState", deviceState)
            putString("displayFramework", displayFramework)
            putString("windowDisplays", windowDisplays)
            putString("activityTasks", activityTasks)
            putString("wallpaper", wallpaper)
            putString("surfaceLayers", surfaceLayers)
        }
    }

'''
    return one(
        text,
        "    // ---- Samsung wallpaper angle reader -------------------------------------\n",
        helper + "    // ---- Samsung wallpaper angle reader -------------------------------------\n",
        "timeline probe helper",
    )


def bridge(text: str) -> str:
    if "fun renderTimelineProbe()" in text:
        return text
    if "fun capturePhysicalForensics(" not in text:
        raise RuntimeError("S1H bridge diagnostics must be applied first")
    addition = r'''    /**
     * S1I read-only dynamic timeline snapshot. Blocking; call only from the
     * forensic IO worker, never the main/render thread.
     */
    fun renderTimelineProbe(): Bundle? =
        call(ShellProtocol.RENDER_TIMELINE_PROBE)

'''
    return one(
        text,
        "    /** Receives angles from the shell-side wallpaper log reader. */\n",
        addition + "    /** Receives angles from the shell-side wallpaper log reader. */\n",
        "bridge timeline method",
    )


def visual(text: str) -> str:
    if M in text:
        return text
    if "S1H_RENDER_STACK_CONTEXT_V1" not in text:
        raise RuntimeError("S1H render-context diagnostics must be applied first")

    text = one(
        text,
        '    private const val MARKER = "STABILIZATION_S1H_VISUAL_FORENSICS_V1"\n',
        '    private const val MARKER = "STABILIZATION_S1H_VISUAL_FORENSICS_V1"\n'
        f'    private const val CORRELATION_MARKER = "{M}"\n',
        "correlation marker",
    )

    text = one(
        text,
        '''        val darkFraction: Double?,
    )
''',
        '''        val darkFraction: Double?,
        // S1I: true wall-clock timing around each individual capture call.
        val captureStartedElapsedMs: Long = -1L,
        val captureFinishedElapsedMs: Long = -1L,
        val wallCaptureMs: Long = -1L,
        val backendCaptureMs: Long = -1L,
        val sourceWidth: Int = -1,
        val sourceHeight: Int = -1,
    )
''',
        "record timing fields",
    )

    text = one(
        text,
        '''                appendLine("marker=$MARKER")
                appendLine("started=${Instant.now()}")
                appendLine("generation=$openingGeneration")
''',
        '''                appendLine("marker=$MARKER")
                appendLine("correlationMarker=$CORRELATION_MARKER")
                appendLine("started=${Instant.now()}")
                appendLine("startedElapsedRealtimeMs=$startedElapsed")
                appendLine("generation=$openingGeneration")
''',
        "readme timing metadata",
    )

    old_loop = '''                for (panel in listOf("cover", "inner")) {
                    val route = routes[panel]
                    val physicalId = if (panel == "cover") coverPhysical else innerPhysical

                    val logical = if (route == null) {
                        Record(index, target, actual, panel, "logical-excluded", -1, physicalId,
                            Display.STATE_UNKNOWN, exclusions.size, "NO_LOGICAL_ROUTE", false, null,
                            null, 0L, null, null, null, null)
                    } else {
                        captureLogical(session, index, target, actual, panel, route, physicalId, exclusions)
                    }
                    records += logical

                    val physicalRecord = capturePhysical(session, index, target, actual, panel, route, physicalId)
                    records += physicalRecord
                }
'''
    new_loop = '''                for (panel in listOf("cover", "inner")) {
                    val route = routes[panel]
                    val physicalId = if (panel == "cover") coverPhysical else innerPhysical

                    val logicalStarted = SystemClock.elapsedRealtime()
                    val logicalBase = if (route == null) {
                        Record(index, target, actual, panel, "logical-excluded", -1, physicalId,
                            Display.STATE_UNKNOWN, exclusions.size, "NO_LOGICAL_ROUTE", false, null,
                            null, 0L, null, null, null, null)
                    } else {
                        captureLogical(session, index, target, actual, panel, route, physicalId, exclusions)
                    }
                    val logicalFinished = SystemClock.elapsedRealtime()
                    val logical = logicalBase.copy(
                        captureStartedElapsedMs = logicalStarted,
                        captureFinishedElapsedMs = logicalFinished,
                        wallCaptureMs = logicalFinished - logicalStarted,
                    )
                    records += logical

                    val physicalStarted = SystemClock.elapsedRealtime()
                    val physicalBase = capturePhysical(session, index, target, actual, panel, route, physicalId)
                    val physicalFinished = SystemClock.elapsedRealtime()
                    val physicalRecord = physicalBase.copy(
                        captureStartedElapsedMs = physicalStarted,
                        captureFinishedElapsedMs = physicalFinished,
                        wallCaptureMs = physicalFinished - physicalStarted,
                    )
                    records += physicalRecord
                }

                captureTimelineContext(
                    session = session,
                    sample = index,
                    targetMs = target,
                    sampleLoopActualMs = actual,
                    burstStartedElapsedMs = startedElapsed,
                    openingGeneration = openingGeneration,
                    displayManager = displayManager,
                )
'''
    text = one(text, old_loop, new_loop, "measured capture loop")

    # Retain shell/backend-reported capture duration and logical source dimensions.
    text = one(
        text,
        '''            return Record(sample, target, actual, panel, "logical-excluded", route.id, physicalId,
                route.state, exclusions.size, result.status, result.secureLayers, result.error,
                null, 0L, null, null, null, null)
''',
        '''            return Record(sample, target, actual, panel, "logical-excluded", route.id, physicalId,
                route.state, exclusions.size, result.status, result.secureLayers, result.error,
                null, 0L, null, null, null, null,
                backendCaptureMs = result.captureMs,
                sourceWidth = result.sourceWidth,
                sourceHeight = result.sourceHeight,
            )
''',
        "logical failure backend timing",
    )
    text = one(
        text,
        '''            Record(sample, target, actual, panel, "logical-excluded", route.id, physicalId,
                route.state, exclusions.size, "CAPTURED", false, null, name, file.length(), sha256(file),
                metric.mean, metric.range, metric.dark)
''',
        '''            Record(sample, target, actual, panel, "logical-excluded", route.id, physicalId,
                route.state, exclusions.size, "CAPTURED", false, null, name, file.length(), sha256(file),
                metric.mean, metric.range, metric.dark,
                backendCaptureMs = result.captureMs,
                sourceWidth = result.sourceWidth,
                sourceHeight = result.sourceHeight,
            )
''',
        "logical success backend timing",
    )
    text = one(
        text,
        '''            Record(sample, target, actual, panel, "logical-excluded", route.id, physicalId,
                route.state, exclusions.size, "PERSIST_FAILED", false,
                "${error.javaClass.simpleName}: ${error.message}", null, 0L, null, null, null, null)
''',
        '''            Record(sample, target, actual, panel, "logical-excluded", route.id, physicalId,
                route.state, exclusions.size, "PERSIST_FAILED", false,
                "${error.javaClass.simpleName}: ${error.message}", null, 0L, null, null, null, null,
                backendCaptureMs = result.captureMs,
                sourceWidth = result.sourceWidth,
                sourceHeight = result.sourceHeight,
            )
''',
        "logical persist timing",
    )

    text = one(
        text,
        '''            return Record(sample, target, actual, panel, "physical-screencap", route?.id ?: -1, physicalId,
                route?.state ?: Display.STATE_UNKNOWN, 0, result.status, false,
                listOfNotNull(result.error, result.commandOutput).joinToString(" | ").ifBlank { null },
                null, 0L, null, null, null, null)
''',
        '''            return Record(sample, target, actual, panel, "physical-screencap", route?.id ?: -1, physicalId,
                route?.state ?: Display.STATE_UNKNOWN, 0, result.status, false,
                listOfNotNull(result.error, result.commandOutput).joinToString(" | ").ifBlank { null },
                null, 0L, null, null, null, null,
                backendCaptureMs = result.captureMs,
            )
''',
        "physical failure backend timing",
    )
    text = one(
        text,
        '''        val bitmap = BitmapFactory.decodeFile(file.absolutePath)
        val metric = bitmap?.let(::metrics)
        bitmap?.recycle()
        return Record(sample, target, actual, panel, "physical-screencap", route?.id ?: -1, physicalId,
            route?.state ?: Display.STATE_UNKNOWN, 0, "CAPTURED", false, result.commandOutput,
            name, file.length(), sha256(file), metric?.mean, metric?.range, metric?.dark)
''',
        '''        val bitmap = BitmapFactory.decodeFile(file.absolutePath)
        val sourceWidth = bitmap?.width ?: -1
        val sourceHeight = bitmap?.height ?: -1
        val metric = bitmap?.let(::metrics)
        bitmap?.recycle()
        return Record(sample, target, actual, panel, "physical-screencap", route?.id ?: -1, physicalId,
            route?.state ?: Display.STATE_UNKNOWN, 0, "CAPTURED", false, result.commandOutput,
            name, file.length(), sha256(file), metric?.mean, metric?.range, metric?.dark,
            backendCaptureMs = result.captureMs,
            sourceWidth = sourceWidth,
            sourceHeight = sourceHeight,
        )
''',
        "physical success backend timing",
    )

    helper = r'''    // STABILIZATION_S1I_CORRELATED_FORENSICS_V1: one compact dynamic
    // render/presentation state snapshot per scheduled visual sample. The probe
    // begins only after that sample's screenshot calls have completed. Exact
    // probe timing is recorded so diagnostic overhead cannot masquerade as
    // transition timing.
    private fun captureTimelineContext(
        session: File,
        sample: Int,
        targetMs: Long,
        sampleLoopActualMs: Long,
        burstStartedElapsedMs: Long,
        openingGeneration: Long,
        displayManager: DisplayManager,
    ) {
        val probeWallStarted = SystemClock.elapsedRealtime()
        val shell = runCatching { ShizukuBridge.renderTimelineProbe() }.getOrNull()
        val probeWallFinished = SystemClock.elapsedRealtime()
        val displays = displayManager.displays.joinToString("\n") { display ->
            val mode = runCatching { display.mode }.getOrNull()
            "id=${display.displayId} state=${display.state} name=${display.name} " +
                "mode=${mode?.physicalWidth ?: -1}x${mode?.physicalHeight ?: -1}@${mode?.refreshRate ?: -1f}"
        }

        fun field(name: String): String = shell?.getString(name).orEmpty().ifBlank { "<unavailable>" }
        File(session, "s${sample}-${targetMs}ms-correlated-context.txt").writeText(
            buildString {
                appendLine("marker=$CORRELATION_MARKER")
                appendLine("generation=$openingGeneration")
                appendLine("sample=$sample")
                appendLine("targetMs=$targetMs")
                appendLine("sampleLoopActualMs=$sampleLoopActualMs")
                appendLine("probeStartRelativeMs=${probeWallStarted - burstStartedElapsedMs}")
                appendLine("probeEndRelativeMs=${probeWallFinished - burstStartedElapsedMs}")
                appendLine("probeWallMs=${probeWallFinished - probeWallStarted}")
                appendLine("shellProbeOk=${shell?.getBoolean("ok", false) == true}")
                appendLine("shellProbeStartedElapsedMs=${shell?.getLong("probeStartedElapsedMs", -1L) ?: -1L}")
                appendLine("shellProbeMs=${shell?.getLong("probeMs", -1L) ?: -1L}")
                appendLine("shellProbeTimings=${field("probeTimings")}")
                appendLine("shellProbeError=${shell?.getString("error") ?: ""}")
                appendLine("\n=== app_display_manager ===\n${displays.ifBlank { "<none>" }}")
                appendLine("\n=== device_state ===\n${field("deviceState")}")
                appendLine("\n=== display_framework ===\n${field("displayFramework")}")
                appendLine("\n=== window_displays ===\n${field("windowDisplays")}")
                appendLine("\n=== activity_tasks ===\n${field("activityTasks")}")
                appendLine("\n=== wallpaper ===\n${field("wallpaper")}")
                appendLine("\n=== surface_layers ===\n${field("surfaceLayers")}")
            }
        )

        val device = field("deviceState").lineSequence().firstOrNull().orEmpty().take(160)
        val focus = field("windowDisplays").lineSequence()
            .firstOrNull { it.contains("focus", ignoreCase = true) }.orEmpty().take(220)
        DuoDiagnostics.event(
            "visual-forensics-sample",
            "generation=$openingGeneration sample=$sample target=$targetMs " +
                "loop=$sampleLoopActualMs probeStart=${probeWallStarted - burstStartedElapsedMs} " +
                "probeMs=${probeWallFinished - probeWallStarted} device=$device focus=$focus",
        )
    }

'''
    text = one(
        text,
        "    private fun isCurrent(generation: Long): Boolean =\n",
        helper + "    private fun isCurrent(generation: Long): Boolean =\n",
        "timeline context helper",
    )

    text = one(
        text,
        '''        file.writeText("sample\ttargetMs\tactualMs\tpanel\tbackend\tlogicalId\tphysicalId\tdisplayState\trawStatus\tclassification\tsecure\tfile\tbytes\tsha256\tmeanLuma\tlumaRange\tdarkFraction\terror\n")
''',
        '''        file.writeText("sample\ttargetMs\tactualMs\tpanel\tbackend\tlogicalId\tphysicalId\tdisplayState\trawStatus\tclassification\tsecure\tfile\tbytes\tsha256\tmeanLuma\tlumaRange\tdarkFraction\tcaptureStartedElapsedMs\tcaptureFinishedElapsedMs\twallCaptureMs\tbackendCaptureMs\tsourceWidth\tsourceHeight\terror\n")
''',
        "manifest timing header",
    )
    text = one(
        text,
        '''                r.lumaRange ?: "", r.darkFraction?.let { "%.4f".format(Locale.US, it) }.orEmpty(),
                sanitize(r.error)
''',
        '''                r.lumaRange ?: "", r.darkFraction?.let { "%.4f".format(Locale.US, it) }.orEmpty(),
                r.captureStartedElapsedMs, r.captureFinishedElapsedMs, r.wallCaptureMs, r.backendCaptureMs,
                r.sourceWidth, r.sourceHeight, sanitize(r.error)
''',
        "manifest timing values",
    )

    return text


def validate(p: str, s: str, b: str, v: str) -> None:
    required = (
        (p, ["RENDER_TIMELINE_PROBE = 20"]),
        (s, [M, "renderTimelineProbe()", "probeTimings", "displayFramework", "windowDisplays", "surfaceLayers"]),
        (b, ["fun renderTimelineProbe()", "RENDER_TIMELINE_PROBE"]),
        (v, [M, "captureStartedElapsedMs", "backendCaptureMs", "sourceWidth", "s0-", "correlated-context.txt", "visual-forensics-sample"]),
    )
    for text, needles in required:
        for needle in needles:
            if needle not in text:
                raise RuntimeError("missing S1I invariant: " + needle)


def apply(repo: Path, check: bool) -> None:
    for path in (P, S, B, V):
        if not (repo / path).exists():
            raise RuntimeError("missing " + str(path))
    p = protocol((repo / P).read_text())
    s = shell((repo / S).read_text())
    b = bridge((repo / B).read_text())
    v = visual((repo / V).read_text())
    validate(p, s, b, v)
    if not check:
        for path, text in ((P, p), (S, s), (B, b), (V, v)):
            (repo / path).write_text(text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        source = "object X {\n    const val CAPTURE_PHYSICAL_FORENSIC = 19\n\n    const val CB_ANGLE = 1\n}\n"
        out = protocol(source)
        assert "RENDER_TIMELINE_PROBE = 20" in out
        assert out.count("RENDER_TIMELINE_PROBE = 20") == 1
        print("stabilization S1I correlated forensics transformer self-test: PASS")
        if not args.check:
            return 0
    apply(Path(args.repo).resolve(), args.check)
    print("stabilization S1I correlated forensics: " + ("source shape verified" if args.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
