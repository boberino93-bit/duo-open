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
            str(root / "tools/apply_gen12_4_angle_authority_model_fix1.py"),
            "--repo",
            str(root),
        ],
        check=True,
    )

    arbiter = root / "app/src/full/java/com/duoopen/shell/Fold7AngleTargetArbiter.kt"
    test = root / "app/src/test/java/com/duoopen/shell/Fold7AngleTargetArbiterTest.kt"

    replace_once(
        arbiter,
        '''    private var promotionCount = 0L
    private var failoverCount = 0L
    private var timeoutCount = 0L
''',
        '''    private var promotionCount = 0L
    private var failoverCount = 0L
    private var timeoutCount = 0L
    private var restartSuppressed = false
    private var lastCandidateSet: Set<String> = emptySet()
''',
        "recovery circuit fields",
    )

    replace_once(
        arbiter,
        '''    @get:Synchronized
    val timeouts: Long
        get() = timeoutCount

    @Synchronized
    fun reset() {
''',
        '''    @get:Synchronized
    val timeouts: Long
        get() = timeoutCount

    @get:Synchronized
    val readerRecoveryArmed: Boolean
        get() = !restartSuppressed

    @Synchronized
    fun reset() {
''',
        "recovery armed property",
    )

    replace_once(
        arbiter,
        '''        promotionCount = 0L
        failoverCount = 0L
        timeoutCount = 0L
    }
''',
        '''        promotionCount = 0L
        failoverCount = 0L
        timeoutCount = 0L
        restartSuppressed = false
        lastCandidateSet = emptySet()
    }
''',
        "reset recovery circuit",
    )

    replace_once(
        arbiter,
        '''        proven = targetKey
        attemptedThisRound.clear()
        exhausted = 0
        lastAckUptimeMs = nowUptimeMs
''',
        '''        proven = targetKey
        attemptedThisRound.clear()
        exhausted = 0
        restartSuppressed = false
        lastAckUptimeMs = nowUptimeMs
''',
        "ack rearms reader recovery",
    )

    replace_once(
        arbiter,
        '''        val candidates =
            candidateKeys
                .filter { it.isNotBlank() }
                .toSet()

        if (
            targetKey == null ||
''',
        '''        val candidates =
            candidateKeys
                .filter { it.isNotBlank() }
                .toSet()

        if (candidates != lastCandidateSet) {
            // A real topology/target-set change creates a new failure epoch.
            // This is evidence worth one fresh reader-recovery attempt.
            lastCandidateSet = candidates
            attemptedThisRound.retainAll(candidates)
            exhausted = 0
            restartSuppressed = false
        }

        if (
            targetKey == null ||
''',
        "candidate epoch rearm",
    )

    replace_once(
        arbiter,
        '''        val requestRestart =
            exhausted >= restartAfterExhaustedRounds &&
                cooldownSatisfied

        if (requestRestart) {
            lastRestartRequestUptimeMs = nowUptimeMs
            exhausted = 0
        }
''',
        '''        val requestRestart =
            exhausted >= restartAfterExhaustedRounds &&
                cooldownSatisfied &&
                !restartSuppressed

        if (requestRestart) {
            lastRestartRequestUptimeMs = nowUptimeMs
            exhausted = 0
            // One successful replacement is enough diagnostic intervention for
            // an unchanged dead target set. Do not churn the reader forever.
            restartSuppressed = true
        }
''',
        "single restart per target failure epoch",
    )

    replace_once(
        arbiter,
        '''        return (
            "${proven ?: "probing"} " +
                "age=$ageText " +
                "rounds=$exhausted " +
                "failover=$failoverCount"
            )
''',
        '''        return (
            "${proven ?: "probing"} " +
                "age=$ageText " +
                "rounds=$exhausted " +
                "failover=$failoverCount " +
                "readerRecovery=${if (restartSuppressed) "latched" else "armed"}"
            )
''',
        "summary recovery state",
    )

    replace_once(
        test,
        '''            "probing age=none rounds=0 failover=0",
            arbiter.summary(100L),
        )

        arbiter.onAck(inner.key, 100L)
        assertEquals(
            "0:1968x2184 age=50ms rounds=0 failover=0",
            arbiter.summary(150L),
        )
''',
        '''            "probing age=none rounds=0 failover=0 readerRecovery=armed",
            arbiter.summary(100L),
        )

        arbiter.onAck(inner.key, 100L)
        assertEquals(
            "0:1968x2184 age=50ms rounds=0 failover=0 readerRecovery=armed",
            arbiter.summary(150L),
        )
''',
        "summary recovery expectations",
    )

    replace_once(
        test,
        '''    @Test
    fun successfulAckClearsProbeRoundAndRestartPressure() {
''',
        '''    @Test
    fun unchangedDeadTargetSetDoesNotRestartReaderForever() {
        val arbiter =
            Fold7AngleTargetArbiter(
                restartAfterExhaustedRounds = 1,
                restartCooldownMs = 0L,
            )
        val keys = listOf(inner.key)

        assertTrue(
            arbiter.onMiss(inner.key, keys, 100L)
                .requestReaderRestart
        )
        arbiter.onReaderRestart()
        assertFalse(arbiter.readerRecoveryArmed)

        repeat(4) { index ->
            assertFalse(
                arbiter.onMiss(
                    inner.key,
                    keys,
                    200L + index,
                ).requestReaderRestart
            )
        }
    }

    @Test
    fun targetSetChangeRearmsReaderRecovery() {
        val arbiter =
            Fold7AngleTargetArbiter(
                restartAfterExhaustedRounds = 1,
                restartCooldownMs = 0L,
            )

        assertTrue(
            arbiter.onMiss(
                inner.key,
                listOf(inner.key),
                100L,
            ).requestReaderRestart
        )
        arbiter.onReaderRestart()
        assertFalse(arbiter.readerRecoveryArmed)

        val changed = listOf(inner.key, cover.key)
        assertFalse(
            arbiter.onMiss(inner.key, changed, 200L)
                .requestReaderRestart
        )
        assertTrue(arbiter.readerRecoveryArmed)
        assertTrue(
            arbiter.onMiss(cover.key, changed, 201L)
                .requestReaderRestart
        )
    }

    @Test
    fun successfulAckClearsProbeRoundAndRestartPressure() {
''',
        "circuit breaker tests",
    )

    print("GEN12.4 ANGLE AUTHORITY MODEL FIX2: PASS")


if __name__ == "__main__":
    main()
