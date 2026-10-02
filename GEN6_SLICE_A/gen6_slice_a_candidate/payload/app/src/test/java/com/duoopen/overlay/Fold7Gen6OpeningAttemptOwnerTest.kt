package com.duoopen.overlay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertNotNull
import org.junit.Test

class Fold7Gen6OpeningAttemptOwnerTest {
    @Test
    fun zeroToOneCreatesAttemptWithoutGeometryAuthority() {
        val owner = Fold7Gen6OpeningAttemptOwner(serviceEpoch = 9L)
        val attempt = owner.onWakeHint(0, 1, 100L)
        assertNotNull(attempt)
        assertEquals(1L, attempt!!.id)
        assertEquals(9L, attempt.serviceEpoch)
        assertEquals(0, attempt.previousStateId)
        assertEquals(1, attempt.currentStateId)
        assertNull(attempt.semanticGeneration)
    }

    @Test
    fun zeroToTwoAlsoCreatesAttempt() {
        val owner = Fold7Gen6OpeningAttemptOwner(1L)
        assertNotNull(owner.onWakeHint(0, 2, 100L))
    }

    @Test
    fun duplicateHintCannotCreateSecondActiveAttempt() {
        val owner = Fold7Gen6OpeningAttemptOwner(1L)
        val first = owner.onWakeHint(0, 1, 100L)
        assertNotNull(first)
        assertNull(owner.onWakeHint(0, 2, 101L))
        assertEquals(first, owner.current())
    }

    @Test
    fun semanticGenerationIsAttachedButDoesNotStartAttempt() {
        val owner = Fold7Gen6OpeningAttemptOwner(1L)
        assertNull(owner.markSemanticAccepted(44L))
        owner.onWakeHint(0, 1, 100L)
        val updated = owner.markSemanticAccepted(44L)
        assertEquals(44L, updated!!.semanticGeneration)
    }

    @Test
    fun returnedClosedFinishesAndRearmsNextAttemptId() {
        val owner = Fold7Gen6OpeningAttemptOwner(1L)
        owner.onWakeHint(0, 1, 100L)
        val terminal = owner.finish("corroborated-closed", 120L)
        assertEquals(1L, terminal!!.attempt.id)
        assertNull(owner.current())
        assertEquals(2L, owner.onWakeHint(0, 1, 200L)!!.id)
    }
}
