package com.duoopen.lab

internal enum class LabLevel {
    OFF,
    BASIC,
    FULL_LAB,
}

internal enum class HingeSampleSource {
    SAMSUNG_FOLD_INTERACTIVE,
    PUBLIC_HINGE,
    COARSE_FALLBACK,
    SYNTHETIC_ENDPOINT,
}

internal enum class TimestampQuality {
    /** Native timestamp already in the canonical monotonic domain. */
    EXACT_MONOTONIC,

    /** Converted from SensorEvent.timestamp / elapsedRealtimeNanos. */
    CONVERTED_ELAPSED_REALTIME,

    /** Reconstructed from a wall-clock log timestamp plus an explicit anchor. */
    ESTIMATED_WALL_TO_UPTIME,

    /** No source timestamp exists; arrival time is the only usable instant. */
    ARRIVAL_ONLY,
}

internal data class HingeSampleRecord(
    val sequence: Long,
    val angleDegrees: Float,
    val sourceTimeNs: Long?,
    /** Binder callback entry for Samsung/Shizuku samples; null for direct local sources. */
    val binderArrivalTimeNs: Long?,
    /** Time at which the production consumer receives the sample on its delivery thread. */
    val consumerDeliveryTimeNs: Long,
    val source: HingeSampleSource,
    val timestampQuality: TimestampQuality,
    val synthetic: Boolean = false,
    val uncertaintyNs: Long? = null,
) {
    val sourceToBinderLagNs: Long?
        get() =
            if (sourceTimeNs != null && binderArrivalTimeNs != null) {
                (binderArrivalTimeNs - sourceTimeNs).coerceAtLeast(0L)
            } else {
                null
            }

    val binderToConsumerLagNs: Long?
        get() =
            binderArrivalTimeNs?.let {
                (consumerDeliveryTimeNs - it).coerceAtLeast(0L)
            }

    val sourceToConsumerLagNs: Long?
        get() =
            sourceTimeNs?.let {
                (consumerDeliveryTimeNs - it).coerceAtLeast(0L)
            }

    /** Compatibility name for the end-to-end source-to-consumer delivery lag. */
    val deliveryLagNs: Long?
        get() = sourceToConsumerLagNs
}

internal data class FramePlanRecord(
    val callbackTimeNs: Long,
    val frameTimeNs: Long,
    val expectedPresentationTimeNs: Long,
    val deadlineNs: Long,
    val vsyncId: Long,
    val latestHingeSequence: Long? = null,
    val measuredAngleDegrees: Float? = null,
    val visualAngleDegrees: Float? = null,
    val predictionLeadNs: Long? = null,
    val predictionConfidence: Float? = null,
)

internal enum class TransactionEventKind {
    INSTRUMENTED,
    SUBMITTED_ON_DRAW,
    COMMITTED,
    COMPLETED,
}

internal data class TransactionTimingRecord(
    val transactionSequence: Long,
    val kind: TransactionEventKind,
    val timeNs: Long,
    val vsyncId: Long? = null,
    val submissionAccepted: Boolean? = null,
    val latchTimeNs: Long? = null,
    val presentTimeNs: Long? = null,
    val presentFenceValid: Boolean? = null,
)
