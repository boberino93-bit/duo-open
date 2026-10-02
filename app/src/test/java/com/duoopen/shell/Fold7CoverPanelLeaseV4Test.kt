package com.duoopen.shell

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7CoverPanelLeaseV4Test {
    private val openInner =
        Fold7CoverPanelLease.Topology(
            nativeCover = false,
            innerIsDefault = true,
            coverSecondaryLogicalId = null,
            coverSecondaryPhysicalId = null,
        )

    private fun owner(cycle: Long, generation: Long) =
        Fold7CoverPanelLease.OwnerIdentity(
            serviceEpoch = 77L,
            closeCycleId = cycle,
            transitionGeneration = generation,
        )

    private fun acquireHeld(
        model: Fold7CoverPanelLease,
        owner: Fold7CoverPanelLease.OwnerIdentity,
    ): Fold7CoverPanelLease.Snapshot {
        val start =
            model.beginPrewarmV4(
                newOwner = owner,
                expectedLeaseId = 0L,
                expectedEpoch = 0L,
                expectedOwnerServiceEpoch = -1L,
                expectedOwnerCloseCycleId = -1L,
                expectedOwnerGeneration = -1L,
            )
        assertTrue(start.accepted)
        val action =
            start.actions.single() as
                Fold7CoverPanelLease.Action.PowerPhysicalCover
        model.onPhysicalPrewarmResult(
            action.leaseId,
            action.epoch,
            true,
            222L,
            openInner,
        )
        return model.snapshot()
    }

    private fun adopt(
        model: Fold7CoverPanelLease,
        newOwner: Fold7CoverPanelLease.OwnerIdentity,
        expected: Fold7CoverPanelLease.Snapshot,
    ) =
        model.beginPrewarmV4(
            newOwner = newOwner,
            expectedLeaseId = expected.leaseId,
            expectedEpoch = expected.epoch,
            expectedOwnerServiceEpoch = expected.ownerServiceEpoch,
            expectedOwnerCloseCycleId = expected.ownerCloseCycleId,
            expectedOwnerGeneration = expected.ownerGeneration,
        )

    @Test
    fun tokenlessHeldAdoptionIsRejectedAndInert() {
        val m = Fold7CoverPanelLease()
        acquireHeld(m, owner(1, 10))
        val before = m.snapshot()

        val result =
            m.beginPrewarmV4(
                newOwner = owner(2, 20),
                expectedLeaseId = 0L,
                expectedEpoch = 0L,
                expectedOwnerServiceEpoch = -1L,
                expectedOwnerCloseCycleId = -1L,
                expectedOwnerGeneration = -1L,
            )

        assertFalse(result.accepted)
        assertTrue(result.stale)
        assertEquals(before, m.snapshot())
    }

    @Test
    fun delayedOldPrewarmCannotStealNewerExactAdoption() {
        val m = Fold7CoverPanelLease()
        val old = acquireHeld(m, owner(1, 10))
        val newer = adopt(m, owner(2, 20), old)
        assertTrue(newer.accepted)
        val afterNew = m.snapshot()

        val stale = adopt(m, owner(1, 10), old)

        assertFalse(stale.accepted)
        assertTrue(stale.stale)
        assertEquals(afterNew, m.snapshot())
        assertEquals(20L, m.snapshot().ownerGeneration)
        assertEquals(2L, m.snapshot().ownerCloseCycleId)
    }

    @Test
    fun sameOwnerExactRetryIsIdempotent() {
        val m = Fold7CoverPanelLease()
        val held = acquireHeld(m, owner(1, 10))
        val before = m.snapshot()
        val retry = adopt(m, owner(1, 10), held)

        assertTrue(retry.accepted)
        assertEquals("idempotent-retry", retry.reason)
        assertEquals(before, m.snapshot())
    }

    @Test
    fun releasePendingCanBeReadoptedOnlyByExactCurrentToken() {
        val m = Fold7CoverPanelLease()
        acquireHeld(m, owner(1, 10))
        m.requestRelease(10, "reverse", openInner)
        val pending = m.snapshot()

        val adopted = adopt(m, owner(2, 20), pending)

        assertTrue(adopted.accepted)
        assertEquals(Fold7CoverPanelLease.State.HELD, m.snapshot().state)
        assertEquals(20L, m.snapshot().ownerGeneration)

        val stale = adopt(m, owner(3, 30), pending)
        assertFalse(stale.accepted)
        assertEquals(20L, m.snapshot().ownerGeneration)
    }

    @Test
    fun crossServiceOldTokenCannotRegainAuthority() {
        val m = Fold7CoverPanelLease()
        val first = acquireHeld(m, owner(1, 10))

        val nextServiceOwner =
            Fold7CoverPanelLease.OwnerIdentity(
                serviceEpoch = 88L,
                closeCycleId = 1L,
                transitionGeneration = 1L,
            )

        val adopted = adopt(m, nextServiceOwner, first)
        assertTrue(adopted.accepted)
        val after = m.snapshot()

        val stale = adopt(m, owner(1, 10), first)
        assertFalse(stale.accepted)
        assertEquals(after, m.snapshot())
    }
}
