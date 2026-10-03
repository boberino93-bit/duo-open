#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

SHELL = Path("app/src/full/java/com/duoopen/shell/DuoShellService.kt")
COORD = Path("app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt")
MARKER = "STABILIZATION_S1G_FORENSIC_SUPERSET_V1"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_shell(text: str) -> str:
    if MARKER in text:
        return text
    if "STABILIZATION_S1F_LAYOUT_MAP_TRUTH_V1" not in text:
        raise RuntimeError("S1F targeted layout-map truth must be applied first")
    if "STABILIZATION_S1C_ACTIVE_TRANSFER_V1" in text or "STABILIZATION_S1D_REAL_INNER_EDGE_V1" in text:
        raise RuntimeError("S1G must remain read-only and must not stack S1C/S1D power mutations")

    text = replace_once(
        text,
        '''    private val logicalLayoutTruthLock = Any()
    private var lastLogicalLayoutTruthOpeningAttempt = -1L

    init {
''',
        f'''    private val logicalLayoutTruthLock = Any()
    private var lastLogicalLayoutTruthOpeningAttempt = -1L

    // {MARKER}: broad one-shot forensic sweep. It is deliberately gated per
    // semantic opening and runs only after the existing early wake/route probes,
    // S1B SurfaceFlinger truth, and S1E layout truth have already completed.
    // Therefore it cannot change whether the immediate INNER route probe succeeds.
    private val forensicTruthLock = Any()
    private var lastForensicTruthOpeningAttempt = -1L

    init {{
''',
        "S1G forensic gate",
    )

    helper = f'''    // {MARKER}: diagnostic-only cross-layer snapshot. Commands are
    // intentionally read-only and individually failure-tolerant. Each excerpt is
    // capped so one unexpectedly verbose Samsung service cannot overflow Binder.
    private data class ForensicTruth(
        val probed: Boolean,
        val probeStartMs: Long,
        val probeMs: Long,
        val probeTimings: String?,
        val stateBefore: String?,
        val stateMid: String?,
        val stateAfter: String?,
        val deviceStateService: String?,
        val displayFramework: String?,
        val windowDisplays: String?,
        val windowPolicy: String?,
        val activityTasks: String?,
        val powerManager: String?,
        val inputViewports: String?,
        val surfaceFlingerCore: String?,
        val kernelDisplay: String?,
        val deviceStateConfig: String?,
        val overlayFoldConfig: String?,
        val serviceDiscovery: String?,
        val buildIdentity: String?,
        val error: String?,
    )

    private fun compactForensic(value: String, cap: Int): String =
        value.lineSequence()
            .map {{ it.trim() }}
            .filter {{ it.isNotBlank() }}
            .joinToString(" | ")
            .take(cap)

    private fun probeForensicTruth(
        openingAttempt: Long,
        wakeStartedMs: Long,
    ): ForensicTruth {{
        if (openingAttempt < 0L) {{
            return ForensicTruth(
                false, -1L, -1L, null,
                null, null, null, null, null, null, null, null, null, null,
                null, null, null, null, null, null,
                "opening attempt unavailable",
            )
        }}

        synchronized(forensicTruthLock) {{
            if (lastForensicTruthOpeningAttempt == openingAttempt) {{
                return ForensicTruth(
                    false, -1L, -1L, null,
                    null, null, null, null, null, null, null, null, null, null,
                    null, null, null, null, null, null,
                    null,
                )
            }}
            lastForensicTruthOpeningAttempt = openingAttempt
        }}

        val probeStarted = SystemClock.elapsedRealtime()
        val probeStartMs = probeStarted - wakeStartedMs
        val timings = mutableListOf<String>()

        fun snap(label: String, command: String, cap: Int): String {{
            val started = SystemClock.elapsedRealtime()
            val value = runCatching {{
                compactForensic(runProbe(command), cap)
            }}.getOrElse {{ error ->
                "probe-error=${{error.javaClass.simpleName}}:${{error.message}}"
            }}
            timings += "$label=${{SystemClock.elapsedRealtime() - started}}ms"
            return value
        }}

        return runCatching {{
            val stateBefore = snap(
                "state-before",
                "cmd device_state state 2>/dev/null",
                1500,
            )

            // DeviceStateManager's dump distinguishes base, pending, committed,
            // and override state. This catches policy latency and stale overrides.
            val deviceStateService = snap(
                "device-state-service",
                "dumpsys device_state 2>/dev/null | head -n 260",
                9000,
            )

            // One targeted DisplayManager snapshot includes LogicalDisplayMapper,
            // registered layouts, physical/logical identity, and display-power
            // controller readiness without retaining giant brightness splines.
            val displayFramework = snap(
                "display-framework",
                "dumpsys display 2>/dev/null | " +
                    "grep -E -i 'LogicalDisplayMapper:|mCurrentLayout=|mDeviceState=|" +
                    "mPendingDeviceState=|mDeviceStateToBeAppliedAfterBoot=|" +
                    "DeviceStateToLayoutMap:|Registered Layouts:|state\\(-?[0-9]+\\):|" +
                    "Logical Displays:|^[[:space:]]*Display [0-9]+:|mIsEnabled=|" +
                    "mPrimaryDisplayDevice=|DisplayDeviceInfo\\{|uniqueId=|address \\{|" +
                    "DisplayPowerController|mDisplayReadyLocked=|mPendingRequestLocked=|" +
                    "mPendingRequestChangedLocked=|mPendingUpdatePowerStateLocked=|" +
                    "mPowerRequest=|mDisplayEnabled=|mIsEnabled=|mIsInTransition=|" +
                    "mScreenState=|mState=|mCommittedState=|mBrightnessState=' | head -n 320",
                14000,
            )

            val stateMid = snap(
                "state-mid",
                "cmd device_state state 2>/dev/null",
                1500,
            )

            // WM answers a different question from DisplayManager: whether the
            // display/configuration is ready for windows and whether a transition,
            // freeze, or config wait is blocking visible content.
            val windowDisplays = snap(
                "window-displays",
                "dumpsys window displays 2>/dev/null | " +
                    "grep -E -i 'Display: mDisplayId=|DisplayContent|mCurrentFocus|" +
                    "mFocusedApp|mWaitingForConfig|mDisplayReady|mOpeningApps|" +
                    "mClosingApps|mChangingContainers|mTransition|collecting|" +
                    "waitingForRemoteDisplayChange|init=|cur=|app=' | head -n 260",
                10000,
            )

            // Policy-level screen-on blockers can leave a powered/logical display
            // black even after routing is correct.
            val windowPolicy = snap(
                "window-policy",
                "dumpsys window policy 2>/dev/null | " +
                    "grep -E -i 'mAwake|mScreenOnEarly|mScreenOnFully|" +
                    "mKeyguardDrawComplete|mWindowManagerDrawComplete|keyguard|" +
                    "interactive|lid|fold|screen.?on|display' | head -n 220",
                8000,
            )

            // Determine whether Launcher/SystemUI/tasks have actually migrated to
            // the INNER/default logical display when the panel becomes available.
            val activityTasks = snap(
                "activity-tasks",
                "dumpsys activity activities 2>/dev/null | " +
                    "grep -E -i 'Display #[0-9]+|RootTask|Task\\{|mResumedActivity|" +
                    "topResumedActivity|mLastPausedActivity|realActivity=|" +
                    "homeActivity|launcher|systemui' | head -n 260",
                10000,
            )

            val powerManager = snap(
                "power-manager",
                "dumpsys power 2>/dev/null | " +
                    "grep -E -i 'mWakefulness=|mWakefulnessChanging=|" +
                    "mDisplayGroupPowerStateMapper|Display Group|wakefulness|" +
                    "mWakeLockSummary|mUserActivitySummary|mLastWakeTime|" +
                    "mLastWakeReason|mDozeStartInProgress|SuspendBlocker|interactive' | head -n 220",
                8500,
            )

            // Input viewports provide an independent physical<->logical routing
            // signal and catch cases where display routing changes without input.
            val inputViewports = snap(
                "input-viewports",
                "dumpsys input 2>/dev/null | " +
                    "grep -E -i 'Display Viewports|Viewport|displayId=|uniqueId=|" +
                    "physicalPort=|INTERNAL' | head -n 200",
                7500,
            )

            // S1B's --hwclayers parser could not identify Samsung's active display.
            // Ask the main SF dump for active-display/layer-stack clues as a fallback.
            val surfaceFlingerCore = snap(
                "surfaceflinger-core",
                "dumpsys SurfaceFlinger 2>/dev/null | " +
                    "grep -E -i 'active.?display|mActiveDisplay|Display [0-9]+|" +
                    "physical.*display|layerStack|powerMode|DisplayDevice' | head -n 220",
                8500,
            )

            // Optional kernel/HWC cross-check. Missing nodes or permission errors are
            // expected and are retained as evidence rather than treated as failure.
            val kernelDisplay = snap(
                "kernel-display",
                "sh -c 'for p in /sys/class/drm/*/status /sys/class/drm/*/enabled " +
                    "/sys/class/graphics/fb*/blank /sys/class/backlight/*/actual_brightness " +
                    "/sys/class/backlight/*/brightness; do if [ -r \"\\$p\" ]; then " +
                    "printf \"%s=\" \"\\$p\"; cat \"\\$p\"; fi; done' 2>/dev/null",
                6000,
            )

            // Vendor/data device-state configuration may expose the exact predicates
            // or thresholds Samsung uses to leave TENT and enter HALF_OPENED.
            val deviceStateConfig = snap(
                "device-state-config",
                "sh -c 'for p in " +
                    "/data/system/devicestate/device_state_configuration.xml " +
                    "/vendor/etc/devicestate/device_state_configuration.xml " +
                    "/product/etc/devicestate/device_state_configuration.xml " +
                    "/system_ext/etc/devicestate/device_state_configuration.xml; do " +
                    "if [ -r \"\\$p\" ]; then echo FILE=\"\\$p\"; cat \"\\$p\"; fi; done' 2>/dev/null",
                12000,
            )

            // Resource overlays control which states Android treats as folded,
            // half-folded, open, concurrent, wake-up, and sleep states. Lookup is
            // best-effort because some Samsung builds hide array resources here.
            val overlayFoldConfig = snap(
                "overlay-fold-config",
                "sh -c 'for r in config_foldedDeviceStates config_halfFoldedDeviceStates " +
                    "config_openDeviceStates config_concurrentDisplayDeviceStates " +
                    "config_deviceStatesOnWhichToWakeUp config_deviceStatesOnWhichToSleep; do " +
                    "echo RESOURCE=\\$r; cmd overlay lookup android android:array/\\$r 2>/dev/null || true; done; " +
                    "echo RESOURCE=config_windowManagerPauseRotationWhenUnfolding; " +
                    "cmd overlay lookup android android:bool/config_windowManagerPauseRotationWhenUnfolding 2>/dev/null || true'",
                7000,
            )

            // Discover Samsung-specific fold/display services now so a later phase
            // does not require another APK merely to learn their service names.
            val serviceDiscovery = snap(
                "service-discovery",
                "dumpsys -l 2>/dev/null | " +
                    "grep -E -i 'display|device.?state|fold|hinge|window|power|sensor|sem' | head -n 180",
                6000,
            )

            val buildIdentity = snap(
                "build-identity",
                "sh -c 'echo fingerprint=$(getprop ro.build.fingerprint); " +
                    "echo incremental=$(getprop ro.build.version.incremental); " +
                    "echo security_patch=$(getprop ro.build.version.security_patch); " +
                    "echo oneui=$(getprop ro.build.version.oneui)'",
                3500,
            )

            val stateAfter = snap(
                "state-after",
                "cmd device_state state 2>/dev/null",
                1500,
            )

            val ended = SystemClock.elapsedRealtime()
            ForensicTruth(
                probed = true,
                probeStartMs = probeStartMs,
                probeMs = ended - probeStarted,
                probeTimings = timings.joinToString(","),
                stateBefore = stateBefore,
                stateMid = stateMid,
                stateAfter = stateAfter,
                deviceStateService = deviceStateService,
                displayFramework = displayFramework,
                windowDisplays = windowDisplays,
                windowPolicy = windowPolicy,
                activityTasks = activityTasks,
                powerManager = powerManager,
                inputViewports = inputViewports,
                surfaceFlingerCore = surfaceFlingerCore,
                kernelDisplay = kernelDisplay,
                deviceStateConfig = deviceStateConfig,
                overlayFoldConfig = overlayFoldConfig,
                serviceDiscovery = serviceDiscovery,
                buildIdentity = buildIdentity,
                error = null,
            )
        }}.getOrElse {{ error ->
            ForensicTruth(
                true,
                probeStartMs,
                SystemClock.elapsedRealtime() - probeStarted,
                timings.joinToString(","),
                null, null, null, null, null, null, null, null, null, null,
                null, null, null, null, null,
                "${{error.javaClass.simpleName}}: ${{error.message}}",
            )
        }}
    }}

'''

    text = replace_once(
        text,
        '''    private fun wakeInnerPhysicalDisplay(
        serviceEpoch: Long,
        openingAttempt: Long,
    ): Bundle {
''',
        helper + '''    private fun wakeInnerPhysicalDisplay(
        serviceEpoch: Long,
        openingAttempt: Long,
    ): Bundle {
''',
        "S1G forensic helpers",
    )

    text = replace_once(
        text,
        '''        val logicalLayoutTruth =
            probeLogicalLayoutTruth(
                openingAttempt = openingAttempt,
                wakeStartedMs = t0,
            )

        return Bundle().apply {
''',
        '''        val logicalLayoutTruth =
            probeLogicalLayoutTruth(
                openingAttempt = openingAttempt,
                wakeStartedMs = t0,
            )

        // S1G deliberately starts only after all pre-existing early wake, route,
        // SurfaceFlinger, and LogicalDisplayMapper decisions have already run.
        val forensicTruth =
            probeForensicTruth(
                openingAttempt = openingAttempt,
                wakeStartedMs = t0,
            )

        return Bundle().apply {
''',
        "S1G post-decision forensic invocation",
    )

    text = replace_once(
        text,
        '''            if (logicalLayoutTruth.error != null) putString("layoutTruthError", logicalLayoutTruth.error)
            // Backward compatibility only. This legacy field never proves
''',
        '''            if (logicalLayoutTruth.error != null) putString("layoutTruthError", logicalLayoutTruth.error)
            putBoolean("forensicTruthProbed", forensicTruth.probed)
            putLong("forensicProbeStartMs", forensicTruth.probeStartMs)
            putLong("forensicProbeMs", forensicTruth.probeMs)
            putString("forensicProbeTimings", forensicTruth.probeTimings)
            putString("forensicStateBefore", forensicTruth.stateBefore)
            putString("forensicStateMid", forensicTruth.stateMid)
            putString("forensicStateAfter", forensicTruth.stateAfter)
            putString("forensicDeviceStateService", forensicTruth.deviceStateService)
            putString("forensicDisplayFramework", forensicTruth.displayFramework)
            putString("forensicWindowDisplays", forensicTruth.windowDisplays)
            putString("forensicWindowPolicy", forensicTruth.windowPolicy)
            putString("forensicActivityTasks", forensicTruth.activityTasks)
            putString("forensicPowerManager", forensicTruth.powerManager)
            putString("forensicInputViewports", forensicTruth.inputViewports)
            putString("forensicSurfaceFlingerCore", forensicTruth.surfaceFlingerCore)
            putString("forensicKernelDisplay", forensicTruth.kernelDisplay)
            putString("forensicDeviceStateConfig", forensicTruth.deviceStateConfig)
            putString("forensicOverlayFoldConfig", forensicTruth.overlayFoldConfig)
            putString("forensicServiceDiscovery", forensicTruth.serviceDiscovery)
            putString("forensicBuildIdentity", forensicTruth.buildIdentity)
            if (forensicTruth.error != null) putString("forensicTruthError", forensicTruth.error)
            // Backward compatibility only. This legacy field never proves
''',
        "S1G bundle fields",
    )

    return text


