#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

SHELL = Path("app/src/full/java/com/duoopen/shell/DuoShellService.kt")
COORD = Path("app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt")
MARKER = "STABILIZATION_S1C_ACTIVE_TRANSFER_V1"


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
    if "INNER_PHYSICAL_BRIDGE_V4_NON_OCCLUDING" not in text:
        raise RuntimeError("V4 non-occluding bridge must be applied first")

    text = replace_once(
        text,
        '''    private val sfPowerTruthLock = Any()
    private var lastSfPowerTruthOpeningAttempt = -1L

    init {
''',
        f'''    private val sfPowerTruthLock = Any()
    private var lastSfPowerTruthOpeningAttempt = -1L

    // {MARKER}: one ownership-transfer pulse per semantic opening.
    // The steady-state power request remains ON for both physical panels.
    private val innerOwnershipPulseLock = Any()
    private var lastInnerOwnershipPulseServiceEpoch = -1L
    private var lastInnerOwnershipPulseAttempt = -1L

    init {{
''',
        "S1C ownership pulse gate",
    )

    helper = f'''    // {MARKER}: counterpart to setPhysicalPowerNormal().
    // Powering the currently active cover OFF before requesting INNER ON gives
    // SurfaceFlinger the condition it requires to promote the other internal
    // foldable display. The cover is restored ON immediately after INNER ON.
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
            false to
                "${{error.javaClass.simpleName}}: ${{error.message}}"
        }}
    }}

'''

    text = replace_once(
        text,
        '''    private fun setCoverPhysicalPowerNormal():
''',
        helper + '''    private fun setCoverPhysicalPowerNormal():
''',
        "S1C physical OFF helper",
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

        val ownershipTransferAttempted =
            synchronized(innerOwnershipPulseLock) {{
                val freshAttempt =
                    serviceEpoch >= 0L &&
                        openingAttempt >= 0L &&
                        (
                            serviceEpoch != lastInnerOwnershipPulseServiceEpoch ||
                                openingAttempt != lastInnerOwnershipPulseAttempt
                        )
                if (freshAttempt) {{
                    lastInnerOwnershipPulseServiceEpoch = serviceEpoch
                    lastInnerOwnershipPulseAttempt = openingAttempt
                }}
                freshAttempt &&
                    coverPhysicalId >= 0L &&
                    physicalId >= 0L &&
                    coverPhysicalId != physicalId
            }}

        var coverOffOk = false
        var coverOffMs = -1L
        var coverOffError: String? = null
        if (ownershipTransferAttempted) {{
            val coverOffStart = SystemClock.elapsedRealtime()
            val offResult = setPhysicalPowerOff(coverPhysicalId)
            coverOffOk = offResult.first
            coverOffError = offResult.second
            coverOffMs = SystemClock.elapsedRealtime() - coverOffStart
        }}

        val physicalStart =
            SystemClock.elapsedRealtime()

        val (powered, error) =
            setPhysicalPowerNormal(
                physicalId
            )

        val physicalPowerMs =
            SystemClock.elapsedRealtime() - physicalStart

        var coverRestoreOk = false
        var coverRestoreMs = -1L
        var coverRestoreError: String? = null
        if (ownershipTransferAttempted && coverOffOk) {{
            val coverRestoreStart = SystemClock.elapsedRealtime()
            val restoreResult = setPhysicalPowerNormal(coverPhysicalId)
            coverRestoreOk = restoreResult.first
            coverRestoreError = restoreResult.second
            coverRestoreMs = SystemClock.elapsedRealtime() - coverRestoreStart
        }}
''',
        "S1C cover-OFF INNER-ON cover-ON pulse",
    )

    text = replace_once(
        text,
        '''            putBoolean("physicalPowered", powered)
            putLong("physicalPowerMs", physicalPowerMs)
''',
        '''            putBoolean("ownershipTransferAttempted", ownershipTransferAttempted)
            putLong("coverPhysicalDisplayId", coverPhysicalId)
            putBoolean("coverOffOk", coverOffOk)
            putLong("coverOffMs", coverOffMs)
            if (coverOffError != null) putString("coverOffError", coverOffError)
            putBoolean("coverRestoreOk", coverRestoreOk)
            putLong("coverRestoreMs", coverRestoreMs)
            if (coverRestoreError != null) putString("coverRestoreError", coverRestoreError)
            putBoolean("physicalPowered", powered)
            putLong("physicalPowerMs", physicalPowerMs)
''',
        "S1C wake result telemetry",
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
                        // {MARKER}: ownership pulse telemetry only.
                        "ownershipPulse=${{result?.getBoolean("ownershipTransferAttempted", false) == true}} " +
                        "coverPhysical=${{result?.getLong("coverPhysicalDisplayId", -1L) ?: -1L}} " +
                        "coverOffOk=${{result?.getBoolean("coverOffOk", false) == true}} " +
                        "coverOffMs=${{result?.getLong("coverOffMs", -1L) ?: -1L}} " +
                        "coverRestoreOk=${{result?.getBoolean("coverRestoreOk", false) == true}} " +
                        "coverRestoreMs=${{result?.getLong("coverRestoreMs", -1L) ?: -1L}} " +
''',
        "S1C coordinator telemetry",
    )


def validate(shell: str, coord: str) -> None:
    required_shell = (
        MARKER,
        ".invoke(null, token, 0)",
        "ownershipTransferAttempted",
        "coverOffOk",
        "coverRestoreOk",
        "setPhysicalPowerNormal(coverPhysicalId)",
        "tx.setAlpha(layer, 0.0f)",
        "tx.setLayer(layer, Int.MIN_VALUE + 64)",
    )
    for value in required_shell:
        if value not in shell:
            raise RuntimeError(f"missing S1C shell invariant: {value}")

    required_coord = (
        MARKER,
        "ownershipPulse=",
        "coverOffOk=",
        "coverRestoreOk=",
        "sfInner=",
        "sfCover=",
    )
    for value in required_coord:
        if value not in coord:
            raise RuntimeError(f"missing S1C coordinator invariant: {value}")

    # Phase boundary: S1C changes only physical ownership ordering. It must not
    # change thresholds, hinge authority, transition identity, or animation.
    forbidden = (
        "FIRST_USEFUL_PIXEL",
        "COVER_PREWARM_DEG =",
        "INNER_WAKE_MIN_DEG =",
    )
    marker_window = coord[coord.index(MARKER) :]
    for value in forbidden:
        if value in marker_window[:2200]:
            raise RuntimeError(f"S1C unexpectedly touches later-phase behavior: {value}")


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
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    apply(Path(args.repo).resolve(), args.check)
    print(
        "stabilization S1C active transfer: " +
        ("source shape verified" if args.check else "applied")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
