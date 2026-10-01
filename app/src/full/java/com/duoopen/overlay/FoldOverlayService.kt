package com.duoopen.overlay

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.hardware.display.DisplayManager
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.util.Log
import android.view.Display
import com.duoopen.debug.DuoDiagnostics
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityManager
import com.duoopen.fold.HingeAngleSource
import com.duoopen.fold.isLivePanel
import com.duoopen.settings.DuoSettings
import com.duoopen.shell.ShizukuBridge
import com.duoopen.shell.WallpaperAngleFeed
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.MainScope
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * System-wide fold effect. Accessibility services may screenshot any display
 * and draw above every other window, which is what lets the fold cover the
 * launcher, lock screen and apps — not just the wallpaper.
 *
 * Runs one [PanelEngine] per lit built-in display and keeps that set in step
 * with the DisplayManager: a panel that lights up mid-fold gets an engine
 * (which captures it as the second half of the fold), one that switches off
 * loses its engine. Phones that only ever light one panel (OnePlus Open)
 * therefore run a single engine whose display flips mode at the swap; phones
 * that keep both panels on run the cover and inner engines together, so the
 * handover has no gap.
 */
class FoldOverlayService : AccessibilityService() {

    private val handler = Handler(Looper.getMainLooper())
    private val scope = MainScope()
    private lateinit var hinge: HingeAngleSource
    private lateinit var displayManager: DisplayManager
    private val engines = LinkedHashMap<Int, PanelEngine>()
    private val snapshots = SnapshotCache(maxAgeMs = SNAPSHOT_MAX_AGE_MS)
    private var angleFeed: WallpaperAngleFeed? = null

    private lateinit var continuity: Fold7ContinuityCoordinator

    /**
     * Automatically arm Fold7 geometry continuity once per accessibility-service
     * lifetime after Shizuku becomes ready.
     *
     * This is equivalent to pressing "Arm geometry continuity (4°)" once after
     * startup. It deliberately does not repeatedly re-arm on later Shizuku state
     * emissions, which could otherwise reset an active fold transition.
     */
    private var continuityAutoArmAttempted =
        false

    private var pendingProbeReason =
        "service-connected"

    private var lastDisplayProbeUptime =
        0L

    private val displayProbeRunnable =
        Runnable {
            runDisplayProbe(
                pendingProbeReason
            )
        }

    private var coverRoutePrimeAttempted =
        false

    private var pendingDisplaySyncReason =
        ""

    private val displaySyncRunnable =
        Runnable {
            val reason =
                pendingDisplaySyncReason

            pendingDisplaySyncReason =
                ""

            com.duoopen.debug.DuoDiagnostics.event(
                "live-mirror",
                "display callbacks coalesced reason=$reason",
            )

            syncDisplays()
        }

    private fun scheduleDisplaySync(
        reason: String,
    ) {
        pendingDisplaySyncReason =
            reason

        handler.removeCallbacks(
            displaySyncRunnable
        )

        handler.postDelayed(
            displaySyncRunnable,
            DISPLAY_SYNC_DEBOUNCE_MS,
        )
    }

    private val displayListener =
        object :
            DisplayManager.DisplayListener {

            override fun onDisplayAdded(
                displayId: Int,
            ) {
                scheduleDisplaySync(
                    "display-added:$displayId"
                )
            }

            override fun onDisplayRemoved(
                displayId: Int,
            ) {
                scheduleDisplaySync(
                    "display-removed:$displayId"
                )
            }

            override fun onDisplayChanged(
                displayId: Int,
            ) {
                scheduleDisplaySync(
                    "display-changed:$displayId"
                )
            }
        }

