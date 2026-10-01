package com.duoopen.lab

import android.content.Context
import com.duoopen.BuildConfig
import com.duoopen.debug.DuoDiagnostics
import java.io.File
import java.util.concurrent.atomic.AtomicLong

/**
 * Observation-only runtime for Transition Lab.
 *
 * Debug full builds default to BASIC, which records hinge timing events only.
 * Release builds default to OFF. FULL_LAB will later add vsync/transaction
 * instrumentation; merely adding this object must not change fold behavior.
 */
internal object TransitionLab {
    private val hingeSequence =
        AtomicLong(0L)

    @Volatile
    var level: LabLevel =
        if (BuildConfig.DEBUG) {
            LabLevel.BASIC
        } else {
            LabLevel.OFF
        }
        private set

    @Volatile
    var latestHingeSample: HingeSampleRecord? =
        null
        private set

    @Volatile
    private var writer:
        TransitionSessionWriter? = null

    private val recordedSamples =
        AtomicLong(0L)

    fun init(
        context: Context,
    ) {
        if (
            level == LabLevel.OFF ||
            writer != null
        ) {
            return
        }

        synchronized(this) {
            if (
                level == LabLevel.OFF ||
                writer != null
            ) {
                return
            }

            val directory =
                File(
                    context.applicationContext.filesDir,
                    "transition-lab",
                )

            val created =
                runCatching {
                    TransitionSessionWriter(
                        directory = directory,
                    )
                }.onFailure { error ->
                    DuoDiagnostics.event(
                        "transition-lab",
                        "session start failed",
                        error,
                    )
                }.getOrNull()
                    ?: return

            writer = created

            DuoDiagnostics.event(
                "transition-lab",
                "session started level=$level " +
                    "file=${created.file.absolutePath}",
            )
        }
    }

    fun recordSamsungSample(
        angleDegrees: Float,
        sourceUptimeMs: Long,
        binderArrivalTimeNs: Long,
        consumerDeliveryTimeNs: Long =
            TransitionClock.nowNs(),
    ): HingeSampleRecord? {
        if (
            level == LabLevel.OFF ||
            !angleDegrees.isFinite()
        ) {
            return null
        }

        val record =
            HingeSampleRecord(
                sequence =
                    hingeSequence.incrementAndGet(),
                angleDegrees =
                    angleDegrees,
                sourceTimeNs =
                    TransitionClock.uptimeMsToNs(
                        sourceUptimeMs
                    ),
                binderArrivalTimeNs =
                    binderArrivalTimeNs,
                consumerDeliveryTimeNs =
                    consumerDeliveryTimeNs,
                source =
                    HingeSampleSource.SAMSUNG_FOLD_INTERACTIVE,
                timestampQuality =
                    TimestampQuality.ESTIMATED_WALL_TO_UPTIME,
                synthetic =
                    false,
            )

        latestHingeSample =
            record

        writer?.record(
            record.toEvent(
                reason =
                    "Samsung FoldInteractive logcat sample",
            )
        )

        maybeLogSummary(record)

        return record
    }

    fun recordSyntheticEndpoint(
        angleDegrees: Float,
        reason: String,
        consumerDeliveryTimeNs: Long =
            TransitionClock.nowNs(),
    ): HingeSampleRecord? {
        if (
            level == LabLevel.OFF ||
            !angleDegrees.isFinite()
        ) {
            return null
        }

        val record =
            HingeSampleRecord(
                sequence =
                    hingeSequence.incrementAndGet(),
                angleDegrees =
                    angleDegrees,
                sourceTimeNs =
                    null,
                binderArrivalTimeNs =
                    null,
                consumerDeliveryTimeNs =
                    consumerDeliveryTimeNs,
                source =
                    HingeSampleSource.SYNTHETIC_ENDPOINT,
                timestampQuality =
                    TimestampQuality.ARRIVAL_ONLY,
                synthetic =
                    true,
            )

        latestHingeSample =
            record

        writer?.record(
            record.toEvent(
                reason = reason,
            )
        )

        return record
    }

    fun sessionFile(): File? =
        writer?.file

    fun droppedEventCount(): Long =
        writer?.droppedEventCount() ?: 0L

    private fun maybeLogSummary(
        record: HingeSampleRecord,
    ) {
        val count =
            recordedSamples.incrementAndGet()

        if (
            count == 1L ||
            count % SUMMARY_SAMPLE_INTERVAL == 0L
        ) {
            DuoDiagnostics.event(
                "transition-lab",
                "hinge samples=$count " +
                    "latest=${record.angleDegrees} " +
                    "sourceToBinderNs=${record.sourceToBinderLagNs} " +
                    "binderToConsumerNs=${record.binderToConsumerLagNs} " +
                    "sourceToConsumerNs=${record.sourceToConsumerLagNs} " +
                    "dropped=${droppedEventCount()}",
            )
        }
    }

    private fun HingeSampleRecord.toEvent(
        reason: String,
    ): TransitionEvent =
        TransitionEvent(
            timeNs =
                consumerDeliveryTimeNs,
            type =
                "hinge-sample",
            hingeSampleSequence =
                sequence,
            measuredAngle =
                angleDegrees,
            hingeSource =
                source.name,
            hingeSourceTimeNs =
                sourceTimeNs,
            hingeBinderArrivalTimeNs =
                binderArrivalTimeNs,
            hingeConsumerDeliveryTimeNs =
                consumerDeliveryTimeNs,
            timestampQuality =
                timestampQuality.name,
            sourceToBinderLagNs =
                sourceToBinderLagNs,
            binderToConsumerLagNs =
                binderToConsumerLagNs,
            sourceToConsumerLagNs =
                sourceToConsumerLagNs,
            reason =
                reason,
        )

    private const val SUMMARY_SAMPLE_INTERVAL =
        250L
}
