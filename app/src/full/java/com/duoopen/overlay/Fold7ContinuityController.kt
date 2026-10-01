package com.duoopen.overlay

/**
 * Fold7-specific continuity state machine.
 *
 * This class is intentionally Android-free so every transition can be unit
 * tested without a device or framework objects. Physical panel identity is
 * represented by geometry/topology facts; logical display ids are diagnostic
 * only and are never retained as identity.
 */
internal class Fold7ContinuityController(
    private val onTransition: (Transition) -> Unit = {},
) {
    enum class State {
        OPEN_INNER,
        CLOSING_INTENT,
        COVER_PREWARMING,
        COVER_READY_HIDDEN,
        COVER_VISUAL,
        NATIVE_COVER,
        OPENING_FROM_CLOSED,
        INNER_HANDOFF,
    }

    enum class Direction {
        OPENING,
        CLOSING,
        STEADY,
    }

    data class Topology(
        val innerLogicalId: Int?,
        val coverLogicalId: Int?,
        val innerActive: Boolean,
        val coverActive: Boolean,
        val innerIsDefault: Boolean,
        val coverIsDefault: Boolean,
    ) {
        val nativeCover: Boolean
            get() = coverActive && coverIsDefault && !innerActive

        val nativeInner: Boolean
            get() = innerActive && innerIsDefault
    }

    sealed interface Action {
        val generation: Long

        data class BeginPrewarm(
            override val generation: Long,
        ) : Action

        data class WakeInner(
            override val generation: Long,
        ) : Action

        data class ShowMirror(
            override val generation: Long,
        ) : Action

        data class HideMirror(
            override val generation: Long,
        ) : Action

        data class ReleaseSecondary(
            override val generation: Long,
        ) : Action
    }

    data class Transition(
        val from: State,
        val to: State,
        val generation: Long,
        val angle: Float,
        val direction: Direction,
        val reason: String,
        val topology: Topology,
    )

    data class Decision(
        val state: State,
        val generation: Long,
        val actions: List<Action>,
    )

    var state: State = State.OPEN_INNER
        private set

    var generation: Long = 0L
        private set

    var direction: Direction = Direction.STEADY
        private set

    private var lastAngle = Float.NaN
    private var lastSampleMs = 0L

    private var intentStartAngle = Float.NaN
    private var intentStartMs = 0L
    private var intentSamples = 0
    private var intentLastAngle = Float.NaN

    private var closingFloorAngle = Float.NaN
    private var prewarmRetryAfterMs = 0L
    private var activePrewarmGeneration = -1L

    fun isGenerationCurrent(candidate: Long): Boolean =
        candidate == generation

    fun reset(
        angle: Float,
        nowMs: Long,
        topology: Topology,
    ): Decision {
        generation++
        activePrewarmGeneration = -1L
        prewarmRetryAfterMs = 0L
        resetIntent()

        lastAngle = angle.takeIf { it.isFinite() } ?: Float.NaN
        lastSampleMs = nowMs
        direction = Direction.STEADY

        state = when {
            topology.nativeCover ||
                (
                    angle.isFinite() &&
                        angle <= NATIVE_COVER_MAX_DEG &&
                        topology.coverActive &&
                        !topology.innerActive
                    ) ->
                State.NATIVE_COVER

            angle.isFinite() &&
                angle >= OPEN_LATCH_DEG &&
                topology.innerActive ->
                State.OPEN_INNER

            topology.innerActive ->
                State.INNER_HANDOFF

            else ->
                State.OPEN_INNER
        }

        return decision()
    }

    fun onTopology(
        angle: Float,
        nowMs: Long,
        topology: Topology,
    ): Decision =
        reduce(
            angle = angle,
            nowMs = nowMs,
            topology = topology,
            sampleMotion = false,
        )

    fun onHinge(
        angle: Float,
        nowMs: Long,
        topology: Topology,
    ): Decision =
        reduce(
            angle = angle,
            nowMs = nowMs,
            topology = topology,
            sampleMotion = true,
        )

    fun onPrewarmResult(
        requestGeneration: Long,
        ok: Boolean,
        nowMs: Long,
        topology: Topology,
    ): Decision {
        val actions = mutableListOf<Action>()
        val angle = lastAngle.takeIf { it.isFinite() } ?: 180f

        if (
            requestGeneration != activePrewarmGeneration ||
            state != State.COVER_PREWARMING
        ) {
            // The asynchronous operation completed after a reversal/state change.
            // If it actually enabled anything, immediately hand it back to Samsung.
            if (ok) {
                actions += Action.ReleaseSecondary(generation)
            }
            return decision(actions)
        }

        activePrewarmGeneration = -1L

        if (!ok) {
            transition(
                to = State.CLOSING_INTENT,
                angle = angle,
                reason = "prewarm-failed",
                topology = topology,
            )
            prewarmRetryAfterMs = nowMs + PREWARM_RETRY_MS
            return decision(actions)
        }

        transition(
            to = State.COVER_READY_HIDDEN,
            angle = angle,
            reason = "prewarm-ready-hidden",
            topology = topology,
        )

        if (
            angle <= COVER_VISUAL_START_DEG &&
            direction != Direction.OPENING
        ) {
            transition(
                to = State.COVER_VISUAL,
                angle = angle,
                reason = "visual-threshold-already-crossed",
                topology = topology,
            )
            actions += Action.ShowMirror(generation)
        }

        return decision(actions)
    }

    private fun reduce(
        angle: Float,
        nowMs: Long,
        topology: Topology,
        sampleMotion: Boolean,
    ): Decision {
        if (!angle.isFinite()) return decision()

        val actions = mutableListOf<Action>()
        val previous = lastAngle
        val previousSampleMs = lastSampleMs

        if (sampleMotion) {
            direction = when {
                previous.isFinite() &&
                    angle - previous >= SAMPLE_EPSILON_DEG ->
                    Direction.OPENING

                previous.isFinite() &&
                    previous - angle >= SAMPLE_EPSILON_DEG ->
                    Direction.CLOSING

                else ->
                    Direction.STEADY
            }

            lastAngle = angle
            lastSampleMs = nowMs
        }

        // Native cover ownership wins immediately near the closed endpoint.
        if (
            topology.nativeCover &&
            angle <= NATIVE_COVER_MAX_DEG &&
            state != State.NATIVE_COVER
        ) {
            val wasVisual = state == State.COVER_VISUAL
            val hadSecondary = state in SECONDARY_STATES

            transition(
                to = State.NATIVE_COVER,
                angle = angle,
                reason = "native-cover-authoritative",
                topology = topology,
            )

            if (wasVisual) {
                actions += Action.HideMirror(generation)
            }

            if (hadSecondary) {
                actions += Action.ReleaseSecondary(generation)
            }

            activePrewarmGeneration = -1L
            resetIntent()

            return decision(actions)
        }

        // Stable fully-open endpoint. This keeps topology/angle jitter from
        // immediately re-entering the fold path.
        if (
            angle >= OPEN_LATCH_DEG &&
            topology.innerActive &&
            state in OPENING_STATES
        ) {
            transition(
                to = State.OPEN_INNER,
                angle = angle,
                reason = "inner-open-latched",
                topology = topology,
            )

            activePrewarmGeneration = -1L
            resetIntent()

            return decision(actions)
        }

        when (state) {
            State.NATIVE_COVER -> {
                if (
                    sampleMotion &&
                    direction == Direction.OPENING &&
                    previous.isFinite() &&
                    previous <= NATIVE_COVER_MAX_DEG &&
                    angle >= INNER_WAKE_MIN_DEG
                ) {
                    transition(
                        to = State.OPENING_FROM_CLOSED,
                        angle = angle,
                        reason = "early-inner-wake",
                        topology = topology,
                    )

                    /*
                     * Do not wait for Samsung to expose the inner logical route.
                     * The coordinator wakes the stable physical 1968x2184 panel.
                     * Logical ids remain disposable and are never cached.
                     */
                    actions += Action.WakeInner(generation)
                }
            }

            State.OPENING_FROM_CLOSED -> {
                if (
                    topology.innerActive ||
                    angle >= INNER_HANDOFF_MIN_DEG
                ) {
                    transition(
                        to = State.INNER_HANDOFF,
                        angle = angle,
                        reason = "inner-handoff-start",
                        topology = topology,
                    )
                }
            }

            State.OPEN_INNER,
            State.INNER_HANDOFF,
            -> {
                if (sampleMotion) {
                    val gapMs =
                        if (previousSampleMs == 0L) {
                            0L
                        } else {
                            (nowMs - previousSampleMs).coerceAtLeast(0L)
                        }

                    if (
                        consumeClosingIntent(
                            angle = angle,
                            previous = previous,
                            nowMs = nowMs,
                            sampleGapMs = gapMs,
                        )
                    ) {
                        transition(
                            to = State.CLOSING_INTENT,
                            angle = angle,
                            reason = "deliberate-close-detected",
                            topology = topology,
                        )

                        closingFloorAngle = angle

                        /*
                         * Fast-close path.
                         *
                         * A single hinge callback may both:
                         *
                         * 1. prove deliberate closing intent, and
                         * 2. already be below the early cover prewarm threshold.
                         *
                         * Waiting for another callback here adds avoidable latency
                         * and was the reason the fast-close unit tests failed.
                         *
                         * PREWARM still does NOT imply visibility. Successful
                         * completion enters COVER_READY_HIDDEN, and the mirror is
                         * independently gated by COVER_VISUAL_START_DEG.
                         */
                        if (
                            angle <= COVER_PREWARM_DEG &&
                            nowMs >= prewarmRetryAfterMs
                        ) {
                            transition(
                                to = State.COVER_PREWARMING,
                                angle = angle,
                                reason = "cover-prewarm-threshold",
                                topology = topology,
                            )

                            activePrewarmGeneration = generation
                            actions += Action.BeginPrewarm(generation)
                        }
                    }
                }
            }

            State.CLOSING_INTENT -> {
                updateClosingFloor(angle)

                if (hasOpeningReversal(angle)) {
                    val target =
                        if (angle >= OPEN_REARM_DEG) {
                            State.OPEN_INNER
                        } else {
                            State.INNER_HANDOFF
                        }

                    transition(
                        to = target,
                        angle = angle,
                        reason = "closing-intent-reversed",
                        topology = topology,
                    )

                    resetIntent()

                    return decision(actions)
                }

                if (
                    angle <= COVER_PREWARM_DEG &&
                    nowMs >= prewarmRetryAfterMs
                ) {
                    transition(
                        to = State.COVER_PREWARMING,
                        angle = angle,
                        reason = "cover-prewarm-threshold",
                        topology = topology,
                    )

                    activePrewarmGeneration = generation
                    actions += Action.BeginPrewarm(generation)
                }
            }

            State.COVER_PREWARMING -> {
                updateClosingFloor(angle)

                if (hasOpeningReversal(angle)) {
                    transition(
                        to = State.INNER_HANDOFF,
                        angle = angle,
                        reason = "prewarm-reversed",
                        topology = topology,
                    )

                    activePrewarmGeneration = -1L
                    actions += Action.ReleaseSecondary(generation)
                }
            }

            State.COVER_READY_HIDDEN -> {
                updateClosingFloor(angle)

                if (hasOpeningReversal(angle)) {
                    transition(
                        to = State.INNER_HANDOFF,
                        angle = angle,
                        reason = "hidden-cover-reversed",
                        topology = topology,
                    )

                    actions += Action.ReleaseSecondary(generation)

                    return decision(actions)
                }

                if (
                    direction != Direction.OPENING &&
                    angle <= COVER_VISUAL_START_DEG
                ) {
                    transition(
                        to = State.COVER_VISUAL,
                        angle = angle,
                        reason = "cover-visual-threshold",
                        topology = topology,
                    )

                    actions += Action.ShowMirror(generation)
                }
            }

            State.COVER_VISUAL -> {
                updateClosingFloor(angle)

                if (
                    hasOpeningReversal(angle) &&
                    angle >= COVER_VISUAL_HIDE_OPEN_DEG
                ) {
                    transition(
                        to = State.INNER_HANDOFF,
                        angle = angle,
                        reason = "cover-visual-reversed",
                        topology = topology,
                    )

                    actions += Action.HideMirror(generation)
                    actions += Action.ReleaseSecondary(generation)
                }
            }
        }

        return decision(actions)
    }

    private fun consumeClosingIntent(
        angle: Float,
        previous: Float,
        nowMs: Long,
        sampleGapMs: Long,
    ): Boolean {
        if (
            direction != Direction.CLOSING ||
            !previous.isFinite()
        ) {
            if (
                direction == Direction.OPENING &&
                intentLastAngle.isFinite() &&
                angle - intentLastAngle >= INTENT_REVERSAL_RESET_DEG
            ) {
                resetIntent()
            }

            return false
        }

        val strongSample =
            previous - angle >= STRONG_CLOSE_SAMPLE_DEG

        val expired =
            intentStartMs != 0L &&
                nowMs - intentStartMs > INTENT_WINDOW_MS

        val staleGap =
            sampleGapMs > INTENT_MAX_SAMPLE_GAP_MS

        if (
            intentStartAngle.isNaN() ||
            expired ||
            staleGap
        ) {
            intentStartAngle = previous
            intentStartMs = nowMs
            intentSamples = 1
        } else {
            intentSamples++
        }

        intentLastAngle = angle

        val travel =
            intentStartAngle - angle

        return strongSample ||
            (
                intentSamples >= INTENT_SAMPLE_COUNT &&
                    travel >= INTENT_TRAVEL_DEG &&
                    nowMs - intentStartMs <= INTENT_WINDOW_MS
                )
    }

    private fun updateClosingFloor(angle: Float) {
        if (
            closingFloorAngle.isNaN() ||
            angle < closingFloorAngle
        ) {
            closingFloorAngle = angle
        }
    }

    private fun hasOpeningReversal(angle: Float): Boolean =
        direction == Direction.OPENING &&
            closingFloorAngle.isFinite() &&
            angle - closingFloorAngle >= REVERSAL_HYSTERESIS_DEG

    private fun resetIntent() {
        intentStartAngle = Float.NaN
        intentStartMs = 0L
        intentSamples = 0
        intentLastAngle = Float.NaN
        closingFloorAngle = Float.NaN
    }

    private fun transition(
        to: State,
        angle: Float,
        reason: String,
        topology: Topology,
    ) {
        if (state == to) return

        val from = state

        state = to
        generation++

        onTransition(
            Transition(
                from = from,
                to = to,
                generation = generation,
                angle = angle,
                direction = direction,
                reason = reason,
                topology = topology,
            )
        )
    }

    private fun decision(
        actions: List<Action> = emptyList(),
    ): Decision =
        Decision(
            state = state,
            generation = generation,
            actions = actions,
        )

    companion object {
        const val NATIVE_COVER_MAX_DEG = 12f
        const val INNER_WAKE_MIN_DEG = 3f
        const val INNER_HANDOFF_MIN_DEG = 8f

        const val COVER_PREWARM_DEG = 174f
        const val COVER_VISUAL_START_DEG = 135f
        const val COVER_VISUAL_HIDE_OPEN_DEG = 140f

        const val OPEN_LATCH_DEG = 172f
        const val OPEN_REARM_DEG = 166f

        const val SAMPLE_EPSILON_DEG = 0.35f

        const val INTENT_TRAVEL_DEG = 3f
        const val INTENT_SAMPLE_COUNT = 3
        const val INTENT_WINDOW_MS = 1_800L
        const val INTENT_MAX_SAMPLE_GAP_MS = 700L
        const val INTENT_REVERSAL_RESET_DEG = 1.25f

        const val STRONG_CLOSE_SAMPLE_DEG = 5f
        const val REVERSAL_HYSTERESIS_DEG = 1.5f

        const val PREWARM_RETRY_MS = 180L

        private val SECONDARY_STATES =
            setOf(
                State.COVER_PREWARMING,
                State.COVER_READY_HIDDEN,
                State.COVER_VISUAL,
            )

        private val OPENING_STATES =
            setOf(
                State.OPENING_FROM_CLOSED,
                State.INNER_HANDOFF,
            )
    }
}
