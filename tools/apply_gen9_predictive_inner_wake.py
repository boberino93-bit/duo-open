#!/usr/bin/env python3
"""Apply Gen9 predictive inner prewake + low-latency animation after Gen8."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def replace_regex_once(text: str, pattern: str, replacement: str, label: str) -> str:
    out, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one regex match, found {count}")
    return out


def apply(repo: Path) -> None:
    # Version
    build = repo / "app/build.gradle.kts"
    text = build.read_text()
    text = replace_once(text, "versionCode = 44", "versionCode = 45", "versionCode")
    text = replace_once(
        text,
        'versionName = "5.2.0-gen8-anchored-zfold7"',
        'versionName = "5.3.0-gen9-responsive-zfold7"',
        "versionName",
    )
    build.write_text(text)

    # DeviceState: expose the earlier folded->folded Samsung transition as an
    # infrastructure-only hint. It never becomes visual geometry or authority.
    observer = repo / "app/src/full/java/com/duoopen/overlay/Fold7DeviceStateObserver.kt"
    text = observer.read_text()
    if "onPreOpeningHint" not in text:
        text = replace_once(
            text,
            """    private val onOpeningEdge: (\n        previousStateId: Int,\n        currentStateId: Int,\n    ) -> Unit,\n) {""",
            """    private val onPreOpeningHint: (\n        previousStateId: Int,\n        currentStateId: Int,\n    ) -> Unit = { _, _ -> },\n    private val onOpeningEdge: (\n        previousStateId: Int,\n        currentStateId: Int,\n    ) -> Unit,\n) {""",
            "device-state pre-opening callback",
        )

        opening_block = """        if (\n            previousId != null &&\n            previousFolded == true &&\n            inferredFolded == false\n        ) {\n            onOpeningEdge(\n                previousId,\n                id,\n            )\n        }"""
        pre_block = """        /* GEN9_PREDICTIVE_INNER_WAKE\n         * Fold7 field evidence repeatedly showed a Samsung folded-state\n         * transition (for example 0 -> 1) 0.48-0.83 s before the existing\n         * unfolded/90-degree wake edge. Treat this only as a speculative\n         * infrastructure hint: both states must still be physically folded.\n         */\n        if (\n            previousId != null &&\n            previousId != id &&\n            previousFolded == true &&\n            inferredFolded == true\n        ) {\n            onPreOpeningHint(\n                previousId,\n                id,\n            )\n        }\n\n""" + opening_block
        text = replace_once(text, opening_block, pre_block, "device-state hint emission")
    observer.write_text(text)

    # Service wiring: hint wakes infrastructure, normal opening edge continues
    # to own semantic transition + Gen3 visual start.
    service = repo / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"
    text = service.read_text()
    if "onPreOpeningHint =" not in text:
        text = replace_once(
            text,
            """            Fold7DeviceStateObserver(\n                context = this,\n                handler = handler,\n            ) {""",
            """            Fold7DeviceStateObserver(\n                context = this,\n                handler = handler,\n                onPreOpeningHint = {\n                        previousStateId,\n                        currentStateId,\n                    ->\n                    val reason =\n                        \"device-state-pre:$previousStateId->$currentStateId\"\n\n                    angleFeed\n                        ?.kickBurst(\n                            reason\n                        )\n\n                    continuity\n                        .onPreOpeningHint(\n                            reason\n                        )\n                },\n            ) {""",
            "service predictive prewake wiring",
        )
    service.write_text(text)

    # Coordinator: physical-only speculative wake with cooldown. This does not
    # mutate controller state/generation and does not touch logical routing.
    coordinator = repo / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"
    text = coordinator.read_text()
    if "innerPrewakeInFlight" not in text:
        text = replace_once(
            text,
            """    @Volatile private var prewarmInFlightGeneration = -1L\n    @Volatile private var prewarmInFlightConnectionEpoch = -1L""",
            """    @Volatile private var prewarmInFlightGeneration = -1L\n    @Volatile private var prewarmInFlightConnectionEpoch = -1L\n    @Volatile private var innerPrewakeInFlight = false\n    private var lastInnerPrewakeUptimeMs = 0L""",
            "coordinator prewake state",
        )

        marker = """    /**\n     * Wake-only ingress from DeviceStateManager."""
        method = """    /**\n     * Gen9 speculative infrastructure prewake.\n     *\n     * Samsung's early folded-state transition is useful prediction, not\n     * authority. We only power the stable physical inner panel while native\n     * cover ownership is still proven. Logical routing and visible handoff\n     * remain owned by the ordinary WakeInner path after a real opening edge.\n     */\n    fun onPreOpeningHint(\n        reason: String,\n    ) {\n        if (\n            !renderOwnershipArmed ||\n            !ShizukuBridge.ready\n        ) {\n            return\n        }\n\n        val now =\n            SystemClock.uptimeMillis()\n\n        val topologyNow =\n            topology()\n\n        val accepted =\n            controller.state ==\n                Fold7ContinuityController.State.NATIVE_COVER &&\n                topologyNow.nativeCover &&\n                !innerPrewakeInFlight &&\n                (\n                    lastInnerPrewakeUptimeMs == 0L ||\n                        now - lastInnerPrewakeUptimeMs >=\n                        INNER_PREWAKE_COOLDOWN_MS\n                    )\n\n        if (!accepted) {\n            DuoDiagnostics.event(\n                \"inner-prewake\",\n                \"ignored reason=$reason state=${controller.state} \" +\n                    \"nativeCover=${topologyNow.nativeCover} inFlight=$innerPrewakeInFlight\",\n            )\n            return\n        }\n\n        innerPrewakeInFlight = true\n        lastInnerPrewakeUptimeMs = now\n        val requestGeneration =\n            controller.generation\n        val queuedAtNs =\n            SystemClock.elapsedRealtimeNanos()\n\n        DuoDiagnostics.event(\n            \"inner-prewake\",\n            \"START reason=$reason generation=$requestGeneration\",\n        )\n\n        scope.launch(Dispatchers.IO) {\n            val startedAtNs =\n                SystemClock.elapsedRealtimeNanos()\n\n            val result =\n                runCatching {\n                    ShizukuBridge.prewakeInnerPhysical()\n                }.getOrNull()\n\n            val completedAtNs =\n                SystemClock.elapsedRealtimeNanos()\n\n            handler.post {\n                innerPrewakeInFlight = false\n\n                val currentTopology =\n                    topology()\n\n                DuoDiagnostics.event(\n                    \"inner-prewake\",\n                    \"DONE reason=$reason requestGeneration=$requestGeneration \" +\n                        \"currentGeneration=${controller.generation} state=${controller.state} \" +\n                        \"ok=${result?.getBoolean(\"ok\", false) == true} \" +\n                        \"physical=${result?.getLong(\"physicalDisplayId\", -1L) ?: -1L} \" +\n                        \"queueMs=${\"%.3f\".format((startedAtNs - queuedAtNs) / 1_000_000.0)} \" +\n                        \"shellLatencyMs=${result?.getLong(\"latencyMs\", -1L) ?: -1L} \" +\n                        \"totalMs=${\"%.3f\".format((completedAtNs - queuedAtNs) / 1_000_000.0)} \" +\n                        \"innerActive=${currentTopology.innerActive} innerDefault=${currentTopology.innerIsDefault} \" +\n                        \"error=${result?.getString(\"error\")}\",\n                )\n            }\n        }\n    }\n\n""" + marker
        text = replace_once(text, marker, method, "coordinator predictive prewake method")

    text = text.replace(
        "const val INNER_WAKE_RETRY_MS = 55L",
        "const val INNER_PREWAKE_COOLDOWN_MS = 350L\n        const val INNER_WAKE_RETRY_MS = 40L",
        1,
    )
    coordinator.write_text(text)

    # New shell command: physical-only wake. No logical route mutation.
    protocol = repo / "app/src/full/java/com/duoopen/shell/ShellProtocol.kt"
    text = protocol.read_text()
    if "INNER_PREWAKE_V1" not in text:
        text = replace_once(
            text,
            "    const val COVER_PRESENTATION_V1 = 19\n",
            "    const val COVER_PRESENTATION_V1 = 19\n\n    // Gen9: speculative physical-only inner prewake; never grants display authority.\n    const val INNER_PREWAKE_V1 = 20\n",
            "shell protocol inner prewake",
        )
    protocol.write_text(text)

    bridge = repo / "app/src/full/java/com/duoopen/shell/ShizukuBridge.kt"
    text = bridge.read_text()
    if "prewakeInnerPhysical" not in text:
        text = replace_once(
            text,
            """    /** Wake the stable physical 1968x2184 Fold7 inner panel. Blocking; call off main. */\n    fun wakeInnerDisplay(): Bundle? =\n        call(\n            ShellProtocol.WAKE_INNER_DISPLAY\n        )""",
            """    /** Physical-only speculative Fold7 inner prewake. Blocking; call off main. */\n    fun prewakeInnerPhysical(): Bundle? =\n        call(\n            ShellProtocol.INNER_PREWAKE_V1\n        )\n\n    /** Wake the stable physical 1968x2184 Fold7 inner panel. Blocking; call off main. */\n    fun wakeInnerDisplay(): Bundle? =\n        call(\n            ShellProtocol.WAKE_INNER_DISPLAY\n        )""",
            "Shizuku physical prewake bridge",
        )
    bridge.write_text(text)

    shell = repo / "app/src/full/java/com/duoopen/shell/DuoShellService.kt"
    text = shell.read_text()
    if "ShellProtocol.INNER_PREWAKE_V1" not in text:
        open_mirror = """            ShellProtocol.OPEN_MIRROR_SESSION -> {"""
        transact = """            ShellProtocol.INNER_PREWAKE_V1 -> {\n                val identity =\n                    clearCallingIdentity()\n\n                val result =\n                    try {\n                        prewakeInnerPhysicalDisplay()\n                    } catch (t: Throwable) {\n                        Bundle().apply {\n                            putBoolean(\"ok\", false)\n                            putLong(\"physicalDisplayId\", -1L)\n                            putString(\n                                \"error\",\n                                \"${t.javaClass.simpleName}: ${t.message}\",\n                            )\n                        }\n                    } finally {\n                        restoreCallingIdentity(identity)\n                    }\n\n                out.writeNoException()\n                out.writeBundle(result)\n            }\n\n""" + open_mirror
        text = replace_once(text, open_mirror, transact, "shell inner prewake transact")

        wake_method = """    private fun wakeInnerPhysicalDisplay(): Bundle {"""
        pre_method = """    private fun prewakeInnerPhysicalDisplay(): Bundle {\n        val t0 =\n            SystemClock.elapsedRealtime()\n\n        val physicalId =\n            resolveFold7InnerPhysicalDisplayId()\n\n        val (powered, error) =\n            setPhysicalPowerNormal(\n                physicalId\n            )\n\n        return Bundle().apply {\n            putBoolean(\"ok\", powered)\n            putLong(\"physicalDisplayId\", physicalId)\n            putBoolean(\"physicalPowered\", powered)\n            putString(\n                \"command\",\n                \"Gen9 Fold7 physical-only inner prewake\",\n            )\n            if (error != null) {\n                putString(\"error\", error)\n            }\n            putLong(\n                \"latencyMs\",\n                SystemClock.elapsedRealtime() - t0,\n            )\n        }\n    }\n\n""" + wake_method
        text = replace_once(text, wake_method, pre_method, "shell physical prewake method")
    shell.write_text(text)

    # Animation response: Gen5 is direct-vsync and bypasses TiltFollower, so
    # tighten its slew budget rather than adding another smoothing layer.
    virtual = repo / "app/src/main/java/com/duoopen/fold/Fold7VirtualHingeGen5.kt"
    text = virtual.read_text()
    text = replace_once(
        text,
        "const val MAX_VISUAL_SPEED_DPS = 480.0",
        "const val MAX_VISUAL_SPEED_DPS = 720.0",
        "Gen5 max visual speed",
    )
    text = replace_once(
        text,
        "const val MIN_SLEW_DEG_PER_FRAME = 1.0f",
        "const val MIN_SLEW_DEG_PER_FRAME = 1.5f",
        "Gen5 min slew",
    )
    virtual.write_text(text)

    test = repo / "app/src/test/java/com/duoopen/fold/Fold7VirtualHingeGen5Test.kt"
    text = test.read_text()
    text = text.replace("<= 8.2f", "<= 12.2f")
    text = text.replace("<= 8.5f", "<= 12.5f")
    if "fasterGen9SlewReachesNinetyWithoutSnap" not in text:
        marker = """    @Test\n    fun repeatedReversalEntersOscillationGuard() {"""
        method = """    @Test\n    fun fasterGen9SlewReachesNinetyWithoutSnap() {\n        val v = Fold7VirtualHingeGen5()\n        v.startOpening(0L)\n        v.addSample(sample(0, 90f))\n\n        var now = 16_666_667L\n        var target = v.targetForFrame(now, now + 16_666_667L)\n        repeat(7) {\n            now += 16_666_667L\n            target = v.targetForFrame(now, now + 16_666_667L)\n        }\n\n        assertTrue(target.angleDegrees >= 88f)\n        assertTrue(target.angleDegrees <= 90f)\n    }\n\n""" + marker
        text = replace_once(text, marker, method, "Gen9 slew regression test")
    test.write_text(text)

    # Lower-lag followers/fades for non-Gen5 paths.
    panel = repo / "app/src/full/java/com/duoopen/overlay/PanelEngine.kt"
    text = panel.read_text()
    text = replace_once(text, "const val SETTLE_TIMEOUT_MS = 700L", "const val SETTLE_TIMEOUT_MS = 550L", "settle timeout")
    text = replace_once(text, "const val FADE_IN_MS = 140L", "const val FADE_IN_MS = 90L", "fade in")
    text = replace_once(text, "const val FADE_OUT_FLAT_MS = 120L", "const val FADE_OUT_FLAT_MS = 80L", "fade out")
    text = replace_once(text, "const val SAMSUNG_LIVE_TAU_S = 0.028f", "const val SAMSUNG_LIVE_TAU_S = 0.020f", "Samsung live tau")
    panel.write_text(text)

    host = repo / "app/src/full/java/com/duoopen/overlay/Fold7CoverVisualHost.kt"
    text = host.read_text()
    text = replace_once(text, "const val OPENING_TAU_S =\n            0.09f", "const val OPENING_TAU_S =\n            0.050f", "cover opening tau")
    text = replace_once(text, "const val CLOSING_TAU_S =\n            0.028f", "const val CLOSING_TAU_S =\n            0.022f", "cover closing tau")
    host.write_text(text)


def verify(repo: Path) -> None:
    paths = [
        "app/build.gradle.kts",
        "app/src/full/java/com/duoopen/overlay/Fold7DeviceStateObserver.kt",
        "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt",
        "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt",
        "app/src/full/java/com/duoopen/shell/ShellProtocol.kt",
        "app/src/full/java/com/duoopen/shell/ShizukuBridge.kt",
        "app/src/full/java/com/duoopen/shell/DuoShellService.kt",
        "app/src/main/java/com/duoopen/fold/Fold7VirtualHingeGen5.kt",
        "app/src/full/java/com/duoopen/overlay/PanelEngine.kt",
        "app/src/full/java/com/duoopen/overlay/Fold7CoverVisualHost.kt",
    ]
    joined = "\n".join((repo / p).read_text() for p in paths)
    required = [
        'versionCode = 45',
        'versionName = "5.3.0-gen9-responsive-zfold7"',
        'onPreOpeningHint',
        'device-state-pre:',
        'fun onPreOpeningHint(',
        '"inner-prewake"',
        'INNER_PREWAKE_V1 = 20',
        'fun prewakeInnerPhysical()',
        'prewakeInnerPhysicalDisplay()',
        'MAX_VISUAL_SPEED_DPS = 720.0',
        'MIN_SLEW_DEG_PER_FRAME = 1.5f',
        'SAMSUNG_LIVE_TAU_S = 0.020f',
        'OPENING_TAU_S =\n            0.050f',
        'CLOSING_TAU_S =\n            0.022f',
    ]
    missing = [needle for needle in required if needle not in joined]
    if missing:
        raise RuntimeError(f"Gen9 verification failed; missing: {missing}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    apply(repo)
    verify(repo)
    print("Gen9 predictive inner wake + responsive animation applied and verified")


if __name__ == "__main__":
    main()
