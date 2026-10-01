package com.duoopen.overlay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7ContinuityControllerTest {
    private val openTopology =
        Fold7ContinuityController.Topology(
            innerLogicalId = 0,
            coverLogicalId = 1,
            innerActive = true,
            coverActive = true,
            innerIsDefault = true,
            coverIsDefault = false,
        )

    private val closedTopology =
        Fold7ContinuityController.Topology(
            innerLogicalId = null,
            coverLogicalId = 0,
            innerActive = false,
            coverActive = true,
            innerIsDefault = false,
            coverIsDefault = true,
        )

    @Test
    fun openJitterDoesNotPrewarm() {
        val c = Fold7ContinuityController()
        c.reset(179f, 0L, openTopology)

        c.onHinge(178.8f, 20L, openTopology)
        c.onHinge(179.1f, 40L, openTopology)
        c.onHinge(178.7f, 60L, openTopology)
        c.onHinge(178.9f, 80L, openTopology)

        assertEquals(
            Fold7ContinuityController.State.OPEN_INNER,
            c.state,
        )
    }

    @Test
    fun deliberateClosePrewarmsButStaysHiddenUntil135() {
        val c = Fold7ContinuityController()
        c.reset(179f, 0L, openTopology)

        c.onHinge(177.8f, 100L, openTopology)
        c.onHinge(176.3f, 150L, openTopology)
        c.onHinge(174.8f, 200L, openTopology)

        assertEquals(
            Fold7ContinuityController.State.CLOSING_INTENT,
            c.state,
        )

        val prewarm = c.onHinge(149f, 240L, openTopology)
        val request =
            prewarm.actions.single()
                as Fold7ContinuityController.Action.BeginPrewarm

        val ready =
            c.onPrewarmResult(
                requestGeneration = request.generation,
                ok = true,
                nowMs = 280L,
                topology = openTopology,
            )

        assertEquals(
            Fold7ContinuityController.State.COVER_READY_HIDDEN,
            c.state,
        )
        assertTrue(ready.actions.isEmpty())

        val visible = c.onHinge(134f, 320L, openTopology)

        assertEquals(
            Fold7ContinuityController.State.COVER_VISUAL,
            c.state,
        )
        assertTrue(
            visible.actions.any {
                it is Fold7ContinuityController.Action.ShowMirror
            }
        )
    }

    @Test
    fun openingFromClosedNeedsNoShellAction() {
        val c = Fold7ContinuityController()
        c.reset(0f, 0L, closedTopology)

        val firstMotion = c.onHinge(1f, 20L, closedTopology)

        assertEquals(
            Fold7ContinuityController.State.OPENING_FROM_CLOSED,
            c.state,
        )
        assertTrue(firstMotion.actions.isEmpty())
    }

    @Test
    fun reversalHidesMirrorAndReleasesSecondary() {
        val c = Fold7ContinuityController()
        c.reset(179f, 0L, openTopology)

        c.onHinge(176f, 50L, openTopology)
        val prewarm = c.onHinge(149f, 100L, openTopology)
        val request =
            prewarm.actions.single()
                as Fold7ContinuityController.Action.BeginPrewarm

        c.onPrewarmResult(
            requestGeneration = request.generation,
            ok = true,
            nowMs = 120L,
            topology = openTopology,
        )
        c.onHinge(134f, 150L, openTopology)

        val reversal = c.onHinge(141f, 200L, openTopology)

        assertEquals(
            Fold7ContinuityController.State.INNER_HANDOFF,
            c.state,
        )
        assertTrue(
            reversal.actions.any {
                it is Fold7ContinuityController.Action.HideMirror
            }
        )
        assertTrue(
            reversal.actions.any {
                it is Fold7ContinuityController.Action.ReleaseSecondary
            }
        )
    }

    @Test
    fun latePrewarmCompletionIsReleased() {
        val c = Fold7ContinuityController()
        c.reset(179f, 0L, openTopology)

        c.onHinge(176f, 50L, openTopology)
        val prewarm = c.onHinge(149f, 100L, openTopology)
        val request =
            prewarm.actions.single()
                as Fold7ContinuityController.Action.BeginPrewarm

        // Reverse before the shell response comes back.
        c.onHinge(151f, 130L, openTopology)

        val late =
            c.onPrewarmResult(
                requestGeneration = request.generation,
                ok = true,
                nowMs = 180L,
                topology = openTopology,
            )

        assertTrue(
            late.actions.any {
                it is Fold7ContinuityController.Action.ReleaseSecondary
            }
        )
    }
}
