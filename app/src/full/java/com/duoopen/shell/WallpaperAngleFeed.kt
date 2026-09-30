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
    private data class AnchorBinding(
        val key: String,
        val displayId: Int,
        val width: Int,
        val height: Int,
        val view: View,
        val windowManager: WindowManager,
    )

    private var running = false
    private var action = ""

    /**
     * Fold7 can expose the cover and inner panels as two logical routes at the
     * same time. Keep a tiny wallpaper target on every known physical Fold7
     * panel so the FoldInteractive service can answer before Samsung changes
     * which route is DEFAULT_DISPLAY.
     */
    private val anchors =
        LinkedHashMap<String, AnchorBinding>()

    private val anchorRetryAfter =
        HashMap<String, Long>()

    private var lastAnchorSummary =
        ""

    private var lastCallbackUptime = 0L

    private var lastDeliveryLagMs = -1L
    private var maxDeliveryLagMs = 0L

    private var lastAngleSeen = Float.NaN
    private var lastAngleChangeUptime = 0L

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
                runCatching {
                    ensureAnchors()
                }.onFailure { error ->
                    status =
                        "Anchor refresh failed: ${error.message}"
                }

                for (binding in anchors.values) {
                    val view =
                        binding.view

                    if (view.windowToken != null) {
                        runCatching {
                            WallpaperManager
                                .getInstance(
                                    view.context
                                )
                                .sendWallpaperCommand(
                                    view.windowToken,
                                    action,
                                    0,
                                    0,
                                    0,
                                    null,
                                )
                        }.onFailure { error ->
                            com.duoopen.debug.DuoDiagnostics.event(
                                "angle-source",
                                "wallpaper command failed " +
                                    "display=${binding.displayId} " +
                                    "geometry=${binding.width}x${binding.height} " +
                                    "error=${error.javaClass.simpleName}:" +
                                    "${error.message}",
                            )
                        }
                    }
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
                        " · anchors ${anchors.size}" +
                        " · visible ${b.getInt("visibleParsed", 0)}" +
                        " · hidden ${b.getInt("hiddenAccepted", 0)}/" +
                        "${b.getInt("hiddenParsed", 0)}" +
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
            ) { angle, sourceUptime ->
                handler.post {
                    onAngle(
                        angle,
                        sourceUptime,
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
        removeAnchors()
        status = "Stopped"
        Log.i(TAG, "wallpaper angle feed stopped")
    }

    /** Re-check the Fold7 wallpaper targets after any display topology change. */
    fun onDisplayChanged() {
        if (running) {
            runCatching {
                ensureAnchors()
            }
        }
    }

    private fun onAngle(
        angle: Float,
        sourceUptime: Long,
    ) {
        if (!running) return

        val now =
            SystemClock.uptimeMillis()

        lastCallbackUptime =
            now

        lastDeliveryLagMs =
            (now - sourceUptime)
                .coerceAtLeast(0L)

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

    private fun isFold7Panel(
        display: Display,
    ): Boolean {
        val mode =
            runCatching {
                display.mode
            }.getOrNull()
                ?: return false

        return (
            mode.physicalWidth ==
                COVER_WIDTH &&
                mode.physicalHeight ==
                    COVER_HEIGHT
            ) ||
            (
                mode.physicalWidth ==
                    INNER_WIDTH &&
                    mode.physicalHeight ==
                    INNER_HEIGHT
                )
    }

    /**
     * Keep wallpaper-showing 1×1 windows on every currently exposed physical
     * Fold7 panel. Samsung may keep FoldInteractive associated with the inner
     * route while the cover is DEFAULT_DISPLAY, so a default-only anchor can
     * miss the beginning of an unfold.
     *
     * Other devices retain the old behavior and get one anchor on the default
     * display only.
     */
    private fun ensureAnchors() {
        val displayManager =
            context.getSystemService(
                DisplayManager::class.java
            )

        val allDisplays =
            displayManager.displays
                .toList()

        val fold7Displays =
            allDisplays.filter(
                ::isFold7Panel
            )

        val targets =
            if (fold7Displays.isNotEmpty()) {
                fold7Displays
            } else {
                listOfNotNull(
                    displayManager.getDisplay(
                        Display.DEFAULT_DISPLAY
                    )
                )
            }

        val wantedKeys =
            targets.mapTo(
                LinkedHashSet<String>()
            ) { display ->
                displayKey(
                    display
                )
            }

        val iterator =
            anchors.entries.iterator()

        while (iterator.hasNext()) {
            val entry =
                iterator.next()

            if (entry.key !in wantedKeys) {
                val binding =
                    entry.value

                runCatching {
                    binding.windowManager
                        .removeViewImmediate(
                            binding.view
                        )
                }

                iterator.remove()

                com.duoopen.debug.DuoDiagnostics.event(
                    "angle-source",
                    "anchor removed display=${binding.displayId} " +
                        "geometry=${binding.width}x${binding.height}",
                )
            }
        }

        val now =
            SystemClock.uptimeMillis()

        for (display in targets) {
            val key =
                displayKey(
                    display
                )

            if (anchors.containsKey(key)) {
                continue
            }

            val retryAfter =
                anchorRetryAfter[key] ?:
                    0L

            if (now < retryAfter) {
                continue
            }

            val mode =
                runCatching {
                    display.mode
                }.getOrNull()
                    ?: continue

            runCatching {
                val displayContext =
                    context
                        .createDisplayContext(
                            display
                        )
                        .createWindowContext(
                            WindowManager.LayoutParams
                                .TYPE_ACCESSIBILITY_OVERLAY,
                            null,
                        )

                val windowManager =
                    displayContext.getSystemService(
                        WindowManager::class.java
                    )

                val view =
                    View(
                        displayContext
                    )

                val params =
                    WindowManager.LayoutParams(
                        1,
                        1,
                        WindowManager.LayoutParams
                            .TYPE_ACCESSIBILITY_OVERLAY,
                        WindowManager.LayoutParams
                            .FLAG_NOT_FOCUSABLE or
                            WindowManager.LayoutParams
                                .FLAG_NOT_TOUCHABLE or
                            WindowManager.LayoutParams
                                .FLAG_SHOW_WALLPAPER,
                        PixelFormat.TRANSLUCENT,
                    ).apply {
                        gravity =
                            Gravity.TOP or
                                Gravity.START

                        title =
                            "DuoOpenAngleAnchor-" +
                                "${mode.physicalWidth}x" +
                                "${mode.physicalHeight}"
                    }

                windowManager.addView(
                    view,
                    params,
                )

                AnchorBinding(
                    key =
                        key,
                    displayId =
                        display.displayId,
                    width =
                        mode.physicalWidth,
                    height =
                        mode.physicalHeight,
                    view =
                        view,
                    windowManager =
                        windowManager,
                )
            }.onSuccess { binding ->
                anchors[key] =
                    binding

                anchorRetryAfter.remove(
                    key
                )

                com.duoopen.debug.DuoDiagnostics.event(
                    "angle-source",
                    "anchor attached display=${binding.displayId} " +
                        "geometry=${binding.width}x${binding.height} " +
                        "default=" +
                        (
                            binding.displayId ==
                                Display.DEFAULT_DISPLAY
                            ),
                )
            }.onFailure { error ->
                anchorRetryAfter[key] =
                    now +
                        ANCHOR_RETRY_MS

                com.duoopen.debug.DuoDiagnostics.event(
                    "angle-source",
                    "anchor unavailable display=${display.displayId} " +
                        "geometry=${mode.physicalWidth}x${mode.physicalHeight} " +
                        "error=${error.javaClass.simpleName}:" +
                        "${error.message}",
                )
            }
        }

        val summary =
            anchors.values
                .joinToString(
                    separator =
                        " | "
                ) { binding ->
                    "${binding.displayId}:" +
                        "${binding.width}x${binding.height}"
                }

        if (summary != lastAnchorSummary) {
            com.duoopen.debug.DuoDiagnostics.event(
                "angle-source",
                "anchors=${summary.ifEmpty { "none" }}",
            )

            lastAnchorSummary =
                summary
        }
    }

    private fun removeAnchors() {
        for (binding in anchors.values) {
            runCatching {
                binding.windowManager
                    .removeViewImmediate(
                        binding.view
                    )
            }
        }

        anchors.clear()
        anchorRetryAfter.clear()
        lastAnchorSummary =
            ""
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

        private const val ANCHOR_RETRY_MS =
            1_000L

        private const val COVER_WIDTH =
            1080

        private const val COVER_HEIGHT =
            2520

        private const val INNER_WIDTH =
            1968

        private const val INNER_HEIGHT =
            2184

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