def transform_coord(text: str) -> str:
    if "STABILIZATION_S1G_COORD_TELEMETRY" in text:
        return text
    if "STABILIZATION_S1E_COORD_TELEMETRY" not in text:
        raise RuntimeError("S1E coordinator telemetry must be applied before S1G")

    return replace_once(
        text,
        '''                        "layoutError=${result?.getString("layoutTruthError")} " +
                        "innerActive=${topologyNow.innerActive} innerDefault=${topologyNow.innerIsDefault} " +
''',
        '''                        "layoutError=${result?.getString("layoutTruthError")} " +
                        // STABILIZATION_S1G_COORD_TELEMETRY
                        "forensicProbed=${result?.getBoolean("forensicTruthProbed", false) == true} " +
                        "forensicStartMs=${result?.getLong("forensicProbeStartMs", -1L) ?: -1L} " +
                        "forensicMs=${result?.getLong("forensicProbeMs", -1L) ?: -1L} " +
                        "forensicTimings=${result?.getString("forensicProbeTimings")} " +
                        "forensicStateBefore=${result?.getString("forensicStateBefore")} " +
                        "forensicStateMid=${result?.getString("forensicStateMid")} " +
                        "forensicStateAfter=${result?.getString("forensicStateAfter")} " +
                        "forensicDeviceState=${result?.getString("forensicDeviceStateService")} " +
                        "forensicDisplay=${result?.getString("forensicDisplayFramework")} " +
                        "forensicWindowDisplays=${result?.getString("forensicWindowDisplays")} " +
                        "forensicWindowPolicy=${result?.getString("forensicWindowPolicy")} " +
                        "forensicActivity=${result?.getString("forensicActivityTasks")} " +
                        "forensicPower=${result?.getString("forensicPowerManager")} " +
                        "forensicInput=${result?.getString("forensicInputViewports")} " +
                        "forensicSfCore=${result?.getString("forensicSurfaceFlingerCore")} " +
                        "forensicKernel=${result?.getString("forensicKernelDisplay")} " +
                        "forensicStateConfig=${result?.getString("forensicDeviceStateConfig")} " +
                        "forensicOverlay=${result?.getString("forensicOverlayFoldConfig")} " +
                        "forensicServices=${result?.getString("forensicServiceDiscovery")} " +
                        "forensicBuild=${result?.getString("forensicBuildIdentity")} " +
                        "forensicError=${result?.getString("forensicTruthError")} " +
                        "innerActive=${topologyNow.innerActive} innerDefault=${topologyNow.innerIsDefault} " +
''',
        "S1G coordinator forensic telemetry",
    )


