package com.duoopen.overlay

enum class Fold7WakeReason {
    DEVICE_STATE_EDGE,
    VENDOR_ANGLE_EDGE,
    PRECISE_ANGLE_FALLBACK,
}

sealed interface Fold7EarlyWakeAction {
    data class WakeInner(
        val generation: Long,
        val reason: Fold7WakeReason,
    ) : Fold7EarlyWakeAction

    data class KickPreciseBurst(
        val generation: Long,
        val reason: Fold7WakeReason,
    ) : Fold7EarlyWakeAction
}

/**
 * Android-free Fold7 early-wake lease.
 *
 * Edge sources may make infrastructure ready earlier, but only a precise angle
 * is authoritative visual geometry. One wake lease may fire per confirmed
 * folded-rest generation. Startup already open/mid-fold never speculative-wakes.
 */
internal class Fold7EarlyWakeIngress(
    private val closedMaxDeg: Float = 12f,
    private val preciseFallbackMinDeg: Float = 3f,
    private val vendorMotionMinDeg: Float = 0.75f,
) {
    private var generation = 0L
    private var nativeCover = false
    private var foldedConfirmed = false
    private var wakeIssued = false
    private var lastPrecise = Float.NaN
    private var lastVendor = Float.NaN
    private var lastFoldedState: Boolean? = null

    val authoritativeAngle: Float
        get() = lastPrecise

    fun reset(
        nativeCover: Boolean,
        preciseAngle: Float? = null,
        folded: Boolean? = null,
    ) {
        generation++
        this.nativeCover = nativeCover
        wakeIssued = false
        lastPrecise = preciseAngle?.takeIf { it.isFinite() } ?: Float.NaN
        lastVendor = Float.NaN
        lastFoldedState = folded
        foldedConfirmed =
            folded == true ||
                (
                    nativeCover &&
                        lastPrecise.isFinite() &&
                        lastPrecise <= closedMaxDeg
                    )
    }

    fun onTopology(
        nativeCover: Boolean,
    ) {
        this.nativeCover = nativeCover
        if (!nativeCover) {
            wakeIssued = false
        }
    }

    fun onFoldedState(
        folded: Boolean,
    ): List<Fold7EarlyWakeAction> {
        val prior = lastFoldedState
        lastFoldedState = folded

        if (folded) {
            if (!foldedConfirmed) generation++
            foldedConfirmed = true
            wakeIssued = false
            return emptyList()
        }

        if (
            prior != true ||
            !foldedConfirmed ||
            !nativeCover
        ) {
            return emptyList()
        }

        return fire(
            Fold7WakeReason.DEVICE_STATE_EDGE
        )
    }

    fun onVendorAngle(
        angle: Float,
    ): List<Fold7EarlyWakeAction> {
        if (!angle.isFinite()) return emptyList()

        val previous = lastVendor
        lastVendor = angle

        if (
            !nativeCover ||
            !foldedConfirmed ||
            wakeIssued ||
            !previous.isFinite()
        ) {
            return emptyList()
        }

        if (
            previous <= closedMaxDeg &&
            angle - previous >= vendorMotionMinDeg
        ) {
            return fire(
                Fold7WakeReason.VENDOR_ANGLE_EDGE
            )
        }

        return emptyList()
    }

    fun onPreciseAngle(
        angle: Float,
    ): List<Fold7EarlyWakeAction> {
        if (!angle.isFinite()) return emptyList()

        val previous = lastPrecise
        lastPrecise = angle

        if (
            nativeCover &&
            angle <= closedMaxDeg
        ) {
            foldedConfirmed = true
        }

        if (
            !nativeCover ||
            !foldedConfirmed ||
            wakeIssued ||
            !previous.isFinite()
        ) {
            return emptyList()
        }

        if (
            previous <= closedMaxDeg &&
            angle >= preciseFallbackMinDeg &&
            angle > previous
        ) {
            return fire(
                Fold7WakeReason.PRECISE_ANGLE_FALLBACK
            )
        }

        return emptyList()
    }

    private fun fire(
        reason: Fold7WakeReason,
    ): List<Fold7EarlyWakeAction> {
        if (wakeIssued) return emptyList()
        wakeIssued = true

        return listOf(
            Fold7EarlyWakeAction.KickPreciseBurst(
                generation,
                reason,
            ),
            Fold7EarlyWakeAction.WakeInner(
                generation,
                reason,
            ),
        )
    }
}
