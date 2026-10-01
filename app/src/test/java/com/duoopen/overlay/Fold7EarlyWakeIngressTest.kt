package com.duoopen.overlay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7EarlyWakeIngressTest {
    private fun List<Fold7EarlyWakeAction>.wakeCount() =
        count { it is Fold7EarlyWakeAction.WakeInner }

    private fun List<Fold7EarlyWakeAction>.burstCount() =
        count { it is Fold7EarlyWakeAction.KickPreciseBurst }

    @Test
    fun foldedToUnfoldedEdgeWakesExactlyOnce() {
        val model = Fold7EarlyWakeIngress()
        model.reset(nativeCover = true, preciseAngle = 0f, folded = true)
        val first = model.onFoldedState(false)
        val duplicate = model.onFoldedState(false)
        assertEquals(1, first.wakeCount())
        assertEquals(1, first.burstCount())
        assertTrue(duplicate.isEmpty())
        assertEquals(0f, model.authoritativeAngle)
    }

    @Test
    fun startupAlreadyUnfoldedDoesNotWake() {
        val model = Fold7EarlyWakeIngress()
        model.reset(nativeCover = true, preciseAngle = null, folded = null)
        assertTrue(model.onFoldedState(false).isEmpty())
    }

    @Test
    fun nonNativeCoverCannotOwnEarlyWake() {
        val model = Fold7EarlyWakeIngress()
        model.reset(nativeCover = false, preciseAngle = 0f, folded = true)
        assertTrue(model.onFoldedState(false).isEmpty())
    }

    @Test
    fun foldedReturnRearmsNextGeneration() {
        val model = Fold7EarlyWakeIngress()
        model.reset(nativeCover = true, preciseAngle = 0f, folded = true)
        assertEquals(1, model.onFoldedState(false).wakeCount())
        assertTrue(model.onFoldedState(true).isEmpty())
        assertEquals(1, model.onFoldedState(false).wakeCount())
    }

    @Test
    fun vendorEdgeDoesNotBecomeGeometry() {
        val model = Fold7EarlyWakeIngress()
        model.reset(nativeCover = true, preciseAngle = 0f, folded = true)
        model.onVendorAngle(0f)
        assertEquals(1, model.onVendorAngle(1f).wakeCount())
        assertEquals(0f, model.authoritativeAngle)
        model.onPreciseAngle(4f)
        assertEquals(4f, model.authoritativeAngle)
    }

    @Test
    fun preciseAngleRemainsFallback() {
        val model = Fold7EarlyWakeIngress()
        model.reset(nativeCover = true, preciseAngle = 0f, folded = true)
        assertTrue(model.onPreciseAngle(1f).isEmpty())
        assertEquals(1, model.onPreciseAngle(3.2f).wakeCount())
    }

    @Test
    fun latePreciseSampleCannotDuplicateEdgeWake() {
        val model = Fold7EarlyWakeIngress()
        model.reset(nativeCover = true, preciseAngle = 0f, folded = true)
        assertEquals(1, model.onFoldedState(false).wakeCount())
        assertTrue(model.onPreciseAngle(90f).isEmpty())
        assertEquals(90f, model.authoritativeAngle)
    }

    @Test
    fun topologyLossSuppressesStaleEdge() {
        val model = Fold7EarlyWakeIngress()
        model.reset(nativeCover = true, preciseAngle = 0f, folded = true)
        model.onTopology(nativeCover = false)
        assertTrue(model.onFoldedState(false).isEmpty())
    }
}