def validate(shell: str, coord: str) -> None:
    shell_needles = (
        MARKER,
        "probeForensicTruth",
        'runProbe("cmd device_state state 2>/dev/null")',
        '"dumpsys device_state 2>/dev/null | head -n 260"',
        '"dumpsys display 2>/dev/null | " +',
        '"dumpsys window displays 2>/dev/null | " +',
        '"dumpsys window policy 2>/dev/null | " +',
        '"dumpsys activity activities 2>/dev/null | " +',
        '"dumpsys power 2>/dev/null | " +',
        '"dumpsys input 2>/dev/null | " +',
        '"dumpsys SurfaceFlinger 2>/dev/null | " +',
        "/sys/class/drm/*/status",
        "device_state_configuration.xml",
        "config_concurrentDisplayDeviceStates",
        '"dumpsys -l 2>/dev/null | " +',
        'putString("forensicDisplayFramework", forensicTruth.displayFramework)',
        'putString("forensicStateConfig", forensicTruth.deviceStateConfig)' if False else 'putString("forensicDeviceStateConfig", forensicTruth.deviceStateConfig)',
        "STABILIZATION_S1F_LAYOUT_MAP_TRUTH_V1",
        "probeSurfaceFlingerPowerTruth",
        "tx.setAlpha(layer, 0.0f)",
        "tx.setLayer(layer, Int.MIN_VALUE + 64)",
    )
    for needle in shell_needles:
        if needle not in shell:
            raise RuntimeError(f"missing S1G shell invariant: {needle}")

    forbidden = (
        "STABILIZATION_S1C_ACTIVE_TRANSFER_V1",
        "STABILIZATION_S1D_REAL_INNER_EDGE_V1",
        'cmd device_state state 4',
        'cmd device_state state 5',
        'cmd device_state state reset',
        'cmd device_state base-state',
        'setDisplayPowerMode(token, 0)',
    )
    for needle in forbidden:
        if needle in shell:
            raise RuntimeError(f"S1G unexpectedly contains behavior mutation: {needle}")

    coord_needles = (
        "STABILIZATION_S1G_COORD_TELEMETRY",
        "forensicProbed=",
        "forensicStateBefore=",
        "forensicDisplay=",
        "forensicWindowDisplays=",
        "forensicStateConfig=",
    )
    for needle in coord_needles:
        if needle not in coord:
            raise RuntimeError(f"missing S1G coordinator invariant: {needle}")


def apply(repo: Path, check: bool) -> None:
    shell_path = repo / SHELL
    coord_path = repo / COORD
    if not shell_path.exists() or not coord_path.exists():
        raise RuntimeError("required generated runtime sources missing")

    shell = transform_shell(shell_path.read_text(encoding="utf-8"))
    coord = transform_coord(coord_path.read_text(encoding="utf-8"))
    validate(shell, coord)
    if not check:
        shell_path.write_text(shell, encoding="utf-8")
        coord_path.write_text(coord, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    apply(Path(args.repo).resolve(), args.check)
    print(
        "stabilization S1G forensic superset: " +
        ("source shape verified" if args.check else "applied")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
