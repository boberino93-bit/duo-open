package com.duoopen.overlay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7HingeIngressBatchTest {
    @Test
    fun preservesOrderAndObservationTimes() {
        val q = Fold7HingeIngressBatch(8)
        assertTrue(q.offer(130f, 100L))
        assertFalse(q.offer(135f, 110L))
        assertFalse(q.offer(128f, 120L))

        val d = q.drain()
        assertFalse(d.overflowed)
        assertEquals(listOf(130f, 135f, 128f), d.samples.map { it.angle })
        assertEquals(listOf(100L, 110L, 120L), d.samples.map { it.observedUptimeMs })
        assertEquals(listOf(1L, 2L, 3L), d.samples.map { it.sequence })
    }

    @Test
    fun overflowIsExplicitAndBounded() {
        val q = Fold7HingeIngressBatch(4)
        q.offer(140f, 10L)
        q.offer(135f, 20L)
        q.offer(130f, 30L)
        q.offer(125f, 40L)
        q.offer(145f, 50L)
        q.offer(128f, 60L)

        val d = q.drain()
        assertTrue(d.overflowed)
        assertEquals(2, d.droppedSamples)
        assertEquals(listOf(130f, 125f, 145f, 128f), d.samples.map { it.angle })
    }
}
