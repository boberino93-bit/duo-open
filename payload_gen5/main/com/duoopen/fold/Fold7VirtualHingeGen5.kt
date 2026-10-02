package com.duoopen.fold

import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/**
 * Gen5 visual-only Fold7 shadow hinge.
 *
 * It may predict what should be drawn at the next presentation instant, but it
 * MUST NOT be used as continuity state, panel authority, power authority or
 * terminal-handoff truth.
 */
class Fold7VirtualHingeGen5 {
    data class Sample(
        val sourceTimeNs: Long,
        val deliveryTimeNs: Long,
        val angleDegrees: Float,
    )

    enum class Mode {
        IDLE,
        BLIND_BOOTSTRAP,
        STALE_HOLD,
        INSUFFICIENT,
        REVERSAL_GUARD,
        OSCILLATION_GUARD,
        LOW_CONFIDENCE,
        REACQUIRE,
        PREDICT,
    }

    data class FrameTarget(
        val angleDegrees: Float,
        val desiredAngleDegrees: Float,
        val confidence: Float,
        val mode: Mode,
        val correctionDegrees: Float,
        val slewLimited: Boolean,
        val measurementAgeMs: Long?,
        val predictedLeadNs: Long,
    )

    data class AddResult(
        val accepted: Boolean,
        val reversal: Boolean,
        val oscillationGuardEntered: Boolean,
        val reacquiring: Boolean,
    )

    private data class Fit(
        val velocityDegPerSec: Double,
        val rmseDegrees: Double,
    )

    private val history = ArrayList<Sample>(HISTORY_SIZE)
    private val reversalTimesNs = ArrayList<Long>(4)

    private var active = false
    private var openingStartedNs = 0L
    private var initialAngle = CLOSED_SEED_DEG
    private var visualAngle = CLOSED_SEED_DEG
    private var lastFrameNs = Long.MIN_VALUE
    private var lastDirectionSign = 0
    private var reversalGuardUntilNs = Long.MIN_VALUE
    private var oscillationGuardUntilNs = Long.MIN_VALUE
    private var reacquireUntilNs = Long.MIN_VALUE
    private var lastAcceptedDeliveryNs = Long.MIN_VALUE

    fun startOpening(
        nowNs: Long,
        seedAngleDegrees: Float = CLOSED_SEED_DEG,
    ) {
        reset()
        active = true
        openingStartedNs = nowNs
        initialAngle = seedAngleDegrees.coerceIn(0f, BLIND_SEED_MAX_DEG)
        visualAngle = initialAngle
        lastFrameNs = nowNs
    }

    fun stop() {
        reset()
    }

    fun reset() {
        active = false
        history.clear()
        reversalTimesNs.clear()
        openingStartedNs = 0L
        initialAngle = CLOSED_SEED_DEG
        visualAngle = CLOSED_SEED_DEG
        lastFrameNs = Long.MIN_VALUE
        lastDirectionSign = 0
        reversalGuardUntilNs = Long.MIN_VALUE
        oscillationGuardUntilNs = Long.MIN_VALUE
        reacquireUntilNs = Long.MIN_VALUE
        lastAcceptedDeliveryNs = Long.MIN_VALUE
    }

    fun addSample(sample: Sample): AddResult {
        if (!sample.angleDegrees.isFinite()) {
            return AddResult(false, false, false, false)
        }

        val previous = history.lastOrNull()
        if (previous != null && sample.sourceTimeNs <= previous.sourceTimeNs) {
            return AddResult(false, false, false, false)
        }

        val accepted = sample.copy(
            angleDegrees = sample.angleDegrees.coerceIn(0f, 180f),
        )

        var reversal = false
        var oscillationEntered = false
        var reacquiring = false

        val priorDelivery = lastAcceptedDeliveryNs
        if (
            (
                priorDelivery != Long.MIN_VALUE &&
                    accepted.deliveryTimeNs - priorDelivery > REACQUIRE_GAP_NS
            ) ||
            (
                priorDelivery == Long.MIN_VALUE &&
                    active &&
                    accepted.deliveryTimeNs - openingStartedNs > REACQUIRE_GAP_NS
            )
        ) {
            reacquiring = true
            reacquireUntilNs = accepted.deliveryTimeNs + REACQUIRE_WINDOW_NS
        }

        if (previous != null) {
            val dtNs = accepted.sourceTimeNs - previous.sourceTimeNs
            if (dtNs > 0L) {
                val velocity =
                    (accepted.angleDegrees - previous.angleDegrees) /
                        (dtNs / 1_000_000_000.0)
                val sign = when {
                    velocity > REVERSAL_SPEED_EPS_DPS -> 1
                    velocity < -REVERSAL_SPEED_EPS_DPS -> -1
                    else -> 0
                }

                if (sign != 0 && lastDirectionSign != 0 && sign != lastDirectionSign) {
                    reversal = true
                    reversalGuardUntilNs = accepted.deliveryTimeNs + REVERSAL_GUARD_NS
                    reversalTimesNs.removeAll {
                        accepted.deliveryTimeNs - it > OSCILLATION_WINDOW_NS
                    }
                    reversalTimesNs += accepted.deliveryTimeNs
                    if (reversalTimesNs.size >= 2) {
                        val next = accepted.deliveryTimeNs + OSCILLATION_GUARD_NS
                        oscillationEntered = next > oscillationGuardUntilNs
                        oscillationGuardUntilNs = max(oscillationGuardUntilNs, next)
                    }
                }
                if (sign != 0) {
                    lastDirectionSign = sign
                }
            }
        }

        history += accepted
        while (history.size > HISTORY_SIZE) history.removeAt(0)
        lastAcceptedDeliveryNs = accepted.deliveryTimeNs

        return AddResult(true, reversal, oscillationEntered, reacquiring)
    }

