package com.duoopen.overlay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7StandbyRouteLeaseTest {
    private fun owner(
        cycle: Long,
        generation: Long,
    ) =
        Fold7StandbyRouteLease.Owner(
            serviceEpoch = 100L,
            closeCycleId = cycle,
            transitionGeneration = generation,
        )

    @Test
    fun retainedOwnerSurvivesUntilExactTicketExpires() {
        val gate = Fold7StandbyRouteLease()
        val expected = owner(cycle = 9L, generation = 66L)
        val ticket = gate.retain(expected)

        assertEquals(expected, gate.owner())
        assertTrue(gate.isCurrent(ticket))
        assertTrue(gate.consumeExpiry(ticket))
        assertNull(gate.owner())
        assertFalse(gate.consumeExpiry(ticket))
    }

    @Test
    fun newerCloseCancellationMakesOldTimerInert() {
        val gate = Fold7StandbyRouteLease()
        val old = owner(cycle = 9L, generation = 66L)
        val ticket = gate.retain(old)

        assertEquals(old, gate.cancel())
        assertNull(gate.owner())
        assertFalse(gate.isCurrent(ticket))
        assertFalse(gate.consumeExpiry(ticket))
    }

    @Test
    fun replacementStandbyOwnerCannotBeExpiredByOlderTicket() {
        val gate = Fold7StandbyRouteLease()
        val oldTicket = gate.retain(owner(cycle = 9L, generation = 66L))
        val newer = owner(cycle = 10L, generation = 71L)
        val newTicket = gate.retain(newer)

        assertFalse(gate.consumeExpiry(oldTicket))
        assertEquals(newer, gate.owner())
        assertTrue(gate.consumeExpiry(newTicket))
        assertNull(gate.owner())
    }

    @Test
    fun repeatedCancelInvalidatesEveryEarlierTicket() {
        val gate = Fold7StandbyRouteLease()
        val ticket = gate.retain(owner(cycle = 4L, generation = 20L))

        gate.cancel()
        gate.cancel()

        assertFalse(gate.isCurrent(ticket))
        assertFalse(gate.consumeExpiry(ticket))
        assertNull(gate.owner())
    }
}
