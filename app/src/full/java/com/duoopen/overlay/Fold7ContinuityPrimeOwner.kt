package com.duoopen.overlay

internal class Fold7ContinuityPrimeOwner(
    private val maxAttemptsPerCycle: Int = 3,
) {
    enum class State { IDLE, IN_FLIGHT, READY, RETRYABLE }
    enum class Source { SHIZUKU }

    data class AttemptToken(
        val serviceEpoch: Long,
        val closeCycleId: Long,
        val attemptSequence: Long,
        val source: Source,
    )

    data class Snapshot(
        val state: State,
        val serviceEpoch: Long,
        val closeCycleId: Long,
        val attemptSequence: Long,
        val source: Source?,
        val failureReason: String?,
    )

    private var state = State.IDLE
    private var serviceEpoch = 0L
    private var closeCycleId = 0L
    private var attemptSequence = 0L
    private var source: Source? = null
    private var failureReason: String? = null

    fun beginCycle(cycle: Fold7CycleEnvelope.CloseCycle) {
        if (serviceEpoch == cycle.serviceEpoch && closeCycleId == cycle.closeCycleId) return
        state = State.IDLE
        serviceEpoch = cycle.serviceEpoch
        closeCycleId = cycle.closeCycleId
        attemptSequence = 0L
        source = null
        failureReason = null
    }

    fun invalidate(cycle: Fold7CycleEnvelope.CloseCycle) {
        if (serviceEpoch != cycle.serviceEpoch || closeCycleId != cycle.closeCycleId) return
        clear()
    }

    fun reserve(cycle: Fold7CycleEnvelope.CloseCycle, requestedSource: Source): AttemptToken? {
        beginCycle(cycle)
        if (state == State.IN_FLIGHT || state == State.READY) return null
        if (attemptSequence >= maxAttemptsPerCycle) return null
        attemptSequence += 1L
        source = requestedSource
        failureReason = null
        state = State.IN_FLIGHT
        return token()
    }

    fun isCurrent(token: AttemptToken): Boolean =
        state == State.IN_FLIGHT && token == tokenOrNull()

    fun markReady(token: AttemptToken): Boolean {
        if (!isCurrent(token)) return false
        state = State.READY
        failureReason = null
        return true
    }

    fun markFailed(token: AttemptToken, reason: String): Boolean {
        if (!isCurrent(token)) return false
        state = State.RETRYABLE
        failureReason = reason
        return true
    }

    fun snapshot(): Snapshot = Snapshot(
        state = state,
        serviceEpoch = serviceEpoch,
        closeCycleId = closeCycleId,
        attemptSequence = attemptSequence,
        source = source,
        failureReason = failureReason,
    )

    private fun token(): AttemptToken = AttemptToken(
        serviceEpoch = serviceEpoch,
        closeCycleId = closeCycleId,
        attemptSequence = attemptSequence,
        source = source ?: error("attempt source missing"),
    )

    private fun tokenOrNull(): AttemptToken? =
        source?.let {
            AttemptToken(serviceEpoch, closeCycleId, attemptSequence, it)
        }

    private fun clear() {
        state = State.IDLE
        serviceEpoch = 0L
        closeCycleId = 0L
        attemptSequence = 0L
        source = null
        failureReason = null
    }
}