    /**
     * Returns an allocation-light visual target for the next presented frame.
     * [expectedPresentationTimeNs] is the best available compositor estimate;
     * passing callback time + one frame interval is an acceptable fallback.
     */
    fun targetForFrame(
        callbackTimeNs: Long,
        expectedPresentationTimeNs: Long,
    ): FrameTarget {
        if (!active) {
            return FrameTarget(
                angleDegrees = visualAngle,
                desiredAngleDegrees = visualAngle,
                confidence = 0f,
                mode = Mode.IDLE,
                correctionDegrees = 0f,
                slewLimited = false,
                measurementAgeMs = null,
                predictedLeadNs = 0L,
            )
        }

        val latest = history.lastOrNull()
        val raw = chooseDesired(callbackTimeNs, expectedPresentationTimeNs, latest)
        val dtNs =
            if (lastFrameNs == Long.MIN_VALUE) DEFAULT_FRAME_NS
            else (callbackTimeNs - lastFrameNs).coerceIn(MIN_FRAME_NS, MAX_FRAME_NS)
        lastFrameNs = callbackTimeNs

        val maxStep =
            max(
                MIN_SLEW_DEG_PER_FRAME,
                (MAX_VISUAL_SPEED_DPS * (dtNs / 1_000_000_000.0)).toFloat(),
            )
        val delta = raw.desired - visualAngle
        val step = delta.coerceIn(-maxStep, maxStep)
        val next = (visualAngle + step).coerceIn(0f, 180f)
        val limited = abs(step - delta) > 0.0001f
        val correction = next - visualAngle
        visualAngle = next

        return FrameTarget(
            angleDegrees = next,
            desiredAngleDegrees = raw.desired,
            confidence = raw.confidence,
            mode = raw.mode,
            correctionDegrees = correction,
            slewLimited = limited,
            measurementAgeMs = latest?.let {
                ((callbackTimeNs - it.deliveryTimeNs).coerceAtLeast(0L) / 1_000_000L)
            },
            predictedLeadNs = raw.leadNs,
        )
    }

    private data class RawTarget(
        val desired: Float,
        val confidence: Float,
        val mode: Mode,
        val leadNs: Long,
    )

    private fun chooseDesired(
        callbackTimeNs: Long,
        expectedPresentationTimeNs: Long,
        latest: Sample?,
    ): RawTarget {
        if (latest == null) {
            val elapsedNs = (callbackTimeNs - openingStartedNs).coerceAtLeast(0L)
            val elapsedSec = elapsedNs / 1_000_000_000.0
            val blind =
                (initialAngle + BLIND_VELOCITY_DPS * elapsedSec)
                    .toFloat()
                    .coerceAtMost(BLIND_MAX_ANGLE_DEG)
            val confidence =
                (BLIND_INITIAL_CONFIDENCE -
                    (elapsedNs / 1_000_000_000.0 * BLIND_CONFIDENCE_DECAY_PER_SEC))
                    .toFloat()
                    .coerceIn(BLIND_MIN_CONFIDENCE, BLIND_INITIAL_CONFIDENCE)
            return RawTarget(blind, confidence, Mode.BLIND_BOOTSTRAP, 0L)
        }

        val ageNs = callbackTimeNs - latest.deliveryTimeNs
        if (ageNs > HARD_STALE_NS) {
            return RawTarget(latest.angleDegrees, 0f, Mode.STALE_HOLD, 0L)
        }

        if (callbackTimeNs < oscillationGuardUntilNs) {
            return RawTarget(latest.angleDegrees, 0f, Mode.OSCILLATION_GUARD, 0L)
        }

        if (callbackTimeNs < reversalGuardUntilNs) {
            return RawTarget(latest.angleDegrees, 0f, Mode.REVERSAL_GUARD, 0L)
        }

        if (callbackTimeNs < reacquireUntilNs) {
            return RawTarget(latest.angleDegrees, 0.25f, Mode.REACQUIRE, 0L)
        }

        if (ageNs > PREDICTION_STALE_NS) {
            return RawTarget(latest.angleDegrees, 0f, Mode.STALE_HOLD, 0L)
        }

        val fit = fit() ?: return RawTarget(latest.angleDegrees, 0f, Mode.INSUFFICIENT, 0L)
        val confidence =
            (1.0 - fit.rmseDegrees / RMSE_FULL_LOSS_DEG)
                .coerceIn(0.0, 1.0)
                .toFloat()

        if (confidence < MIN_CONFIDENCE) {
            return RawTarget(latest.angleDegrees, confidence, Mode.LOW_CONFIDENCE, 0L)
        }

        val requestedLeadNs =
            (expectedPresentationTimeNs - latest.sourceTimeNs) + PHASE_COMPENSATION_NS
        val leadNs = requestedLeadNs.coerceIn(0L, MAX_HORIZON_NS)
        val endpointDistance = min(latest.angleDegrees, 180f - latest.angleDegrees)
        val endpointScale = (endpointDistance / ENDPOINT_TAPER_DEG).coerceIn(0.35f, 1f)
        val leadDegrees =
            fit.velocityDegPerSec * (leadNs / 1_000_000_000.0) * confidence * endpointScale
        val predicted =
            (latest.angleDegrees + leadDegrees)
                .toFloat()
                .coerceIn(0f, 180f)

        return RawTarget(predicted, confidence, Mode.PREDICT, leadNs)
    }

