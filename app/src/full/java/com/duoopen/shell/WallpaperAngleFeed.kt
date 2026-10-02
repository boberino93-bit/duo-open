package com.duoopen.shell

import android.app.WallpaperManager
import android.content.ComponentName
import android.content.Context
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.os.Handler
import android.os.PowerManager
import android.os.SystemClock
import android.util.Log
import android.view.Display
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import com.duoopen.debug.DuoDiagnostics
import com.duoopen.fold.HingeAngleSource
import com.duoopen.lab.TransitionClock
import com.duoopen.lab.TransitionLab
import kotlin.math.abs

/**
 * Fold7 Gen-2 Samsung precise-angle acquisition.
 *
 * The wallpaper command still has to originate from an attached window token,
 * so anchor/window work remains on [mainHandler]. Scheduling, session ownership,
 * response acceptance and HingeAngleSource delivery are serialized on
 * [controlHandler].
 *
 * Invariants:
 * - 8 ms target while interactive, including at rest;
 * - at most one Samsung wallpaper poll in flight;
 * - every reader lifetime and poll are explicitly identified;
 * - a late old-session / old-poll callback is rejected;
 * - next poll is scheduled only after response/timeout completion;
 * - the precise Samsung angle remains authoritative geometry.
 */
class WallpaperAngleFeed(
    private val context: Context,
    private val mainHandler: Handler,
    private val controlHandler: Handler,
    private val hinge: HingeAngleSource,
) {
    @Volatile
    private var running = false

    @Volatile
    private var readerSession = 0L

    private var actionPrefix = ""

    // Main-thread-owned window state.
    private var anchor: View? = null
    private var anchorWm: WindowManager? = null
    private var anchorKey = ""

    // Control-thread-owned acquisition state.
    private val pipeline =
        Fold7AnglePipelineGen2(
            targetPeriodMs = INTERACTIVE_POLL_MS,
            minimumYieldMs = MINIMUM_YIELD_MS,
        )

    private var lastCallbackUptime = 0L
    private var lastDeliveryLagMs = -1L
    private var maxDeliveryLagMs = 0L
    private var lastAngleSeen = Float.NaN
    private var lastAngleChangeUptime = 0L
    private var endpointBridgeGeneration = 0L
    private var duplicateAngles = 0L
    private var droppedSessionSamples = 0L
    private var droppedPollSamples = 0L
    private var timedOutPolls = 0L
    private var lastWallpaperIdentity = ""
    private var lastFreshState: Boolean? = null
    private var startedAt = 0L
    private var scheduledPollSession = -1L

    /** One line for the UI. */
    @Volatile
    var status: String = "Idle"
        private set

    val active: Boolean
        get() = running

    private val pollRunnable =
        Runnable {
            val session = scheduledPollSession
            if (!isCurrent(session)) {
                return@Runnable
            }
            startPoll(session)
        }

    private val statusTick =
        object : Runnable {
            override fun run() {
                if (!running) return

                val now =
                    SystemClock.uptimeMillis()

                val b =
                    ShizukuBridge.angleStatus()

                val age =
                    if (lastCallbackUptime == 0L) {
                        -1L
                    } else {
                        now - lastCallbackUptime
                    }

                val fresh =
                    age in 0..STALE_MS ||
                        (
                            age < 0L &&
                                now - startedAt <= STALE_MS
                            )

                val wallpaper =
                    wallpaperIdentity(context)

                if (wallpaper != lastWallpaperIdentity) {
                    DuoDiagnostics.event(
                        "angle-source",
                        "wallpaper changed from=" +
                            "${lastWallpaperIdentity.ifEmpty { "(initial)" }} " +
                            "to=$wallpaper readerFresh=$fresh ageMs=$age",
                    )

                    lastWallpaperIdentity = wallpaper
                }

                if (lastFreshState != fresh) {
                    DuoDiagnostics.event(
                        "angle-source",
                        "readerFresh=$fresh ageMs=$age wallpaper=$wallpaper",
                    )
                    lastFreshState = fresh
                }

                val inFlight =
                    pipeline.inFlightPoll

                status =
                    if (b == null) {
                        "Reader unreachable · wallpaper $wallpaper"
                    } else {
                        "Reader ${b.getString("state")}: " +
                            "${b.getInt("parsed")} angles / ${b.getInt("lines")} lines" +
                            (
                                if (age >= 0L) {
                                    " · last ${age} ms ago"
                                } else {
                                    " · waiting for first angle"
                                }
                            ) +
                            (
                                if (lastDeliveryLagMs >= 0L) {
                                    " · delivery ${lastDeliveryLagMs} ms (max ${maxDeliveryLagMs})"
                                } else {
                                    ""
                                }
                            ) +
                            " · target ${INTERACTIVE_POLL_MS} ms" +
                            " · session $readerSession" +
                            " · inFlight ${inFlight?.sequence ?: "none"}" +
                            " · timeout $timedOutPolls" +
                            " · drop ${droppedSessionSamples + droppedPollSamples}" +
                            " · dup $duplicateAngles" +
                            " · source ${if (fresh) "live" else "stale"}" +
                            " · wallpaper $wallpaper"
                    }

                if (
                    !fresh &&
                    (
                        age > STALE_MS ||
                            (
                                age < 0L &&
                                    now - startedAt > STALE_MS
                                )
                        )
                ) {
                    controlHandler.post {
                        if (running) {
                            hinge.expireExternal("reader-stale")
                        }
                    }
                }

                mainHandler.postDelayed(
                    this,
                    STATUS_TICK_MS,
                )
            }
        }

    fun start() {
        if (running) return

        if (!ShizukuBridge.ready) {
            status = "Shizuku not ready"
            return
        }

        val session =
            readerSession + 1L

        readerSession = session
        actionPrefix =
            "com.duoopen.angle.READ_${SystemClock.elapsedRealtime()}_$session"

        val prefix =
            actionPrefix

        if (
            !ShizukuBridge.startAnglesSequenced(
                prefix,
            ) { angle, sourceUptime, binderArrivalTimeNs, pollSequence ->
                controlHandler.post {
                    onAngle(
                        session = session,
                        pollSequence = pollSequence,
                        angle = angle,
                        sourceUptime = sourceUptime,
                        binderArrivalTimeNs = binderArrivalTimeNs,
                    )
                }
            }
        ) {
            status = "Couldn't start the log reader"
            return
        }

        running = true
        startedAt = SystemClock.uptimeMillis()

        lastCallbackUptime = 0L
        lastDeliveryLagMs = -1L
        maxDeliveryLagMs = 0L
        lastAngleSeen = Float.NaN
        lastAngleChangeUptime = 0L
        endpointBridgeGeneration = 0L
        duplicateAngles = 0L
        droppedSessionSamples = 0L
        droppedPollSamples = 0L
        timedOutPolls = 0L
        lastWallpaperIdentity = ""
        lastFreshState = null

        status = "Starting Fold7 Gen-2 Samsung hinge reader"

        mainHandler.post {
            if (isCurrent(session)) {
                runCatching {
                    ensureAnchor()
                }.onFailure {
                    status =
                        "Anchor failed: ${it.message}"
                }
            }
        }

        controlHandler.post {
            if (!isCurrent(session)) {
                return@post
            }

            hinge.beginExternalSession(session)
            pipeline.startSession()

            TransitionLab.recordIngressStage(
                type = "angle-session-start",
                angleSession = session,
                reason = "FoldInteractive Gen2 reader start",
            )

            schedulePoll(
                session = session,
                delayMs = 0L,
            )
        }

        mainHandler.postDelayed(
            statusTick,
            STATUS_TICK_MS,
        )

        Log.i(
            TAG,
            "wallpaper angle feed Gen2 started ($prefix)",
        )
    }

    fun stop() {
        if (!running) return

        val oldSession =
            readerSession

        running = false
        readerSession = oldSession + 1L

        controlHandler.removeCallbacks(
            pollRunnable
        )

        controlHandler.post {
            pipeline.invalidateSession()
            hinge.revokeExternalSession(
                session = oldSession,
                reason = "feed-stop",
            )

            TransitionLab.recordIngressStage(
                type = "angle-session-stop",
                angleSession = oldSession,
                reason = "FoldInteractive Gen2 reader stop",
            )
        }

        mainHandler.removeCallbacks(
            statusTick
        )

        ShizukuBridge.stopAngles()

        mainHandler.post {
            removeAnchor()
        }

        status = "Stopped"
        Log.i(TAG, "wallpaper angle feed stopped")
    }

    /**
     * An independent opening edge can pull the next precise sample forward
     * without inventing any visual angle.
     */
    fun kickBurst(
        reason: String,
    ) {
        val session =
            readerSession

        controlHandler.post {
            if (!isCurrent(session)) return@post

            TransitionLab.recordIngressStage(
                type = "poll-kick",
                angleSession = session,
                reason = reason,
            )

            if (pipeline.inFlightPoll == null) {
                schedulePoll(
                    session = session,
                    delayMs = 0L,
                )
            }
        }
    }

    /** Re-check the anchor after a panel swap. Main-thread entry. */
    fun onDisplayChanged() {
        if (!running) return

        mainHandler.post {
            if (running) {
                runCatching {
                    ensureAnchor()
                }.onFailure {
                    status =
                        "Anchor failed: ${it.message}"
                }
            }
        }
    }

    private fun startPoll(
        session: Long,
    ) {
        if (!isCurrent(session)) return

        val pm =
            context.getSystemService(
                PowerManager::class.java,
            )

        if (pm?.isInteractive == false) {
            schedulePoll(
                session = session,
                delayMs = NON_INTERACTIVE_RECHECK_MS,
            )
            return
        }

        val now =
            SystemClock.uptimeMillis()

        val poll =
            pipeline.tryStartPoll(now)
                ?: return

        TransitionLab.recordIngressStage(
            type = "poll-due",
            angleSession = session,
            pollSequence = poll.sequence,
            valueNs = now * TransitionClock.NS_PER_MS,
        )

        mainHandler.post {
            if (!isCurrent(session)) {
                controlHandler.post {
                    completePollWithoutSample(
                        session = session,
                        poll = poll,
                        reason = "session-invalid-before-command",
                    )
                }
                return@post
            }

            val commandStartNs =
                TransitionClock.nowNs()

            TransitionLab.recordIngressStage(
                type = "poll-command-start",
                timeNs = commandStartNs,
                angleSession = session,
                pollSequence = poll.sequence,
            )

            val sent =
                runCatching {
                    ensureAnchor()

                    val a =
                        anchor

                    if (
                        a == null ||
                        a.windowToken == null
                    ) {
                        false
                    } else {
                        val action =
                            "$actionPrefix:${poll.sequence}"

                        WallpaperManager
                            .getInstance(a.context)
                            .sendWallpaperCommand(
                                a.windowToken,
                                action,
                                0,
                                0,
                                0,
                                null,
                            )
                        true
                    }
                }.onFailure {
                    status =
                        "Wallpaper command failed: ${it.message}"
                }.getOrDefault(false)

            val commandReturnNs =
                TransitionClock.nowNs()

            TransitionLab.recordIngressStage(
                type = "poll-command-return",
                timeNs = commandReturnNs,
                angleSession = session,
                pollSequence = poll.sequence,
                reason = "sent=$sent",
                valueNs =
                    commandReturnNs -
                        commandStartNs,
            )

            controlHandler.post {
                if (!isCurrent(session)) {
                    return@post
                }

                if (!sent) {
                    completePollWithoutSample(
                        session = session,
                        poll = poll,
                        reason = "command-not-sent",
                    )
                } else {
                    controlHandler.postDelayed(
                        {
                            onPollTimeout(
                                session = session,
                                poll = poll,
                            )
                        },
                        POLL_TIMEOUT_MS,
                    )
                }
            }
        }
    }

    private fun onPollTimeout(
        session: Long,
        poll: Fold7AnglePipelineGen2.PollToken,
    ) {
        if (!isCurrent(session)) return

        val current =
            pipeline.inFlightPoll

        if (
            current?.session !=
            poll.session ||
            current.sequence !=
            poll.sequence
        ) {
            return
        }

        timedOutPolls++

        TransitionLab.recordIngressStage(
            type = "poll-timeout",
            angleSession = session,
            pollSequence = poll.sequence,
        )

        val next =
            pipeline.timeoutPoll(
                token = poll,
                timeoutUptimeMs =
                    SystemClock.uptimeMillis(),
            ) ?: return

        schedulePoll(
            session = session,
            delayMs = next,
        )
    }

    private fun completePollWithoutSample(
        session: Long,
        poll: Fold7AnglePipelineGen2.PollToken,
        reason: String,
    ) {
        if (!isCurrent(session)) return

        TransitionLab.recordIngressStage(
            type = "poll-complete-no-sample",
            angleSession = session,
            pollSequence = poll.sequence,
            reason = reason,
        )

        val next =
            pipeline.completePoll(
                token = poll,
                completionUptimeMs =
                    SystemClock.uptimeMillis(),
            ) ?: return

        schedulePoll(
            session = session,
            delayMs = next,
        )
    }

    private fun onAngle(
        session: Long,
        pollSequence: Long,
        angle: Float,
        sourceUptime: Long,
        binderArrivalTimeNs: Long,
    ) {
        val consumerDeliveryTimeNs =
            TransitionClock.nowNs()

        if (!isCurrent(session)) {
            droppedSessionSamples++

            TransitionLab.recordIngressStage(
                type = "sample-drop-session",
                timeNs = consumerDeliveryTimeNs,
                angleSession = session,
                pollSequence = pollSequence,
                reason = "current=$readerSession",
            )
            return
        }

        val poll =
            pipeline.inFlightPoll

        if (
            poll == null ||
            poll.sequence != pollSequence
        ) {
            droppedPollSamples++

            TransitionLab.recordIngressStage(
                type = "sample-drop-poll",
                timeNs = consumerDeliveryTimeNs,
                angleSession = session,
                pollSequence = pollSequence,
                reason =
                    "inFlight=${poll?.sequence}",
            )
            return
        }

        val sample =
            pipeline.nextSample(
                poll = poll,
                angle = angle,
            ) ?: run {
                droppedPollSamples++
                return
            }

        TransitionLab.recordIngressStage(
            type = "control-accept",
            timeNs = consumerDeliveryTimeNs,
            angleSession = session,
            pollSequence = pollSequence,
            sampleSequence = sample.sampleSequence,
            valueFloat = angle,
        )

        TransitionLab.recordSamsungSample(
            angleDegrees = angle,
            sourceUptimeMs = sourceUptime,
            binderArrivalTimeNs = binderArrivalTimeNs,
            consumerDeliveryTimeNs = consumerDeliveryTimeNs,
            angleSession = session,
            pollSequence = pollSequence,
            sampleSequence = sample.sampleSequence,
        )

        val now =
            SystemClock.uptimeMillis()

        endpointBridgeGeneration++

        val priorAngle =
            lastAngleSeen

        val priorChangeUptime =
            lastAngleChangeUptime

        lastCallbackUptime =
            now

        lastDeliveryLagMs =
            now - sourceUptime

        if (
            lastDeliveryLagMs >
            maxDeliveryLagMs
        ) {
            maxDeliveryLagMs =
                lastDeliveryLagMs
        }

        if (
            lastAngleSeen.isNaN() ||
            abs(
                angle -
                    lastAngleSeen,
            ) >= ANGLE_CHANGE_EPS
        ) {
            lastAngleSeen = angle
            lastAngleChangeUptime = now
        } else {
            duplicateAngles++
        }

        hinge.feedExternal(
            session = session,
            sequence = sample.sampleSequence,
            angle = angle,
            sourceUptimeMs = sourceUptime,
            receivedUptimeMs = now,
        )

        scheduleEndpointBridge(
            session = session,
            angle = angle,
            priorAngle = priorAngle,
            priorChangeUptime = priorChangeUptime,
            now = now,
        )

        val next =
            pipeline.completePoll(
                token = poll,
                completionUptimeMs = now,
            ) ?: return

        TransitionLab.recordIngressStage(
            type = "poll-complete",
            angleSession = session,
            pollSequence = poll.sequence,
            sampleSequence = sample.sampleSequence,
            valueNs =
                (now - poll.startedUptimeMs)
                    .coerceAtLeast(0L) *
                    TransitionClock.NS_PER_MS,
        )

        schedulePoll(
            session = session,
            delayMs = next,
        )
    }

    private fun schedulePoll(
        session: Long,
        delayMs: Long,
    ) {
        if (!isCurrent(session)) return

        scheduledPollSession = session

        controlHandler.removeCallbacks(
            pollRunnable
        )

        controlHandler.postDelayed(
            pollRunnable,
            delayMs.coerceAtLeast(0L),
        )
    }

    private fun scheduleEndpointBridge(
        session: Long,
        angle: Float,
        priorAngle: Float,
        priorChangeUptime: Long,
        now: Long,
    ) {
        if (
            !priorAngle.isFinite() ||
            priorChangeUptime == 0L
        ) {
            return
        }

        val dtMs =
            now - priorChangeUptime

        if (
            dtMs <= 0L ||
            dtMs >
            ENDPOINT_BRIDGE_SAMPLE_MAX_MS
        ) {
            return
        }

        val velocity =
            (angle - priorAngle) *
                1_000f /
                dtMs.toFloat()

        val target =
            when {
                angle <= ENDPOINT_BRIDGE_CLOSED_MAX_DEG &&
                    velocity <= -ENDPOINT_BRIDGE_MIN_SPEED_DPS ->
                    0f

                angle >= ENDPOINT_BRIDGE_OPEN_MIN_DEG &&
                    velocity >= ENDPOINT_BRIDGE_MIN_SPEED_DPS ->
                    180f

                else ->
                    return
            }

        val generation =
            endpointBridgeGeneration

        controlHandler.postDelayed(
            {
                if (
                    !isCurrent(session) ||
                    endpointBridgeGeneration != generation ||
                    SystemClock.uptimeMillis() -
                    lastCallbackUptime <
                    ENDPOINT_BRIDGE_DELAY_MS
                ) {
                    return@postDelayed
                }

                DuoDiagnostics.event(
                    "angle-source",
                    "endpoint bridge from=$angle to=$target velocity=$velocity",
                )

                lastAngleSeen = target
                lastAngleChangeUptime =
                    SystemClock.uptimeMillis()

                TransitionLab.recordSyntheticEndpoint(
                    angleDegrees = target,
                    reason =
                        "endpoint bridge from=$angle velocity=$velocity",
                )

                hinge.feedSyntheticExternal(
                    session = session,
                    angle = target,
                    sourceUptimeMs = SystemClock.uptimeMillis(),
                    reason = "endpoint-bridge",
                )
            },
            ENDPOINT_BRIDGE_DELAY_MS,
        )
    }

    private fun isCurrent(
        session: Long,
    ): Boolean =
        running &&
            session ==
            readerSession

    private fun displayKey(
        display: Display,
    ): String {
        val mode =
            runCatching {
                display.mode
            }.getOrNull()
                ?: return "${display.displayId}"

        return (
            "${display.displayId}:" +
                "${mode.physicalWidth}x${mode.physicalHeight}"
            )
    }

    /**
     * Main-thread-only window anchor. Samsung's FoldInteractive service answers
     * commands from the current default display's wallpaper-showing token.
     */
    private fun ensureAnchor() {
        val dm =
            context.getSystemService(
                DisplayManager::class.java,
            )

        val display =
            dm.getDisplay(
                Display.DEFAULT_DISPLAY
            ) ?: return

        val key =
            displayKey(display)

        if (
            anchor != null &&
            key == anchorKey
        ) {
            return
        }

        removeAnchor()

        val c =
            context
                .createDisplayContext(display)
                .createWindowContext(
                    WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                    null,
                )

        val wm =
            c.getSystemService(
                WindowManager::class.java,
            )

        val view =
            View(c)

        val params =
            WindowManager.LayoutParams(
                1,
                1,
                WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                    WindowManager.LayoutParams.FLAG_SHOW_WALLPAPER,
                PixelFormat.TRANSLUCENT,
            ).apply {
                gravity =
                    Gravity.TOP or
                        Gravity.START
                title =
                    "DuoOpenAngleAnchor"
            }

        wm.addView(
            view,
            params,
        )

        anchor = view
        anchorWm = wm
        anchorKey = key
    }

    private fun removeAnchor() {
        val view =
            anchor ?: return

        runCatching {
            anchorWm
                ?.removeViewImmediate(view)
        }

        anchor = null
        anchorWm = null
        anchorKey = ""
    }

    companion object {
        private const val TAG =
            "DuoAngleFeed"

        /** Full interactive cadence, including stationary closed/open rest. */
        const val INTERACTIVE_POLL_MS =
            8L

        const val MINIMUM_YIELD_MS =
            1L

        const val NON_INTERACTIVE_RECHECK_MS =
            500L

        const val POLL_TIMEOUT_MS =
            96L

        const val STATUS_TICK_MS =
            1_000L

        const val ANGLE_CHANGE_EPS =
            0.10f

        private const val ENDPOINT_BRIDGE_DELAY_MS =
            140L

        private const val ENDPOINT_BRIDGE_SAMPLE_MAX_MS =
            300L

        private const val ENDPOINT_BRIDGE_CLOSED_MAX_DEG =
            8.0f

        private const val ENDPOINT_BRIDGE_OPEN_MIN_DEG =
            172.0f

        private const val ENDPOINT_BRIDGE_MIN_SPEED_DPS =
            18.0f

        private const val STALE_MS =
            2_500L

        val FOLD_WALLPAPER =
            ComponentName(
                "com.samsung.android.wallpaper.live",
                "com.samsung.android.wallpaper.live.fold.FoldInteractive",
            )

        /**
         * WallpaperManager metadata is diagnostic only.
         *
         * Samsung may report FoldInteractive on the inner display and a Video
         * wallpaper on the cover display even during the same physical fold
         * session, so this must never be used as the live-angle kill switch.
         */
        fun foldWallpaperActive(
            context: Context,
        ): Boolean {
            val info =
                runCatching {
                    WallpaperManager
                        .getInstance(context)
                        .wallpaperInfo
                }.getOrNull()
                    ?: return false

            return (
                info.packageName ==
                    FOLD_WALLPAPER.packageName &&
                    (
                        info.serviceName ==
                            FOLD_WALLPAPER.className ||
                            info.serviceName.contains(
                                "FoldInteractive"
                            )
                        )
                )
        }

        fun wallpaperIdentity(
            context: Context,
        ): String {
            val info =
                runCatching {
                    WallpaperManager
                        .getInstance(context)
                        .wallpaperInfo
                }.getOrNull()
                    ?: return "none"

            val service =
                info.serviceName
                    .substringAfterLast('.')
                    .ifEmpty {
                        "unknown"
                    }

            return (
                "${info.packageName.substringAfterLast('.')}/" +
                    service
                )
        }
    }
}