    /** `adb shell am broadcast -a com.duoopen.DEMO` plays the effect over whatever is on screen. */
    private val demoReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) = playDemo()
    }
    private var receiverRegistered = false

    override fun onServiceConnected() {
        super.onServiceConnected()
        PersistentRuntimeService.ensureRunning(this)
        instance = this

        PersistentRuntimeService.ensureRunning(
            this
        )
        if (!receiverRegistered) {
            registerReceiver(demoReceiver, IntentFilter(ACTION_DEMO), RECEIVER_EXPORTED)
            receiverRegistered = true
        }
        displayManager = getSystemService(DisplayManager::class.java)
        continuity = Fold7ContinuityCoordinator(
            service = this,
            displayManager = displayManager,
            handler = handler,
            scope = scope,
            currentHingeAngle = { hinge.lastAngle },
            onStatus = { message -> _secondaryDisplayStatus.value = message },
        )
        displayManager.registerDisplayListener(displayListener, handler)
        hinge = HingeAngleSource(this) { onHinge(it) }
        hinge.start()
        ShizukuBridge.init(this)
        angleFeed = WallpaperAngleFeed(this, handler, hinge)
        scope.launch {
            ShizukuBridge.state.collect { state ->
                syncAngleFeed()

                if (
                    state is
                        ShizukuBridge.State.Ready
                ) {
                    continuity.onPrivilegedReady()

                    if (!continuityAutoArmAttempted) {
                        continuityAutoArmAttempted =
                            true

                        continuity.arm()
                    }
                    primeCoverRoute(
                        "shizuku-ready"
                    )
                } else {
                    continuity.onPrivilegedUnavailable()
                }
            }
        }

        scope.launch {
            DuoSettings.config.collect {
                syncAngleFeed()
            }
        }

        syncDisplays()

        Log.i(
            TAG,
            "connected; hinge=${hinge.sensor?.name} live displays=${engines.keys}",
        )
    }

    override fun onDestroy() {
        instance = null

        if (::continuity.isInitialized) {
            continuity.destroy()
        }

        handler.removeCallbacks(
            displayProbeRunnable
        )

        handler.removeCallbacks(
            displaySyncRunnable
        )

        angleFeed?.stop()
        if (receiverRegistered) unregisterReceiver(demoReceiver)
        hinge.stop()
        displayManager.unregisterDisplayListener(displayListener)
        for (e in engines.values) e.destroy()
        engines.clear()
        OverlayState.setRunning(false)
        scope.cancel()
        super.onDestroy()
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit
    override fun onInterrupt() = Unit

    private fun onHinge(angle: Float) {
        continuity.onHinge(angle)

        for (engine in engines.values.toList()) {
            engine.onHinge(angle)
        }
    }

    /** Starts engines for panels that lit up, stops those that went dark, then lets each re-evaluate. */
    private fun syncDisplays() {
        // `adb shell settings put global duoopen_test_displays 1` lets a
        // simulated secondary display stand in for a second panel (see Panels.kt).
        val testDisplays = Settings.Global.getInt(contentResolver, TEST_DISPLAYS_SETTING, 0) != 0
        val defaultName = runCatching { displayManager.getDisplay(Display.DEFAULT_DISPLAY)?.name }.getOrNull()
        val live = displayManager.displays
            .filter { it.isLivePanel(defaultDisplayName = defaultName, includePresentation = testDisplays) }
            .associateBy { it.displayId }
        val gone = engines.keys.filter { it !in live }
        for (id in gone) {
            engines.remove(id)?.destroy()
        }
        for ((id, display) in live) {
            if (id !in engines) {
                engines[id] = PanelEngine(
                    service = this,
                    display = display,
                    hinge = hinge,
                    handler = handler,
                    scope = scope,
                    hasLiveInnerElsewhere = { engines.values.any { it !== engines[id] && it.innerPanel } },
                    onShowingChanged = ::updateRunning,
                    cache = snapshots,
                )
            }
        }
        if (gone.isNotEmpty()) updateRunning()
        if (!continuity.visualMirrorActive) {
            for (e in engines.values.toList()) {
                e.evaluate()
            }
        }

        angleFeed?.onDisplayChanged()

        continuity.onTopologyChanged(
            "sync-displays"
        )
    }

    /** Samsung continuous angle via Shizuku + fold wallpaper, when everything lines up. */
    private fun syncAngleFeed() {
        val feed = angleFeed ?: return
        /*
         * Do not gate the live Samsung angle reader on WallpaperManager.
         *
         * On the Fold7, the inner display reports Samsung's FoldInteractive
         * service while the cover display may report a Video wallpaper.
         * That metadata switch does not prove the underlying angle source has
         * disappeared. The real authority is whether fresh angle callbacks
         * continue arriving from the Shizuku-side log reader.
         */
        val want =
            DuoSettings.config.value.shizukuAngle &&
                ShizukuBridge.ready

        if (
            want &&
            !feed.active
        ) {
            feed.start()
        } else if (
            !want &&
            feed.active
        ) {
            feed.stop()
        }
    }

    fun angleFeedStatus(): String =
        angleFeed?.status ?: "Idle"

    private fun scheduleDisplayProbe(
        reason: String,
        delayMs: Long =
            DISPLAY_PROBE_DEBOUNCE_MS,
    ) {
        if (
            !ShizukuBridge.ready
        ) {
            return
        }

        pendingProbeReason =
            reason

        handler.removeCallbacks(
            displayProbeRunnable
        )

        handler.postDelayed(
            displayProbeRunnable,
            delayMs,
        )
    }

    private fun runDisplayProbe(
        reason: String,
    ) {
        if (
            !ShizukuBridge.ready
        ) {
            return
        }

        val now =
            android.os.SystemClock
                .uptimeMillis()

        val elapsed =
            now -
                lastDisplayProbeUptime

        if (
            lastDisplayProbeUptime != 0L &&
            elapsed <
                DISPLAY_PROBE_MIN_GAP_MS
        ) {
            handler.removeCallbacks(
                displayProbeRunnable
            )

            handler.postDelayed(
                displayProbeRunnable,
                DISPLAY_PROBE_MIN_GAP_MS -
                    elapsed,
            )

            return
        }

        lastDisplayProbeUptime =
            now

        val local =
            displayManager.displays
                .joinToString(
                    " | "
                ) { display ->

                    val mode =
                        runCatching {
                            display.mode
                        }.getOrNull()

                    (
                        "id=${display.displayId} " +
                            "name=${display.name} " +
                            "state=${display.state} " +
                            "mode=${mode?.physicalWidth}x" +
                            "${mode?.physicalHeight}@" +
                            "${mode?.refreshRate}Hz"
                        )
                }

        DuoDiagnostics.event(
            "display-probe",
            "begin reason=$reason local=[$local]",
        )

        scope.launch(
            Dispatchers.IO
        ) {
            val result =
                ShizukuBridge.displayProbe()

            if (
                result == null
            ) {
                DuoDiagnostics.event(
                    "display-probe",
                    "unavailable reason=$reason",
                )

                return@launch
            }

            result.getString(
                "error"
            )?.let { error ->

                DuoDiagnostics.event(
                    "display-probe",
                    "shell error reason=$reason error=$error",
                )
            }

            DuoDiagnostics.event(
                "display-probe",
                "shell uid=${result.getInt("uid", -1)} " +
                    "pid=${result.getInt("pid", -1)} " +
                    "reason=$reason",
            )

            listOf(
                "identity",
                "cmd_display",
                "cmd_display_help",
                "surfaceflinger",
                "display_filtered",
                "window_displays",
            ).forEach { key ->

                val value =
                    result.getString(
                        key
                    ) ?: "(missing)"

                DuoDiagnostics.event(
                    "display-probe",
                    "$key=" +
                        value
                            .replace(
                                "\r",
                                ""
                            )
                            .replace(
                                "\n",
                                "\\n"
                            ),
                )
            }
        }
    }

    private fun primeCoverRoute(
        reason: String,
    ) {
        if (
            coverRoutePrimeAttempted ||
            !ShizukuBridge.ready
        ) {
            return
        }

        coverRoutePrimeAttempted =
            true

        scope.launch(
            Dispatchers.IO
        ) {
            val result =
                ShizukuBridge.resolveCoverDisplay()

            val physicalId =
                result?.getLong(
                    "physicalDisplayId",
                    -1L,
                ) ?: -1L

            val innerPhysicalId =
                result?.getLong(
                    "innerPhysicalDisplayId",
                    -1L,
                ) ?: -1L

            val ok =
                result?.getBoolean(
                    "ok",
                    false,
                ) == true

            DuoDiagnostics.event(
                "cover-route",
                "prime reason=$reason coverPhysicalId=$physicalId " +
                    "innerPhysicalId=$innerPhysicalId ok=$ok",
            )
        }
    }

    private fun updateRunning() {
        OverlayState.setRunning(engines.values.any { it.showing })
    }

    /** Replays the effect on every lit panel — the default display is the one you're looking at. */
    fun playDemo() {
        syncDisplays()
        (engines[Display.DEFAULT_DISPLAY]?.let { listOf(it) } ?: engines.values.toList())
            .forEach { it.playDemo() }
    }

    companion object {
        private const val TAG = "DuoOverlay"
        const val ACTION_DEMO = "com.duoopen.DEMO"

        private const val TEST_DISPLAYS_SETTING =
            "duoopen_test_displays"

        private const val DISPLAY_PROBE_DEBOUNCE_MS =
            450L

        private const val DISPLAY_PROBE_MIN_GAP_MS =
            1_500L

        private val _secondaryDisplayStatus =
            MutableStateFlow(
                "Service-owned secondary-panel test is idle."
            )

        val secondaryDisplayStatus:
            StateFlow<String> =
            _secondaryDisplayStatus.asStateFlow()

        fun testSecondaryDisplay(
            enable: Boolean,
        ): Boolean {
            val service =
                instance
                    ?: run {
                        _secondaryDisplayStatus.value =
                            "The Duo Open accessibility service isn't connected."
                        return false
                    }

            if (enable) {
                service.continuity.arm()
            } else {
                service.continuity.release(
                    "user-stop"
                )
            }

            return true
        }

        private const val DISPLAY_SYNC_DEBOUNCE_MS =
            24L

        /** How old a panel's last picture may be and still bridge the next fold. */
        private const val SNAPSHOT_MAX_AGE_MS = 15 * 60_000L

        /** The connected service, for in-process control from the app. */
        @Volatile
        var instance: FoldOverlayService? = null
            private set

        fun isEnabled(context: Context): Boolean {
            val am = context.getSystemService(AccessibilityManager::class.java) ?: return false
            val self = ComponentName(context, FoldOverlayService::class.java)
            return am.getEnabledAccessibilityServiceList(AccessibilityServiceInfo.FEEDBACK_ALL_MASK)
                .any { it.resolveInfo.serviceInfo.let { s -> ComponentName(s.packageName, s.name) } == self }
        }
    }
}
