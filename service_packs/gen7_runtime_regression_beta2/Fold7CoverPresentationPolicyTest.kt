package com.duoopen.overlay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7CoverPresentationPolicyTest {
    @Test
    fun fullyOpenIsExplicitlyOff() {
        val p = Fold7CoverPresentationPolicy()
        val command = p.evaluate(
            angle = 180f,
            direction = Fold7CoverPresentationPolicy.Direction.STEADY,
            innerReferenceBrightness = 0.7f,
            nowMs = 0L,
        )
        assertEquals(false, command?.powerOn)
        assertEquals(null, command?.brightness)
    }

    @Test
    fun closingWakesAt175AtMinimumBrightness() {
        val p = Fold7CoverPresentationPolicy()
        p.evaluate(180f, Fold7CoverPresentationPolicy.Direction.STEADY, 0.7f, 0L)
        assertEquals(
            null,
            p.evaluate(176f, Fold7CoverPresentationPolicy.Direction.CLOSING, 0.7f, 50L),
        )
        val command = p.evaluate(
            175f,
            Fold7CoverPresentationPolicy.Direction.CLOSING,
            0.7f,
            100L,
        )
        assertEquals(true, command?.powerOn)
        assertEquals(
            Fold7CoverPresentationPolicy.MIN_BRIGHTNESS,
            command?.brightness ?: -1f,
            0.0001f,
        )
    }

    @Test
    fun brightnessMatchesInnerByNinety() {
        val p = Fold7CoverPresentationPolicy()
        val target = 0.63f
        assertEquals(
            target,
            p.brightnessFor(90f, target),
            0.0001f,
        )
        assertEquals(
            target,
            p.brightnessFor(45f, target),
            0.0001f,
        )
    }

    @Test
    fun midpointIsBetweenMinimumAndReference() {
        val p = Fold7CoverPresentationPolicy()
        val b = p.brightnessFor(132.5f, 0.8f)
        assertTrue(b > Fold7CoverPresentationPolicy.MIN_BRIGHTNESS)
        assertTrue(b < 0.8f)
    }

    @Test
    fun openingUsesTwoDegreeHysteresis() {
        val p = Fold7CoverPresentationPolicy()
        p.evaluate(90f, Fold7CoverPresentationPolicy.Direction.CLOSING, 0.6f, 0L)
        val stillOn = p.evaluate(
            176f,
            Fold7CoverPresentationPolicy.Direction.OPENING,
            0.6f,
            50L,
        )
        assertFalse(stillOn?.powerOn == false)

        val off = p.evaluate(
            177f,
            Fold7CoverPresentationPolicy.Direction.OPENING,
            0.6f,
            100L,
        )
        assertEquals(false, off?.powerOn)
    }
}
