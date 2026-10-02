package com.duoopen.overlay

import java.util.ArrayDeque

/**
 * R&D prototype: bounded, source-ordered hinge ingress mailbox.
 *
 * Intended producer: the existing serialized Fold7 control Handler.
 * Intended consumer: the main Handler.
 *
 * Unlike the current latest-only bridge, this preserves each accepted sample's
 * source observation time while a main-thread drain is pending. Capacity is
 * deliberately bounded. Overflow is explicit so the coordinator can fail
 * closed (invalidate the active privileged transition) instead of silently
 * pretending the stream remained continuous.
 *
 * PRODUCTION STATUS: R&D ONLY.
 */
internal class Fold7HingeIngressBatch(
    private val capacity: Int = DEFAULT_CAPACITY,
) {
    init {
        require(capacity >= MIN_CAPACITY) {
            "capacity must be >= $MIN_CAPACITY"
        }
    }

    data class Sample(
        val sequence: Long,
        val angle: Float,
        val observedUptimeMs: Long,
    )

    data class Drain(
        val samples: List<Sample>,
        val overflowed: Boolean,
        val droppedSamples: Int,
    )

    private val lock = Any()
    private val samples = ArrayDeque<Sample>(capacity)

    private var nextSequence = 1L
    private var drainPosted = false
    private var overflowed = false
    private var droppedSamples = 0

    /**
     * Adds one already-authorized hinge sample.
     *
     * @return true exactly when the caller must post one main-thread drain.
     */
    fun offer(
        angle: Float,
        observedUptimeMs: Long,
    ): Boolean {
        if (!angle.isFinite() || observedUptimeMs < 0L) {
            return false
        }

        synchronized(lock) {
            if (samples.size >= capacity) {
                samples.removeFirst()
                overflowed = true
                droppedSamples++
            }

            samples.addLast(
                Sample(
                    sequence = nextSequence++,
                    angle = angle.coerceIn(0f, 180f),
                    observedUptimeMs = observedUptimeMs,
                )
            )

            if (drainPosted) {
                return false
            }

            drainPosted = true
            return true
        }
    }

    /**
     * Atomically snapshots the pending batch and opens a new producer window.
     * A producer racing after this call will schedule a separate drain.
     */
    fun drain(): Drain =
        synchronized(lock) {
            val out = samples.toList()
            samples.clear()

            val result =
                Drain(
                    samples = out,
                    overflowed = overflowed,
                    droppedSamples = droppedSamples,
                )

            overflowed = false
            droppedSamples = 0
            drainPosted = false
            result
        }

    /** Service-destroy / failed-post cleanup. */
    fun reset() {
        synchronized(lock) {
            samples.clear()
            overflowed = false
            droppedSamples = 0
            drainPosted = false
        }
    }

    internal fun pendingSizeForTest(): Int =
        synchronized(lock) {
            samples.size
        }

    companion object {
        const val DEFAULT_CAPACITY = 32
        private const val MIN_CAPACITY = 4
    }
}
