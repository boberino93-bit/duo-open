package com.duoopen.fold

import android.os.SystemClock
import kotlin.math.abs

enum class HingeTravel {
    UNKNOWN,
    OPENING,
    CLOSING,
}

/**
 * Debounces hinge direction so tiny reversals do not flip the animation.
 *
 * A new direction becomes authoritative only after a meaningful amount of
 * travel and a short confirmation interval. Endpoints resolve immediately.
 */
class HingeTravelEstimator {
    private var committed =
        HingeTravel.UNKNOWN

    private var candidate =
        HingeTravel.UNKNOWN

    private var candidateStartAngle =
        Float.NaN

    private var candidateStartMs =
        0L

    private var lastAngle =
        Float.NaN

    fun reset() {
        committed =
            HingeTravel.UNKNOWN

        candidate =
            HingeTravel.UNKNOWN

        candidateStartAngle =
            Float.NaN

        candidateStartMs =
            0L

        lastAngle =
            Float.NaN
    }

    fun update(
        angle: Float,
        nowMs: Long = SystemClock.uptimeMillis(),
    ): HingeTravel {
        if (angle.isNaN()) {
            return committed
        }

        if (angle <= CLOSED_ENDPOINT_DEG) {
            committed =
                HingeTravel.CLOSING

            candidate =
                HingeTravel.UNKNOWN

            lastAngle =
                angle

            return committed
        }

        if (angle >= OPEN_ENDPOINT_DEG) {
            committed =
                HingeTravel.OPENING

            candidate =
                HingeTravel.UNKNOWN

            lastAngle =
                angle

            return committed
        }

        val previous =
            lastAngle

        lastAngle =
            angle

        if (previous.isNaN()) {
            return committed
        }

        val delta =
            angle -
                previous

        if (abs(delta) < SAMPLE_EPSILON_DEG) {
            return committed
        }

        val observed =
            if (delta > 0f) {
                HingeTravel.OPENING
            } else {
                HingeTravel.CLOSING
            }

        if (observed == committed) {
            candidate =
                HingeTravel.UNKNOWN

            return committed
        }

        if (observed != candidate) {
            candidate =
                observed

            candidateStartAngle =
                angle

            candidateStartMs =
                nowMs

            return committed
        }

        val candidateTravel =
            abs(
                angle -
                    candidateStartAngle
            )

        val candidateAge =
            nowMs -
                candidateStartMs

        if (
            candidateTravel >= CONFIRM_TRAVEL_DEG &&
            candidateAge >= CONFIRM_TIME_MS
        ) {
            committed =
                candidate

            candidate =
                HingeTravel.UNKNOWN
        }

        return committed
    }

    private companion object {
        const val CLOSED_ENDPOINT_DEG =
            3f

        const val OPEN_ENDPOINT_DEG =
            168f

        const val SAMPLE_EPSILON_DEG =
            0.35f

        const val CONFIRM_TRAVEL_DEG =
            8f

        const val CONFIRM_TIME_MS =
            80L
    }
}
