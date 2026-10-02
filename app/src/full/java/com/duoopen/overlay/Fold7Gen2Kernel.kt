package com.duoopen.overlay

/**
 * Small composition root for Gen2 ownership. It does not perform Android side
 * effects; it only keeps the independent owners correlated to one physical
 * service/cycle lifetime.
 */
internal class Fold7Gen2Kernel<T>(
    serviceEpoch: Long,
) {
    data class CycleChange(
        val started: Fold7CycleEnvelope.CloseCycle? = null,
        val ended: Fold7CycleEnvelope.CloseCycle? = null,
    )

    val cycles = Fold7CycleEnvelope(serviceEpoch)
    val coverAuthority = Fold7CoverLeaseSnapshotGate()
    val coverReadiness = Fold7CoverReadiness()
    val frames = Fold7ContinuityFrameStore<T>()
    val primeOwner = Fold7ContinuityPrimeOwner()

    val activeCycle: Fold7CycleEnvelope.CloseCycle?
        get() = cycles.activeCloseCycle

    fun onTransition(
        from: Fold7ContinuityController.State,
        to: Fold7ContinuityController.State,
        nowUptimeMs: Long,
    ): CycleChange {
        if (
            to == Fold7ContinuityController.State.CLOSING_INTENT &&
            from in setOf(
                Fold7ContinuityController.State.OPEN_INNER,
                Fold7ContinuityController.State.INNER_HANDOFF,
            )
        ) {
            val cycle = cycles.beginClose(nowUptimeMs)
            frames.beginCycle(cycle)
            primeOwner.beginCycle(cycle)
            return CycleChange(started = cycle)
        }

        val current = activeCycle
        if (
            current != null &&
            to in setOf(
                Fold7ContinuityController.State.OPEN_INNER,
                Fold7ContinuityController.State.INNER_HANDOFF,
                Fold7ContinuityController.State.NATIVE_COVER,
            ) &&
            from in setOf(
                Fold7ContinuityController.State.CLOSING_INTENT,
                Fold7ContinuityController.State.COVER_PREWARMING,
                Fold7ContinuityController.State.COVER_READY_HIDDEN,
                Fold7ContinuityController.State.COVER_VISUAL,
            )
        ) {
            cycles.invalidateClose(current.closeCycleId)
            frames.invalidateCycle(current.serviceEpoch, current.closeCycleId)
            primeOwner.invalidate(current)
            coverReadiness.invalidate(current.serviceEpoch, current.closeCycleId)
            return CycleChange(ended = current)
        }

        return CycleChange()
    }

    fun cancelActiveCycle(): Fold7CycleEnvelope.CloseCycle? {
        val current = activeCycle ?: return null
        cycles.invalidateClose(current.closeCycleId)
        frames.invalidateCycle(current.serviceEpoch, current.closeCycleId)
        primeOwner.invalidate(current)
        coverReadiness.invalidate(current.serviceEpoch, current.closeCycleId)
        return current
    }

    fun destroy(): Fold7CycleEnvelope.CloseCycle? {
        val current = cancelActiveCycle()
        coverAuthority.invalidate()
        return current
    }
}
