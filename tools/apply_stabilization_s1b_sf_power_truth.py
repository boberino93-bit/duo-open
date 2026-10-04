#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

MARKER = "STABILIZATION_S1B_SF_POWER_TRUTH_V1"
SHELL = Path("app/src/full/java/com/duoopen/shell/DuoShellService.kt")
COORD = Path("app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_shell(text: str) -> str:
    if MARKER in text:
        return text
    if "INNER_PHYSICAL_BRIDGE_V4_NON_OCCLUDING" not in text:
        raise RuntimeError("V4 non-occluding bridge must be applied before S1B")

    text = replace_once(
        text,
        "    private val innerPhysicalBridgeLayerStack = 0\n\n    init {\n",
        f'''    private val innerPhysicalBridgeLayerStack = 0

    // {MARKER}: diagnostic-only gate. SurfaceFlinger dumps are relatively
    // expensive, so collect one truth snapshot per semantic opening attempt.
    // This does not alter power, topology, routing, bridge, or presentation.
    private val sfPowerTruthLock = Any()
    private var lastSfPowerTruthOpeningAttempt = -1L

    init {{
''',
        "S1B truth-probe gate",
    )

    helpers = f'''    // {MARKER}: SurfaceFlinger readback only. A successful
    // setDisplayPowerMode() call is command acceptance, not proof that HWC lit
    // the panel or that SurfaceFlinger promoted it to active display ownership.
    private data class SfPowerTruth(
        val probed: Boolean,
        val probeStartMs: Long,
        val probeMs: Long,
        val innerPowerMode: String?,
        val coverPowerMode: String?,
        val activePhysicalDisplayId: Long,
        val displaysExcerpt: String?,
        val hwcExcerpt: String?,
        val error: String?,
    )

    private fun sfPowerModeForPhysicalDisplay(
        dump: String,
        physicalId: Long,
    ): String? {{
        if (physicalId < 0L) return null
        val id = Regex.escape(physicalId.toString())
        val block =
            Regex(
                "(?ms)^Display\\\\s+$id\\\\b.*?(?=^Display\\\\s+\\\\d+\\\\b|\\\\z)"
            ).find(dump)?.value
                ?: return null
        return Regex(
            "powerMode=([A-Za-z0-9_]+)",
            RegexOption.IGNORE_CASE,
        ).find(block)?.groupValues?.getOrNull(1)
    }}

    private fun sfActivePhysicalDisplayId(
        dump: String,
    ): Long =
        Regex(
            "(?m)^Display\\\\s+(\\\\d+)\\\\s+\\\\(active\\\\)",
            RegexOption.IGNORE_CASE,
        ).find(dump)
            ?.groupValues
            ?.getOrNull(1)
            ?.toLongOrNull()
            ?: -1L

    private fun compactSfExcerpt(
        dump: String,
        innerPhysicalId: Long,
        coverPhysicalId: Long,
    ): String =
        dump.lineSequence()
            .filter {{ line ->
                line.contains("powerMode=", ignoreCase = true) ||
                    line.contains("(active)", ignoreCase = true) ||
                    line.contains("(inactive)", ignoreCase = true) ||
                    (innerPhysicalId >= 0L && line.contains(innerPhysicalId.toString())) ||
                    (coverPhysicalId >= 0L && line.contains(coverPhysicalId.toString()))
            }}
            .take(40)
            .joinToString(" | ") {{ it.trim() }}
            .take(3000)

    private fun probeSurfaceFlingerPowerTruth(
        innerPhysicalId: Long,
        openingAttempt: Long,
        wakeStartedMs: Long,
    ): SfPowerTruth {{
        if (openingAttempt < 0L) {{
            return SfPowerTruth(
                probed = false,
                probeStartMs = -1L,
                probeMs = -1L,
                innerPowerMode = null,
                coverPowerMode = null,
                activePhysicalDisplayId = -1L,
                displaysExcerpt = null,
                hwcExcerpt = null,
                error = "opening attempt unavailable",
            )
        }}

        synchronized(sfPowerTruthLock) {{
            if (lastSfPowerTruthOpeningAttempt == openingAttempt) {{
                return SfPowerTruth(
                    probed = false,
                    probeStartMs = -1L,
                    probeMs = -1L,
                    innerPowerMode = null,
                    coverPowerMode = null,
                    activePhysicalDisplayId = -1L,
                    displaysExcerpt = null,
                    hwcExcerpt = null,
                    error = null,
                )
            }}
            lastSfPowerTruthOpeningAttempt = openingAttempt
        }}

        val probeStarted = SystemClock.elapsedRealtime()
        val startFromWakeMs = probeStarted - wakeStartedMs
        return runCatching {{
            val coverPhysicalId = resolveFold7CoverPhysicalDisplayId(-1)
            val displays = runProbe("dumpsys SurfaceFlinger --displays 2>/dev/null")
            val hwc = runProbe("dumpsys SurfaceFlinger --hwclayers 2>/dev/null")
            val ended = SystemClock.elapsedRealtime()
            SfPowerTruth(
                probed = true,
                probeStartMs = startFromWakeMs,
                probeMs = ended - probeStarted,
                innerPowerMode = sfPowerModeForPhysicalDisplay(displays, innerPhysicalId),
                coverPowerMode = sfPowerModeForPhysicalDisplay(displays, coverPhysicalId),
                activePhysicalDisplayId = sfActivePhysicalDisplayId(hwc),
                displaysExcerpt = compactSfExcerpt(displays, innerPhysicalId, coverPhysicalId),
                hwcExcerpt = compactSfExcerpt(hwc, innerPhysicalId, coverPhysicalId),
                error = null,
            )
        }}.getOrElse {{ error ->
            SfPowerTruth(
                probed = true,
                probeStartMs = startFromWakeMs,
                probeMs = SystemClock.elapsedRealtime() - probeStarted,
                innerPowerMode = null,
                coverPowerMode = null,
                activePhysicalDisplayId = -1L,
                displaysExcerpt = null,
                hwcExcerpt = null,
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
        helpers + '''    private fun wakeInnerPhysicalDisplay(
        serviceEpoch: Long,
        openingAttempt: Long,
    ): Bundle {
''',
        "S1B SurfaceFlinger helpers",
    )

    text = replace_once(
        text,
        '''        val logicalReady =
            powered && logicalPowered

        return Bundle().apply {
''',
        '''        val logicalReady =
            powered && logicalPowered

        // S1B probes only after the existing power/route work is complete so
        // dumpsys latency cannot change the route-probe decision for this wake.
        val sfTruth =
            probeSurfaceFlingerPowerTruth(
                innerPhysicalId = physicalId,
                openingAttempt = openingAttempt,
                wakeStartedMs = t0,
            )

        return Bundle().apply {
''',
        "S1B post-route truth readback",
    )

    text = replace_once(
        text,
        '''            putBoolean("logicalReady", logicalReady)
            // Backward compatibility only. This legacy field never proves
''',
        '''            putBoolean("logicalReady", logicalReady)
            putBoolean("sfTruthProbed", sfTruth.probed)
            putLong("sfProbeStartMs", sfTruth.probeStartMs)
            putLong("sfProbeMs", sfTruth.probeMs)
            putString("sfInnerPowerMode", sfTruth.innerPowerMode)
            putString("sfCoverPowerMode", sfTruth.coverPowerMode)
            putLong("sfActivePhysicalDisplayId", sfTruth.activePhysicalDisplayId)
            putString("sfDisplaysExcerpt", sfTruth.displaysExcerpt)
            putString("sfHwcExcerpt", sfTruth.hwcExcerpt)
            if (sfTruth.error != null) putString("sfTruthError", sfTruth.error)
            // Backward compatibility only. This legacy field never proves
''',
        "S1B bundle fields",
    )
    return text


def transform_coord(text: str) -> str:
    if "STABILIZATION_S1B_COORD_TELEMETRY" in text:
        return text
    if "STABILIZATION_S1_INGRESS_TELEMETRY_V1" not in text:
        raise RuntimeError("S1 timing telemetry must be applied before S1B")

    return replace_once(
        text,
        '''                        "logicalReady=${result?.getBoolean("logicalReady", false) == true} " +
                        "innerActive=${topologyNow.innerActive} innerDefault=${topologyNow.innerIsDefault} " +
''',
        '''                        "logicalReady=${result?.getBoolean("logicalReady", false) == true} " +
                        // STABILIZATION_S1B_COORD_TELEMETRY
                        "sfProbed=${result?.getBoolean("sfTruthProbed", false) == true} " +
                        "sfProbeStartMs=${result?.getLong("sfProbeStartMs", -1L) ?: -1L} " +
                        "sfProbeMs=${result?.getLong("sfProbeMs", -1L) ?: -1L} " +
                        "sfInner=${result?.getString("sfInnerPowerMode")} " +
                        "sfCover=${result?.getString("sfCoverPowerMode")} " +
                        "sfActivePhysical=${result?.getLong("sfActivePhysicalDisplayId", -1L) ?: -1L} " +
                        "sfError=${result?.getString("sfTruthError")} " +
                        "sfDisplays=${result?.getString("sfDisplaysExcerpt")} " +
                        "sfHwc=${result?.getString("sfHwcExcerpt")} " +
                        "innerActive=${topologyNow.innerActive} innerDefault=${topologyNow.innerIsDefault} " +
''',
        "S1B coordinator readback logging",
    )


def validate(shell: str, coord: str) -> None:
    for needle in (
        MARKER,
        "probeSurfaceFlingerPowerTruth",
        'runProbe("dumpsys SurfaceFlinger --displays 2>/dev/null")',
        'runProbe("dumpsys SurfaceFlinger --hwclayers 2>/dev/null")',
        'putString("sfInnerPowerMode", sfTruth.innerPowerMode)',
        'putLong("sfActivePhysicalDisplayId", sfTruth.activePhysicalDisplayId)',
    ):
        if needle not in shell:
            raise RuntimeError(f"missing S1B shell invariant: {needle}")

    for needle in (
        "STABILIZATION_S1B_COORD_TELEMETRY",
        'sfInner=${result?.getString("sfInnerPowerMode")}',
        'sfActivePhysical=${result?.getLong("sfActivePhysicalDisplayId", -1L) ?: -1L}',
    ):
        if needle not in coord:
            raise RuntimeError(f"missing S1B coordinator invariant: {needle}")

    # Strictly observation-only: preserve the V4 wake/bridge behavior.
    for needle in (
        "tx.setAlpha(layer, 0.0f)",
        "tx.setLayer(layer, Int.MIN_VALUE + 64)",
        "private val innerPhysicalBridgeLayerStack = 0",
    ):
        if needle not in shell:
            raise RuntimeError(f"S1B lost V4 behavior invariant: {needle}")


def apply(repo: Path, check_only: bool) -> None:
    shell_path = repo / SHELL
    coord_path = repo / COORD
    if not shell_path.exists() or not coord_path.exists():
        raise RuntimeError("required generated Android sources missing")
    shell = transform_shell(shell_path.read_text(encoding="utf-8"))
    coord = transform_coord(coord_path.read_text(encoding="utf-8"))
    validate(shell, coord)
    if not check_only:
        shell_path.write_text(shell, encoding="utf-8")
        coord_path.write_text(coord, encoding="utf-8")


def self_test() -> None:
    shell = '''// INNER_PHYSICAL_BRIDGE_V4_NON_OCCLUDING
    private val innerPhysicalBridgeLayerStack = 0

    init {
    }

    private fun wakeInnerPhysicalDisplay(
        serviceEpoch: Long,
        openingAttempt: Long,
    ): Bundle {
        val t0 = SystemClock.elapsedRealtime()
        val physicalId = 1L
        val logicalReady = powered && logicalPowered

        return Bundle().apply {
            putBoolean("logicalReady", logicalReady)
            // Backward compatibility only. This legacy field never proves
        }
    }
'''
    coord = '''// STABILIZATION_S1_INGRESS_TELEMETRY_V1
                        "logicalReady=${result?.getBoolean("logicalReady", false) == true} " +
                        "innerActive=${topologyNow.innerActive} innerDefault=${topologyNow.innerIsDefault} " +
'''
    sout = transform_shell(shell)
    cout = transform_coord(coord)
    assert MARKER in sout
    assert "sfInnerPowerMode" in sout
    assert "STABILIZATION_S1B_COORD_TELEMETRY" in cout
    assert transform_shell(sout) == sout
    assert transform_coord(cout) == cout
    print("stabilization S1B SurfaceFlinger truth probe self-test: PASS")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=".")
    p.add_argument("--check", action="store_true")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        self_test()
        if not a.check:
            return 0
    apply(Path(a.repo).resolve(), a.check)
    print(
        "stabilization S1B SurfaceFlinger power truth: " +
        ("source shape verified" if a.check else "applied")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
