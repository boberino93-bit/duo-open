#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

SERVICE = Path("app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt")
MARKER = "INNER_PHYSICAL_BRIDGE_V1_SERVICE_FIXUPS"


def transform(text: str) -> str:
    if MARKER in text:
        return text
    anchor = '''            ShizukuBridge.state.collect { state ->
'''
    if text.count(anchor) != 1:
        raise RuntimeError(f"Shizuku state collector: expected one match, found {text.count(anchor)}")
    replacement = '''            ShizukuBridge.state.collect { state ->
                // INNER_PHYSICAL_BRIDGE_V1_SERVICE_FIXUPS: binder loss kills
                // the shell reader; clear app-side state so reconnect can start it.
                if (state !is ShizukuBridge.State.Ready) {
                    stopLidEvents()
                }
'''
    return text.replace(anchor, replacement, 1)


def apply(repo: Path, check: bool) -> None:
    path = repo / SERVICE
    if not path.exists():
        raise RuntimeError(f"missing {SERVICE}")
    before = path.read_text(encoding="utf-8")
    if "lid-switch-open" not in before:
        raise RuntimeError("physical bridge service transform must run first")
    after = transform(before)
    if MARKER not in after:
        raise RuntimeError("service fixup marker missing")
    if not check:
        path.write_text(after, encoding="utf-8")


def self_test() -> None:
    sample = "x\n            ShizukuBridge.state.collect { state ->\n                y\n"
    out = transform(sample)
    assert MARKER in out
    assert "state !is ShizukuBridge.State.Ready" in out
    print("inner physical bridge service fixups: PASS")


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
