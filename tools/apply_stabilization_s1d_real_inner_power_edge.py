#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

SHELL = Path("app/src/full/java/com/duoopen/shell/DuoShellService.kt")
COORD = Path("app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt")
MARKER = "STABILIZATION_S1D_REAL_INNER_POWER_EDGE_V1"


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
    if "STABILIZATION_S1C_ACTIVE_TRANSFER_V1" in text:
        raise RuntimeError("S1D must be based directly on S1B, not layered on S1C")

    text = replace_once(
        text,
        '''    private val sfPowerTruthLock = Any()
    private var lastSfPowerTruthOpeningAttempt = -1L

    init {
''',
        f'''    private val sfPowerTruthLock = Any()
    private var lastSfPowerTruthOpeningAttempt = -1L

    // {MARKER}: one real INNER OFF->ON transfer per semantic opening attempt.
    private val s1dTransferLock = Any()
    private var lastS1dServiceEpoch = -1L
    private var lastS1dOpeningAttempt = -1L

    init {{
''',
        "S1D transfer gate",
    )

    helper = f'''    // {MARKER}: physical OFF counterpart to setPhysicalPowerNormal().
    private fun setPhysicalPowerOff(
        physicalId: Long,
    ): Pair<Boolean, String?> {{
        if (physicalId < 0L) {{
            return false to "physical display id unavailable"
        }}

        return runCatching {{
            org.lsposed.hiddenapibypass.HiddenApiBypass
                .addHiddenApiExemptions(
                    "Landroid/view/SurfaceControl;"
                )

            val token =
                SurfaceControl::class.java
                    .getDeclaredMethod(
                        "getPhysicalDisplayToken",
                        java.lang.Long.TYPE,
                    )
                    .invoke(null, physicalId) as? IBinder
                    ?: throw IllegalStateException(
                        "no SurfaceControl token for physical display $physicalId"
                    )

            SurfaceControl::class.java
                .getDeclaredMethod(
                    "setDisplayPowerMode",
                    IBinder::class.java,
                    Integer.TYPE,
                )
                .invoke(null, token, 0)

            true to null
        }}.getOrElse {{ error ->
            false to "${{error.javaClass.simpleName}}: ${{error.message}}"
        }}
    }}

'''

    text = replace_once(
        text,
        '''    private fun setCoverPhysicalPowerNormal():
''',
        helper + '''    private fun setCoverPhysicalPowerNormal():
''',
        "S1D physical OFF helper",
    )

    text = replace_once(
        text,
        '''        val physicalStart =
            SystemClock.elapsedRealtime()

        val (powered, error) =
            setPhysicalPowerNormal(
                physicalId
            )

        val physicalPowerMs =
            SystemClock.elapsedRealtime() - physicalStart
''',
        f'''        val coverPhysicalId =
            resolveFold7CoverPhysicalDisplayId(-1)

        val transferAttempted =
            synchronized(s1dTransferLock) {{
                val fresh =
                    serviceEpoch >= 0L &&
                        openingAttempt >= 0L &&
                        (
                            serviceEpoch != lastS1dServiceEpoch ||
                                openingAttempt != lastS1dOpeningAttempt
                        )
                if (fresh) {{
                    lastS1dServiceEpoch = serviceEpoch
                    lastS1dOpeningAttempt = openingAttempt
                }}
                fresh &&
                    coverPhysicalId >= 0L &&
                    physicalId >= 0L &&
                    coverPhysicalId != physicalId
            }}

        var innerOffOk = false
        var innerOffMs = -1L
        var innerOffError: String? = null
        var coverOffOk = false
        var coverOffMs = -1L
        var coverOffError: String? = null
        var coverRestoreOk = false
        var coverRestoreMs = -1L
        var coverRestoreError: String? = null

        if (transferAttempted) {{
            val innerOffStart = SystemClock.elapsedRealtime()
            val innerOff = setPhysicalPowerOff(physicalId)
            innerOffOk = innerOff.first
            innerOffError = innerOff.second
            innerOffMs = SystemClock.elapsedRealtime() - innerOffStart

            if (innerOffOk) {{
                val coverOffStart = SystemClock.elapsedRealtime()
                val coverOff = setPhysicalPowerOff(coverPhysicalId)
                coverOffOk = coverOff.first
                coverOffError = coverOff.second
                coverOffMs = SystemClock.elapsedRealtime() - coverOffStart
            }}
        }}

        val physicalStart = SystemClock.elapsedRealtime()

        val (powered, error) =
            if (!transferAttempted || (innerOffOk && coverOffOk)) {{
                // Critical S1D edge: INNER transitions OFF -> ON while the
                // formerly active COVER is already OFF. This is the foldable
                // activation condition in SurfaceFlinger.
                setPhysicalPowerNormal(physicalId)
            }} else {{
                false to "S1D preconditions failed before INNER OFF->ON edge"
            }}

        val physicalPowerMs =
            SystemClock.elapsedRealtime() - physicalStart

        if (transferAttempted && coverOffOk) {{
            val coverRestoreStart = SystemClock.elapsedRealtime()
            val restore = setPhysicalPowerNormal(coverPhysicalId)
            coverRestoreOk = restore.first
            coverRestoreError = restore.second
            coverRestoreMs = SystemClock.elapsedRealtime() - coverRestoreStart
        }}
''',
        "S1D real INNER OFF-on transfer sequence",
    )

    text = replace_once(
        text,
        '''            putBoolean("physicalPowered", powered)
            putLong("physicalPowerMs", physicalPowerMs)
''',
        '''            putBoolean("s1dTransferAttempted", transferAttempted)
            putLong("coverPhysicalDisplayId", coverPhysicalId)
            putBoolean("innerOffOk", innerOffOk)
            putLong("innerOffMs", innerOffMs)
            if (innerOffError != null) putString("innerOffError", innerOffError)
            putBoolean("coverOffOk", coverOffOk)
            putLong("coverOffMs", coverOffMs)
            if (coverOffError != null) putString("coverOffError", coverOffError)
            putBoolean("coverRestoreOk", coverRestoreOk)
            putLong("coverRestoreMs", coverRestoreMs)
            if (coverRestoreError != null) putString("coverRestoreError", coverRestoreError)
            putBoolean("physicalPowered", powered)
            putLong("physicalPowerMs", physicalPowerMs)
''',
        "S1D telemetry bundle",
    )

    return text


