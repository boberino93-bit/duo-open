package com.duoopen.shell

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7AnglePipelineGen2Test {
    @Test
    fun onlyOnePollMayBeInFlight() {
        val pipeline = Fold7AnglePipelineGen2()
        pipeline.startSession()
        assertNotNull(pipeline.tryStartPoll(1L))
        assertNull(pipeline.tryStartPoll(2L))
    }

    @Test
    fun completionPacingMaintainsEightMsTarget() {
        val pipeline = Fold7AnglePipelineGen2()
        pipeline.startSession()
        val poll = pipeline.tryStartPoll(100L)!!
        assertEquals(5L, pipeline.completePoll(poll, 103L))
    }

    @Test
    fun overBudgetCompletionYieldsInsteadOfCatchUpBurst() {
        val pipeline = Fold7AnglePipelineGen2()
        pipeline.startSession()
        val poll = pipeline.tryStartPoll(100L)!!
        assertEquals(1L, pipeline.completePoll(poll, 112L))
    }

    @Test
    fun oldSessionSampleAndCompletionAreRejected() {
        val pipeline = Fold7AnglePipelineGen2()
        pipeline.startSession()
        val oldPoll = pipeline.tryStartPoll(100L)!!
        pipeline.invalidateSession()
        assertNull(pipeline.nextSample(oldPoll, 10f))
        assertNull(pipeline.completePoll(oldPoll, 103L))
    }

    @Test
    fun invalidAnglesAreRejected() {
        val pipeline = Fold7AnglePipelineGen2()
        pipeline.startSession()
        val poll = pipeline.tryStartPoll(1L)!!
        assertNull(pipeline.nextSample(poll, Float.NaN))
        assertNull(pipeline.nextSample(poll, 181f))
    }

    @Test
    fun latestOnlyPresentationCoalescesBurst() {
        val pipeline = Fold7AnglePipelineGen2()
        pipeline.startSession()

        val firstPoll = pipeline.tryStartPoll(1L)!!
        val first = pipeline.nextSample(firstPoll, 2f)!!
        assertTrue(pipeline.offerPresentation(first))
        pipeline.completePoll(firstPoll, 2L)

        val secondPoll = pipeline.tryStartPoll(8L)!!
        val second = pipeline.nextSample(secondPoll, 6f)!!
        assertFalse(pipeline.offerPresentation(second))
        assertEquals(6f, pipeline.consumePresentation()!!.angle)
    }
}
