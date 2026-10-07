package com.duoopen.overlay

import java.util.concurrent.atomic.AtomicLong

/**
 * Owns asynchronous visual frames for one active Fold7 transition generation.
 *
 * A capture may finish after detach/re-attach or after a newer transition has
 * started. Only the epoch that is still current may publish its pixels.
 */
internal class Fold7TransitionEpoch {
    private val epoch = AtomicLong(0L)

    fun begin(): Long =
        epoch.incrementAndGet()

    fun invalidate() {
        epoch.incrementAndGet()
    }

    fun owns(candidate: Long): Boolean =
        epoch.get() == candidate
}
