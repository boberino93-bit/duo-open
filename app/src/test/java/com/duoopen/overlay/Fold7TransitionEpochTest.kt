package com.duoopen.overlay

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7TransitionEpochTest {
    @Test
    fun invalidationRejectsInFlightEpoch() {
        val gate = Fold7TransitionEpoch()
        val first = gate.begin()

        assertTrue(gate.owns(first))

        gate.invalidate()

        assertFalse(gate.owns(first))
    }

    @Test
    fun newerTransitionSupersedesOlderTransition() {
        val gate = Fold7TransitionEpoch()
        val first = gate.begin()
        val second = gate.begin()

        assertFalse(gate.owns(first))
        assertTrue(gate.owns(second))
    }
}
