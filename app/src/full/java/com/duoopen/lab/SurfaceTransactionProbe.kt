package com.duoopen.lab

import android.hardware.SyncFence
import android.os.Build
import android.view.SurfaceControl
import java.util.concurrent.Executor
import java.util.concurrent.atomic.AtomicLong

/**
 * API-35 transaction timing probe for FULL_LAB mode.
 *
 * Call instrument() BEFORE passing the transaction to
 * AttachedSurfaceControl.applyTransactionOnDraw().
 *
 * Baseline measurements are deliberately observational: the nearest observed
 * vsync id is stored for correlation, but this probe does NOT call
 * Transaction.setFrameTimeline(), because doing so could affect compositor
 * scheduling and contaminate the baseline.
 *
 * Call markSubmittedOnDraw() immediately around the app-side submission call.
 *
 * The completed callback provides:
 *   - latch timestamp from SurfaceFlinger
 *   - presentation fence, whose signal timestamp is CLOCK_MONOTONIC
 *
 * The probe deliberately never blocks waiting on the fence.
 */
internal class SurfaceTransactionProbe(
    private val callbackExecutor: Executor,
    private val sink: (TransactionTimingRecord) -> Unit,
) {
    data class Token(
        val transactionSequence: Long,
        val vsyncId: Long?,
    )

    private val sequence = AtomicLong(0L)

    fun instrument(
        transaction: SurfaceControl.Transaction,
        frame: FramePlanRecord?,
    ): Token {
        val token =
            Token(
                transactionSequence =
                    sequence.incrementAndGet(),
                vsyncId =
                    frame?.vsyncId,
            )

        if (Build.VERSION.SDK_INT >= 33) {
            transaction.addTransactionCommittedListener(
                callbackExecutor,
            ) {
                sink(
                    TransactionTimingRecord(
                        transactionSequence =
                            token.transactionSequence,
                        kind =
                            TransactionEventKind.COMMITTED,
                        timeNs =
                            TransitionClock.nowNs(),
                        vsyncId =
                            token.vsyncId,
                    )
                )
            }
        }

        if (Build.VERSION.SDK_INT >= 35) {
            transaction.addTransactionCompletedListener(
                callbackExecutor,
            ) { stats ->
                val callbackTime =
                    TransitionClock.nowNs()

                val latchTime =
                    stats.latchTimeNanos

                val fence =
                    stats.presentFence

                var fenceValid = false
                var presentTime: Long? = null

                try {
                    fenceValid =
                        fence.isValid

                    if (fenceValid) {
                        val signal =
                            fence.signalTime

                        if (
                            signal !=
                                SyncFence.SIGNAL_TIME_INVALID &&
                            signal !=
                                SyncFence.SIGNAL_TIME_PENDING
                        ) {
                            presentTime = signal
                        }
                    }
                } finally {
                    fence.close()
                }

                sink(
                    TransactionTimingRecord(
                        transactionSequence =
                            token.transactionSequence,
                        kind =
                            TransactionEventKind.COMPLETED,
                        timeNs =
                            callbackTime,
                        vsyncId =
                            token.vsyncId,
                        latchTimeNs =
                            latchTime,
                        presentTimeNs =
                            presentTime,
                        presentFenceValid =
                            fenceValid,
                    )
                )
            }
        }

        sink(
            TransactionTimingRecord(
                transactionSequence =
                    token.transactionSequence,
                kind =
                    TransactionEventKind.INSTRUMENTED,
                timeNs =
                    TransitionClock.nowNs(),
                vsyncId =
                    token.vsyncId,
            )
        )

        return token
    }

    fun markSubmittedOnDraw(
        token: Token,
        accepted: Boolean,
        timeNs: Long = TransitionClock.nowNs(),
    ) {
        sink(
            TransactionTimingRecord(
                transactionSequence =
                    token.transactionSequence,
                kind =
                    TransactionEventKind.SUBMITTED_ON_DRAW,
                timeNs =
                    timeNs,
                vsyncId =
                    token.vsyncId,
                submissionAccepted =
                    accepted,
            )
        )
    }
}
