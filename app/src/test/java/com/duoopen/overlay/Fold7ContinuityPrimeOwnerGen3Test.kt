package com.duoopen.overlay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7ContinuityPrimeOwnerGen3Test {
    private val cycle =
        Fold7CycleEnvelope.CloseCycle(
            serviceEpoch = 7L,
            closeCycleId = 11L,
            startedUptimeMs = 100L,
        )

    @Test
    fun duplicateReservationIsDeniedWhileCurrentAttemptIsInflight() {
        val owner =
            Fold7ContinuityPrimeOwner()

        assertNotNull(
            owner.reserve(
                cycle,
                Fold7ContinuityPrimeOwner.Source.SHIZUKU,
            )
        )

        assertNull(
            owner.reserve(
                cycle,
                Fold7ContinuityPrimeOwner.Source.SHIZUKU,
            )
        )
    }

    @Test
    fun staleCompletionCannotBeatExplicitRetry() {
        val owner =
            Fold7ContinuityPrimeOwner()

        val first =
            owner.reserve(
                cycle,
                Fold7ContinuityPrimeOwner.Source.SHIZUKU,
            )!!

        assertTrue(
            owner.markFailed(
                first,
                "forced-first-failure",
            )
        )

        val retry =
            owner.reserve(
                cycle,
                Fold7ContinuityPrimeOwner.Source.SHIZUKU,
            )!!

        assertFalse(
            owner.markReady(
                first
            )
        )

        assertTrue(
            owner.markReady(
                retry
            )
        )

        assertEquals(
            Fold7ContinuityPrimeOwner.State.READY,
            owner.snapshot().state,
        )
    }

    @Test
    fun invalidatedCycleRejectsQueuedCompletion() {
        val owner =
            Fold7ContinuityPrimeOwner()

        val first =
            owner.reserve(
                cycle,
                Fold7ContinuityPrimeOwner.Source.SHIZUKU,
            )!!

        owner.invalidate(
            cycle
        )

        assertFalse(
            owner.markReady(
                first
            )
        )
    }
}