    private fun fit(): Fit? {
        if (history.size < MIN_FIT_SAMPLES) return null

        val lastTimeNs = history.last().sourceTimeNs
        val n = history.size
        val xs = DoubleArray(n) { i ->
            (history[i].sourceTimeNs - lastTimeNs) / 1_000_000_000.0
        }
        val ys = DoubleArray(n) { i -> history[i].angleDegrees.toDouble() }
        val weights = DoubleArray(n) { i -> (i + 1).toDouble() }
        val sumW = weights.sum()
        val meanX = xs.indices.sumOf { weights[it] * xs[it] } / sumW
        val meanY = ys.indices.sumOf { weights[it] * ys[it] } / sumW
        val denominator = xs.indices.sumOf {
            weights[it] * (xs[it] - meanX) * (xs[it] - meanX)
        }
        if (denominator < 1e-12) return null

        val velocity =
            (xs.indices.sumOf {
                weights[it] * (xs[it] - meanX) * (ys[it] - meanY)
            } / denominator).coerceIn(-MAX_SPEED_DPS, MAX_SPEED_DPS)

        var weightedSquaredError = 0.0
        for (i in xs.indices) {
            val fitted = meanY + velocity * (xs[i] - meanX)
            val error = ys[i] - fitted
            weightedSquaredError += weights[i] * error * error
        }

        return Fit(
            velocityDegPerSec = velocity,
            rmseDegrees = sqrt(weightedSquaredError / sumW),
        )
    }

    companion object {
        const val HISTORY_SIZE = 7
        const val MIN_FIT_SAMPLES = 4
        const val CLOSED_SEED_DEG = 0.5f
        const val BLIND_SEED_MAX_DEG = 20f
        const val BLIND_VELOCITY_DPS = 180.0
        const val BLIND_MAX_ANGLE_DEG = 92f
        const val BLIND_INITIAL_CONFIDENCE = 0.45f
        const val BLIND_MIN_CONFIDENCE = 0.12f
        const val BLIND_CONFIDENCE_DECAY_PER_SEC = 0.35f
        const val PREDICTION_STALE_NS = 40_000_000L
        const val HARD_STALE_NS = 180_000_000L
        const val REACQUIRE_GAP_NS = 120_000_000L
        const val REACQUIRE_WINDOW_NS = 160_000_000L
        const val REVERSAL_GUARD_NS = 55_000_000L
        const val OSCILLATION_WINDOW_NS = 500_000_000L
        const val OSCILLATION_GUARD_NS = 850_000_000L
        const val PHASE_COMPENSATION_NS = 36_000_000L
        const val MAX_HORIZON_NS = 60_000_000L
        const val MIN_CONFIDENCE = 0.20f
        const val REVERSAL_SPEED_EPS_DPS = 7.0
        const val RMSE_FULL_LOSS_DEG = 3.0
        const val MAX_SPEED_DPS = 900.0
        const val ENDPOINT_TAPER_DEG = 12f
        const val MAX_VISUAL_SPEED_DPS = 480.0
        const val MIN_SLEW_DEG_PER_FRAME = 1.0f
        const val DEFAULT_FRAME_NS = 16_666_667L
        const val MIN_FRAME_NS = 4_000_000L
        const val MAX_FRAME_NS = 40_000_000L
    }
}
