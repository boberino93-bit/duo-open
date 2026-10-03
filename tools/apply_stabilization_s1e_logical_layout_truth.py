#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

SHELL = Path("app/src/full/java/com/duoopen/shell/DuoShellService.kt")
COORD = Path("app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt")
MARKER = "STABILIZATION_S1E_LOGICAL_LAYOUT_TRUTH_V1"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_shell(text: str) -> str:
    if MARKER in text:
        return text
    if "STABILIZATION_S1B_SF_POWER_TRUTH_V1" not in text:
        raise RuntimeError("S1B SurfaceFlinger truth readback must be applied first")
    if "STABILIZATION_S1C_ACTIVE_TRANSFER_V1" in text or "STABILIZATION_S1D_REAL_INNER_EDGE_V1" in text:
        raise RuntimeError("S1E must remain read-only and must not stack S1C/S1D power mutations")

    text = replace_once(
        text,
        '''    private val sfPowerTruthLock = Any()
    private var lastSfPowerTruthOpeningAttempt = -1L

    init {
''',
        f'''    private val sfPowerTruthLock = Any()
    private var lastSfPowerTruthOpeningAttempt = -1L

    // {MARKER}: read-only DisplayManager / DeviceState truth probe.
    // One sample per semantic opening, after existing wake/route/SF work.
    private val logicalLayoutTruthLock = Any()
    private var lastLogicalLayoutTruthOpeningAttempt = -1L

    init {{
''',
        "S1E truth-probe gate",
    )

    helper = f'''    // {MARKER}: Android framework policy readback only. This asks
    // DeviceStateManager and DisplayManager which posture/layout they currently
    // consider authoritative. It does not request or override any device state.
    private data class LogicalLayoutTruth(
        val probed: Boolean,
        val probeStartMs: Long,
        val probeMs: Long,
        val deviceState: String?,
        val supportedStates: String?,
        val displayMapper: String?,
        val error: String?,
    )

    private fun compactLogicalLayoutExcerpt(dump: String): String =
        dump.lineSequence()
            .filter {{ line ->
                line.contains("LogicalDisplayMapper", ignoreCase = true) ||
                    line.contains("mDeviceState", ignoreCase = true) ||
                    line.contains("mPendingDeviceState", ignoreCase = true) ||
                    line.contains("mCurrentLayout", ignoreCase = true) ||
                    line.contains("DisplayLayout", ignoreCase = true) ||
                    line.contains("LogicalDisplay", ignoreCase = true) ||
                    line.contains("isEnabled", ignoreCase = true) ||
                    line.contains("mIsEnabled", ignoreCase = true) ||
                    line.contains("enabled=", ignoreCase = true) ||
                    line.contains("DisplayDeviceInfo", ignoreCase = true) ||
                    line.contains("state=", ignoreCase = true)
            }}
            .take(120)
            .joinToString(" | ") {{ it.trim() }}
            .take(8000)

    private fun compactDeviceStateExcerpt(dump: String): String =
        dump.lineSequence()
            .map {{ it.trim() }}
            .filter {{ it.isNotBlank() }}
            .take(40)
            .joinToString(" | ")
            .take(4000)

    private fun probeLogicalLayoutTruth(
        openingAttempt: Long,
        wakeStartedMs: Long,
    ): LogicalLayoutTruth {{
        if (openingAttempt < 0L) {{
            return LogicalLayoutTruth(
                probed = false,
                probeStartMs = -1L,
                probeMs = -1L,
                deviceState = null,
                supportedStates = null,
                displayMapper = null,
                error = "opening attempt unavailable",
            )
        }}

        synchronized(logicalLayoutTruthLock) {{
            if (lastLogicalLayoutTruthOpeningAttempt == openingAttempt) {{
                return LogicalLayoutTruth(
                    probed = false,
                    probeStartMs = -1L,
                    probeMs = -1L,
                    deviceState = null,
                    supportedStates = null,
                    displayMapper = null,
                    error = null,
                )
            }}
            lastLogicalLayoutTruthOpeningAttempt = openingAttempt
        }}

        val probeStarted = SystemClock.elapsedRealtime()
        val startFromWakeMs = probeStarted - wakeStartedMs
        return runCatching {{
            val state = runProbe("cmd device_state state 2>/dev/null")
            val states = runProbe("cmd device_state print-states 2>/dev/null")
            val display = runProbe("dumpsys display 2>/dev/null")
            val ended = SystemClock.elapsedRealtime()
            LogicalLayoutTruth(
                probed = true,
                probeStartMs = startFromWakeMs,
                probeMs = ended - probeStarted,
                deviceState = compactDeviceStateExcerpt(state),
                supportedStates = compactDeviceStateExcerpt(states),
                displayMapper = compactLogicalLayoutExcerpt(display),
                error = null,
            )
        }}.getOrElse {{ error ->
            LogicalLayoutTruth(
                probed = true,
                probeStartMs = startFromWakeMs,
                probeMs = SystemClock.elapsedRealtime() - probeStarted,
                deviceState = null,
                supportedStates = null,
                displayMapper = null,
                error = "${{error.javaClass.simpleName}}: ${{error.message}}",
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
        "S1E framework-policy helpers",
    )

    text = replace_once(
        text,
        '''        return Bundle().apply {
            putBoolean("ok", error == null)
''',
        '''        // S1E executes only after the existing route and S1B SurfaceFlinger
        // readbacks, so this expensive dumpsys work cannot affect wake decisions.
        val logicalLayoutTruth =
            probeLogicalLayoutTruth(
                openingAttempt = openingAttempt,
                wakeStartedMs = t0,
            )

        return Bundle().apply {
            putBoolean("ok", error == null)
''',
        "S1E post-S1B framework truth readback",
    )

    text = replace_once(
        text,
        '''            if (sfTruth.error != null) putString("sfTruthError", sfTruth.error)
            // Backward compatibility only. This legacy field never proves
''',
        '''            if (sfTruth.error != null) putString("sfTruthError", sfTruth.error)
            putBoolean("layoutTruthProbed", logicalLayoutTruth.probed)
            putLong("layoutProbeStartMs", logicalLayoutTruth.probeStartMs)
            putLong("layoutProbeMs", logicalLayoutTruth.probeMs)
            putString("deviceStateExcerpt", logicalLayoutTruth.deviceState)
            putString("deviceStatesExcerpt", logicalLayoutTruth.supportedStates)
            putString("displayMapperExcerpt", logicalLayoutTruth.displayMapper)
            if (logicalLayoutTruth.error != null) putString("layoutTruthError", logicalLayoutTruth.error)
            // Backward compatibility only. This legacy field never proves
''',
        "S1E bundle fields",
    )
    return text


def transform_coord(text: str) -> str:
    if "STABILIZATION_S1E_COORD_TELEMETRY" in text:
        return text
    if "STABILIZATION_S1B_COORD_TELEMETRY" not in text:
        raise RuntimeError("S1B coordinator telemetry must be applied before S1E")

    return replace_once(
        text,
        '''                        "sfHwc=${result?.getString("sfHwcExcerpt")} " +
                        "innerActive=${topologyNow.innerActive} innerDefault=${topologyNow.innerIsDefault} " +
''',
        '''                        "sfHwc=${result?.getString("sfHwcExcerpt")} " +
                        // STABILIZATION_S1E_COORD_TELEMETRY
                        "layoutProbed=${result?.getBoolean("layoutTruthProbed", false) == true} " +
                        "layoutProbeStartMs=${result?.getLong("layoutProbeStartMs", -1L) ?: -1L} " +
                        "layoutProbeMs=${result?.getLong("layoutProbeMs", -1L) ?: -1L} " +
                        "deviceState=${result?.getString("deviceStateExcerpt")} " +
                        "deviceStates=${result?.getString("deviceStatesExcerpt")} " +
                        "displayMapper=${result?.getString("displayMapperExcerpt")} " +
                        "layoutError=${result?.getString("layoutTruthError")} " +
                        "innerActive=${topologyNow.innerActive} innerDefault=${topologyNow.innerIsDefault} " +
''',
        "S1E coordinator framework-policy logging",
    )


def validate(shell: str, coord: str) -> None:
    for needle in (
        MARKER,
        'runProbe("cmd device_state state 2>/dev/null")',
        'runProbe("cmd device_state print-states 2>/dev/null")',
        'runProbe("dumpsys display 2>/dev/null")',
        'putString("displayMapperExcerpt", logicalLayoutTruth.displayMapper)',
        "probeSurfaceFlingerPowerTruth",
        "tx.setAlpha(layer, 0.0f)",
        "tx.setLayer(layer, Int.MIN_VALUE + 64)",
    ):
        if needle not in shell:
            raise RuntimeError(f"missing S1E shell invariant: {needle}")

    for forbidden in (
        "STABILIZATION_S1C_ACTIVE_TRANSFER_V1",
        "STABILIZATION_S1D_REAL_INNER_EDGE_V1",
        'cmd device_state state 2"',
        'cmd device_state state 1"',
        'cmd device_state base-state',
    ):
        if forbidden in shell:
            raise RuntimeError(f"S1E unexpectedly contains a behavior mutation: {forbidden}")

    for needle in (
        "STABILIZATION_S1E_COORD_TELEMETRY",
        "layoutProbed=",
        "deviceState=",
        "displayMapper=",
        "sfInner=",
    ):
        if needle not in coord:
            raise RuntimeError(f"missing S1E coordinator invariant: {needle}")


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
        "stabilization S1E logical-layout truth: " +
        ("source shape verified" if args.check else "applied")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
