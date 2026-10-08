#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def write_new(path: Path, content: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise RuntimeError(f"new-file collision: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    root = Path(args.repo).resolve()

    arbiter = root / "app/src/full/java/com/duoopen/shell/Fold7AngleTargetArbiter.kt"
    test = root / "app/src/test/java/com/duoopen/shell/Fold7AngleTargetArbiterTest.kt"

    write_new(
        arbiter,
        '''package com.duoopen.shell

/**
 * GEN12_4_ANGLE_AUTHORITY
 *
 * Android-free authority model for choosing which app window token is allowed
 * to drive one Samsung FoldInteractive poll. A successful callback proves the
 * selected target; a timeout only proves that target missed, not that the
 * logcat reader itself is dead.
 *
 * Methods are synchronized because target selection happens immediately before
 * main-thread command dispatch while callback/timeout completion is serialized
 * on the angle control handler.
 */
internal class Fold7AngleTargetArbiter(
    private val restartAfterExhaustedRounds: Int = 2,
    private val restartCooldownMs: Long = 1_000L,
) {
    init {
        require(restartAfterExhaustedRounds > 0)
        require(restartCooldownMs >= 0L)
    }

    data class Candidate(
        val key: String,
        val preferInner: Boolean,
    )

    data class AckDecision(
        val previousProvenKey: String?,
        val provenKey: String,
        val promoted: Boolean,
        val failover: Boolean,
    )

    data class MissDecision(
        val targetKey: String?,
        val roundExhausted: Boolean,
        val exhaustedRounds: Int,
        val requestReaderRestart: Boolean,
    )

    private val attemptedThisRound = LinkedHashSet<String>()

    private var proven: String? = null
    private var exhausted = 0
    private var lastAckUptimeMs = -1L
    private var lastRestartRequestUptimeMs = Long.MIN_VALUE
    private var promotionCount = 0L
    private var failoverCount = 0L
    private var timeoutCount = 0L

    @get:Synchronized
    val provenKey: String?
        get() = proven

    @get:Synchronized
    val exhaustedRounds: Int
        get() = exhausted

    @get:Synchronized
    val promotions: Long
        get() = promotionCount

    @get:Synchronized
    val failovers: Long
        get() = failoverCount

    @get:Synchronized
    val timeouts: Long
        get() = timeoutCount

    @Synchronized
    fun reset() {
        attemptedThisRound.clear()
        proven = null
        exhausted = 0
        lastAckUptimeMs = -1L
        lastRestartRequestUptimeMs = Long.MIN_VALUE
        promotionCount = 0L
        failoverCount = 0L
        timeoutCount = 0L
    }

    /**
     * Select one target only. A proven target wins while it has not already
     * missed in the current probe round; otherwise probe an unattempted target.
     */
    @Synchronized
    fun select(
        candidates: List<Candidate>,
    ): Candidate? {
        val unique =
            candidates
                .filter { it.key.isNotBlank() }
                .distinctBy { it.key }

        if (unique.isEmpty()) return null

        proven?.let { key ->
            unique.firstOrNull {
                it.key == key &&
                    it.key !in attemptedThisRound
            }?.let {
                return it
            }
        }

        return unique
            .asSequence()
            .filter {
                it.key !in attemptedThisRound
            }
            .sortedWith(
                compareByDescending<Candidate> {
                    it.preferInner
                }.thenBy {
                    it.key
                }
            )
            .firstOrNull()
            ?: unique
                .sortedWith(
                    compareByDescending<Candidate> {
                        it.preferInner
                    }.thenBy {
                        it.key
                    }
                )
                .first()
    }

    @Synchronized
    fun onAck(
        targetKey: String,
        nowUptimeMs: Long,
    ): AckDecision {
        require(targetKey.isNotBlank())

        val previous = proven
        val promoted =
            previous != targetKey

        val failover =
            previous != null &&
                previous != targetKey

        if (promoted) {
            promotionCount++
        }
        if (failover) {
            failoverCount++
        }

        proven = targetKey
        attemptedThisRound.clear()
        exhausted = 0
        lastAckUptimeMs = nowUptimeMs

        return AckDecision(
            previousProvenKey = previous,
            provenKey = targetKey,
            promoted = promoted,
            failover = failover,
        )
    }

    /**
     * Record a miss for the one target used by this poll. Reader restart is
     * permitted only after every currently available target has missed for the
     * configured number of complete probe rounds.
     */
    @Synchronized
    fun onMiss(
        targetKey: String?,
        candidateKeys: Collection<String>,
        nowUptimeMs: Long,
    ): MissDecision {
        val candidates =
            candidateKeys
                .filter { it.isNotBlank() }
                .toSet()

        if (
            targetKey == null ||
            targetKey !in candidates
        ) {
            return MissDecision(
                targetKey = targetKey,
                roundExhausted = false,
                exhaustedRounds = exhausted,
                requestReaderRestart = false,
            )
        }

        timeoutCount++
        attemptedThisRound += targetKey

        val roundExhausted =
            candidates.all {
                it in attemptedThisRound
            }

        if (!roundExhausted) {
            return MissDecision(
                targetKey = targetKey,
                roundExhausted = false,
                exhaustedRounds = exhausted,
                requestReaderRestart = false,
            )
        }

        attemptedThisRound.clear()
        exhausted++

        val cooldownSatisfied =
            lastRestartRequestUptimeMs == Long.MIN_VALUE ||
                nowUptimeMs - lastRestartRequestUptimeMs >=
                restartCooldownMs

        val requestRestart =
            exhausted >= restartAfterExhaustedRounds &&
                cooldownSatisfied

        if (requestRestart) {
            lastRestartRequestUptimeMs = nowUptimeMs
            exhausted = 0
        }

        return MissDecision(
            targetKey = targetKey,
            roundExhausted = true,
            exhaustedRounds = exhausted,
            requestReaderRestart = requestRestart,
        )
    }

    /** Reader replacement does not erase which target was last proven. */
    @Synchronized
    fun onReaderRestart() {
        attemptedThisRound.clear()
        exhausted = 0
    }

    @Synchronized
    fun forget(
        key: String,
    ) {
        attemptedThisRound.remove(key)
        if (proven == key) {
            proven = null
            lastAckUptimeMs = -1L
        }
    }

    @Synchronized
    fun lastAckAgeMs(
        nowUptimeMs: Long,
    ): Long =
        if (lastAckUptimeMs < 0L) {
            -1L
        } else {
            (nowUptimeMs - lastAckUptimeMs)
                .coerceAtLeast(0L)
        }

    @Synchronized
    fun summary(
        nowUptimeMs: Long,
    ): String {
        val age = lastAckAgeMs(nowUptimeMs)
        return (
            (proven ?: "probing") +
                " age=" +
                if (age >= 0L) "${age}ms" else "none" +
                " rounds=$exhausted" +
                " failover=$failoverCount"
            )
    }
}
''',
    )

    write_new(
        test,
        '''package com.duoopen.shell

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7AngleTargetArbiterTest {
    private val inner =
        Fold7AngleTargetArbiter.Candidate(
            key = "0:1968x2184",
            preferInner = true,
        )

    private val cover =
        Fold7AngleTargetArbiter.Candidate(
            key = "1:1080x2520",
            preferInner = false,
        )

    @Test
    fun initialProbePrefersInnerButDoesNotCallItProven() {
        val arbiter = Fold7AngleTargetArbiter()

        assertEquals(inner, arbiter.select(listOf(cover, inner)))
        assertNull(arbiter.provenKey)
    }

    @Test
    fun ackMakesExactTargetStickyAcrossCandidateReordering() {
        val arbiter = Fold7AngleTargetArbiter()

        arbiter.onAck(cover.key, 100L)

        assertEquals(cover.key, arbiter.provenKey)
        assertEquals(cover, arbiter.select(listOf(inner, cover)))
        assertEquals(cover, arbiter.select(listOf(cover, inner)))
    }

    @Test
    fun provenMissProbesAlternateAndAlternateAckPromotesIt() {
        val arbiter = Fold7AngleTargetArbiter()
        val candidates = listOf(inner, cover)

        arbiter.onAck(inner.key, 100L)
        val miss =
            arbiter.onMiss(
                targetKey = inner.key,
                candidateKeys = candidates.map { it.key },
                nowUptimeMs = 200L,
            )

        assertFalse(miss.roundExhausted)
        assertEquals(cover, arbiter.select(candidates))

        val ack = arbiter.onAck(cover.key, 210L)
        assertTrue(ack.promoted)
        assertTrue(ack.failover)
        assertEquals(cover.key, arbiter.provenKey)
        assertEquals(1L, arbiter.failovers)
    }

    @Test
    fun readerRestartRequiresRepeatedAllTargetFailure() {
        val arbiter =
            Fold7AngleTargetArbiter(
                restartAfterExhaustedRounds = 2,
                restartCooldownMs = 1_000L,
            )
        val keys = listOf(inner.key, cover.key)

        assertFalse(arbiter.onMiss(inner.key, keys, 100L).roundExhausted)
        val firstRound = arbiter.onMiss(cover.key, keys, 200L)
        assertTrue(firstRound.roundExhausted)
        assertFalse(firstRound.requestReaderRestart)

        assertFalse(arbiter.onMiss(inner.key, keys, 300L).roundExhausted)
        val secondRound = arbiter.onMiss(cover.key, keys, 400L)
        assertTrue(secondRound.roundExhausted)
        assertTrue(secondRound.requestReaderRestart)
    }

    @Test
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

    @Test
    fun successfulAckClearsProbeRoundAndRestartPressure() {
        val arbiter =
            Fold7AngleTargetArbiter(
                restartAfterExhaustedRounds = 2,
                restartCooldownMs = 0L,
            )
        val keys = listOf(inner.key)

        assertFalse(
            arbiter.onMiss(inner.key, keys, 100L)
                .requestReaderRestart
        )
        arbiter.onAck(inner.key, 110L)
        assertEquals(0, arbiter.exhaustedRounds)
        assertFalse(
            arbiter.onMiss(inner.key, keys, 120L)
                .requestReaderRestart
        )
    }

    @Test
    fun forgettingProvenTargetRemovesAuthority() {
        val arbiter = Fold7AngleTargetArbiter()

        arbiter.onAck(inner.key, 100L)
        arbiter.forget(inner.key)

        assertNull(arbiter.provenKey)
        assertEquals(cover, arbiter.select(listOf(cover)))
    }

    @Test
    fun noCandidateDoesNotManufactureReaderFailure() {
        val arbiter = Fold7AngleTargetArbiter(restartAfterExhaustedRounds = 1)

        val miss =
            arbiter.onMiss(
                targetKey = null,
                candidateKeys = emptyList(),
                nowUptimeMs = 100L,
            )

        assertFalse(miss.roundExhausted)
        assertFalse(miss.requestReaderRestart)
        assertEquals(0L, arbiter.timeouts)
    }
}
''',
    )

    print("GEN12.4 ANGLE AUTHORITY MODEL: APPLIED")


if __name__ == "__main__":
    main()
