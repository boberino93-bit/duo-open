package com.duoopen.shell

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.random.Random

class Fold7PanelAuthorityGen4Test {
    @Test
    fun startupInnerWithoutSecondaryRouteIsClean() {
        val m = Fold7PanelAuthorityGen4()
        assertEquals(
            Fold7PanelAuthorityGen4.RecoveryPlan.ReadyInner,
            m.recoveryPlan(false, true, null),
        )
        m.completeRecovery(nativeCover = false)
        assertTrue(m.snapshot().recoveryReady)
        assertEquals(Fold7PanelAuthorityGen4.Phase.INNER_NATIVE, m.snapshot().phase)
    }

    @Test
    fun startupInnerWithSecondaryRouteRequiresReset() {
        val m = Fold7PanelAuthorityGen4()
        assertEquals(
            Fold7PanelAuthorityGen4.RecoveryPlan.ResetSecondaryRoute(7),
            m.recoveryPlan(false, true, 7),
        )
    }

    @Test
    fun ambiguousStartupStaysFailClosed() {
        val m = Fold7PanelAuthorityGen4()
        assertEquals(
            Fold7PanelAuthorityGen4.RecoveryPlan.RetryAmbiguous,
            m.recoveryPlan(false, false, 7),
        )
        assertFalse(m.snapshot().recoveryReady)
    }

    @Test
    fun intentSequenceRejectsLateArrival() {
        val m = Fold7PanelAuthorityGen4()
        m.completeRecovery(false)
        assertTrue(m.admit(100, 1).accepted)
        assertTrue(m.admit(100, 3).accepted)
        val stale = m.admit(100, 2)
        assertFalse(stale.accepted)
        assertTrue(stale.stale)
    }

    @Test
    fun olderServiceEpochCannotRetakeAuthority() {
        val m = Fold7PanelAuthorityGen4()
        m.completeRecovery(false)
        assertTrue(m.admit(100, 1).accepted)
        val stale = m.admit(99, 2)
        assertFalse(stale.accepted)
        assertTrue(stale.stale)
    }

    @Test
    fun replacementServiceMustNormalizePreparedRoute() {
        val m = Fold7PanelAuthorityGen4()
        m.completeRecovery(false)
        assertTrue(m.admit(100, 1).accepted)
        m.beginPrepare(Fold7PanelAuthorityGen4.Owner(100, 4, 8), 1)
        m.completePrepare(1, true, 222, 7, true)

        val replacement = m.admit(200, 1)
        assertFalse(replacement.accepted)
        assertTrue(replacement.cleanupRequired)

        m.completeServiceRollover(200, 1, nativeCover = false)
        assertEquals(200L, m.snapshot().activeServiceEpoch)
        assertEquals(Fold7PanelAuthorityGen4.Phase.INNER_NATIVE, m.snapshot().phase)
        assertEquals(null, m.snapshot().owner)
    }

    @Test
    fun replacementServiceCanTakeCleanInnerStateImmediately() {
        val m = Fold7PanelAuthorityGen4()
        m.completeRecovery(false)
        assertTrue(m.admit(100, 1).accepted)
        assertTrue(m.admit(200, 1).accepted)
        assertEquals(200L, m.snapshot().activeServiceEpoch)
    }

    @Test
    fun prepareRequiresCurrentServiceAndSequence() {
        val m = Fold7PanelAuthorityGen4()
        m.completeRecovery(false)
        assertTrue(m.admit(100, 9).accepted)
        m.beginPrepare(Fold7PanelAuthorityGen4.Owner(100, 2, 3), 9)
        m.completePrepare(9, true, 222, 7, true)
        assertEquals(Fold7PanelAuthorityGen4.Phase.COVER_READY_HIDDEN, m.snapshot().phase)
        assertTrue(m.snapshot().physicalHeld)
        assertTrue(m.snapshot().routeReady)
    }

    @Test
    fun failedPrepareRemainsHiddenAndRetryable() {
        val m = Fold7PanelAuthorityGen4()
        m.completeRecovery(false)
        assertTrue(m.admit(100, 1).accepted)
        m.beginPrepare(Fold7PanelAuthorityGen4.Owner(100, 1, 2), 1)
        m.completePrepare(1, true, 222, -1, false)
        assertEquals(Fold7PanelAuthorityGen4.Phase.COVER_PREPARING, m.snapshot().phase)
        assertFalse(m.snapshot().routeReady)
        assertTrue(m.admit(100, 2).accepted)
    }

