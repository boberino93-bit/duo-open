package rnd.fold7

enum class CaptureSource { ACCESSIBILITY, SHIZUKU }
enum class TimestampQuality { EXACT_CAPTURE, REQUEST_BOUNDED }

data class FrameCandidate(
    val serviceEpoch: Long,
    val closeCycleId: Long,
    val captureSequence: Long,
    val width: Int,
    val height: Int,
    val requestStartedAtMs: Long,
    val capturedAtMs: Long,
    val completedAtMs: Long,
    val source: CaptureSource,
    val timestampQuality: TimestampQuality,
    val contentId: String,
)

data class FrameLease(
    val serviceEpoch: Long,
    val closeCycleId: Long,
    val captureSequence: Long,
    val capturedAtMs: Long,
    val source: CaptureSource,
    val timestampQuality: TimestampQuality,
    val contentId: String,
)

/**
 * Reduced model of CURRENT main's continuity selection semantics:
 * panel kind + dimensions + wall-clock age are sufficient.
 */
class BaselineAgeOnlyFrameCache(private val maxAgeMs: Long) {
    data class Entry(
        val width: Int,
        val height: Int,
        val storedAtMs: Long,
        val contentId: String,
    )

    private var inner: Entry? = null

    fun putInner(width: Int, height: Int, storedAtMs: Long, contentId: String) {
        inner = Entry(width, height, storedAtMs, contentId)
    }

    fun getInner(width: Int, height: Int, nowMs: Long): Entry? {
        val e = inner ?: return null
        if (e.width != width || e.height != height) return null
        if (nowMs - e.storedAtMs > maxAgeMs) return null
        return e
    }
}

/**
 * Generation-2 continuity-frame ownership model.
 *
 * A closeCycleId is stable across CLOSING_INTENT -> PREWARM -> READY -> VISUAL,
 * but is invalidated on reversal/native takeover/service restart. A frame is
 * eligible only if its provenance proves it belongs to that exact cycle.
 */
class ContinuityFrameLeaseStore(
    private val serviceEpoch: Long,
    private val expectedWidth: Int = 1968,
    private val expectedHeight: Int = 2184,
    private val maxAgeMs: Long = 10_000L,
) {
    data class ActiveCycle(
        val id: Long,
        val startedAtMs: Long,
    )

    private var activeCycle: ActiveCycle? = null
    private var currentFrame: FrameCandidate? = null
    private var lastAcceptedSequence = Long.MIN_VALUE

    fun beginCloseCycle(cycleId: Long, startedAtMs: Long) {
        require(cycleId >= 0L)
        activeCycle = ActiveCycle(cycleId, startedAtMs)
        currentFrame = null
        lastAcceptedSequence = Long.MIN_VALUE
    }

    fun invalidateCloseCycle(cycleId: Long) {
        if (activeCycle?.id == cycleId) {
            activeCycle = null
            currentFrame = null
            lastAcceptedSequence = Long.MIN_VALUE
        }
    }

    fun publish(candidate: FrameCandidate): Boolean {
        val cycle = activeCycle ?: return false
        if (candidate.serviceEpoch != serviceEpoch) return false
        if (candidate.closeCycleId != cycle.id) return false
        if (candidate.width != expectedWidth || candidate.height != expectedHeight) return false
        if (candidate.captureSequence <= lastAcceptedSequence) return false
        if (candidate.completedAtMs < candidate.requestStartedAtMs) return false
        if (candidate.capturedAtMs > candidate.completedAtMs) return false

        when (candidate.timestampQuality) {
            TimestampQuality.EXACT_CAPTURE -> {
                // Accessibility ScreenshotResult.timestamp can prove the actual capture instant.
                if (candidate.capturedAtMs < cycle.startedAtMs) return false
            }
            TimestampQuality.REQUEST_BOUNDED -> {
                // Without an exact capture timestamp, fail closed if the request itself predates the cycle.
                if (candidate.requestStartedAtMs < cycle.startedAtMs) return false
                if (candidate.capturedAtMs < candidate.requestStartedAtMs) return false
            }
        }

        currentFrame = candidate
        lastAcceptedSequence = candidate.captureSequence
        return true
    }

    fun leaseForVisual(cycleId: Long, nowMs: Long): FrameLease? {
        val cycle = activeCycle ?: return null
        if (cycle.id != cycleId) return null
        val frame = currentFrame ?: return null
        if (frame.serviceEpoch != serviceEpoch || frame.closeCycleId != cycle.id) return null
        if (frame.capturedAtMs < cycle.startedAtMs) return null
        if (nowMs < frame.capturedAtMs) return null
        if (nowMs - frame.capturedAtMs > maxAgeMs) return null

        return FrameLease(
            serviceEpoch = frame.serviceEpoch,
            closeCycleId = frame.closeCycleId,
            captureSequence = frame.captureSequence,
            capturedAtMs = frame.capturedAtMs,
            source = frame.source,
            timestampQuality = frame.timestampQuality,
            contentId = frame.contentId,
        )
    }

    fun activeCycleId(): Long? = activeCycle?.id
    fun activeCycleStartedAtMs(): Long? = activeCycle?.startedAtMs
}
