package com.duoopen.overlay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7HallOpeningLatchV3Test {
    private val closedTopology =
        Fold7ContinuityController.Topology(
            innerLogicalId = null,
            coverLogicalId = 0,
            innerActive = false,
            coverActive = true,
            innerIsDefault = false,
            coverIsDefault = true,
        )

    private val innerTopology =
        Fold7ContinuityController.Topology(
            innerLogicalId = 0,
            coverLogicalId = null,
            innerActive = true,
            coverActive = false,
            innerIsDefault = true,
            coverIsDefault = false,
        )

    @Test
    fun acceptedHallOpeningSurvivesStaleNativeCoverTopologyAtZeroDegrees() {
        val c = Fold7ContinuityController()
        c.reset(0f, 0L, closedTopology)

        val edge =
            c.onEarlyOpeningEdge(
                nowMs = 5L,
                topology = closedTopology,
            )

        assertEquals(
            1,
            edge.actions.count {
                it is Fold7ContinuityController.Action.WakeInner
            },
        )
        assertEquals(
            Fold7ContinuityController.State.OPENING_FROM_CLOSED,
            c.state,
        )

        // This models the field regression: SW_LID has already opened, but
        // Samsung still reports native cover and 0 degrees for a while.
        c.onTopology(
            angle = 0f,
            nowMs = 50L,
            topology = closedTopology,
        )

        assertEquals(
            Fold7ContinuityController.State.OPENING_FROM_CLOSED,
            c.state,
        )
    }

    @Test
    fun innerTopologyCanCompleteHallLatchedOpening() {
        val c = Fold7ContinuityController()
        c.reset(0f, 0L, closedTopology)
        c.onEarlyOpeningEdge(5L, closedTopology)

        c.onTopology(
            angle = 0f,
            nowMs = 100L,
            topology = innerTopology,
        )

        assertEquals(
            Fold7ContinuityController.State.INNER_HANDOFF,
            c.state,
        )
    }

    @Test
    fun hallCloseAuthoritativelyCancelsLatchedOpening() {
        val c = Fold7ContinuityController()
        c.reset(0f, 0L, closedTopology)
        c.onEarlyOpeningEdge(5L, closedTopology)

        val closed =
            c.onEarlyClosingEdge(
                nowMs = 80L,
                topology = closedTopology,
            )

        assertEquals(
            Fold7ContinuityController.State.NATIVE_COVER,
            c.state,
        )
        assertTrue(closed.actions.isEmpty())
    }
}
