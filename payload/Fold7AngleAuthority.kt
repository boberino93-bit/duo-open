package com.duoopen.fold

import kotlin.math.abs

/**
 * One Fold7 hinge-geometry authority.
 *
 * This class is intentionally Android-free. Producers may observe several angle
 * sources, but only this owner decides which sample is authoritative downstream.
 * A fresh Samsung precise lease wins while public samples continue to be retained
 * as a shadow fallback. When precise authority expires, a still-fresh public
 * sample is promoted without requiring another physical hinge movement.
 */
internal class Fold7AngleAuthority(
    private val preciseMaxAgeMs: Long = DEFAULT_PRECISE_MAX_AGE_MS,
    private val publicMaxAgeMs: Long = DEFAULT_PUBLIC_MAX_AGE_MS,
) {
    enum class Source {
        NONE,
        SAMSUNG_PRECISE,
        SYNTHETIC_ENDPOINT,
        PUBLIC_STANDARD,
        PUBLIC_VENDOR,
    }

    data class Output(
        val angle: Float,
        val observedUptimeMs: Long,
        val deliveredUptimeMs: Long,
        val source: Source,
        val coarse: Boolean,
        val reason: String,
    )

    data class Decision(
        val output: Output? = null,
        val accepted: Boolean = true,
        val stateChanged: Boolean = false,
        val dropReason: String? = null,
        val sourceAgeMs: Long = -1L,
    )

    data class Snapshot(
        val angle: Float,
        val source: Source,
        val observedUptimeMs: Long,
        val sourceAgeMs: Long,
        val coarse: Boolean,
        val preciseSession: Long,
        val preciseLeaseRemainingMs: Long,
        val publicShadowAngle: Float,
        val publicShadowAgeMs: Long,
        val droppedStalePrecise: Long,
        val droppedSessionPrecise: Long,
        val droppedSequencePrecise: Long,
    )

    private data class PublicCandidate(
        val angle: Float,
        val observedUptimeMs: Long,
        val receivedUptimeMs: Long,
        val source: Source,
        val coarse: Boolean,
    )

    private var currentSession = 0L
    private var lastPreciseSequence = 0L
    private var preciseValidUntilUptimeMs = Long.MIN_VALUE

    private var currentAngle = Float.NaN
    private var currentSource = Source.NONE
    private var currentObservedUptimeMs = 0L
    private var currentCoarse = false

    private var publicCandidate: PublicCandidate? = null

    private var droppedStalePrecise = 0L
    private var droppedSessionPrecise = 0L
    private var droppedSequencePrecise = 0L

    fun startPreciseSession(
        session: Long,
        nowUptimeMs: Long,
    ): Decision {
        if (session <= 0L || nowUptimeMs < 0L) {
            return Decision(
                accepted = false,
                dropReason = "invalid-session",
            )
        }

        val sourceWasPrecise =
            currentSource == Source.SAMSUNG_PRECISE ||
                currentSource == Source.SYNTHETIC_ENDPOINT

        currentSession = session
        lastPreciseSequence = 0L
        preciseValidUntilUptimeMs = Long.MIN_VALUE

        if (sourceWasPrecise) {
            currentSource = Source.NONE
            currentCoarse = false
        }

        return Decision(
            accepted = true,
            stateChanged = sourceWasPrecise,
        )
    }

    fun offerPrecise(
        session: Long,
        sequence: Long,
        angle: Float,
        observedUptimeMs: Long,
        receivedUptimeMs: Long,
    ): Decision {
        if (!angle.isFinite() || observedUptimeMs < 0L || receivedUptimeMs < 0L) {
            return Decision(
                accepted = false,
                dropReason = "invalid-sample",
            )
        }

        if (session != currentSession) {
            droppedSessionPrecise++
            return Decision(
                accepted = false,
                dropReason = "old-session",
            )
        }

        if (sequence <= lastPreciseSequence) {
            droppedSequencePrecise++
            return Decision(
                accepted = false,
                dropReason = "old-sequence",
            )
        }

        val ageMs = receivedUptimeMs - observedUptimeMs
        if (ageMs < 0L || ageMs > preciseMaxAgeMs) {
            droppedStalePrecise++
            return Decision(
                accepted = false,
                dropReason = "stale-source-age",
                sourceAgeMs = ageMs,
            )
        }

        lastPreciseSequence = sequence
        preciseValidUntilUptimeMs = observedUptimeMs + preciseMaxAgeMs

        val next = angle.coerceIn(0f, 180f)
        val sourceChanged = currentSource != Source.SAMSUNG_PRECISE
        val changed =
            currentAngle.isNaN() ||
                abs(next - currentAngle) >= CHANGE_EPSILON_DEG ||
                sourceChanged

        currentAngle = next
        currentSource = Source.SAMSUNG_PRECISE
        currentObservedUptimeMs = observedUptimeMs
        currentCoarse = false

        return Decision(
            output =
                if (changed) {
                    Output(
                        angle = next,
                        observedUptimeMs = observedUptimeMs,
                        deliveredUptimeMs = receivedUptimeMs,
                        source = Source.SAMSUNG_PRECISE,
                        coarse = false,
                        reason = "precise-accept",
                    )
                } else {
                    null
                },
            accepted = true,
            stateChanged = sourceChanged,
            sourceAgeMs = ageMs,
        )
    }

    /**
     * Session-scoped endpoint bridge. It may alter the presented angle but never
     * extends the lifetime of the last real Samsung sample.
     */
    fun offerSyntheticEndpoint(
        session: Long,
        angle: Float,
        nowUptimeMs: Long,
        reason: String,
    ): Decision {
        if (
            session != currentSession ||
            !angle.isFinite() ||
            nowUptimeMs < 0L ||
            nowUptimeMs > preciseValidUntilUptimeMs
        ) {
            return Decision(
                accepted = false,
                dropReason = "synthetic-outside-precise-lease",
            )
        }

        val next = angle.coerceIn(0f, 180f)
        val sourceChanged = currentSource != Source.SYNTHETIC_ENDPOINT
        val changed =
            currentAngle.isNaN() ||
                abs(next - currentAngle) >= CHANGE_EPSILON_DEG ||
                sourceChanged

        currentAngle = next
        currentSource = Source.SYNTHETIC_ENDPOINT
        currentObservedUptimeMs = nowUptimeMs
        currentCoarse = false

        return Decision(
            output =
                if (changed) {
                    Output(
                        angle = next,
                        observedUptimeMs = nowUptimeMs,
                        deliveredUptimeMs = nowUptimeMs,
                        source = Source.SYNTHETIC_ENDPOINT,
                        coarse = false,
                        reason = reason,
                    )
                } else {
                    null
                },
            accepted = true,
            stateChanged = sourceChanged,
        )
    }

    fun offerPublic(
        source: Source,
        angle: Float,
        observedUptimeMs: Long,
        receivedUptimeMs: Long,
        coarse: Boolean,
    ): Decision {
        require(
            source == Source.PUBLIC_STANDARD ||
                source == Source.PUBLIC_VENDOR
        ) {
            "public sample must use a public source"
        }

        if (!angle.isFinite() || observedUptimeMs < 0L || receivedUptimeMs < 0L) {
            return Decision(
                accepted = false,
                dropReason = "invalid-public-sample",
            )
        }

        val ageMs = receivedUptimeMs - observedUptimeMs
        if (ageMs < 0L || ageMs > publicMaxAgeMs) {
            return Decision(
                accepted = false,
                dropReason = "stale-public-sample",
                sourceAgeMs = ageMs,
            )
        }

        val next = angle.coerceIn(0f, 180f)
        publicCandidate =
            PublicCandidate(
                angle = next,
                observedUptimeMs = observedUptimeMs,
                receivedUptimeMs = receivedUptimeMs,
                source = source,
                coarse = coarse,
            )

        if (receivedUptimeMs <= preciseValidUntilUptimeMs) {
            return Decision(
                accepted = true,
                sourceAgeMs = ageMs,
            )
        }

        return promotePublic(
            nowUptimeMs = receivedUptimeMs,
            reason = "public-current",
        )
    }

    fun expirePrecise(
        nowUptimeMs: Long,
        reason: String,
    ): Decision {
        if (nowUptimeMs <= preciseValidUntilUptimeMs) {
            return Decision(accepted = true)
        }

        if (
            currentSource != Source.SAMSUNG_PRECISE &&
            currentSource != Source.SYNTHETIC_ENDPOINT
        ) {
            return Decision(accepted = true)
        }

        val promoted =
            promotePublic(
                nowUptimeMs = nowUptimeMs,
                reason = reason,
            )

        if (promoted.output != null) {
            return promoted.copy(stateChanged = true)
        }

        val changed = currentSource != Source.NONE
        currentSource = Source.NONE
        currentCoarse = false

        return Decision(
            accepted = true,
            stateChanged = changed,
        )
    }

    fun revokePreciseSession(
        session: Long,
        nowUptimeMs: Long,
        reason: String,
    ): Decision {
        if (session != currentSession) {
            return Decision(
                accepted = false,
                dropReason = "revoke-old-session",
            )
        }

        preciseValidUntilUptimeMs = Long.MIN_VALUE
        lastPreciseSequence = 0L
        currentSession = session + 1L

        if (
            currentSource != Source.SAMSUNG_PRECISE &&
            currentSource != Source.SYNTHETIC_ENDPOINT
        ) {
            return Decision(accepted = true)
        }

        val promoted =
            promotePublic(
                nowUptimeMs = nowUptimeMs,
                reason = reason,
            )

        if (promoted.output != null) {
            return promoted.copy(stateChanged = true)
        }

        currentSource = Source.NONE
        currentCoarse = false
        return Decision(
            accepted = true,
            stateChanged = true,
        )
    }

    fun nextPreciseExpiryUptimeMs(): Long? =
        preciseValidUntilUptimeMs
            .takeIf {
                it != Long.MIN_VALUE &&
                    (
                        currentSource == Source.SAMSUNG_PRECISE ||
                            currentSource == Source.SYNTHETIC_ENDPOINT
                        )
            }

    fun snapshot(
        nowUptimeMs: Long,
    ): Snapshot {
        val sourceAge =
            if (currentObservedUptimeMs <= 0L) {
                Long.MAX_VALUE
            } else {
                (nowUptimeMs - currentObservedUptimeMs).coerceAtLeast(0L)
            }

        val shadow = publicCandidate
        val shadowAge =
            if (shadow == null) {
                Long.MAX_VALUE
            } else {
                (nowUptimeMs - shadow.observedUptimeMs).coerceAtLeast(0L)
            }

        return Snapshot(
            angle = currentAngle,
            source = currentSource,
            observedUptimeMs = currentObservedUptimeMs,
            sourceAgeMs = sourceAge,
            coarse = currentCoarse,
            preciseSession = currentSession,
            preciseLeaseRemainingMs =
                (preciseValidUntilUptimeMs - nowUptimeMs)
                    .coerceAtLeast(0L),
            publicShadowAngle = shadow?.angle ?: Float.NaN,
            publicShadowAgeMs = shadowAge,
            droppedStalePrecise = droppedStalePrecise,
            droppedSessionPrecise = droppedSessionPrecise,
            droppedSequencePrecise = droppedSequencePrecise,
        )
    }

    private fun promotePublic(
        nowUptimeMs: Long,
        reason: String,
    ): Decision {
        val candidate = publicCandidate
            ?: return Decision(accepted = true)

        val ageMs = nowUptimeMs - candidate.observedUptimeMs
        if (ageMs < 0L || ageMs > publicMaxAgeMs) {
            publicCandidate = null
            return Decision(
                accepted = false,
                dropReason = "public-shadow-stale",
                sourceAgeMs = ageMs,
            )
        }

        val sourceChanged = currentSource != candidate.source
        val changed =
            currentAngle.isNaN() ||
                abs(candidate.angle - currentAngle) >= CHANGE_EPSILON_DEG ||
                sourceChanged

        currentAngle = candidate.angle
        currentSource = candidate.source
        currentObservedUptimeMs = candidate.observedUptimeMs
        currentCoarse = candidate.coarse
        publicCandidate = null

        return Decision(
            output =
                if (changed) {
                    Output(
                        angle = currentAngle,
                        observedUptimeMs = currentObservedUptimeMs,
                        deliveredUptimeMs = nowUptimeMs,
                        source = currentSource,
                        coarse = currentCoarse,
                        reason = reason,
                    )
                } else {
                    null
                },
            accepted = true,
            stateChanged = sourceChanged,
            sourceAgeMs = ageMs,
        )
    }

    companion object {
        /**
         * Alpha3 field budget. This is intentionally finite and conservative.
         * It is 2x the current 96 ms FoldInteractive poll timeout and must be
         * replaced by a measured Fold7 p99/p99.9 budget after field capture.
         */
        const val DEFAULT_PRECISE_MAX_AGE_MS = 192L
        const val DEFAULT_PUBLIC_MAX_AGE_MS = 3_000L
        private const val CHANGE_EPSILON_DEG = 0.10f
    }
}
