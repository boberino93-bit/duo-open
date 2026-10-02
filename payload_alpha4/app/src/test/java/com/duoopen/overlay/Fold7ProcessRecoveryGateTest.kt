package com.duoopen.overlay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7ProcessRecoveryGateTest {
    private fun snapshot(
        state: String,
        ownerServiceEpoch: Long = 0L,
        ownerGeneration: Long = 7L,
        leaseEpoch: Long = 11L,
    ) =
        Fold7CoverLeaseSnapshotGate.Snapshot(
            connectionEpoch = 1L,
            shellSession = 2L,
            shellRevision = 3L,
            leaseState = state,
            leaseId = if (state == "IDLE") 0L else 5L,
            leaseEpoch = if (state == "IDLE") 0L else leaseEpoch,
            ownerGeneration = if (state == "IDLE") -1L else ownerGeneration,
            physicalDisplayId = if (state == "IDLE") -1L else 99L,
            targetLogicalId = -1,
            physicalLeaseHeld = state != "IDLE",
            routeReady = false,
            ok = true,
            ownerServiceEpoch = ownerServiceEpoch,
            ownerCloseCycleId = if (state == "IDLE") 0L else 4L,
        )

    @Test
    fun idleShellUnlocksStartupArm() {
        val gate = Fold7ProcessRecoveryGate(serviceEpoch = 100L)

        val decision =
            gate.observe(
                snapshot = snapshot("IDLE"),
                token = null,
            )

        assertTrue(gate.ready)
        assertEquals(Fold7ProcessRecoveryGate.Action.Arm, decision.action)
    }

    @Test
    fun foreignHeldLeaseRequiresExactCleanupBeforeArm() {
        val gate = Fold7ProcessRecoveryGate(serviceEpoch = 100L)
        val foreign = snapshot("HELD", ownerServiceEpoch = 50L)

        val decision =
            gate.observe(
                snapshot = foreign,
                token = foreign.token,
            )

        assertFalse(gate.ready)
        assertTrue(
            decision.action is
                Fold7ProcessRecoveryGate.Action.ReleaseForeign
        )
    }

    @Test
    fun legacyOwnerIsForeign() {
        val gate = Fold7ProcessRecoveryGate(serviceEpoch = 100L)
        val foreign = snapshot("HELD", ownerServiceEpoch = 0L)

        val decision =
            gate.observe(
                snapshot = foreign,
                token = foreign.token,
            )

        assertFalse(gate.ready)
        assertTrue(
            decision.action is
                Fold7ProcessRecoveryGate.Action.ReleaseForeign
        )
    }

    @Test
    fun identicalForeignTokenIsNotReleasedTwice() {
        val gate = Fold7ProcessRecoveryGate(serviceEpoch = 100L)
        val foreign = snapshot("HELD", ownerServiceEpoch = 50L)

        gate.observe(foreign, foreign.token)
        val repeated = gate.observe(foreign, foreign.token)

        assertFalse(gate.ready)
        assertEquals(
            Fold7ProcessRecoveryGate.Action.None,
            repeated.action,
        )
    }

    @Test
    fun releasePendingStaysFailClosed() {
        val gate = Fold7ProcessRecoveryGate(serviceEpoch = 100L)
        val pending =
            snapshot(
                state = "RELEASE_PENDING",
                ownerServiceEpoch = 50L,
            )

        val decision = gate.observe(pending, pending.token)

        assertFalse(gate.ready)
        assertEquals(
            Fold7ProcessRecoveryGate.Action.None,
            decision.action,
        )
    }

    @Test
    fun foreignCleanupThenIdleUnlocksExactlyOnce() {
        val gate = Fold7ProcessRecoveryGate(serviceEpoch = 100L)
        val foreign = snapshot("HELD", ownerServiceEpoch = 50L)

        gate.observe(foreign, foreign.token)
        val clean = gate.observe(snapshot("IDLE"), null)
        val repeated = gate.observe(snapshot("IDLE"), null)

        assertTrue(gate.ready)
        assertEquals(Fold7ProcessRecoveryGate.Action.Arm, clean.action)
        assertEquals(Fold7ProcessRecoveryGate.Action.None, repeated.action)
    }

    @Test
    fun sameServiceAuthorityMayResumeAfterReentry() {
        val gate = Fold7ProcessRecoveryGate(serviceEpoch = 100L)
        val local = snapshot("HELD", ownerServiceEpoch = 100L)

        val decision = gate.observe(local, local.token)

        assertTrue(gate.ready)
        assertEquals(Fold7ProcessRecoveryGate.Action.Arm, decision.action)
    }

    @Test
    fun invalidNonIdleSnapshotCannotUnlockRecovery() {
        val gate = Fold7ProcessRecoveryGate(serviceEpoch = 100L)
        val invalid = snapshot("HELD", ownerServiceEpoch = 50L)

        val decision = gate.observe(invalid, null)

        assertFalse(gate.ready)
        assertEquals(
            Fold7ProcessRecoveryGate.Action.None,
            decision.action,
        )
    }
}
