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
    fun deliberateClosePrewarmsEarlyButStaysHiddenUntil135() {
        val c = Fold7ContinuityController()
        c.reset(179f, 0L, openTopology)

        c.onHinge(177.8f, 100L, openTopology)
        c.onHinge(176.3f, 150L, openTopology)
        c.onHinge(174.8f, 200L, openTopology)

        assertEquals(
            Fold7ContinuityController.State.CLOSING_INTENT,
            c.state,
        )

        val prewarm =
            c.onHinge(
                173.8f,
                220L,
                openTopology,
            )

        val request =
            prewarm.actions.single()
                as Fold7ContinuityController.Action.BeginPrewarm

        val ready =
            c.onPrewarmResult(
                requestGeneration = request.generation,
                ok = true,
                nowMs = 250L,
                topology = openTopology,
            )

        assertEquals(
            Fold7ContinuityController.State.COVER_READY_HIDDEN,
            c.state,
        )
        assertTrue(ready.actions.isEmpty())

        val visible =
            c.onHinge(
                134f,
                320L,
                openTopology,
            )

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
    fun deviceStateOpeningEdgeWakesBeforePreciseAngle() {
        val c =
            Fold7ContinuityController()

        c.reset(
            0f,
            0L,
            closedTopology,
        )

        val edge =
            c.onEarlyOpeningEdge(
                nowMs = 5L,
                topology = closedTopology,
            )

        assertEquals(
            Fold7ContinuityController.State.OPENING_FROM_CLOSED,
            c.state,
        )

        assertEquals(
            1,
            edge.actions.count {
                it is Fold7ContinuityController.Action.WakeInner
            },
        )

        val duplicate =
            c.onEarlyOpeningEdge(
                nowMs = 10L,
                topology = closedTopology,
            )

        assertTrue(
            duplicate.actions.isEmpty()
        )
    }

    @Test
    fun deviceStateOpeningEdgeIsIgnoredWhenNotNativeCover() {
        val c =
            Fold7ContinuityController()

        c.reset(
            179f,
            0L,
            openTopology,
        )

        val edge =
            c.onEarlyOpeningEdge(
                nowMs = 5L,
                topology = openTopology,
            )

        assertEquals(
            Fold7ContinuityController.State.OPEN_INNER,
            c.state,
        )

        assertTrue(
            edge.actions.isEmpty()
        )
    }

    @Test
    fun openingFromClosedWakesInnerAtThreeDegrees() {
        val c = Fold7ContinuityController()
        c.reset(0f, 0L, closedTopology)

        val tiny =
            c.onHinge(
                1f,
                20L,
                closedTopology,
            )

        assertEquals(
            Fold7ContinuityController.State.NATIVE_COVER,
            c.state,
        )
        assertTrue(tiny.actions.isEmpty())

        val firstRealMotion =
            c.onHinge(
                3.2f,
                40L,
                closedTopology,
            )

        assertEquals(
            Fold7ContinuityController.State.OPENING_FROM_CLOSED,
            c.state,
        )
        assertTrue(
            firstRealMotion.actions.any {
                it is Fold7ContinuityController.Action.WakeInner
            }
        )
    }

    @Test
    fun openingFallsIntoInnerHandoffByEightDegrees() {
        val c = Fold7ContinuityController()
        c.reset(0f, 0L, closedTopology)

        c.onHinge(3.2f, 20L, closedTopology)

        val handoff =
            c.onHinge(
                8.2f,
                40L,
                closedTopology,
            )

        assertEquals(
            Fold7ContinuityController.State.INNER_HANDOFF,
            c.state,
        )
        assertTrue(handoff.actions.isEmpty())
    }

    @Test
    fun fastFirstOpeningSampleWakesInnerExactlyOnce() {
        val c = Fold7ContinuityController()
        c.reset(0f, 0L, closedTopology)

        val jump =
            c.onHinge(
                15f,
                20L,
                closedTopology,
            )

        assertEquals(
            Fold7ContinuityController.State.OPENING_FROM_CLOSED,
            c.state,
        )
        assertEquals(
            1,
            jump.actions.count {
                it is Fold7ContinuityController.Action.WakeInner
            },
        )

        val next =
            c.onHinge(
                15.5f,
                40L,
                closedTopology,
            )

        assertEquals(
            Fold7ContinuityController.State.INNER_HANDOFF,
            c.state,
        )
        assertTrue(
            next.actions.none {
                it is Fold7ContinuityController.Action.WakeInner
            }
        )
    }

    @Test
    fun steadySampleDuringEarlyOpeningDoesNotFallBackToNativeCover() {
        val c = Fold7ContinuityController()
        c.reset(0f, 0L, closedTopology)

        c.onHinge(3.2f, 20L, closedTopology)
        c.onHinge(8.2f, 40L, closedTopology)

        val steady =
            c.onHinge(
                8.3f,
                60L,
                closedTopology,
            )

        assertEquals(
            Fold7ContinuityController.State.INNER_HANDOFF,
            c.state,
        )
        assertTrue(steady.actions.isEmpty())
    }

    @Test
    fun reversingEarlyOpeningReturnsToNativeCover() {
        val c = Fold7ContinuityController()
        c.reset(0f, 0L, closedTopology)

        c.onHinge(3.2f, 20L, closedTopology)
        c.onHinge(8.2f, 40L, closedTopology)

        c.onHinge(
            7.0f,
            60L,
            closedTopology,
        )

        assertEquals(
            Fold7ContinuityController.State.NATIVE_COVER,
            c.state,
        )
    }

    @Test
    fun reversalHidesMirrorAndReleasesSecondary() {
        val c = Fold7ContinuityController()
        c.reset(179f, 0L, openTopology)

        c.onHinge(176f, 50L, openTopology)
        val prewarm =
            c.onHinge(
                149f,
                100L,
                openTopology,
            )
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

        val reversal =
            c.onHinge(
                141f,
                200L,
                openTopology,
            )

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
    fun latePrewarmCompletionCannotReleaseCurrentGenerationRoute() {
        val c = Fold7ContinuityController()
        c.reset(179f, 0L, openTopology)

        c.onHinge(176f, 50L, openTopology)
        val prewarm =
            c.onHinge(
                149f,
                100L,
                openTopology,
            )
        val request =
            prewarm.actions.single()
                as Fold7ContinuityController.Action.BeginPrewarm

        c.onHinge(151f, 130L, openTopology)

        assertTrue(request.generation != c.generation)
        assertEquals(
            Fold7ContinuityController.State.INNER_HANDOFF,
            c.state,
        )

        val late =
            c.onPrewarmResult(
                requestGeneration = request.generation,
                ok = true,
                nowMs = 180L,
                topology = openTopology,
            )

        assertTrue(
            late.actions.none {
                it is Fold7ContinuityController.Action.ReleaseSecondary
            }
        )
        assertEquals(
            Fold7ContinuityController.State.INNER_HANDOFF,
            c.state,
        )
    }
}
