package com.duoopen.lab

import android.os.Build
import android.os.Looper
import android.view.Choreographer

/**
 * API-33+ low-level vsync / FrameTimeline sampler.
 *
 * FrameData itself is valid only inside onVsync(), so every value needed for
 * later analysis is copied into primitive fields before the callback returns.
 */
internal class FrameTimelineProbe(
    private val sink: (FramePlanRecord) -> Unit,
) {
    @Volatile
    private var running = false

    @Volatile
    var latest: FramePlanRecord? = null
        private set

    val isRunning: Boolean
        get() = running

    private var choreographer: Choreographer? = null

    /*
     * stop() cannot cancel a VsyncCallback already queued by Choreographer.
     * Track whether one is pending so a quick stop/start cannot create two
     * independent callback chains.
     */
    private var callbackPosted = false

    private val callback =
        object : Choreographer.VsyncCallback {
            override fun onVsync(
                data: Choreographer.FrameData,
            ) {
                callbackPosted = false

                if (!running) return

                val preferred =
                    data.preferredFrameTimeline

                val record =
                    FramePlanRecord(
                        callbackTimeNs =
                            TransitionClock.nowNs(),
                        frameTimeNs =
                            data.frameTimeNanos,
                        expectedPresentationTimeNs =
                            preferred.expectedPresentationTimeNanos,
                        deadlineNs =
                            preferred.deadlineNanos,
                        vsyncId =
                            preferred.vsyncId,
                    )

                latest = record
                sink(record)

                if (running) {
                    postNext()
                }
            }
        }

    fun start() {
        check(Build.VERSION.SDK_INT >= 33) {
            "FrameTimelineProbe requires API 33+"
        }
        check(Looper.myLooper() != null) {
            "start() must run on a Looper thread"
        }

        if (running) return

        choreographer =
            Choreographer.getInstance()

        running = true
        postNext()
    }

    private fun postNext() {
        if (
            !running ||
            callbackPosted
        ) {
            return
        }

        callbackPosted = true
        choreographer?.postVsyncCallback(
            callback
        )
    }

    /**
     * There is no need to retain FrameData or cancel an already-dispatched
     * callback. The next callback sees running=false and does not repost.
     */
    fun stop() {
        running = false
        latest = null
    }
}
