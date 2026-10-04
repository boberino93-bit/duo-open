#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

GRADLE = Path("app/build.gradle.kts")
PROTOCOL = Path("app/src/full/java/com/duoopen/shell/ShellProtocol.kt")
EXPORTER = Path("app/src/main/java/com/duoopen/debug/DebugBundleExporter.kt")

MARKER = "S1O_HALL_PREWAKE_PROTOCOL_V1"

UNIQUE_IDS = {
    "INNER_PHYSICAL_BRIDGE": 30,
    "START_LID_EVENTS": 31,
    "STOP_LID_EVENTS": 32,
    "CAPTURE_PHYSICAL_FORENSIC": 33,
    "RENDER_TIMELINE_PROBE": 34,
    "PREWAKE_INNER_PHYSICAL_ONLY": 35,
}


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_gradle(text: str) -> str:
    if 'versionName = "5.1.0-beta2-zfold7-s1o"' in text:
        return text
    text = one(text, "        versionCode = 48\n", "        versionCode = 49\n", "versionCode")
    return one(
        text,
        '        versionName = "5.1.0-beta2-zfold7-s1n"\n',
        '        versionName = "5.1.0-beta2-zfold7-s1o"\n',
        "versionName",
    )


def transform_protocol(text: str) -> str:
    if MARKER in text:
        return text

    replacements = {
        "    const val INNER_PHYSICAL_BRIDGE = 19\n":
            f"    // {MARKER}: unique Binder transaction IDs; do not reuse.\n"
            f"    const val INNER_PHYSICAL_BRIDGE = {UNIQUE_IDS['INNER_PHYSICAL_BRIDGE']}\n",
        "    const val START_LID_EVENTS = 20\n":
            f"    const val START_LID_EVENTS = {UNIQUE_IDS['START_LID_EVENTS']}\n",
        "    const val STOP_LID_EVENTS = 21\n":
            f"    const val STOP_LID_EVENTS = {UNIQUE_IDS['STOP_LID_EVENTS']}\n",
        "    const val CAPTURE_PHYSICAL_FORENSIC = 19\n":
            f"    const val CAPTURE_PHYSICAL_FORENSIC = {UNIQUE_IDS['CAPTURE_PHYSICAL_FORENSIC']}\n",
        "    const val RENDER_TIMELINE_PROBE = 20\n":
            f"    const val RENDER_TIMELINE_PROBE = {UNIQUE_IDS['RENDER_TIMELINE_PROBE']}\n",
        "    const val PREWAKE_INNER_PHYSICAL_ONLY = 21\n":
            f"    const val PREWAKE_INNER_PHYSICAL_ONLY = {UNIQUE_IDS['PREWAKE_INNER_PHYSICAL_ONLY']}\n",
    }
    out = text
    for old, new in replacements.items():
        out = one(out, old, new, old.strip())
    return out


def transform_exporter(text: str) -> str:
    if "hallPrewakeProtocol=S1O_HALL_PREWAKE_PROTOCOL_V1" in text:
        return text
    anchor = '''                        appendLine(
                            "concurrentDeviceStateRouteProbe=REMOVED_AFTER_S1M_FIELD_REGRESSION"
                        )
'''
    addition = anchor + '''                        appendLine(
                            "hallPrewakeProtocol=S1O_HALL_PREWAKE_PROTOCOL_V1"
                        )
                        appendLine(
                            "hallPrewakeTrigger=RAW_SW_LID_OPEN_PLUS_SAFE_DEVICE_STATE_0_TO_1_FALLBACK"
                        )
                        appendLine(
                            "shellProtocolCollisionFix=UNIQUE_30_TO_35"
                        )
'''
    return one(text, anchor, addition, "export S1O identity")


def transaction_constants(text: str) -> dict[str, int]:
    found = {}
    for name, value in re.findall(r"^\s*const val ([A-Z0-9_]+) = (\d+)\s*$", text, flags=re.M):
        if name in {"CB_ANGLE", "CB_LID"}:
            continue
        found[name] = int(value)
    return found


def validate(g: str, p: str, e: str) -> None:
    for needle in ('versionCode = 49', 'versionName = "5.1.0-beta2-zfold7-s1o"'):
        if needle not in g:
            raise RuntimeError("missing S1O gradle invariant: " + needle)

    for name, expected in UNIQUE_IDS.items():
        needle = f"const val {name} = {expected}"
        if needle not in p:
            raise RuntimeError("missing S1O protocol invariant: " + needle)

    constants = transaction_constants(p)
    by_value: dict[int, list[str]] = {}
    for name, value in constants.items():
        by_value.setdefault(value, []).append(name)
    collisions = {value: names for value, names in by_value.items() if len(names) > 1}
    if collisions:
        raise RuntimeError(f"Binder transaction ID collision remains: {collisions}")

    if "hallPrewakeProtocol=S1O_HALL_PREWAKE_PROTOCOL_V1" not in e:
        raise RuntimeError("missing S1O exporter identity")

    prohibited = (
        "cmd device_state state 5",
        "scheduleConcurrentOuterRouteProbe",
        "PROBE_CONCURRENT_OUTER_DEFAULT",
    )
    for needle in prohibited:
        if needle in "\n".join((p, e)):
            raise RuntimeError("S1O must not reintroduce S1M route override: " + needle)


def apply(repo: Path, check: bool) -> None:
    for rel in (GRADLE, PROTOCOL, EXPORTER):
        if not (repo / rel).exists():
            raise RuntimeError("missing " + str(rel))

    g = transform_gradle((repo / GRADLE).read_text(encoding="utf-8"))
    p = transform_protocol((repo / PROTOCOL).read_text(encoding="utf-8"))
    e = transform_exporter((repo / EXPORTER).read_text(encoding="utf-8"))
    validate(g, p, e)

    if not check:
        (repo / GRADLE).write_text(g, encoding="utf-8")
        (repo / PROTOCOL).write_text(p, encoding="utf-8")
        (repo / EXPORTER).write_text(e, encoding="utf-8")


def self_test() -> None:
    protocol = """object ShellProtocol {
    const val PING = 1
    const val INNER_PHYSICAL_BRIDGE = 19
    const val START_LID_EVENTS = 20
    const val STOP_LID_EVENTS = 21
    const val CAPTURE_PHYSICAL_FORENSIC = 19
    const val RENDER_TIMELINE_PROBE = 20
    const val PREWAKE_INNER_PHYSICAL_ONLY = 21
    const val CB_ANGLE = 1
    const val CB_LID = 2
}
"""
    out = transform_protocol(protocol)
    values = transaction_constants(out)
    assert len(values.values()) == len(set(values.values()))
    assert values["START_LID_EVENTS"] == 31
    assert values["PREWAKE_INNER_PHYSICAL_ONLY"] == 35
    print("S1O Hall prewake protocol self-test: PASS")


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
    print("S1O Hall prewake protocol: " + ("source shape verified" if args.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
