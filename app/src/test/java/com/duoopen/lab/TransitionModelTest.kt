package com.duoopen.lab

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class TransitionModelTest {
    @Test
    fun samsungSampleKeepsBinderAndConsumerLatencySeparate() {
        val sample =
            HingeSampleRecord(
                sequence = 7L,
                angleDegrees = 123.4f,
                sourceTimeNs = 1_000_000_000L,
                binderArrivalTimeNs = 1_005_000_000L,
                consumerDeliveryTimeNs = 1_009_000_000L,
                source = HingeSampleSource.SAMSUNG_FOLD_INTERACTIVE,
                timestampQuality = TimestampQuality.ESTIMATED_WALL_TO_UPTIME,
            )

        assertEquals(
            5_000_000L,
            sample.sourceToBinderLagNs,
        )
        assertEquals(
            4_000_000L,
            sample.binderToConsumerLagNs,
        )
        assertEquals(
            9_000_000L,
            sample.sourceToConsumerLagNs,
        )
    }

    @Test
    fun estimatedClockResidualIsNotSilentlyClamped() {
        val sample =
            HingeSampleRecord(
                sequence = 1L,
                angleDegrees = 45f,
                sourceTimeNs = 10_000L,
                binderArrivalTimeNs = 9_500L,
                consumerDeliveryTimeNs = 11_000L,
                source = HingeSampleSource.SAMSUNG_FOLD_INTERACTIVE,
                timestampQuality = TimestampQuality.ESTIMATED_WALL_TO_UPTIME,
            )

        assertEquals(
            -500L,
            sample.sourceToBinderLagNs,
        )
        assertEquals(
            1_500L,
            sample.binderToConsumerLagNs,
        )
        assertEquals(
            1_000L,
            sample.sourceToConsumerLagNs,
        )
    }

    @Test
    fun syntheticEndpointHasNoInventedSourceOrBinderTime() {
        val sample =
            HingeSampleRecord(
                sequence = 2L,
                angleDegrees = 180f,
                sourceTimeNs = null,
                binderArrivalTimeNs = null,
                consumerDeliveryTimeNs = 50_000L,
                source = HingeSampleSource.SYNTHETIC_ENDPOINT,
                timestampQuality = TimestampQuality.ARRIVAL_ONLY,
                synthetic = true,
            )

        assertTrue(sample.synthetic)
        assertNull(sample.sourceToBinderLagNs)
        assertNull(sample.binderToConsumerLagNs)
        assertNull(sample.sourceToConsumerLagNs)
    }
}
