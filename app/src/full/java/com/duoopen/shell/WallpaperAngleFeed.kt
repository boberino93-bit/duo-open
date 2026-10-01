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
import com.duoopen.fold.HingeAngleSource
import com.duoopen.lab.TransitionClock
import com.duoopen.lab.TransitionLab
import kotlin.math.abs

/**
 * Continuous hinge angle on Samsung foldables, where the public sensor only
 * reports 0/90/180: Samsung's own "Fold interactive" home wallpaper receives
 * the real angle, and logs it (`mCurrentAngle=…`) whenever it's sent a
 * wallpaper command. So: keep a 1×1 wallpaper-showing anchor window, ping the
 * wallpaper through it at an adaptive cadence, and let the Shizuku-side log reader
 * ([DuoShellService]) call back with each value, which is fed into
 * [HingeAngleSource] as the live angle.
 *
 * Technique from Duo Fold Live (github.com/joeconsorti/duo-fold-live, MIT).
 * Requires: Shizuku authorised, and that wallpaper set as the home wallpaper.
 */
class WallpaperAngleFeed(
    private val context: Context,
    private val handler: Handler,
    private val hinge: HingeAngleSource,
) {
    private var running = false
    private var action = ""
    private var anchor: View? = null
    private var anchorWm: WindowManager? = null
    private var anchorKey = ""
    private var lastCallbackUptime = 0L

    private var lastDeliveryLagMs = -1L
    private var maxDeliveryLagMs = 0L

    private var lastAngleSeen = Float.NaN
    private var lastAngleChangeUptime = 0L

    private var endpointBridgeGeneration = 0L

    private var duplicateAngles = 0L

    private var lastWallpaperIdentity =
        ""

    private var lastFreshState:
        Boolean? = null

    /** One line for the UI. */
    @Volatile
    var status: String = "Idle"
        private set

    val active: Boolean get() = running

    private val poll = object : Runnable {
        override fun run() {
            if (!running) return
            val pm = context.getSystemService(PowerManager::class.java)
            if (pm?.isInteractive != false) {
                runCatching { ensureAnchor() }.onFailure { status = "Anchor failed: ${it.message}" }
                val a = anchor
                if (a != null && a.windowToken != null) {
                    runCatching {
                        WallpaperManager.getInstance(a.context).sendWallpaperCommand(a.windowToken, action, 0, 0, 0, null)
                    }.onFailure { status = "Wallpaper command failed: ${it.message}" }
                }
            }
            handler.postDelayed(
                this,
                pollInterval(
                    SystemClock.uptimeMillis(),
                ),
            )
        }
    }

    private val statusTick = object : Runnable {
        override fun run() {
            if (!running) return

            val now =
                SystemClock.uptimeMillis()

            val b =
                ShizukuBridge.angleStatus()

            val age =
                if (
                    lastCallbackUptime == 0L
                ) {
                    -1L
                } else {
                    now -
                        lastCallbackUptime
                }

            val fresh =
                age in 0..STALE_MS ||
                    (
                        age < 0L &&
                            now - startedAt <=
                            STALE_MS
                        )

            val wallpaper =
                wallpaperIdentity(
                    context
                )

            if (
                wallpaper !=
                lastWallpaperIdentity
            ) {
                com.duoopen.debug.DuoDiagnostics.event(
                    "angle-source",
                    "wallpaper changed from=" +
                        "${lastWallpaperIdentity.ifEmpty { "(initial)" }} " +
                        "to=$wallpaper " +
                        "readerFresh=$fresh ageMs=$age",
                )

                lastWallpaperIdentity =
                    wallpaper
            }

            if (
                lastFreshState != fresh
            ) {
                com.duoopen.debug.DuoDiagnostics.event(
                    "angle-source",
                    "readerFresh=$fresh ageMs=$age " +
                        "wallpaper=$wallpaper",
                )

                lastFreshState =
                    fresh
            }

            status =
                if (
                    b == null
                ) {
                    "Reader unreachable · wallpaper $wallpaper"
                } else {
                    "Reader ${b.getString("state")}: " +
                        "${b.getInt("parsed")} angles / " +
                        "${b.getInt("lines")} lines" +
                        (
                            if (
                                age >= 0
                            ) {
                                " · last ${age} ms ago"
                            } else {
                                " · waiting for first angle"
                            }
                        ) +
                        (
                            if (
                                lastDeliveryLagMs >= 0
                            ) {
                                " · delivery ${lastDeliveryLagMs} ms " +
                                    "(max ${maxDeliveryLagMs})"
                            } else {
                                ""
                            }
                        ) +
                        " · poll ${pollInterval(now)} ms" +
                        " · dup $duplicateAngles" +
                        " · source " +
                        (
                            if (
                                fresh
                            ) {
                                "live"
                            } else {
                                "stale"
                            }
                        ) +
                        " · wallpaper $wallpaper"
                }

            if (
                !fresh &&
                (
                    age > STALE_MS ||
                        (
                            age < 0 &&
                                now - startedAt >
                                STALE_MS
                            )
                    )
            ) {
                hinge.clearExternal()
            }

            handler.postDelayed(
                this,
                1_000
            )
        }
    }
    private var startedAt = 0L

    fun start() {
        if (running) return
        if (!ShizukuBridge.ready) {
            status = "Shizuku not ready"
            return
        }

        /*
         * Samsung exposes different wallpaper metadata on the Fold7 cover
         * display. Always attempt the reader and let fresh/stale callbacks
         * determine whether the continuous source is usable.
         */
        action = "com.duoopen.angle.READ_${SystemClock.elapsedRealtime()}"
        if (
            !ShizukuBridge.startAngles(
                action,
            ) { angle, sourceUptime, binderArrivalTimeNs ->
                handler.post {
                    onAngle(
                        angle,
                        sourceUptime,
                        binderArrivalTimeNs,
                    )
                }
            }
        ) {
            status = "Couldn't start the log reader"
            return
        }
        running = true
        startedAt =
            SystemClock.uptimeMillis()

        lastCallbackUptime = 0L
        lastDeliveryLagMs = -1L
        maxDeliveryLagMs = 0L

        lastAngleSeen = Float.NaN
        lastAngleChangeUptime = 0L

        duplicateAngles = 0L

        lastWallpaperIdentity =
            ""

        lastFreshState =
            null

        status =
            "Starting live Samsung hinge reader"
        Log.i(TAG, "wallpaper angle feed started ($action)")
        handler.post(poll)
        handler.postDelayed(statusTick, 1_000)
    }

    fun stop() {
        if (!running) return
        running = false
        handler.removeCallbacks(poll)
        handler.removeCallbacks(statusTick)
        ShizukuBridge.stopAngles()
        hinge.clearExternal()
        removeAnchor()
        status = "Stopped"
        Log.i(TAG, "wallpaper angle feed stopped")
    }

    /** Re-check the anchor after a panel swap. */
    fun onDisplayChanged() {
        if (running) runCatching { ensureAnchor() }
    }

    private fun onAngle(
        angle: Float,
        sourceUptime: Long,
        binderArrivalTimeNs: Long,
    ) {
        val consumerDeliveryTimeNs =
            TransitionClock.nowNs()

        if (!running) return

        TransitionLab.recordSamsungSample(
            angleDegrees =
                angle,
            sourceUptimeMs =
                sourceUptime,
            binderArrivalTimeNs =
                binderArrivalTimeNs,
            consumerDeliveryTimeNs =
                consumerDeliveryTimeNs,
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
            (now - sourceUptime)

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
            lastAngleSeen =
                angle

            lastAngleChangeUptime =
                now
        } else {
            duplicateAngles++
        }

        hinge.feedExternal(angle)

        scheduleEndpointBridge(
            angle = angle,
            priorAngle = priorAngle,
            priorChangeUptime = priorChangeUptime,
            now = now,
        )
    }

    private fun scheduleEndpointBridge(
        angle: Float,
        priorAngle: Float,
        priorChangeUptime: Long,
        now: Long,
    ) {
        if (!priorAngle.isFinite() || priorChangeUptime == 0L) return

        val dtMs = now - priorChangeUptime
        if (dtMs <= 0L || dtMs > ENDPOINT_BRIDGE_SAMPLE_MAX_MS) return

        val velocity =
            (angle - priorAngle) * 1_000f / dtMs.toFloat()

        val target =
            when {
                angle <= ENDPOINT_BRIDGE_CLOSED_MAX_DEG &&
                    velocity <= -ENDPOINT_BRIDGE_MIN_SPEED_DPS -> 0f

                angle >= ENDPOINT_BRIDGE_OPEN_MIN_DEG &&
                    velocity >= ENDPOINT_BRIDGE_MIN_SPEED_DPS -> 180f

                else -> return
            }

        val generation = endpointBridgeGeneration

        handler.postDelayed(
            {
                if (
                    !running ||
                    endpointBridgeGeneration != generation ||
                    SystemClock.uptimeMillis() - lastCallbackUptime <
                        ENDPOINT_BRIDGE_DELAY_MS
                ) {
                    return@postDelayed
                }

                com.duoopen.debug.DuoDiagnostics.event(
                    "angle-source",
                    "endpoint bridge from=$angle to=$target velocity=$velocity",
                )

                lastAngleSeen = target
                lastAngleChangeUptime = SystemClock.uptimeMillis()

                TransitionLab.recordSyntheticEndpoint(
                    angleDegrees =
                        target,
                    reason =
                        "endpoint bridge from=$angle velocity=$velocity",
                )

                hinge.feedExternal(target)
            },
            ENDPOINT_BRIDGE_DELAY_MS,
        )
    }

    private fun pollInterval(
        now: Long,
    ): Long {

        val moving =
            lastAngleChangeUptime != 0L &&
                now -
                lastAngleChangeUptime <=
                ACTIVE_BURST_MS

        return if (moving) {
            ACTIVE_POLL_MS
        } else {
            IDLE_POLL_MS
        }
    }

    private fun displayKey(d: Display): String {
        val m = runCatching { d.mode }.getOrNull() ?: return "${d.displayId}"
        return "${d.displayId}:${m.physicalWidth}x${m.physicalHeight}"
    }

    /**
     * The wallpaper only answers commands from its current target window, so
     * the anchor shows wallpaper and lives on the default display; it is
     * re-created when that display swaps panels.
     */
    private fun ensureAnchor() {
        val dm = context.getSystemService(DisplayManager::class.java)
        val display = dm.getDisplay(Display.DEFAULT_DISPLAY) ?: return
        val key = displayKey(display)
        if (anchor != null && key == anchorKey) return
        removeAnchor()
        val c = context.createDisplayContext(display)
            .createWindowContext(WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY, null)
        val wm = c.getSystemService(WindowManager::class.java)
        val v = View(c)
        val params = WindowManager.LayoutParams(
            1, 1,
            WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                WindowManager.LayoutParams.FLAG_SHOW_WALLPAPER,
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            title = "DuoOpenAngleAnchor"
        }
        wm.addView(v, params)
        anchor = v
        anchorWm = wm
        anchorKey = key
    }

    private fun removeAnchor() {
        val v = anchor ?: return
        runCatching { anchorWm?.removeViewImmediate(v) }
        anchor = null
        anchorWm = null
        anchorKey = ""
    }

    companion object {
        private const val TAG = "DuoAngleFeed"
        // Low overhead while the phone is stationary.
        const val IDLE_POLL_MS = 33L

        // Near-display-refresh polling while moving.
        const val ACTIVE_POLL_MS = 8L

        // Remain in fast mode briefly after the last movement.
        const val ACTIVE_BURST_MS = 900L

        const val ANGLE_CHANGE_EPS = 0.10f

        private const val ENDPOINT_BRIDGE_DELAY_MS = 140L
        private const val ENDPOINT_BRIDGE_SAMPLE_MAX_MS = 300L
        private const val ENDPOINT_BRIDGE_CLOSED_MAX_DEG = 8.0f
        private const val ENDPOINT_BRIDGE_OPEN_MIN_DEG = 172.0f
        private const val ENDPOINT_BRIDGE_MIN_SPEED_DPS = 18.0f

        private const val STALE_MS = 2_500L
        val FOLD_WALLPAPER = ComponentName(
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
                    WallpaperManager.getInstance(
                        context
                    ).wallpaperInfo
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
                    WallpaperManager.getInstance(
                        context
                    ).wallpaperInfo
                }.getOrNull()
                    ?: return "none"

            val service =
                info.serviceName
                    .substringAfterLast(
                        '.'
                    )
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
