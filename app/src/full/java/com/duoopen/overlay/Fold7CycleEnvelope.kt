package com.duoopen.overlay

/**
 * Stable identity for one AccessibilityService lifetime and one deliberate
 * Fold7 close cycle.
 *
 * This is intentionally separate from Fold7ContinuityController.generation:
 * the controller generation changes at every policy-state transition, while a
 * closeCycleId remains stable from deliberate close intent through cover
 * prewarm/readiness/visual handoff.
 */
internal class Fold7CycleEnvelope(
    val serviceEpoch: Long,
) {
    data class CloseCycle(
        val serviceEpoch: Long,
        val closeCycleId: Long,
        val startedUptimeMs: Long,
    )

    private var nextCloseCycleId = 0L
    private var active: CloseCycle? = null

    val activeCloseCycle: CloseCycle?
        get() = active

    fun beginClose(
        nowUptimeMs: Long,
    ): CloseCycle {
        active?.let { return it }

        return CloseCycle(
            serviceEpoch = serviceEpoch,
            closeCycleId = ++nextCloseCycleId,
            startedUptimeMs = nowUptimeMs,
        ).also {
            active = it
        }
    }

    fun invalidateClose(
        expectedCloseCycleId: Long? = null,
    ): CloseCycle? {
        val current = active ?: return null
        if (
            expectedCloseCycleId != null &&
            expectedCloseCycleId != current.closeCycleId
        ) {
            return null
        }
        active = null
        return current
    }

    fun isCurrent(
        serviceEpoch: Long,
        closeCycleId: Long,
    ): Boolean =
        active?.let {
            it.serviceEpoch == serviceEpoch &&
                it.closeCycleId == closeCycleId
        } == true
}
