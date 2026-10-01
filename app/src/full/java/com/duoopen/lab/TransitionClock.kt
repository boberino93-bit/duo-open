package com.duoopen.lab

import android.os.SystemClock
import kotlin.math.max

/**
 * Canonical Transition Lab clock.
 *
 * Canonical comparison domain:
 *   CLOCK_MONOTONIC / System.nanoTime() nanoseconds.
 *
 * Android documents Choreographer FrameTimeline, SurfaceControl latch timestamps,
 * and SyncFence signal timestamps in this comparison domain.
 *
 * SensorEvent.timestamp is NOT directly in this domain: it follows
 * elapsedRealtimeNanos(), which includes deep sleep. Convert it with a sampled
 * elapsed<->uptime anchor before comparing it with frame/surface timestamps.
 *
 * Wall-clock timestamps are never subtracted from monotonic timestamps directly.
 */
internal object TransitionClock {
    const val NS_PER_MS = 1_000_000L

    /** CLOCK_MONOTONIC-style uptime nanoseconds. */
    fun nowNs(): Long = System.nanoTime()

    fun uptimeMsToNs(uptimeMs: Long): Long =
        uptimeMs * NS_PER_MS

    data class ElapsedRealtimeAnchor(
        val elapsedRealtimeNs: Long,
        val uptimeNs: Long,
        /** Half-width of the sampling window. */
        val samplingUncertaintyNs: Long,
    )

    /**
     * Capture an offset anchor for converting SensorEvent.timestamp
     * (elapsedRealtimeNanos domain) into the lab's uptime domain.
     */
    fun captureElapsedRealtimeAnchor(): ElapsedRealtimeAnchor {
        val before = nowNs()
        val elapsed = SystemClock.elapsedRealtimeNanos()
        val after = nowNs()

        return ElapsedRealtimeAnchor(
            elapsedRealtimeNs = elapsed,
            uptimeNs = midpoint(before, after),
            samplingUncertaintyNs = max(0L, (after - before) / 2L),
        )
    }

    fun elapsedRealtimeToUptimeNs(
        elapsedRealtimeNs: Long,
        anchor: ElapsedRealtimeAnchor,
    ): Long {
        val elapsedMinusUptime =
            anchor.elapsedRealtimeNs - anchor.uptimeNs

        return elapsedRealtimeNs - elapsedMinusUptime
    }

    data class WallClockAnchor(
        val wallTimeMs: Long,
        val uptimeNs: Long,
        /**
         * Sampling-window uncertainty only. The source wall timestamp can add
         * further quantization / log-delivery uncertainty and must be tracked
         * separately by the caller.
         */
        val samplingUncertaintyNs: Long,
    )

    /**
     * Capture a wall<->uptime anchor. Intended for Samsung logcat epoch
     * timestamps. The midpoint reduces skew caused by the clock reads.
     */
    fun captureWallClockAnchor(): WallClockAnchor {
        val before = nowNs()
        val wall = System.currentTimeMillis()
        val after = nowNs()

        return WallClockAnchor(
            wallTimeMs = wall,
            uptimeNs = midpoint(before, after),
            samplingUncertaintyNs = max(0L, (after - before) / 2L),
        )
    }

    /**
     * Convert a wall-clock epoch millisecond timestamp into the canonical
     * uptime domain using an explicit anchor.
     *
     * This does NOT make a wall timestamp "exact". The resulting sample should
     * be tagged ESTIMATED_WALL_TO_UPTIME.
     */
    fun epochMsToUptimeNs(
        epochMs: Long,
        anchor: WallClockAnchor,
    ): Long =
        anchor.uptimeNs -
            ((anchor.wallTimeMs - epochMs) * NS_PER_MS)

    private fun midpoint(
        a: Long,
        b: Long,
    ): Long =
        a + ((b - a) / 2L)
}
