package com.duoopen.fold

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7AngleAuthorityTest {
    @Test
    fun freshPreciseOwnsWhilePublicIsRetainedThenPromoted() {
        val a = Fold7AngleAuthority(preciseMaxAgeMs = 192L)
        a.startPreciseSession(7L, 1_000L)
        val p = a.offerPrecise(7L, 1L, 5f, 1_000L, 1_010L)
        assertNotNull(p.output)

        val shadow = a.offerPublic(
            source = Fold7AngleAuthority.Source.PUBLIC_STANDARD,
            angle = 90f,
            observedUptimeMs = 1_050L,
            receivedUptimeMs = 1_050L,
            coarse = true,
        )
        assertNull(shadow.output)

        val expired = a.expirePrecise(1_193L, "lease-expired")
        assertEquals(90f, expired.output!!.angle)
        assertEquals(Fold7AngleAuthority.Source.PUBLIC_STANDARD, expired.output!!.source)
        assertTrue(expired.output!!.coarse)
    }

    @Test
    fun delayedPreciseCannotAcquireAuthority() {
        val a = Fold7AngleAuthority(preciseMaxAgeMs = 192L)
        a.startPreciseSession(1L, 0L)
        val d = a.offerPrecise(1L, 1L, 42f, 0L, 193L)
        assertFalse(d.accepted)
        assertEquals("stale-source-age", d.dropReason)
        assertEquals(Fold7AngleAuthority.Source.NONE, a.snapshot(193L).source)
    }

    @Test
    fun oldSessionAndDuplicateSequenceAreRejected() {
        val a = Fold7AngleAuthority()
        a.startPreciseSession(4L, 100L)
        assertTrue(a.offerPrecise(4L, 1L, 10f, 100L, 101L).accepted)
        assertFalse(a.offerPrecise(4L, 1L, 11f, 102L, 103L).accepted)
        a.revokePreciseSession(4L, 104L, "stop")
        a.startPreciseSession(6L, 105L)
        assertFalse(a.offerPrecise(4L, 2L, 12f, 106L, 107L).accepted)
    }

    @Test
    fun syntheticEndpointIsSessionScopedAndDoesNotExtendLease() {
        val a = Fold7AngleAuthority(preciseMaxAgeMs = 192L)
        a.startPreciseSession(2L, 1_000L)
        a.offerPrecise(2L, 1L, 4f, 1_000L, 1_004L)
        val before = a.nextPreciseExpiryUptimeMs()
        val synthetic = a.offerSyntheticEndpoint(2L, 0f, 1_140L, "bridge")
        assertNotNull(synthetic.output)
        assertEquals(before, a.nextPreciseExpiryUptimeMs())
        a.revokePreciseSession(2L, 1_150L, "stop")
        assertFalse(a.offerSyntheticEndpoint(2L, 180f, 1_151L, "old").accepted)
    }

    @Test
    fun publicOwnsImmediatelyWhenNoPreciseLeaseExists() {
        val a = Fold7AngleAuthority()
        val d = a.offerPublic(
            source = Fold7AngleAuthority.Source.PUBLIC_VENDOR,
            angle = 88f,
            observedUptimeMs = 500L,
            receivedUptimeMs = 501L,
            coarse = false,
        )
        assertEquals(88f, d.output!!.angle)
        assertEquals(Fold7AngleAuthority.Source.PUBLIC_VENDOR, d.output!!.source)
    }
    @Test
    fun preciseExpiryWithoutFallbackBecomesUnknown() {
        val a = Fold7AngleAuthority(preciseMaxAgeMs = 192L)
        a.startPreciseSession(9L, 1_000L)
        a.offerPrecise(9L, 1L, 44f, 1_000L, 1_010L)
        val expired = a.expirePrecise(1_193L, "lease-expired")
        assertNull(expired.output)
        assertTrue(expired.stateChanged)
        assertEquals(Fold7AngleAuthority.Source.NONE, a.snapshot(1_193L).source)
    }

}
