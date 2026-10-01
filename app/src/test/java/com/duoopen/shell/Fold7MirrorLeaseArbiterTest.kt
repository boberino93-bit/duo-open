package com.duoopen.shell

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7MirrorLeaseArbiterTest {
    @Test
    fun staleStopCannotKillNewerLease() {
        val a = Fold7MirrorLeaseArbiter()
        val session = a.openSession().session
        val first = a.reserveStart(session, 1, 101, 10)!!
        assertTrue(a.commitStart(first).accepted)
        val newer = a.reserveStart(session, 3, 303, 11)!!
        assertTrue(a.commitStart(newer).accepted)
        assertFalse(a.stop(session, 2, 101).accepted)
        assertEquals(303L, a.snapshot().currentLeaseId)
    }

    @Test
    fun laterStopFromOldLeaseCannotKillCurrentLease() {
        val a = Fold7MirrorLeaseArbiter()
        val session = a.openSession().session
        a.reserveStart(session, 1, 101, 10)!!.also { a.commitStart(it) }
        a.reserveStart(session, 2, 202, 11)!!.also { a.commitStart(it) }
        val stop = a.stop(session, 3, 101)
        assertTrue(stop.accepted)
        assertFalse(stop.releaseCurrent)
        assertEquals("lease-mismatch", stop.reason)
        assertEquals(202L, a.snapshot().currentLeaseId)
    }

    @Test
    fun failedNewerStartPreservesCurrentLeaseAndFencesOlderIntent() {
        val a = Fold7MirrorLeaseArbiter()
        val session = a.openSession().session
        a.reserveStart(session, 1, 101, 10)!!.also { a.commitStart(it) }
        val failed = a.reserveStart(session, 3, 303, 12)!!
        assertTrue(a.failStart(failed))
        assertEquals(101L, a.snapshot().currentLeaseId)
        assertNull(a.reserveStart(session, 2, 202, 11))
    }

    @Test
    fun sessionRolloverInvalidatesOldCommands() {
        val a = Fold7MirrorLeaseArbiter()
        val old = a.openSession().session
        val ticket = a.reserveStart(old, 1, 101, 10)!!
        val fresh = a.openSession().session
        assertFalse(a.commitStart(ticket).accepted)
        assertFalse(a.stop(old, 99, 101).accepted)
        assertTrue(fresh > old)
        assertNull(a.snapshot().currentLeaseId)
    }

    @Test
    fun forceStopIsSessionAndSequenceScoped() {
        val a = Fold7MirrorLeaseArbiter()
        val session = a.openSession().session
        a.reserveStart(session, 1, 101, 10)!!.also { a.commitStart(it) }
        assertFalse(a.forceStop(session + 1, 2).accepted)
        val stop = a.forceStop(session, 2)
        assertTrue(stop.releaseCurrent)
        assertNull(a.snapshot().currentLeaseId)
    }

    private sealed interface Command { val seq: Long
        data class Start(override val seq: Long) : Command
        data class Stop(override val seq: Long) : Command
    }

    private fun <T> permutations(items: List<T>): List<List<T>> {
        if (items.size <= 1) return listOf(items)
        val out = mutableListOf<List<T>>()
        for (i in items.indices) {
            val rest = items.toMutableList()
            val head = rest.removeAt(i)
            permutations(rest).forEach { out += listOf(head) + it }
        }
        return out
    }

    @Test
    fun allFiveCommandPermutationsConvergeOnHighestStart() {
        val commands = listOf(
            Command.Start(1), Command.Stop(2), Command.Start(3),
            Command.Stop(4), Command.Start(5),
        )
        val orders = permutations(commands)
        assertEquals(120, orders.size)
        for (order in orders) {
            val a = Fold7MirrorLeaseArbiter()
            val session = a.openSession().session
            for (command in order) {
                when (command) {
                    is Command.Start -> {
                        val ticket = a.reserveStart(session, command.seq, command.seq, 10)
                        if (ticket != null) a.commitStart(ticket)
                    }
                    is Command.Stop -> a.stop(session, command.seq, command.seq - 1)
                }
            }
            assertEquals(5L, a.snapshot().lastSequence)
            assertEquals(5L, a.snapshot().currentLeaseId)
        }
    }
}
