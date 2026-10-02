package com.duoopen.fold

import kotlin.math.PI
import kotlin.math.floor
import kotlin.math.sin

/** Allocation-free Gen5 visual state lookup for the physical 0..180 degree hinge. */
class Fold7VisualStateLut(
    private val stepDegrees: Float = 0.25f,
) {
    data class State(
        val glassAmount: Float,
        val rightPaneTiltDegrees: Float,
    )

    private val count = floor(180f / stepDegrees).toInt() + 1
    private val states = Array(count) { index -> exact(index * stepDegrees) }

    fun stateFor(angleDegrees: Float): State {
        val a = angleDegrees.coerceIn(0f, 180f)
        val raw = a / stepDegrees
        val lo = floor(raw).toInt().coerceIn(0, count - 1)
        val hi = (lo + 1).coerceAtMost(count - 1)
        if (lo == hi) return states[lo]
        val f = raw - lo
        val x = states[lo]
        val y = states[hi]
        return State(
            glassAmount = lerp(x.glassAmount, y.glassAmount, f),
            rightPaneTiltDegrees = lerp(x.rightPaneTiltDegrees, y.rightPaneTiltDegrees, f),
        )
    }

    private fun exact(angle: Float): State {
        val envelope = sin(PI * (angle / 180.0)).toFloat().coerceIn(0f, 1f)
        return State(
            glassAmount = envelope,
            rightPaneTiltDegrees = envelope * MAX_TILT_DEG,
        )
    }

    private fun lerp(a: Float, b: Float, f: Float) = a + (b - a) * f

    companion object {
        const val MAX_TILT_DEG = 60f
    }
}
