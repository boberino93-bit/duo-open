package com.duoopen.lab

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.view.SurfaceControl
import com.duoopen.BuildConfig
import com.duoopen.debug.DuoDiagnostics
import java.io.File
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicLong
import kotlin.math.abs

/**
 * Observation-only runtime for Transition Lab.
 *
 * Debug full builds use FULL_LAB, but expensive frame recording is armed only
 * around real movement / Fold7 state activity. Release builds remain OFF.
 *
 * FrameTimeline and SurfaceControl probes are observation-only in this baseline:
 * the lab does not call Transaction.setFrameTimeline() and does not alter the
 * production controller, renderer thresholds, display power, or mirror geometry.
 */
internal object TransitionLab {
    private val hingeSequence =
        AtomicLong(0L)

    @Volatile
    var level: LabLevel =
        if (BuildConfig.DEBUG) {
            LabLevel.FULL_LAB
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

    @Volatile
    private var publicHingeProbe:
        PublicHingeProbe? = null

    private var mainHandler:
        Handler? = null

    private var frameTimelineProbe:
        FrameTimelineProbe? = null

    private var surfaceTransactionProbe:
        SurfaceTransactionProbe? = null

    private var transactionExecutor:
        ExecutorService? = null

    @Volatile
    private var latestFramePlan:
        FramePlanRecord? = null

    @Volatile
    private var presentationWindowDeadlineNs =
        Long.MIN_VALUE

    @Volatile
    private var frameStartPosted =
        false

    @Volatile
    private var lastSamsungConsumerTimeNs =
        Long.MIN_VALUE

    private var lastSamsungAngle =
        Float.NaN

    private var lastPublicAngle =
        Float.NaN

    private val recordedSamsungSamples =
        AtomicLong(0L)

    private val recordedPublicSamples =
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

            val appContext =
                context.applicationContext

            val directory =
                File(
                    appContext.filesDir,
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

            mainHandler =
                Handler(
                    Looper.getMainLooper()
                )

            if (level == LabLevel.FULL_LAB) {
                val executor =
                    Executors.newSingleThreadExecutor { runnable ->
                        Thread(
                            runnable,
                            "DuoTransitionTx",
                        ).apply {
                            isDaemon = true
                        }
                    }

                transactionExecutor =
                    executor

                frameTimelineProbe =
                    FrameTimelineProbe(
                        sink =
                            ::recordFrame,
                    )

                surfaceTransactionProbe =
                    SurfaceTransactionProbe(
                        callbackExecutor =
                            executor,
                        sink =
                            ::recordTransaction,
                    )
            }

            /*
             * Existing Fold7ContinuityCoordinator diagnostics are synchronous
             * with the controller transition / effect milestone that emitted
             * them. Mirroring only the fold7-state category gives the lab a
             * precise monotonic timestamp without changing controller code.
             */
            DuoDiagnostics.observer =
                ::recordDiagnostic

            publicHingeProbe =
                PublicHingeProbe(
                    context = appContext,
                    sink =
                        ::recordPublicHingeSample,
                ).also {
                    it.start()
                }

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

        val movementDetected =
            lastSamsungAngle.isNaN() ||
                abs(
                    angleDegrees -
                        lastSamsungAngle
                ) >= MOVEMENT_EPS_DEG

        lastSamsungAngle =
            angleDegrees

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

        lastSamsungConsumerTimeNs =
            consumerDeliveryTimeNs

        latestHingeSample =
            record

        writer?.record(
            record.toEvent(
                reason =
                    "Samsung FoldInteractive logcat sample",
            )
        )

        if (movementDetected) {
            armPresentationWindow(
                atTimeNs =
                    consumerDeliveryTimeNs,
            )
        }

        val count =
            recordedSamsungSamples.incrementAndGet()

        if (
            count == 1L ||
            count % SUMMARY_SAMPLE_INTERVAL == 0L
        ) {
            DuoDiagnostics.event(
                "transition-lab",
                "Samsung hinge samples=$count " +
                    "latest=${record.angleDegrees} " +
                    "sourceToBinderNs=${record.sourceToBinderLagNs} " +
                    "binderToConsumerNs=${record.binderToConsumerLagNs} " +
                    "sourceToConsumerNs=${record.sourceToConsumerLagNs} " +
                    "dropped=${droppedEventCount()}",
            )
        }

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

        armPresentationWindow(
            atTimeNs =
                consumerDeliveryTimeNs,
        )

        return record
    }

    private fun recordPublicHingeSample(
        sample: PublicHingeProbe.Sample,
    ) {
        if (level == LabLevel.OFF) return

        /*
         * SensorEvent.timestamp is elapsedRealtimeNanos(). Convert it into the
         * lab's uptime/monotonic comparison domain with an explicit sampled
         * anchor and retain the anchor uncertainty instead of pretending the
         * conversion is exact.
         */
        val anchor =
            TransitionClock
                .captureElapsedRealtimeAnchor()

        val sourceTimeNs =
            TransitionClock
                .elapsedRealtimeToUptimeNs(
                    elapsedRealtimeNs =
                        sample.sensorTimestampNs,
                    anchor =
                        anchor,
                )

        val record =
            HingeSampleRecord(
                sequence =
                    hingeSequence.incrementAndGet(),
                angleDegrees =
                    sample.angleDegrees,
                sourceTimeNs =
                    sourceTimeNs,
                binderArrivalTimeNs =
                    null,
                consumerDeliveryTimeNs =
                    sample.callbackArrivalTimeNs,
                source =
                    if (sample.coarse) {
                        HingeSampleSource.COARSE_FALLBACK
                    } else {
                        HingeSampleSource.PUBLIC_HINGE
                    },
                timestampQuality =
                    TimestampQuality.CONVERTED_ELAPSED_REALTIME,
                synthetic =
                    false,
                uncertaintyNs =
                    anchor.samplingUncertaintyNs,
            )

        /*
         * Record public sensor traffic even while Samsung's finer source is
         * alive, but do not let an observed 0/90/180 callback become the
         * correlation anchor for controller events that are actually driven by
         * fresh Samsung samples.
         */
        val samsungFresh =
            lastSamsungConsumerTimeNs !=
                Long.MIN_VALUE &&
                sample.callbackArrivalTimeNs -
                    lastSamsungConsumerTimeNs in
                    0L..SAMSUNG_AUTHORITY_WINDOW_NS

        val movementDetected =
            lastPublicAngle.isNaN() ||
                abs(
                    sample.angleDegrees -
                        lastPublicAngle
                ) >= MOVEMENT_EPS_DEG

        lastPublicAngle =
            sample.angleDegrees

        if (!samsungFresh) {
            latestHingeSample =
                record

            if (movementDetected) {
                armPresentationWindow(
                    atTimeNs =
                        sample.callbackArrivalTimeNs,
                )
            }
        }

        writer?.record(
            record.toEvent(
                reason =
                    "public sensor=${sample.sensorName} " +
                        "type=${sample.sensorType} " +
                        "resolution=${sample.resolutionDegrees} " +
                        "samsungFresh=$samsungFresh",
            )
        )

        val count =
            recordedPublicSamples.incrementAndGet()

        if (
            count == 1L ||
            count % SUMMARY_SAMPLE_INTERVAL == 0L
        ) {
            DuoDiagnostics.event(
                "transition-lab",
                "public hinge samples=$count " +
                    "latest=${record.angleDegrees} " +
                    "sourceToConsumerNs=${record.sourceToConsumerLagNs} " +
                    "uncertaintyNs=${record.uncertaintyNs} " +
                    "samsungFresh=$samsungFresh",
            )
        }
    }

    /**
     * Timestamp the existing controller/effect diagnostics in the same clock
     * domain as the hinge samples. No production transition logic is modified.
     */
    private fun recordDiagnostic(
        category: String,
        message: String,
        timeNs: Long,
    ) {
        if (
            level == LabLevel.OFF ||
            category != FOLD7_STATE_CATEGORY
        ) {
            return
        }

        armPresentationWindow(
            atTimeNs =
                timeNs,
        )

        val hinge =
            latestHingeSample

        val transition =
            STATE_TRANSITION.find(
                message
            )

        val generation =
            GENERATION.find(
                message
            )?.groupValues
                ?.getOrNull(1)
                ?.toLongOrNull()

        writer?.record(
            TransitionEvent(
                timeNs =
                    timeNs,
                type =
                    if (transition != null) {
                        "state-transition"
                    } else {
                        "fold7-state"
                    },
                hingeSampleSequence =
                    hinge?.sequence,
                measuredAngle =
                    transition?.groupValues
                        ?.getOrNull(3)
                        ?.toFloatOrNull()
                        ?: hinge?.angleDegrees,
                hingeSource =
                    hinge?.source?.name,
                hingeSourceTimeNs =
                    hinge?.sourceTimeNs,
                hingeBinderArrivalTimeNs =
                    hinge?.binderArrivalTimeNs,
                hingeConsumerDeliveryTimeNs =
                    hinge?.consumerDeliveryTimeNs,
                timestampQuality =
                    hinge?.timestampQuality?.name,
                sourceToBinderLagNs =
                    hinge?.sourceToBinderLagNs,
                binderToConsumerLagNs =
                    hinge?.binderToConsumerLagNs,
                sourceToConsumerLagNs =
                    hinge?.sourceToConsumerLagNs,
                direction =
                    transition?.groupValues
                        ?.getOrNull(4),
                physicalState =
                    transition?.groupValues
                        ?.getOrNull(2),
                generation =
                    generation,
                reason =
                    message,
            )
        )
    }


    private fun armPresentationWindow(
        atTimeNs: Long =
            TransitionClock.nowNs(),
    ) {
        if (level != LabLevel.FULL_LAB) {
            return
        }

        val nextDeadline =
            atTimeNs +
                PRESENTATION_WINDOW_NS

        if (
            nextDeadline >
            presentationWindowDeadlineNs
        ) {
            presentationWindowDeadlineNs =
                nextDeadline
        }

        val probe =
            frameTimelineProbe
                ?: return

        if (
            probe.isRunning ||
            frameStartPosted
        ) {
            return
        }

        frameStartPosted =
            true

        mainHandler?.post {
            frameStartPosted =
                false

            if (
                level ==
                    LabLevel.FULL_LAB &&
                TransitionClock.nowNs() <=
                    presentationWindowDeadlineNs
            ) {
                probe.start()
            }
        }
    }

    private fun recordFrame(
        raw: FramePlanRecord,
    ) {
        if (
            level != LabLevel.FULL_LAB
        ) {
            return
        }

        if (
            raw.callbackTimeNs >
            presentationWindowDeadlineNs
        ) {
            latestFramePlan =
                null
            frameTimelineProbe?.stop()
            return
        }

        val hinge =
            latestHingeSample

        val frame =
            raw.copy(
                latestHingeSequence =
                    hinge?.sequence,
                measuredAngleDegrees =
                    hinge?.angleDegrees,
            )

        latestFramePlan =
            frame

        writer?.record(
            TransitionEvent(
                timeNs =
                    frame.callbackTimeNs,
                type =
                    "vsync",
                hingeSampleSequence =
                    hinge?.sequence,
                measuredAngle =
                    hinge?.angleDegrees,
                hingeSource =
                    hinge?.source?.name,
                hingeSourceTimeNs =
                    hinge?.sourceTimeNs,
                hingeBinderArrivalTimeNs =
                    hinge?.binderArrivalTimeNs,
                hingeConsumerDeliveryTimeNs =
                    hinge?.consumerDeliveryTimeNs,
                timestampQuality =
                    hinge?.timestampQuality?.name,
                sourceToBinderLagNs =
                    hinge?.sourceToBinderLagNs,
                binderToConsumerLagNs =
                    hinge?.binderToConsumerLagNs,
                sourceToConsumerLagNs =
                    hinge?.sourceToConsumerLagNs,
                vsyncId =
                    frame.vsyncId,
                frameTimeNs =
                    frame.frameTimeNs,
                deadlineNs =
                    frame.deadlineNs,
                expectedPresentNs =
                    frame.expectedPresentationTimeNs,
                reason =
                    "FrameTimeline preferred vsync",
            )
        )
    }

    fun instrumentTransaction(
        transaction: SurfaceControl.Transaction,
    ): SurfaceTransactionProbe.Token? {
        if (
            level != LabLevel.FULL_LAB
        ) {
            return null
        }

        armPresentationWindow()

        return surfaceTransactionProbe
            ?.instrument(
                transaction =
                    transaction,
                frame =
                    latestFramePlan,
            )
    }

    fun markTransactionSubmitted(
        token: SurfaceTransactionProbe.Token?,
        accepted: Boolean,
    ) {
        if (token == null) return

        surfaceTransactionProbe
            ?.markSubmittedOnDraw(
                token =
                    token,
                accepted =
                    accepted,
            )
    }

    private fun recordTransaction(
        record: TransactionTimingRecord,
    ) {
        if (
            level != LabLevel.FULL_LAB
        ) {
            return
        }

        val hinge =
            latestHingeSample

        writer?.record(
            TransitionEvent(
                timeNs =
                    record.timeNs,
                type =
                    "surface-transaction-" +
                        record.kind.name
                            .lowercase(),
                hingeSampleSequence =
                    hinge?.sequence,
                measuredAngle =
                    hinge?.angleDegrees,
                hingeSource =
                    hinge?.source?.name,
                hingeSourceTimeNs =
                    hinge?.sourceTimeNs,
                hingeBinderArrivalTimeNs =
                    hinge?.binderArrivalTimeNs,
                hingeConsumerDeliveryTimeNs =
                    hinge?.consumerDeliveryTimeNs,
                timestampQuality =
                    hinge?.timestampQuality?.name,
                sourceToBinderLagNs =
                    hinge?.sourceToBinderLagNs,
                binderToConsumerLagNs =
                    hinge?.binderToConsumerLagNs,
                sourceToConsumerLagNs =
                    hinge?.sourceToConsumerLagNs,
                vsyncId =
                    record.vsyncId,
                transactionSequence =
                    record.transactionSequence,
                transactionSubmitNs =
                    if (
                        record.kind ==
                        TransactionEventKind.SUBMITTED_ON_DRAW
                    ) {
                        record.timeNs
                    } else {
                        null
                    },
                transactionCommitNs =
                    if (
                        record.kind ==
                        TransactionEventKind.COMMITTED
                    ) {
                        record.timeNs
                    } else {
                        null
                    },
                transactionLatchNs =
                    record.latchTimeNs,
                actualPresentNs =
                    record.presentTimeNs,
                reason =
                    "accepted=${record.submissionAccepted} " +
                        "presentFenceValid=${record.presentFenceValid}",
            )
        )
    }

    fun sessionFile(): File? =
        writer?.file

    fun droppedEventCount(): Long =
        writer?.droppedEventCount() ?: 0L

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

    private const val MOVEMENT_EPS_DEG =
        0.10f

    private const val PRESENTATION_WINDOW_NS =
        1_500_000_000L

    private const val FOLD7_STATE_CATEGORY =
        "fold7-state"

    private const val SAMSUNG_AUTHORITY_WINDOW_NS =
        3_000_000_000L

    /**
     * Existing transition diagnostic:
     * STATE A -> B generation=N hinge=X direction=D ...
     */
    private val STATE_TRANSITION =
        Regex(
            """STATE\s+(\S+)\s+->\s+(\S+)\s+generation=\d+\s+hinge=([-+0-9.Ee]+)\s+direction=(\S+)"""
        )

    private val GENERATION =
        Regex(
            """generation=(\d+)"""
        )
}
