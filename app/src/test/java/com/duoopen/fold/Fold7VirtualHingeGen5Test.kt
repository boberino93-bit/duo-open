package com.duoopen.fold

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs
import kotlin.random.Random

class Fold7VirtualHingeGen5Test {
    private fun sample(ms: Long, angle: Float) =
        Fold7VirtualHingeGen5.Sample(
            sourceTimeNs = ms * 1_000_000L,
            deliveryTimeNs = (ms + 1) * 1_000_000L,
            angleDegrees = angle,
        )

    @Test
    fun blindBootstrapMovesButCannotRunPastGlassPeak() {
        val v = Fold7VirtualHingeGen5()
        v.startOpening(0L)
        val early = v.targetForFrame(100_000_000L, 116_666_667L)
        val late = v.targetForFrame(700_000_000L, 716_666_667L)
        assertEquals(Fold7VirtualHingeGen5.Mode.BLIND_BOOTSTRAP, early.mode)
        assertTrue(early.angleDegrees > Fold7VirtualHingeGen5.CLOSED_SEED_DEG)
        assertTrue(late.angleDegrees <= Fold7VirtualHingeGen5.BLIND_MAX_ANGLE_DEG)
    }

    @Test
    fun stableMotionPredictsAhead() {
        val v = Fold7VirtualHingeGen5()
        v.startOpening(0L)
        v.addSample(sample(0, 10f))
        v.addSample(sample(8, 12f))
        v.addSample(sample(16, 14f))
        v.addSample(sample(24, 16f))
        val t = v.targetForFrame(26_000_000L, 42_000_000L)
        assertEquals(Fold7VirtualHingeGen5.Mode.PREDICT, t.mode)
        assertTrue(t.desiredAngleDegrees > 16f)
    }

    @Test
    fun reacquisitionCannotSnapMoreThanOneFrameBudget() {
        val v = Fold7VirtualHingeGen5()
        v.startOpening(0L)
        v.targetForFrame(400_000_000L, 416_666_667L)
        val before = v.targetForFrame(416_666_667L, 433_333_334L).angleDegrees
        v.addSample(sample(420, 140f))
        val after = v.targetForFrame(433_333_334L, 450_000_001L)
        assertTrue(abs(after.angleDegrees - before) <= 8.2f)
    }

    @Test
    fun repeatedReversalEntersOscillationGuard() {
        val v = Fold7VirtualHingeGen5()
        v.startOpening(0L)
        v.addSample(sample(0, 30f)); v.addSample(sample(8, 40f)); v.addSample(sample(16, 50f)); v.addSample(sample(24, 60f))
        v.addSample(sample(32, 55f))
        v.addSample(sample(40, 45f)); v.addSample(sample(48, 35f))
        val second = v.addSample(sample(56, 40f))
        val target = v.targetForFrame(58_000_000L, 74_000_000L)
        assertTrue(second.oscillationGuardEntered)
        assertEquals(Fold7VirtualHingeGen5.Mode.OSCILLATION_GUARD, target.mode)
    }

    @Test
    fun glassEnvelopePeaksAtNinetyAndClearsAtEndpoints() {
        val lut = Fold7VisualStateLut()
        assertTrue(lut.stateFor(0f).glassAmount < 0.001f)
        assertTrue(abs(lut.stateFor(90f).glassAmount - 1f) < 0.001f)
        assertTrue(lut.stateFor(180f).glassAmount < 0.001f)
        assertTrue(abs(lut.stateFor(45f).glassAmount - lut.stateFor(135f).glassAmount) < 0.002f)
    }

    @Test
    fun fuzzNeverLeavesPhysicalDomainOrSlewBudget() {
        val rng = Random(0x5A17)
        val v = Fold7VirtualHingeGen5()
        v.startOpening(0L)
        var now = 0L
        var physical = 0.5f
        repeat(100_000) { i ->
            now += if (i % 2 == 0) 8_333_333L else 16_666_667L
            if (i % 3 == 0) {
                physical = (physical + rng.nextDouble(-7.0, 9.0).toFloat()).coerceIn(0f, 180f)
                v.addSample(
                    Fold7VirtualHingeGen5.Sample(
                        sourceTimeNs = now - 2_000_000L,
                        deliveryTimeNs = now,
                        angleDegrees = physical,
                    )
                )
            }
            val t = v.targetForFrame(now, now + 8_333_333L)
            assertTrue(t.angleDegrees.isFinite())
            assertTrue(t.angleDegrees in 0f..180f)
            assertTrue(abs(t.correctionDegrees) <= 8.5f)
        }
    }
}