def transform_coord(text: str) -> str:
    if MARKER in text:
        return text
    if "sfActivePhysical=" not in text:
        raise RuntimeError("S1B coordinator telemetry must be present")

    return replace_once(
        text,
        '''                        "physicalPowered=${result?.getBoolean("physicalPowered", false) == true} " +
                        "physicalPowerMs=${result?.getLong("physicalPowerMs", -1L) ?: -1L} " +
''',
        f'''                        "physicalPowered=${{result?.getBoolean("physicalPowered", false) == true}} " +
                        "physicalPowerMs=${{result?.getLong("physicalPowerMs", -1L) ?: -1L}} " +
                        // {MARKER}: real INNER OFF->ON ownership edge telemetry.
                        "s1dTransfer=${{result?.getBoolean("s1dTransferAttempted", false) == true}} " +
                        "innerOffOk=${{result?.getBoolean("innerOffOk", false) == true}} " +
                        "innerOffMs=${{result?.getLong("innerOffMs", -1L) ?: -1L}} " +
                        "coverOffOk=${{result?.getBoolean("coverOffOk", false) == true}} " +
                        "coverOffMs=${{result?.getLong("coverOffMs", -1L) ?: -1L}} " +
                        "coverRestoreOk=${{result?.getBoolean("coverRestoreOk", false) == true}} " +
                        "coverRestoreMs=${{result?.getLong("coverRestoreMs", -1L) ?: -1L}} " +
''',
        "S1D coordinator telemetry",
    )


def validate(shell: str, coord: str) -> None:
    required_shell = (
        MARKER,
        ".invoke(null, token, 0)",
        "innerOffOk",
        "coverOffOk",
        "setPhysicalPowerNormal(physicalId)",
        "setPhysicalPowerNormal(coverPhysicalId)",
        "tx.setAlpha(layer, 0.0f)",
        "tx.setLayer(layer, Int.MIN_VALUE + 64)",
    )
    for value in required_shell:
        if value not in shell:
            raise RuntimeError(f"missing S1D shell invariant: {value}")

    required_coord = (
        MARKER,
        "s1dTransfer=",
        "innerOffOk=",
        "coverOffOk=",
        "coverRestoreOk=",
        "sfInner=",
        "sfCover=",
    )
    for value in required_coord:
        if value not in coord:
            raise RuntimeError(f"missing S1D coordinator invariant: {value}")

    if "STABILIZATION_S1C_ACTIVE_TRANSFER_V1" in shell or "ownershipPulse=" in coord:
        raise RuntimeError("S1C pulse must not be present in S1D runtime")


def apply(repo: Path, check: bool) -> None:
    shell_path = repo / SHELL
    coord_path = repo / COORD
    if not shell_path.exists() or not coord_path.exists():
        raise RuntimeError("required generated runtime sources missing")

    shell_before = shell_path.read_text(encoding="utf-8")
    coord_before = coord_path.read_text(encoding="utf-8")
    shell_after = transform_shell(shell_before)
    coord_after = transform_coord(coord_before)
    validate(shell_after, coord_after)

    if not check:
        shell_path.write_text(shell_after, encoding="utf-8")
        coord_path.write_text(coord_after, encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=".")
    p.add_argument("--check", action="store_true")
    a = p.parse_args()
    apply(Path(a.repo).resolve(), a.check)
    print("stabilization S1D real inner power edge: " + ("source shape verified" if a.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
