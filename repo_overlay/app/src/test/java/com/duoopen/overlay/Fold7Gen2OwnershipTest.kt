package com.duoopen.overlay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7Gen2OwnershipTest {
    @Test
    fun closeCycle_stableUntilInvalidated() {
        val e = Fold7CycleEnvelope(99L)
        val a = e.beginClose(100L)
        val b = e.beginClose(120L)
        assertEquals(a, b)
        assertTrue(e.isCurrent(99L, a.closeCycleId))
        e.invalidateClose(a.closeCycleId)
        assertFalse(e.isCurrent(99L, a.closeCycleId))
        val c = e.beginClose(200L)
        assertTrue(c.closeCycleId > a.closeCycleId)
    }

    @Test
    fun leaseGate_rejectsOldConnectionAndRevision() {
        val gate = Fold7CoverLeaseSnapshotGate()
        gate.onConnectionEpoch(4L)
        val good = leaseSnapshot(connection = 4L, session = 10L, revision = 1L)
        assertTrue(gate.accept(good).accepted)
        assertFalse(gate.accept(good.copy(shellRevision = 1L)).accepted)
        assertFalse(gate.accept(good.copy(connectionEpoch = 3L, shellRevision = 2L)).accepted)
        assertTrue(gate.accept(good.copy(shellRevision = 2L, leaseEpoch = 2L)).accepted)
    }

    @Test
    fun leaseGate_newShellSessionInvalidatesOldAuthority() {
        val gate = Fold7CoverLeaseSnapshotGate()
        gate.onConnectionEpoch(1L)
        val first = gate.accept(leaseSnapshot(connection = 1L, session = 7L, revision = 9L))
        val oldToken = first.token!!
        assertTrue(gate.ownsExactly(oldToken))

        val second = gate.accept(leaseSnapshot(connection = 1L, session = 8L, revision = 1L))
        assertTrue(second.accepted)
        assertFalse(gate.ownsExactly(oldToken))
    }

    @Test
    fun readiness_requiresExactDemandAndObservedRoute() {
        val token = leaseSnapshot(1L, 2L, 1L).token!!
        val readiness = Fold7CoverReadiness()
        val demand = Fold7CoverReadiness.Demand(
            serviceEpoch = 50L,
            closeCycleId = 3L,
            transitionGeneration = 11L,
            leaseToken = token,
            expectedLogicalId = 6,
        )
        readiness.begin(demand, shellRouteReady = true)

        assertFalse(
            readiness.observe(
                50L,
                3L,
                Fold7CoverReadiness.Topology(
                    innerActive = true,
                    coverActive = true,
                    innerIsDefault = true,
                    coverIsDefault = false,
                    coverLogicalId = 5,
                ),
            ).becameReady,
        )

        assertTrue(
            readiness.observe(
                50L,
                3L,
                Fold7CoverReadiness.Topology(
                    innerActive = true,
                    coverActive = true,
                    innerIsDefault = true,
                    coverIsDefault = false,
                    coverLogicalId = 6,
                ),
            ).becameReady,
        )
    }

    @Test
    fun frameStore_neverReplaysPriorCycle() {
        val envelope = Fold7CycleEnvelope(9L)
        val store = Fold7ContinuityFrameStore<String>()
        val first = envelope.beginClose(100L)
        store.beginCycle(first)
        val ticket = store.beginCapture(
            first,
            width = 1968,
            height = 2184,
            requestStartedUptimeMs = 110L,
            source = Fold7ContinuityFrameStore.Source.SHIZUKU,
        )!!
        assertNotNull(
            store.publish(
                ticket,
                capturedUptimeMs = 120L,
                completedUptimeMs = 130L,
                timestampQuality = Fold7ContinuityFrameStore.TimestampQuality.REQUEST_BOUNDED,
                payload = "cycle-1",
            ),
        )

        envelope.invalidateClose(first.closeCycleId)
        store.invalidateCycle(first.serviceEpoch, first.closeCycleId)
        val second = envelope.beginClose(200L)
        store.beginCycle(second)

        assertNull(store.current(second, 210L, 10_000L, 1968, 2184))
    }

    @Test
    fun frameStore_requestBoundedRejectsPreCycleButExactCaptureMayProveCurrentCycle() {
        val envelope = Fold7CycleEnvelope(9L)
        val store = Fold7ContinuityFrameStore<String>()
        val cycle = envelope.beginClose(100L)
        store.beginCycle(cycle)

        val shizuku =
            store.beginCapture(
                cycle,
                1968,
                2184,
                requestStartedUptimeMs = 99L,
                source = Fold7ContinuityFrameStore.Source.SHIZUKU,
            )!!
        assertNull(
            store.publish(
                shizuku,
                capturedUptimeMs = 101L,
                completedUptimeMs = 102L,
                timestampQuality = Fold7ContinuityFrameStore.TimestampQuality.REQUEST_BOUNDED,
                payload = "pre-cycle-shizuku",
            ),
        )

        val accessibility =
            store.beginCapture(
                cycle,
                1968,
                2184,
                requestStartedUptimeMs = 99L,
                source = Fold7ContinuityFrameStore.Source.ACCESSIBILITY,
            )!!
        assertNotNull(
            store.publish(
                accessibility,
                capturedUptimeMs = 101L,
                completedUptimeMs = 103L,
                timestampQuality = Fold7ContinuityFrameStore.TimestampQuality.EXACT_CAPTURE,
                payload = "exact-current-cycle",
            ),
        )
    }

    @Test
    fun presentationLease_rejectsLateOldAttempt() {
        val p = Fold7PresentationLease()
        p.openHost()
        val old = p.begin(1L, 4L, 10L, Fold7PresentationLease.RenderPath.FROZEN_VIEW)
        val current = p.begin(1L, 4L, 11L, Fold7PresentationLease.RenderPath.FROZEN_VIEW)
        assertFalse(p.onPresented(old))
        assertTrue(p.onDraw(current))
        assertTrue(p.onFrameCommit(current))
        assertTrue(p.onPresented(current))
        assertTrue(p.snapshot()!!.presented)
    }

    @Test
    fun presentationLease_attemptInvalidationMakesCallbacksInertWithoutClosingHost() {
        val p = Fold7PresentationLease()
        p.openHost()
        val old = p.begin(1L, 2L, 3L, Fold7PresentationLease.RenderPath.FROZEN_VIEW)
        p.invalidateAttempt(old)
        assertFalse(p.onFrameCommit(old))
        val next = p.begin(1L, 2L, 4L, Fold7PresentationLease.RenderPath.LIVE_MIRROR)
        assertTrue(p.onTransactionCommit(next))
    }

    @Test
    fun presentationLease_hostInvalidationMakesCallbacksInert() {
        val p = Fold7PresentationLease()
        val host = p.openHost()
        val id = p.begin(1L, 2L, 3L, Fold7PresentationLease.RenderPath.LIVE_MIRROR)
        p.invalidateHost(host)
        assertFalse(p.onTransactionCommit(id))
        assertFalse(p.onPresented(id))
    }

    private fun leaseSnapshot(
        connection: Long,
        session: Long,
        revision: Long,
    ) = Fold7CoverLeaseSnapshotGate.Snapshot(
        connectionEpoch = connection,
        shellSession = session,
        shellRevision = revision,
        leaseState = "HELD",
        leaseId = 3L,
        leaseEpoch = 1L,
        ownerGeneration = 8L,
        physicalDisplayId = 123L,
        targetLogicalId = 6,
        physicalLeaseHeld = true,
        routeReady = true,
        ok = true,
    )
}