    @Test
    fun failedReleaseRemainsPendingUntilLaterIntentRetries() {
        val m = Fold7PanelAuthorityGen4()
        m.completeRecovery(false)
        assertTrue(m.admit(100, 1).accepted)
        m.beginPrepare(Fold7PanelAuthorityGen4.Owner(100, 1, 2), 1)
        m.completePrepare(1, true, 222, 7, true)
        assertTrue(m.admit(100, 2).accepted)
        m.beginRelease(100, 2)
        m.completeRelease(2, false, false)
        assertEquals(Fold7PanelAuthorityGen4.Phase.RELEASE_PENDING, m.snapshot().phase)
        assertTrue(m.admit(100, 3).accepted)
    }

    @Test
    fun nativeCoverRecoveryNeverRequestsSecondaryReset() {
        val m = Fold7PanelAuthorityGen4()
        assertEquals(
            Fold7PanelAuthorityGen4.RecoveryPlan.ReadyNativeCover,
            m.recoveryPlan(true, false, 7),
        )
        m.completeRecovery(true)
        assertEquals(Fold7PanelAuthorityGen4.Phase.NATIVE_COVER, m.snapshot().phase)
    }
    @Test
    fun fixedSeedHundredThousandIntentFuzzMaintainsAuthorityInvariants() {
        val random = Random(0x47454E34)
        val m = Fold7PanelAuthorityGen4()
        m.completeRecovery(nativeCover = false)

        var serviceEpoch = 100L
        var sequence = 0L

        repeat(100_000) {
            when (random.nextInt(7)) {
                0 -> {
                    sequence += 1L
                    m.admit(serviceEpoch, sequence)
                }

                1 -> {
                    sequence += 1L
                    if (m.admit(serviceEpoch, sequence).accepted) {
                        m.beginPrepare(
                            owner =
                                Fold7PanelAuthorityGen4.Owner(
                                    serviceEpoch = serviceEpoch,
                                    closeCycleId = (it + 1).toLong(),
                                    transitionGeneration = (it % 1000).toLong(),
                                ),
                            intentSequence = sequence,
                        )
                        val physical = random.nextBoolean()
                        val route = physical && random.nextBoolean()
                        m.completePrepare(
                            intentSequence = sequence,
                            success = physical,
                            physicalDisplayId = 222L,
                            logicalDisplayId = if (route) 7 else -1,
                            routeReady = route,
                        )
                    }
                }

                2 -> {
                    sequence += 1L
                    if (m.admit(serviceEpoch, sequence).accepted) {
                        m.beginRelease(serviceEpoch, sequence)
                        m.completeRelease(
                            intentSequence = sequence,
                            success = random.nextBoolean(),
                            nativeCover = false,
                        )
                    }
                }

                3 -> {
                    val stale = m.admit(serviceEpoch, sequence.coerceAtLeast(1L))
                    assertFalse(stale.accepted)
                }

                4 -> {
                    val nextService = serviceEpoch + 1L
                    val decision = m.admit(nextService, 1L)
                    if (decision.cleanupRequired) {
                        m.completeServiceRollover(
                            serviceEpoch = nextService,
                            intentSequence = 1L,
                            nativeCover = false,
                        )
                    } else {
                        assertTrue(decision.accepted)
                    }
                    serviceEpoch = nextService
                    sequence = 1L
                }

                5 -> {
                    if (serviceEpoch > 1L) {
                        val stale = m.admit(serviceEpoch - 1L, sequence + 1000L)
                        assertFalse(stale.accepted)
                        assertTrue(stale.stale)
                    }
                }

                else -> {
                    if (random.nextBoolean()) {
                        m.markNativeCover()
                    }
                }
            }

            val snapshot = m.snapshot()
            assertTrue(snapshot.activeServiceEpoch >= 0L)
            assertTrue(snapshot.lastIntentSequence >= 0L)
            if (snapshot.routeReady) {
                assertEquals(
                    Fold7PanelAuthorityGen4.Phase.COVER_READY_HIDDEN,
                    snapshot.phase,
                )
                assertTrue(snapshot.physicalHeld)
                assertTrue(snapshot.owner != null)
            }
            if (
                snapshot.phase == Fold7PanelAuthorityGen4.Phase.INNER_NATIVE ||
                snapshot.phase == Fold7PanelAuthorityGen4.Phase.NATIVE_COVER
            ) {
                assertFalse(snapshot.routeReady)
                assertFalse(snapshot.physicalHeld)
            }
        }
    }

}
