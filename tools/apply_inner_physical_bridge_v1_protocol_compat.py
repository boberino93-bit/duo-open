#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

PROTOCOL = Path("app/src/full/java/com/duoopen/shell/ShellProtocol.kt")
BETA2_BLOCK = '''    const val COVER_PANEL_GEN4 = 18

    // Beta2: serialized physical cover power + brightness presentation.
    const val COVER_PRESENTATION_V1 = 19

    const val CB_ANGLE = 1
'''
BASE_SHAPE = '''    const val COVER_PANEL_GEN4 = 18

    const val CB_ANGLE = 1
'''
PHYSICAL_SHAPE = '''    // INNER_PHYSICAL_BRIDGE_V1: bounded Fold7 experiment only.
    const val INNER_PHYSICAL_BRIDGE = 19
    const val START_LID_EVENTS = 20
    const val STOP_LID_EVENTS = 21

    const val CB_ANGLE = 1
'''
FINAL_SHAPE = '''    // INNER_PHYSICAL_BRIDGE_V1: bounded Fold7 experiment only.
    const val INNER_PHYSICAL_BRIDGE = 19
    const val START_LID_EVENTS = 20
    const val STOP_LID_EVENTS = 21

    // Beta2 cover-presentation command is remapped only inside this isolated
    // experiment build to avoid a transaction-code collision.
    const val COVER_PRESENTATION_V1 = 22

    const val CB_ANGLE = 1
'''


def replace_one(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected one match, found {n}")
    return text.replace(old, new, 1)


def transform(text: str, phase: str) -> str:
    if phase == "pre":
        if FINAL_SHAPE in text:
            raise RuntimeError("final experiment protocol already present; pre phase is not idempotent across phases")
        return replace_one(text, BETA2_BLOCK, BASE_SHAPE, "remove Beta2 code-19 block")
    if phase == "post":
        return replace_one(text, PHYSICAL_SHAPE, FINAL_SHAPE, "restore Beta2 as code 22")
    raise ValueError(phase)


def apply(repo: Path, phase: str, check: bool) -> None:
    path = repo / PROTOCOL
    if not path.exists():
        raise RuntimeError(f"missing {PROTOCOL}")
    before = path.read_text(encoding="utf-8")
    after = transform(before, phase)
    if phase == "pre":
        if "COVER_PRESENTATION_V1" in after:
            raise RuntimeError("Beta2 presentation constant still present after pre phase")
    else:
        required = {
            "INNER_PHYSICAL_BRIDGE = 19",
            "START_LID_EVENTS = 20",
            "STOP_LID_EVENTS = 21",
            "COVER_PRESENTATION_V1 = 22",
        }
        missing = [x for x in required if x not in after]
        if missing:
            raise RuntimeError(f"final protocol missing: {missing}")
    if not check:
        path.write_text(after, encoding="utf-8")


def self_test() -> None:
    pre = transform(BETA2_BLOCK, "pre")
    assert pre == BASE_SHAPE
    physical = pre.replace(
        BASE_SHAPE,
        '''    const val COVER_PANEL_GEN4 = 18\n\n''' + PHYSICAL_SHAPE,
        1,
    )
    post = transform(physical, "post")
    assert "COVER_PRESENTATION_V1 = 22" in post
    assert "INNER_PHYSICAL_BRIDGE = 19" in post
    assert "START_LID_EVENTS = 20" in post
    assert "STOP_LID_EVENTS = 21" in post
    print("inner physical bridge protocol compatibility: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--phase", choices=("pre", "post"))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    if args.phase:
        apply(Path(args.repo).resolve(), args.phase, args.check)
    elif not args.self_test:
        parser.error("--phase is required unless --self-test is used")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
