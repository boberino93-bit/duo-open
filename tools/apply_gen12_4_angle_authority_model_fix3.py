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
            str(root / "tools/apply_gen12_4_angle_authority_model_fix2.py"),
            "--repo",
            str(root),
        ],
        check=True,
    )

    test = root / "app/src/test/java/com/duoopen/shell/Fold7AngleTargetArbiterTest.kt"

    replace_once(
        test,
        '''    @Test
    fun restartRequestsAreRateLimitedWhenTargetsRemainDead() {
        val arbiter =
            Fold7AngleTargetArbiter(
                restartAfterExhaustedRounds = 1,
                restartCooldownMs = 1_000L,
            )
        val keys = listOf(inner.key)

        assertTrue(
            arbiter.onMiss(inner.key, keys, 1_000L)
                .requestReaderRestart
        )
        assertFalse(
            arbiter.onMiss(inner.key, keys, 1_200L)
                .requestReaderRestart
        )
        assertTrue(
            arbiter.onMiss(inner.key, keys, 2_000L)
                .requestReaderRestart
        )
    }
''',
        '''    @Test
    fun unchangedFailureEpochStaysLatchedEvenAfterCooldown() {
        val arbiter =
            Fold7AngleTargetArbiter(
                restartAfterExhaustedRounds = 1,
                restartCooldownMs = 1_000L,
            )
        val keys = listOf(inner.key)

        assertTrue(
            arbiter.onMiss(inner.key, keys, 1_000L)
                .requestReaderRestart
        )
        arbiter.onReaderRestart()
        assertFalse(
            arbiter.onMiss(inner.key, keys, 1_200L)
                .requestReaderRestart
        )
        assertFalse(
            arbiter.onMiss(inner.key, keys, 2_500L)
                .requestReaderRestart
        )
        assertFalse(arbiter.readerRecoveryArmed)
    }
''',
        "obsolete cooldown-only restart expectation",
    )

    print("GEN12.4 ANGLE AUTHORITY MODEL FIX3: PASS")


if __name__ == "__main__":
    main()
