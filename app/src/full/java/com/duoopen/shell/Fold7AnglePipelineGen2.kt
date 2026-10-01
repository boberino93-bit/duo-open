package com.duoopen.shell

import kotlin.math.max

/**
 * Android-free ownership/backpressure model for Fold7 Samsung precise-angle polling.
 *
 * Invariants:
 * - one poll in flight per reader session;
 * - completion-paced scheduling with no catch-up burst;
 * - old-session samples/completions rejected;
 * - monotonically increasing sample ownership;
 * - latest-only presentation coalescing.
 */
internal class Fold7AnglePipelineGen2(
    private val targetPeriodMs: Long = 8L,
    private val minimumYieldMs: Long = 1L,
) {
    data class PollToken(
        val session: Long,
        val sequence: Long,
        val startedUptimeMs: Long,
    )

    data class Sample(
        val session: Long,
        val pollSequence: Long,
        val sampleSequence: Long,
        val angle: Float,
    )

    private var session = 0L
    private var nextPollSequence = 0L
    private var nextSampleSequence = 0L
    private var lastAcceptedSampleSequence = 0L
    private var inFlight: PollToken? = null
    private var latestPresentation: Sample? = null
    private var presentationPending = false

    val currentSession: Long
        get() = session

    val inFlightPoll: PollToken?
        get() = inFlight

    fun startSession(): Long {
        session++
        nextPollSequence = 0L
        nextSampleSequence = 0L
        lastAcceptedSampleSequence = 0L
        inFlight = null
        latestPresentation = null
        presentationPending = false
        return session
    }

    fun invalidateSession() {
        session++
        inFlight = null
        latestPresentation = null
        presentationPending = false
    }

    fun tryStartPoll(
        nowUptimeMs: Long,
    ): PollToken? {
        if (inFlight != null) return null

        return PollToken(
            session = session,
            sequence = ++nextPollSequence,
            startedUptimeMs = nowUptimeMs,
        ).also {
            inFlight = it
        }
    }

    fun completePoll(
        token: PollToken,
        completionUptimeMs: Long,
    ): Long? {
        val current = inFlight ?: return null

        if (
            token.session != session ||
            current.session != token.session ||
            current.sequence != token.sequence
        ) {
            return null
        }

        inFlight = null

        val roundTripMs =
            (completionUptimeMs - token.startedUptimeMs)
                .coerceAtLeast(0L)

        return max(
            minimumYieldMs,
            targetPeriodMs - roundTripMs,
        )
    }

    fun timeoutPoll(
        token: PollToken,
        timeoutUptimeMs: Long,
    ): Long? =
        completePoll(
            token = token,
            completionUptimeMs = timeoutUptimeMs,
        )

    fun nextSample(
        poll: PollToken,
        angle: Float,
    ): Sample? {
        if (
            poll.session != session ||
            !angle.isFinite() ||
            angle !in 0f..180f
        ) {
            return null
        }

        val current = inFlight ?: return null

        if (
            current.session != poll.session ||
            current.sequence != poll.sequence
        ) {
            return null
        }

        val sample =
            Sample(
                session = session,
                pollSequence = poll.sequence,
                sampleSequence = ++nextSampleSequence,
                angle = angle,
            )

        if (
            sample.sampleSequence <=
            lastAcceptedSampleSequence
        ) {
            return null
        }

        lastAcceptedSampleSequence =
            sample.sampleSequence

        return sample
    }

    /**
     * True means the caller must enqueue one main/presentation callback.
     * Later accepted samples replace the payload while that callback is pending.
     */
    fun offerPresentation(
        sample: Sample,
    ): Boolean {
        if (
            sample.session != session ||
            sample.sampleSequence <
            lastAcceptedSampleSequence
        ) {
            return false
        }

        latestPresentation = sample

        if (presentationPending) {
            return false
        }

        presentationPending = true
        return true
    }

    fun consumePresentation(): Sample? {
        val latest = latestPresentation
        latestPresentation = null
        presentationPending = false
        return latest
    }

    fun hasNewerPresentation(): Boolean =
        latestPresentation != null
}
