package com.duoopen.overlay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7OpeningCommitHoldV3Test {
    private val nativeCover =
        Fold7ContinuityController.Topology(
            innerLogicalId = null,
            coverLogicalId = 0,
            innerActive = false,
            coverActive = true,
            innerIsDefault = false,
            coverIsDefault = true,
        )

    @Test
    fun hallOpeningCommitSurvivesTransientNativeCoverTopology() {
        val controller = Fold7ContinuityController()
        controller.reset(angle = 0f, nowMs = 1_000L, topology = nativeCover)

        val opening =
            controller.onEarlyOpeningEdge(
                nowMs = 1_010L,
                topology = nativeCover,
            )

        assertEquals(Fold7ContinuityController.State.OPENING_FROM_CLOSED, opening.state)
        assertTrue(opening.actions.any { it is Fold7ContinuityController.Action.WakeInner })
        val openingGeneration = opening.generation

        val transientCover =
            controller.onTopology(
                angle = 0f,
                nowMs = 1_100L,
                topology = nativeCover,
            )

        assertEquals(Fold7ContinuityController.State.OPENING_FROM_CLOSED, transientCover.state)
        assertEquals(openingGeneration, transientCover.generation)

        // DeviceState confirmation of the same physical opening must not create
        // a second wake attempt while the Hall-committed opening remains active.
        val duplicateEdge =
            controller.onEarlyOpeningEdge(
                nowMs = 1_180L,
                topology = nativeCover,
            )

        assertEquals(Fold7ContinuityController.State.OPENING_FROM_CLOSED, duplicateEdge.state)
        assertEquals(openingGeneration, duplicateEdge.generation)
        assertTrue(duplicateEdge.actions.none { it is Fold7ContinuityController.Action.WakeInner })
    }

    @Test
    fun nativeCoverCanReclaimAfterBoundedHoldExpires() {
        val controller = Fold7ContinuityController()
        controller.reset(angle = 0f, nowMs = 2_000L, topology = nativeCover)
        controller.onEarlyOpeningEdge(nowMs = 2_010L, topology = nativeCover)

        val afterExpiry =
            controller.onTopology(
                angle = 0f,
                nowMs = 2_010L + Fold7ContinuityController.OPENING_COMMIT_HOLD_MS + 1L,
                topology = nativeCover,
            )

        assertEquals(Fold7ContinuityController.State.NATIVE_COVER, afterExpiry.state)
    }
}
