#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

SHELL = Path("app/src/full/java/com/duoopen/shell/DuoShellService.kt")
MARKER = "STABILIZATION_S1F_LAYOUT_MAP_TRUTH_V1"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_shell(text: str) -> str:
    if MARKER in text:
        return text
    if "STABILIZATION_S1E_LOGICAL_LAYOUT_TRUTH_V1" not in text:
        raise RuntimeError("S1E logical-layout truth must be applied first")
    if "STABILIZATION_S1C_ACTIVE_TRANSFER_V1" in text or "STABILIZATION_S1D_REAL_INNER_EDGE_V1" in text:
        raise RuntimeError("S1F must remain read-only and must not stack S1C/S1D power mutations")

    old = '''    private fun compactLogicalLayoutExcerpt(dump: String): String =
        dump.lineSequence()
            .filter { line ->
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
            }
            .take(120)
            .joinToString(" | ") { it.trim() }
            .take(8000)
'''

    new = f'''    // {MARKER}: S1E's broad filter was dominated by long DisplayDeviceInfo
    // lines before it reached LogicalDisplayMapper. Restrict the readback to the
    // mapper block itself and retain the registered state->layout table.
    private fun compactLogicalLayoutExcerpt(dump: String): String {{
        val marker = dump.indexOf("LogicalDisplayMapper:")
        val block = if (marker >= 0) dump.substring(marker) else dump
        return block.lineSequence()
            .filter {{ line ->
                line.contains("LogicalDisplayMapper:", ignoreCase = true) ||
                    line.contains("mCurrentLayout=", ignoreCase = true) ||
                    line.contains("mDeviceState=", ignoreCase = true) ||
                    line.contains("mPendingDeviceState=", ignoreCase = true) ||
                    line.contains("mDeviceStateToBeAppliedAfterBoot=", ignoreCase = true) ||
                    line.contains("Logical Displays:", ignoreCase = true) ||
                    Regex("^\\\\s*Display \\\\d+:").containsMatchIn(line) ||
                    line.contains("mIsEnabled=", ignoreCase = true) ||
                    line.contains("isEnabled=", ignoreCase = true) ||
                    line.contains("mPrimaryDisplayDevice=", ignoreCase = true) ||
                    line.contains("DeviceStateToLayoutMap:", ignoreCase = true) ||
                    line.contains("Registered Layouts:", ignoreCase = true) ||
                    Regex("state\\\\(-?\\\\d+\\\\):").containsMatchIn(line)
            }}
            .take(180)
            .joinToString(" | ") {{ it.trim() }}
            .take(12000)
    }}
'''

    return replace_once(text, old, new, "S1F targeted LogicalDisplayMapper excerpt")


def validate(shell: str) -> None:
    for needle in (
        MARKER,
        'dump.indexOf("LogicalDisplayMapper:")',
        'line.contains("mCurrentLayout=", ignoreCase = true)',
        'line.contains("mDeviceState=", ignoreCase = true)',
        'line.contains("DeviceStateToLayoutMap:", ignoreCase = true)',
        'line.contains("Registered Layouts:", ignoreCase = true)',
        'Regex("state\\\\(-?\\\\d+\\\\):")',
        'runProbe("dumpsys display 2>/dev/null")',
        'runProbe("cmd device_state state 2>/dev/null")',
        "probeSurfaceFlingerPowerTruth",
        "tx.setAlpha(layer, 0.0f)",
        "tx.setLayer(layer, Int.MIN_VALUE + 64)",
    ):
        if needle not in shell:
            raise RuntimeError(f"missing S1F invariant: {needle}")

    for forbidden in (
        "STABILIZATION_S1C_ACTIVE_TRANSFER_V1",
        "STABILIZATION_S1D_REAL_INNER_EDGE_V1",
        'cmd device_state state 4',
        'cmd device_state state 5',
        'cmd device_state state reset',
        'cmd device_state base-state',
    ):
        if forbidden in shell:
            raise RuntimeError(f"S1F unexpectedly contains behavior mutation: {forbidden}")


def apply(repo: Path, check: bool) -> None:
    shell_path = repo / SHELL
    if not shell_path.exists():
        raise RuntimeError("required generated DuoShellService source missing")
    shell = transform_shell(shell_path.read_text(encoding="utf-8"))
    validate(shell)
    if not check:
        shell_path.write_text(shell, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    apply(Path(args.repo).resolve(), args.check)
    print(
        "stabilization S1F layout-map truth: " +
        ("source shape verified" if args.check else "applied")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
