package com.duoopen.lab

import java.io.BufferedWriter
import java.io.Closeable
import java.io.File
import java.io.FileOutputStream
import java.io.OutputStreamWriter
import java.util.UUID
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong
import org.json.JSONObject

/**
 * R&D-only asynchronous JSONL session writer.
 *
 * The render / callback thread only allocates the event and attempts a bounded
 * queue offer. JSON formatting and file I/O happen on the writer thread.
 *
 * FULL_LAB overhead still has to be measured on-device; this is intentionally
 * not a production telemetry design.
 */
internal class TransitionSessionWriter(
    directory: File,
    val sessionId: String = UUID.randomUUID().toString(),
    queueCapacity: Int = 32_768,
) : Closeable {
    private sealed interface WorkItem

    private data class QueuedEvent(
        val eventSequence: Long,
        val event: TransitionEvent,
    ) : WorkItem

    private data class FlushRequest(
        val latch: CountDownLatch,
    ) : WorkItem

    private val sequence = AtomicLong(0L)
    private val dropped = AtomicLong(0L)
    private val running = AtomicBoolean(true)
    private val queue =
        ArrayBlockingQueue<WorkItem>(queueCapacity)

    val file: File

    private val thread: Thread

    init {
        directory.mkdirs()
        file = File(
            directory,
            "transition-$sessionId.jsonl",
        )

        thread =
            Thread(
                ::writerLoop,
                "DuoTransitionLabWriter",
            ).apply {
                isDaemon = true
                start()
            }
    }

    fun record(event: TransitionEvent): Boolean {
        if (!running.get()) return false

        val row =
            QueuedEvent(
                eventSequence = sequence.incrementAndGet(),
                event = event,
            )

        val accepted = queue.offer(row)

        if (!accepted) {
            dropped.incrementAndGet()
        }

        return accepted
    }

    fun droppedEventCount(): Long =
        dropped.get()

    /**
     * Force all events currently ahead of this request in the writer queue to
     * durable file output. Used immediately before the in-app debug export.
     */
    fun flush(
        timeoutMs: Long = 1_500L,
    ): Boolean {
        if (!running.get()) {
            return true
        }

        val latch =
            CountDownLatch(1)

        val offered =
            queue.offer(
                FlushRequest(latch)
            )

        if (!offered) {
            return false
        }

        return latch.await(
            timeoutMs,
            TimeUnit.MILLISECONDS,
        )
    }

    override fun close() {
        if (!running.getAndSet(false)) return

        if (Thread.currentThread() !== thread) {
            thread.join(2_000L)
        }
    }

    private fun writerLoop() {
        BufferedWriter(
            OutputStreamWriter(
                FileOutputStream(file, false),
                Charsets.UTF_8,
            ),
            64 * 1024,
        ).use { writer ->
            var dirty = false
            var rowsSinceFlush = 0

            while (
                running.get() ||
                queue.isNotEmpty()
            ) {
                val item =
                    queue.poll(
                        FLUSH_IDLE_MS,
                        TimeUnit.MILLISECONDS,
                    )

                if (item == null) {
                    if (dirty) {
                        writer.flush()
                        dirty = false
                        rowsSinceFlush = 0
                    }
                    continue
                }

                when (item) {
                    is QueuedEvent -> {
                        writer.write(
                            toJson(item)
                        )
                        writer.newLine()
                        dirty = true
                        rowsSinceFlush++

                        if (
                            rowsSinceFlush >=
                            FLUSH_ROW_INTERVAL
                        ) {
                            writer.flush()
                            dirty = false
                            rowsSinceFlush = 0
                        }
                    }

                    is FlushRequest -> {
                        writer.flush()
                        dirty = false
                        rowsSinceFlush = 0
                        item.latch.countDown()
                    }
                }
            }

            writer.flush()
        }
    }

    private fun toJson(
        row: QueuedEvent,
    ): String {
        val e = row.event
        val o = JSONObject()

        o.put("sessionId", sessionId)
        o.put("eventSequence", row.eventSequence)
        o.put("timestampNs", e.timeNs)
        o.put("eventType", e.type)

        put(o, "hingeSampleSequence", e.hingeSampleSequence)
        put(o, "measuredAngle", e.measuredAngle)
        put(o, "visualAngle", e.visualAngle)
        put(o, "predictedAngle", e.predictedAngle)
        put(o, "hingeSource", e.hingeSource)
        put(o, "hingeSourceTimeNs", e.hingeSourceTimeNs)
        put(o, "hingeBinderArrivalTimeNs", e.hingeBinderArrivalTimeNs)
        put(o, "hingeConsumerDeliveryTimeNs", e.hingeConsumerDeliveryTimeNs)
        put(o, "timestampQuality", e.timestampQuality)
        put(o, "sourceToBinderLagNs", e.sourceToBinderLagNs)
        put(o, "binderToConsumerLagNs", e.binderToConsumerLagNs)
        put(o, "sourceToConsumerLagNs", e.sourceToConsumerLagNs)
        put(o, "velocityDegPerSec", e.velocityDegPerSec)

        put(o, "direction", e.direction)
        put(o, "physicalState", e.physicalState)
        put(o, "generation", e.generation)

        put(o, "coverLogicalId", e.coverLogicalId)
        put(o, "innerLogicalId", e.innerLogicalId)
        put(o, "coverState", e.coverState)
        put(o, "innerState", e.innerState)
        put(o, "coverDefault", e.coverDefault)
        put(o, "innerDefault", e.innerDefault)
        put(o, "coverWidth", e.coverWidth)
        put(o, "coverHeight", e.coverHeight)
        put(o, "innerWidth", e.innerWidth)
        put(o, "innerHeight", e.innerHeight)
        put(o, "refreshRateHz", e.refreshRateHz)

        put(o, "vsyncId", e.vsyncId)
        put(o, "frameTimeNs", e.frameTimeNs)
        put(o, "deadlineNs", e.deadlineNs)
        put(o, "expectedPresentNs", e.expectedPresentNs)
        put(o, "predictionLeadNs", e.predictionLeadNs)
        put(o, "predictionConfidence", e.predictionConfidence)

        put(o, "transactionSequence", e.transactionSequence)
        put(o, "transactionSubmitNs", e.transactionSubmitNs)
        put(o, "transactionCommitNs", e.transactionCommitNs)
        put(o, "transactionLatchNs", e.transactionLatchNs)
        put(o, "actualPresentNs", e.actualPresentNs)

        put(o, "jankType", e.jankType)
        put(o, "scheduledAppFrameTimeNs", e.scheduledAppFrameTimeNs)
        put(o, "actualAppFrameTimeNs", e.actualAppFrameTimeNs)

        put(o, "reason", e.reason)
        put(o, "valueNs", e.valueNs)
        put(o, "valueFloat", e.valueFloat)

        return o.toString()
    }

    private fun put(
        o: JSONObject,
        key: String,
        value: Any?,
    ) {
        if (value != null) {
            o.put(key, value)
        }
    }

    private companion object {
        const val FLUSH_IDLE_MS =
            250L

        const val FLUSH_ROW_INTERVAL =
            64
    }
}
