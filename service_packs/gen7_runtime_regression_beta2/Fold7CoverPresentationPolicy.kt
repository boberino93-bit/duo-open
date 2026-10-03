package com.duoopen.overlay

import kotlin.math.abs
import kotlin.math.pow

/**
 * Fold7 cover/front-panel presentation policy.
 *
 * This is intentionally Android-free. It converts semantic hinge motion into
 * sparse physical-panel commands; the shell daemon remains the only component
 * that mutates physical display power/brightness.
 *
 * Requested field behavior:
 * - fully open: cover off;
 * - closing: cover wakes at 175 degrees at minimum useful brightness;
 * - 175 -> 90 degrees: perceptually eased brightness ramp;
 * - <= 90 degrees: match the last unfolded inner-display brightness;
 * - opening: retain the cover through 175 and switch it off at 177 degrees,
 *   providing hysteresis around the open endpoint.
 */
internal class Fold7CoverPresentationPolicy(
    private val minBrightness: Float = MIN_BRIGHTNESS,
    private val onClosingDeg: Float = POWER_ON_CLOSING_DEG,
    private val offOpeningDeg: Float = POWER_OFF_OPENING_DEG,
    private val matchBrightnessDeg: Float = MATCH_BRIGHTNESS_DEG,
    private val minBrightnessDelta: Float = MIN_BRIGHTNESS_DELTA,
    private val minUpdateIntervalMs: Long = MIN_UPDATE_INTERVAL_MS,
) {
    enum class Direction {
        OPENING,
        CLOSING,
        STEADY,
    }

    data class Command(
        val powerOn: Boolean,
        val brightness: Float?,
        val reason: String,
    )

    private var commandedPower: Boolean? = null
    private var commandedBrightness = Float.NaN
    private var lastCommandMs = Long.MIN_VALUE

    fun reset() {
        commandedPower = null
        commandedBrightness = Float.NaN
        lastCommandMs = Long.MIN_VALUE
    }

    fun evaluate(
        angle: Float,
        direction: Direction,
        innerReferenceBrightness: Float,
        nowMs: Long,
    ): Command? {
        if (!angle.isFinite()) return null

        val reference =
            innerReferenceBrightness
                .takeIf { it.isFinite() }
                ?.coerceIn(minBrightness, 1f)
                ?: DEFAULT_INNER_REFERENCE

        val powerWanted =
            when {
                // Once opening reaches the hysteresis-off edge (or is sitting
                // fully open), the cover is explicitly dark/off.
                angle >= offOpeningDeg && direction != Direction.CLOSING ->
                    false

                // On a close, do not light the front panel until 175 degrees.
                angle > onClosingDeg && direction == Direction.CLOSING ->
                    commandedPower ?: false

                // At/below 175 degrees the cover participates in continuity.
                angle <= onClosingDeg ->
                    true

                else ->
                    commandedPower ?: false
            }

        if (!powerWanted) {
            if (commandedPower != false) {
                commandedPower = false
                commandedBrightness = Float.NaN
                lastCommandMs = nowMs
                return Command(
                    powerOn = false,
                    brightness = null,
                    reason = "open-endpoint-off",
                )
            }
            return null
        }

        val targetBrightness =
            brightnessFor(
                angle = angle,
                innerReferenceBrightness = reference,
            )

        if (commandedPower != true) {
            commandedPower = true
            commandedBrightness = targetBrightness
            lastCommandMs = nowMs
            return Command(
                powerOn = true,
                brightness = targetBrightness,
                reason = "cover-wake",
            )
        }

        val elapsed =
            if (lastCommandMs == Long.MIN_VALUE) Long.MAX_VALUE
            else (nowMs - lastCommandMs).coerceAtLeast(0L)

        val materiallyChanged =
            !commandedBrightness.isFinite() ||
                abs(targetBrightness - commandedBrightness) >= minBrightnessDelta

        if (
            materiallyChanged &&
            elapsed >= minUpdateIntervalMs
        ) {
            commandedBrightness = targetBrightness
            lastCommandMs = nowMs
            return Command(
                powerOn = true,
                brightness = targetBrightness,
                reason = "hinge-brightness-ramp",
            )
        }

        return null
    }

    internal fun brightnessFor(
        angle: Float,
        innerReferenceBrightness: Float,
    ): Float {
        val reference =
            innerReferenceBrightness
                .coerceIn(minBrightness, 1f)

        if (angle <= matchBrightnessDeg) {
            return reference
        }

        if (angle >= onClosingDeg) {
            return minBrightness
        }

        val linear =
            ((onClosingDeg - angle) /
                (onClosingDeg - matchBrightnessDeg))
                .coerceIn(0f, 1f)

        // Smoothstep removes hard slope changes at both endpoints. The mild
        // gamma keeps the first few degrees deliberately dim while still
        // converging smoothly to the unfolded display level by 90 degrees.
        val smooth =
            linear * linear * (3f - 2f * linear)

        val perceptual =
            smooth
                .toDouble()
                .pow(BRIGHTNESS_GAMMA.toDouble())
                .toFloat()

        return (
            minBrightness +
                (reference - minBrightness) * perceptual
            )
            .coerceIn(minBrightness, reference)
    }

    companion object {
        const val POWER_ON_CLOSING_DEG = 175f
        const val POWER_OFF_OPENING_DEG = 177f
        const val MATCH_BRIGHTNESS_DEG = 90f
        const val MIN_BRIGHTNESS = 0.01f
        const val DEFAULT_INNER_REFERENCE = 0.50f
        const val BRIGHTNESS_GAMMA = 1.35f
        const val MIN_BRIGHTNESS_DELTA = 0.0125f
        const val MIN_UPDATE_INTERVAL_MS = 40L
    }
}
