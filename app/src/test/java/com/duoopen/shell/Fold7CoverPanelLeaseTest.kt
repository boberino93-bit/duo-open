package com.duoopen.shell

import kotlin.random.Random
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7CoverPanelLeaseTest {
    private fun openInner(noRoute: Boolean = true, logicalId: Int = 7, physicalId: Long = 222L) =
        Fold7CoverPanelLease.Topology(
            nativeCover = false,
            innerIsDefault = true,
            coverSecondaryLogicalId = if (noRoute) null else logicalId,
            coverSecondaryPhysicalId = if (noRoute) null else physicalId,
        )

    private val nativeCover =
        Fold7CoverPanelLease.Topology(true, false, null, null)

    @Test
    fun physicalOnlyReversalRemainsPendingWithoutRoute() {
        val m = Fold7CoverPanelLease()
        val a = m.beginPrewarm(10).single() as Fold7CoverPanelLease.Action.PowerPhysicalCover
        m.onPhysicalPrewarmResult(a.leaseId, a.epoch, true, 222L, openInner())
        assertTrue(m.requestRelease(10, "reversal", openInner()).isEmpty())
        assertEquals(Fold7CoverPanelLease.State.RELEASE_PENDING, m.snapshot().state)
    }

    @Test
    fun matchingFreshRouteResetsThenClearsLease() {
        val m = Fold7CoverPanelLease()
        val a = m.beginPrewarm(1).single() as Fold7CoverPanelLease.Action.PowerPhysicalCover
        m.onPhysicalPrewarmResult(a.leaseId, a.epoch, true, 222L, openInner())
        m.requestRelease(1, "reverse", openInner())
        val reset = m.onTopology(openInner(false)).single() as Fold7CoverPanelLease.Action.ResetLogicalCoverPower
        m.onLogicalResetResult(reset.leaseId, reset.epoch, reset.logicalId, true)
        assertEquals(Fold7CoverPanelLease.State.IDLE, m.snapshot().state)
    }

    @Test
    fun mismatchedPhysicalRouteIsNeverReset() {
        val m = Fold7CoverPanelLease()
        val a = m.beginPrewarm(2).single() as Fold7CoverPanelLease.Action.PowerPhysicalCover
        m.onPhysicalPrewarmResult(a.leaseId, a.epoch, true, 222L, openInner())
        m.requestRelease(2, "reverse", openInner())
        assertTrue(m.onTopology(Fold7CoverPanelLease.Topology(false, true, 7, 333L)).isEmpty())
        assertEquals(Fold7CoverPanelLease.State.RELEASE_PENDING, m.snapshot().state)
    }

    @Test
    fun nativeCoverRelinquishesWithoutRawOff() {
        val m = Fold7CoverPanelLease()
        val a = m.beginPrewarm(3).single() as Fold7CoverPanelLease.Action.PowerPhysicalCover
        m.onPhysicalPrewarmResult(a.leaseId, a.epoch, true, 222L, openInner())
        assertTrue(m.requestRelease(3, "native", nativeCover).isEmpty())
        assertEquals(Fold7CoverPanelLease.State.IDLE, m.snapshot().state)
    }

    @Test
    fun newCloseAdoptsPendingLeaseAndInvalidatesLateReset() {
        val m = Fold7CoverPanelLease()
        val a = m.beginPrewarm(4).single() as Fold7CoverPanelLease.Action.PowerPhysicalCover
        m.onPhysicalPrewarmResult(a.leaseId, a.epoch, true, 222L, openInner())
        m.requestRelease(4, "reverse", openInner())
        val reset = m.onTopology(openInner(false)).single() as Fold7CoverPanelLease.Action.ResetLogicalCoverPower
        assertTrue(m.beginPrewarm(5).isEmpty())
        m.onLogicalResetResult(reset.leaseId, reset.epoch, reset.logicalId, true)
        assertEquals(Fold7CoverPanelLease.State.HELD, m.snapshot().state)
        assertEquals(5L, m.snapshot().ownerGeneration)
    }

    @Test
    fun fixedSeedHundredThousandOperationFuzzMaintainsCoreInvariants() {
        val random = Random(0xD00F7)
        val m = Fold7CoverPanelLease()
        var generation = 1L
        repeat(100_000) {
            val topology = when (random.nextInt(4)) {
                0 -> openInner()
                1 -> openInner(false)
                2 -> nativeCover
                else -> Fold7CoverPanelLease.Topology(false, false, 7, 222L)
            }
            when (random.nextInt(6)) {
                0 -> m.beginPrewarm(generation++)
                1 -> {
                    val s = m.snapshot()
                    if (s.ownerGeneration >= 0L) m.requestRelease(s.ownerGeneration, "fuzz", topology)
                }
                2 -> m.onTopology(topology)
                3 -> {
                    val s = m.snapshot()
                    m.onPhysicalPrewarmResult(s.leaseId, s.epoch, random.nextBoolean(), 222L, topology)
                }
                4 -> {
                    val s = m.snapshot()
                    m.onLogicalResetResult(s.leaseId, s.epoch, 7, random.nextBoolean())
                }
                else -> Unit
            }
            val s = m.snapshot()
            if (s.state == Fold7CoverPanelLease.State.IDLE) {
                assertEquals(-1L, s.ownerGeneration)
                assertEquals(null, s.physicalId)
                assertEquals(null, s.pendingReleaseReason)
            }
            assertTrue(s.leaseId >= 0L)
            assertTrue(s.epoch >= 0L)
        }
    }
}
