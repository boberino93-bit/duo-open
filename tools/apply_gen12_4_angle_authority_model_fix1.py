#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"ERROR: {label}: expected exactly one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    root = Path(args.repo).resolve()

    subprocess.run(
        [
            "python3",
            str(root / "tools/apply_gen12_4_angle_authority_model.py"),
            "--repo",
            str(root),
        ],
        check=True,
    )

    arbiter = root / "app/src/full/java/com/duoopen/shell/Fold7AngleTargetArbiter.kt"
    test = root / "app/src/test/java/com/duoopen/shell/Fold7AngleTargetArbiterTest.kt"

    replace_once(
        arbiter,
        '''        val age = lastAckAgeMs(nowUptimeMs)
        return (
            (proven ?: "probing") +
                " age=" +
                if (age >= 0L) "${age}ms" else "none" +
                " rounds=$exhausted" +
                " failover=$failoverCount"
            )
''',
        '''        val age = lastAckAgeMs(nowUptimeMs)
        val ageText =
            if (age >= 0L) {
                "${age}ms"
            } else {
                "none"
            }

        return (
            "${proven ?: "probing"} " +
                "age=$ageText " +
                "rounds=$exhausted " +
                "failover=$failoverCount"
            )
''',
        "summary precedence",
    )

    replace_once(
        test,
        '''    @Test
    fun noCandidateDoesNotManufactureReaderFailure() {
''',
        '''    @Test
    fun summaryAlwaysIncludesAllAuthorityFields() {
        val arbiter = Fold7AngleTargetArbiter()

        assertEquals(
            "probing age=none rounds=0 failover=0",
            arbiter.summary(100L),
        )

        arbiter.onAck(inner.key, 100L)
        assertEquals(
            "0:1968x2184 age=50ms rounds=0 failover=0",
            arbiter.summary(150L),
        )
    }

    @Test
    fun noCandidateDoesNotManufactureReaderFailure() {
''',
        "summary test",
    )

    print("GEN12.4 ANGLE AUTHORITY MODEL FIX1: PASS")


if __name__ == "__main__":
    main()
