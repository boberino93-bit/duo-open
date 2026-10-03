#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

TARGET = Path("tools/apply_inner_physical_bridge_v1.py")
MARKER = "BETA2_DEVICE_STATE_CALLBACK_PRESERVED"
START = "    pattern = r'''            \\) \\{\n"
END = "    text = replace_once(\n        text,\n        '''                    continuity.onPrivilegedReady()\n"
STOP_START = "    text = replace_once(\n        text,\n        '''                } else {\n                    setEarlyOpeningVisualLatched(\n"
STOP_END = "    text = replace_once(\n        text,\n        '''        deviceStateObserver\n            ?.stop()\n"


def transform(text: str) -> str:
    if MARKER in text:
        return text
    start = text.find(START)
    if start < 0:
        raise RuntimeError("legacy DeviceState extraction block start not found")
    end = text.find(END, start)
    if end < 0:
        raise RuntimeError("legacy DeviceState extraction block end not found")
    text = (
        text[:start]
        + f"    # {MARKER}: Beta2's proven DeviceState fallback stays untouched;\n"
          "    # the new SW_LID path calls handleEarlyOpeningEdge independently.\n\n"
        + text[end:]
    )

    stop_start = text.find(STOP_START)
    if stop_start < 0:
        raise RuntimeError("obsolete Shizuku-unavailable rewrite start not found")
    stop_end = text.find(STOP_END, stop_start)
    if stop_end < 0:
        raise RuntimeError("obsolete Shizuku-unavailable rewrite end not found")
    text = (
        text[:stop_start]
        + "    # Beta2 Shizuku-unavailable shape is preserved; a separate runtime\n"
          "    # fixup resets the lid-reader flag at the collector boundary.\n\n"
        + text[stop_end:]
    )
    return text


def apply(repo: Path, check: bool) -> None:
    path = repo / TARGET
    if not path.exists():
        raise RuntimeError(f"missing {TARGET}")
    before = path.read_text(encoding="utf-8")
    after = transform(before)
    if MARKER not in after:
        raise RuntimeError("preparation marker missing")
    if "device state callback extraction" in after:
        raise RuntimeError("obsolete DeviceState extraction still present")
    if "stop lid when unavailable" in after:
        raise RuntimeError("obsolete unavailable-state extraction still present")
    if not check:
        path.write_text(after, encoding="utf-8")


def self_test() -> None:
    sample = (
        "before\n" + START + "old callback matcher\n" + END
        + "middle\n" + STOP_START + "old unavailable rewrite\n" + STOP_END + "after\n"
    )
    out = transform(sample)
    assert MARKER in out
    assert "old callback matcher" not in out
    assert "old unavailable rewrite" not in out
    assert END in out
    assert STOP_END in out
    print("inner physical bridge transformer preparation: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    if not args.self_test or args.check:
        apply(Path(args.repo).resolve(), args.check)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
