package com.duoopen.overlay

/**
 * Continuity-only frame authority. Generic SnapshotCache may continue to serve
 * ordinary bridge behavior, but deterministic Fold7 continuity must select an
 * exact current-cycle lease from this store.
 */
internal class Fold7ContinuityFrameStore<T> {
    enum class Source {
        ACCESSIBILITY,
        SHIZUKU,
    }

    enum class TimestampQuality {
        EXACT_CAPTURE,
        REQUEST_BOUNDED,
    }

    data class CaptureTicket(
        val serviceEpoch: Long,
        val closeCycleId: Long,
        val captureSequence: Long,
        val width: Int,
        val height: Int,
        val requestStartedUptimeMs: Long,
        val source: Source,
    )

    data class FrameLease<T>(
        val serviceEpoch: Long,
        val closeCycleId: Long,
        val captureSequence: Long,
        val contentLeaseId: Long,
        val width: Int,
        val height: Int,
        val requestStartedUptimeMs: Long,
        val capturedUptimeMs: Long,
        val completedUptimeMs: Long,
        val source: Source,
        val timestampQuality: TimestampQuality,
        val payload: T,
    )

    private var activeCycle: Fold7CycleEnvelope.CloseCycle? = null
    private var nextCaptureSequence = 0L
    private var newestStartedCaptureSequence = 0L
    private var nextContentLeaseId = 0L
    private var latest: FrameLease<T>? = null

    fun beginCycle(
        cycle: Fold7CycleEnvelope.CloseCycle,
    ) {
        if (activeCycle == cycle) return
        activeCycle = cycle
        nextCaptureSequence = 0L
        newestStartedCaptureSequence = 0L
        latest = null
    }

    fun invalidateCycle(
        serviceEpoch: Long,
        closeCycleId: Long,
    ) {
        val current = activeCycle ?: return
        if (
            current.serviceEpoch != serviceEpoch ||
            current.closeCycleId != closeCycleId
        ) {
            return
        }
        activeCycle = null
        newestStartedCaptureSequence = 0L
        latest = null
    }

    fun beginCapture(
        cycle: Fold7CycleEnvelope.CloseCycle,
        width: Int,
        height: Int,
        requestStartedUptimeMs: Long,
        source: Source,
    ): CaptureTicket? {
        if (activeCycle != cycle) return null
        if (width <= 0 || height <= 0) return null

        // A newer capture attempt supersedes the previous frame immediately.
        // If this attempt later fails, current() must return null rather than
        // resurrecting an older same-cycle image.
        latest = null

        val sequence =
            ++nextCaptureSequence

        newestStartedCaptureSequence =
            sequence

        return CaptureTicket(
            serviceEpoch = cycle.serviceEpoch,
            closeCycleId = cycle.closeCycleId,
            captureSequence = sequence,
            width = width,
            height = height,
            requestStartedUptimeMs = requestStartedUptimeMs,
            source = source,
        )
    }

    fun publish(
        ticket: CaptureTicket,
        capturedUptimeMs: Long,
        completedUptimeMs: Long,
        timestampQuality: TimestampQuality,
        payload: T,
    ): FrameLease<T>? {
        val cycle = activeCycle ?: return null

        if (
            ticket.serviceEpoch != cycle.serviceEpoch ||
            ticket.closeCycleId != cycle.closeCycleId ||
            ticket.captureSequence <= 0L ||
            ticket.captureSequence != newestStartedCaptureSequence ||
            completedUptimeMs < ticket.requestStartedUptimeMs ||
            capturedUptimeMs > completedUptimeMs
        ) {
            return null
        }

        if (
            timestampQuality == TimestampQuality.EXACT_CAPTURE &&
            capturedUptimeMs < cycle.startedUptimeMs
        ) {
            return null
        }

        if (
            timestampQuality == TimestampQuality.REQUEST_BOUNDED &&
            ticket.requestStartedUptimeMs < cycle.startedUptimeMs
        ) {
            return null
        }

        val current = latest
        if (
            current != null &&
            ticket.captureSequence <= current.captureSequence
        ) {
            return null
        }

        return FrameLease(
            serviceEpoch = cycle.serviceEpoch,
            closeCycleId = cycle.closeCycleId,
            captureSequence = ticket.captureSequence,
            contentLeaseId = ++nextContentLeaseId,
            width = ticket.width,
            height = ticket.height,
            requestStartedUptimeMs = ticket.requestStartedUptimeMs,
            capturedUptimeMs = capturedUptimeMs,
            completedUptimeMs = completedUptimeMs,
            source = ticket.source,
            timestampQuality = timestampQuality,
            payload = payload,
        ).also {
            latest = it
        }
    }

    fun current(
        cycle: Fold7CycleEnvelope.CloseCycle,
        nowUptimeMs: Long,
        maxAgeMs: Long,
        width: Int,
        height: Int,
    ): FrameLease<T>? {
        if (activeCycle != cycle) return null

        val frame = latest ?: return null
        if (
            frame.serviceEpoch != cycle.serviceEpoch ||
            frame.closeCycleId != cycle.closeCycleId ||
            frame.width != width ||
            frame.height != height
        ) {
            return null
        }

        val age = nowUptimeMs - frame.capturedUptimeMs
        if (age < 0L || age > maxAgeMs) return null

        return frame
    }
}
