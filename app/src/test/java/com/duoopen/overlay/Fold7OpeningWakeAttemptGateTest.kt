package com.duoopen.overlay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7OpeningWakeAttemptGateTest {
    @Test
    fun ordinaryInnerHandoffPreservesOpeningKey() {
        val gate = Fold7OpeningWakeAttemptGate(serviceEpoch = 7L)
        val opened =
            gate.onTransition(
                from = Fold7ContinuityController.State.NATIVE_COVER,
                to = Fold7ContinuityController.State.OPENING_FROM_CLOSED,
                generation = 10L,
            )
        assertNotNull(opened)

        val handoff =
            gate.onTransition(
                from = Fold7ContinuityController.State.OPENING_FROM_CLOSED,
                to = Fold7ContinuityController.State.INNER_HANDOFF,
                generation = 11L,
            )

        assertEquals(opened, handoff)
        assertTrue(gate.isCurrent(opened!!))
    }

    @Test
    fun reversalToNativeCoverRevokesOpening() {
        val gate = Fold7OpeningWakeAttemptGate(serviceEpoch = 7L)
        val opened =
            gate.onTransition(
                from = Fold7ContinuityController.State.NATIVE_COVER,
                to = Fold7ContinuityController.State.OPENING_FROM_CLOSED,
                generation = 10L,
            )!!

        gate.onTransition(
            from = Fold7ContinuityController.State.INNER_HANDOFF,
            to = Fold7ContinuityController.State.NATIVE_COVER,
            generation = 12L,
        )

        assertFalse(gate.isCurrent(opened))
        assertNull(gate.current())
    }

    @Test
    fun newOpeningCannotReuseOldOpeningKey() {
        val gate = Fold7OpeningWakeAttemptGate(serviceEpoch = 7L)
        val first =
            gate.onTransition(
                from = Fold7ContinuityController.State.NATIVE_COVER,
                to = Fold7ContinuityController.State.OPENING_FROM_CLOSED,
                generation = 10L,
            )!!

        gate.onTransition(
            from = Fold7ContinuityController.State.INNER_HANDOFF,
            to = Fold7ContinuityController.State.NATIVE_COVER,
            generation = 12L,
        )

        val second =
            gate.onTransition(
                from = Fold7ContinuityController.State.NATIVE_COVER,
                to = Fold7ContinuityController.State.OPENING_FROM_CLOSED,
                generation = 13L,
            )!!

        assertNotEquals(first.openingAttemptSequence, second.openingAttemptSequence)
        assertFalse(gate.isCurrent(first))
        assertTrue(gate.isCurrent(second))
    }

    @Test
    fun explicitLifecycleInvalidationRejectsDelayedWake() {
        val gate = Fold7OpeningWakeAttemptGate(serviceEpoch = 7L)
        val key =
            gate.onTransition(
                from = Fold7ContinuityController.State.NATIVE_COVER,
                to = Fold7ContinuityController.State.OPENING_FROM_CLOSED,
                generation = 10L,
            )!!

        gate.invalidate()

        assertFalse(gate.isCurrent(key))
        assertNull(gate.current())
    }
}
