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

    private var mirrorRequested =
        false

    private var mirrorHost:
        DisplayMirrorHost? =
        null

    private var continuityArmed =
        false

    private var coverPowerHold =
        false

    private var openReferenceAngle =
        Float.NaN

    private var lastContinuityAngle =
        Float.NaN

    private var deliberateCloseSamples =
        0

    private var deliberateCloseStartAngle =
        Float.NaN

    private var deliberateCloseStartUptime =
        0L

    private var mirrorHostCreatedUptime =
        0L

    private val openReleaseRunnable =
        Runnable {
            if (
                coverPowerHold &&
                lastContinuityAngle >=
                    COVER_RELEASE_OPEN_MIN_DEG
            ) {
                releaseCoverPowerHold(
                    "returned-open-stable"
                )
            }
        }

    private var lastPowerAssertMs =
        0L

    private var powerAssertInFlight =
        false

    private var lastCoverLogicalId =
        -1

    private var coverRoutePrimeAttempted =
        false

    /**
     * Last watchdog power result, used only to avoid flooding diagnostics with
     * an identical event every 100 ms while the physical cover is held on.
     */
    private var lastPowerAssertOk:
        Boolean? =
        null

    private val coverPowerWatchdog =
        object : Runnable {
            override fun run() {
                if (!coverPowerHold) {
                    return
                }

                assertCoverPower(
                    reason =
                        "watchdog",
                    force =
                        true,
                )

                handler.postDelayed(
                    this,
                    COVER_POWER_ASSERT_INTERVAL_MS,
                )
            }
        }

    private val mirrorRefreshRunnable =
        Runnable {
            syncMirrorHost(
                "display-topology-change"
            )
        }

    private val secondaryDisplaySafetyReset =
        object : Runnable {
            override fun run() {
                if (safeToReleaseSecondaryPanel()) {
                    runSecondaryDisplayExperiment(
                        enable = false,
                        reason = "90-second safety release",
                    )
                } else {
                    _secondaryDisplayStatus.value =
                        "Safety release is waiting until the phone is fully open."

                    handler.postDelayed(
                        this,
                        2_000L,
                    )
                }
            }
        }

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
                    if (!continuityAutoArmAttempted) {
                        continuityAutoArmAttempted =
                            true

                        continuity.arm()
                    }
                    primeCoverRoute(
                        "shizuku-ready"
                    )
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
            mirrorRefreshRunnable
        )

        handler.removeCallbacks(
            openReleaseRunnable
        )

        mirrorRequested =
            false

        mirrorHost?.detach()
        mirrorHost =
            null
        mirrorHostCreatedUptime =
            0L

        runCatching {
            ShizukuBridge.stopDisplayMirror()
        }

        handler.removeCallbacks(
            secondaryDisplaySafetyReset
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

    private fun resolveCoverLogicalId(): Int {
        val cover =
            displayManager.displays
                .firstOrNull { candidate ->
                    val mode =
                        candidate.mode

                    mode.physicalWidth == 1080 &&
                        mode.physicalHeight == 2520
                }

        if (cover != null) {
            lastCoverLogicalId =
                cover.displayId
        }

        return lastCoverLogicalId
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

    private fun assertCoverPower(
        reason: String,
        force: Boolean = false,
    ) {
        if (force && reason.isEmpty()) {
            Log.d(TAG, "logical power watchdog disabled")
        }
    }

    private fun releaseCoverPowerHold(
        reason: String,
    ) {
        if (
            !coverPowerHold &&
            !mirrorRequested
        ) {
            openReferenceAngle =
                Float.NaN

            return
        }

        coverPowerHold =
            false

        mirrorRequested =
            false

        lastPowerAssertMs =
            0L

        handler.removeCallbacks(
            mirrorRefreshRunnable
        )

        handler.removeCallbacks(
            openReleaseRunnable
        )

        handler.removeCallbacks(
            coverPowerWatchdog
        )

        mirrorHost?.detach()
        mirrorHost =
            null
        mirrorHostCreatedUptime =
            0L

        val releaseTarget =
            resolveCurrentSecondaryCoverLogicalId()

        scope.launch(
            Dispatchers.IO
        ) {
            ShizukuBridge.stopDisplayMirror()

            ShizukuBridge.resetSecondaryDisplay(
                releaseTarget
            )
        }

        openReferenceAngle =
            Float.NaN

        _secondaryDisplayStatus.value =
            "Geometry continuity armed; cover returned to Samsung."

        com.duoopen.debug.DuoDiagnostics.event(
            "cover-power",
            "released reason=$reason target=$releaseTarget",
        )
    }

    private fun armGeometryContinuity() {
        continuityArmed =
            true

        coverPowerHold =
            false

        mirrorRequested =
            false

        openReferenceAngle =
            Float.NaN

        lastPowerAssertMs =
            0L

        powerAssertInFlight =
            false

        lastCoverLogicalId =
            -1

        lastContinuityAngle =
            Float.NaN

        lastPowerAssertOk =
            null

        handler.removeCallbacks(
            mirrorRefreshRunnable
        )

        handler.removeCallbacks(
            openReleaseRunnable
        )

        handler.removeCallbacks(
            coverPowerWatchdog
        )

        handler.removeCallbacks(
            secondaryDisplaySafetyReset
        )

        mirrorHost?.detach()
        mirrorHost =
            null
        mirrorHostCreatedUptime =
            0L

        _secondaryDisplayStatus.value =
            "ARMED: cover stays off until 4° of deliberate closing travel."

        com.duoopen.debug.DuoDiagnostics.event(
            "cover-power",
            "armed triggerDeg=$COVER_WAKE_TRAVEL_DEG " +
                "releaseOpenMinDeg=$COVER_RELEASE_OPEN_MIN_DEG",
        )

        scope.launch(
            Dispatchers.IO
        ) {
            ShizukuBridge.stopDisplayMirror()
        }
    }

    private fun resetDeliberateCloseEvidence() {
        deliberateCloseSamples =
            0

        deliberateCloseStartAngle =
            Float.NaN

        deliberateCloseStartUptime =
            0L
    }

    /**
     * A logical id is usable only while DisplayManager says it is the
     * non-default 1080x2520 physical cover. Never cache this value.
     */
    private fun resolveCurrentSecondaryCoverLogicalId(): Int {
        val cover =
            displayManager.displays
                .firstOrNull { candidate ->
                    val mode =
                        candidate.mode

                    mode.physicalWidth == 1080 &&
                        mode.physicalHeight == 2520 &&
                        candidate.displayId !=
                            Display.DEFAULT_DISPLAY &&
                        candidate.state !=
                            Display.STATE_OFF &&
                        candidate.state !=
                            Display.STATE_UNKNOWN
                }

        return cover?.displayId
            ?: -1
    }

    private fun handleContinuityHinge(
        angle: Float,
    ) {
        val previous =
            lastContinuityAngle

        lastContinuityAngle =
            angle

        if (!continuityArmed) {
            return
        }

        if (openReferenceAngle.isNaN()) {
            openReferenceAngle =
                angle

            DuoDiagnostics.event(
                "cover-power",
                "baseline=$angle mode=armed",
            )

            return
        }

        val closingSample =
            !previous.isNaN() &&
                previous - angle >=
                    COVER_SAMPLE_EPSILON_DEG

        val openingSample =
            !previous.isNaN() &&
                angle - previous >=
                    COVER_SAMPLE_EPSILON_DEG

        if (
            openingSample &&
            previous <=
                COVER_CLOSED_READY_MAX_DEG
        ) {
            DuoDiagnostics.event(
                "cover-power",
                "closed-open-start angle=$angle previous=$previous serviceHot=true",
            )
        }

        if (!coverPowerHold) {
            if (angle > openReferenceAngle) {
                openReferenceAngle =
                    angle
            }

            /*
             * CLOSED -> OPEN: the native cover is already the active
             * screen. Keep the runtime, Shizuku daemon and angle feed
             * hot while shut; the local cover effect reacts to the
             * first real opening sample without a shell wake command.
             *
             * OPEN -> CLOSED: do not expose anything on the front in
             * the upper half. Pre-warm the secondary cover around 150°
             * so it is ready, but keep the live mirror hidden until
             * the hinge reaches the quarter-fold point (~135°).
             */
            if (
                closingSample &&
                angle <= COVER_CLOSE_PREWARM_DEG &&
                angle > COVER_NATIVE_HANDOFF_MAX_DEG
            ) {
                val currentCover =
                    resolveCurrentSecondaryCoverLogicalId()

                if (currentCover >= 0) {
                    coverPowerHold =
                        true

                    mirrorRequested =
                        false

                    _secondaryDisplayStatus.value =
                        "Closing: cover pre-warmed; front visual starts after one-quarter fold travel."

                    DuoDiagnostics.event(
                        "cover-power",
                        "closing-prewarm angle=$angle target=$currentCover " +
                            "visualStart=$COVER_CLOSE_VISUAL_START_DEG",
                    )

                    runSecondaryDisplayExperiment(
                        enable = true,
                        reason = "closing-prewarm",
                    )
                } else {
                    DuoDiagnostics.event(
                        "cover-power",
                        "closing-prewarm deferred angle=$angle " +
                            "reason=no-stable-secondary-cover",
                    )
                }
            }

            return
        }

        if (
            closingSample &&
            !mirrorRequested &&
            angle <= COVER_CLOSE_VISUAL_START_DEG
        ) {
            mirrorRequested =
                true

            DuoDiagnostics.event(
                "cover-power",
                "closing-visual-start angle=$angle",
            )

            syncMirrorHost(
                "closing-quarter-visual"
            )
        }

        if (
            openingSample &&
            mirrorRequested &&
            angle >= COVER_CLOSE_VISUAL_END_DEG
        ) {
            mirrorRequested =
                false

            mirrorHost?.detach()
            mirrorHost =
                null

            mirrorHostCreatedUptime =
                0L

            scope.launch(
                Dispatchers.IO
            ) {
                ShizukuBridge.stopDisplayMirror()
            }

            DuoDiagnostics.event(
                "cover-power",
                "opening-cover-visual-hidden angle=$angle",
            )
        }

        if (
            openingSample &&
            angle >= COVER_RELEASE_OPEN_MIN_DEG
        ) {
            handler.removeCallbacks(
                openReleaseRunnable
            )

            handler.postDelayed(
                openReleaseRunnable,
                COVER_RELEASE_DWELL_MS,
            )
        } else if (
            angle < COVER_RELEASE_CANCEL_DEG
        ) {
            handler.removeCallbacks(
                openReleaseRunnable
            )
        }

        val cover =
            displayManager.displays
                .firstOrNull { candidate ->
                    val mode = candidate.mode
                    mode.physicalWidth == 1080 &&
                        mode.physicalHeight == 2520
                }

        val inner =
            displayManager.displays
                .firstOrNull { candidate ->
                    val mode = candidate.mode
                    mode.physicalWidth == 1968 &&
                        mode.physicalHeight == 2184
                }

        val nativeCover =
            cover?.displayId == Display.DEFAULT_DISPLAY &&
                cover.state != Display.STATE_OFF &&
                cover.state != Display.STATE_UNKNOWN &&
                (
                    inner == null ||
                        inner.state == Display.STATE_OFF ||
                        inner.state == Display.STATE_UNKNOWN
                    )

        if (
            nativeCover &&
            angle <= COVER_NATIVE_HANDOFF_MAX_DEG
        ) {
            handler.removeCallbacks(
                openReleaseRunnable
            )

            releaseCoverPowerHold(
                "native-cover-handoff"
            )
        }
    }

    fun runSecondaryDisplayExperiment(
        enable: Boolean,
        reason: String = "user",
    ) {
        if (!ShizukuBridge.ready) {
            _secondaryDisplayStatus.value =
                "Shizuku isn't ready."

            DuoDiagnostics.event(
                "dual-shell",
                "refused enable=$enable reason=$reason; Shizuku not ready",
            )
            return
        }

        handler.removeCallbacks(
            secondaryDisplaySafetyReset
        )

        _secondaryDisplayStatus.value =
            if (enable) {
                "Requesting the inactive Fold7 panel from the persistent service…"
            } else {
                "Returning the secondary panel to Samsung's normal power state…"
            }

        com.duoopen.debug.DuoDiagnostics.event(
            "dual-shell",
            "begin enable=$enable reason=$reason",
        )

        if (!enable) {
            continuityArmed =
                false

            coverPowerHold =
                false

            openReferenceAngle =
                Float.NaN

            mirrorRequested =
                false

            handler.removeCallbacks(
                mirrorRefreshRunnable
            )

            mirrorHost?.detach()
            mirrorHost =
                null
        }

        val targetHint =
            resolveCurrentSecondaryCoverLogicalId()

        if (
            enable &&
            targetHint < 0
        ) {
            _secondaryDisplayStatus.value =
                "Fold7 cover route is changing; unsafe enable skipped."

            DuoDiagnostics.event(
                "dual-shell",
                "skip enable reason=$reason; no stable secondary cover route",
            )

            return
        }

        scope.launch(Dispatchers.IO) {
            if (!enable) {
                ShizukuBridge.stopDisplayMirror()
            }

            val result =
                if (enable) {
                    ShizukuBridge.enableSecondaryDisplay(
                    targetHint
                )
                } else {
                    ShizukuBridge.resetSecondaryDisplay(
                    targetHint
                )
                }

            if (result == null) {
                _secondaryDisplayStatus.value =
                    "No response from the Shizuku display service."

                DuoDiagnostics.event(
                    "dual-shell",
                    "no binder response enable=$enable reason=$reason",
                )
                return@launch
            }

            val ok =
                result.getBoolean(
                    "ok",
                    false,
                )

            val target =
                result.getInt(
                    "targetDisplayId",
                    -1,
                )

            if (
                enable &&
                target >= 0 &&
                target ==
                    resolveCurrentSecondaryCoverLogicalId()
            ) {
                lastCoverLogicalId =
                    target
            }

            val width =
                result.getInt(
                    "targetWidth",
                    -1,
                )

            val height =
                result.getInt(
                    "targetHeight",
                    -1,
                )

            val visibleAfter =
                result.getBoolean(
                    "visibleAfter",
                    false,
                )

            val error =
                result.getString("error")

            val command =
                result.getString("command")

            val commandOutput =
                result.getString(
                    "commandOutput"
                ) ?: ""

            _secondaryDisplayStatus.value =
                when {
                    !ok ->
                        "Shell command did not succeed" +
                            (error?.let { ": $it" } ?: ".")

                    enable && visibleAfter ->
                        "Success: Android exposes Fold7 display $target " +
                            "($width×$height). Leave Duo Open and test it."

                    enable ->
                        "Fast enable accepted for display $target; " +
                            "waiting for the Fold7 topology callback."

                    else ->
                        "Secondary panel power was returned to Samsung."
                }

            DuoDiagnostics.event(
                "dual-shell",
                "result enable=$enable ok=$ok target=$target " +
                    "size=${width}x$height visibleAfter=$visibleAfter " +
                    "command=$command error=$error output=" +
                    commandOutput
                        .replace("\r", "")
                        .replace("\n", "\\n"),
            )

            if (
                enable &&
                ok
            ) {
                handler.post {
                    mirrorRequested =
                        true

                    syncMirrorHost(
                        "secondary-enabled"
                    )
                }
            }

        }
    }

    private fun scheduleMirrorRefresh(
        reason: String,
    ) {
        if (!mirrorRequested) {
            return
        }

        handler.removeCallbacks(
            mirrorRefreshRunnable
        )

        handler.removeCallbacks(
            openReleaseRunnable
        )

        handler.postDelayed(
            mirrorRefreshRunnable,
            MIRROR_REBIND_DEBOUNCE_MS,
        )

        com.duoopen.debug.DuoDiagnostics.event(
            "live-mirror",
            "refresh scheduled reason=$reason",
        )
    }

    private fun syncMirrorHost(
        reason: String,
    ) {
        if (!mirrorRequested) {
            return
        }

        val displays =
            displayManager.displays.toList()

        fun isActive(
            candidate: Display,
        ): Boolean =
            candidate.state != Display.STATE_OFF &&
                candidate.state != Display.STATE_UNKNOWN

        fun isInnerPanel(
            candidate: Display,
        ): Boolean {
            val mode =
                candidate.mode

            return mode.physicalWidth == 1968 &&
                mode.physicalHeight == 2184
        }

        fun isCoverPanel(
            candidate: Display,
        ): Boolean {
            val mode =
                candidate.mode

            return mode.physicalWidth == 1080 &&
                mode.physicalHeight == 2520
        }

        val inner =
            displays.firstOrNull(
                ::isInnerPanel
            )

        val cover =
            displays.firstOrNull(
                ::isCoverPanel
            )

        val activeInner =
            inner?.takeIf(
                ::isActive
            )

        val activeCover =
            cover?.takeIf(
                ::isActive
            )

        com.duoopen.debug.DuoDiagnostics.event(
            "live-mirror",
            "physical-resolve reason=$reason " +
                "innerLogical=${inner?.displayId} " +
                "innerMode=${inner?.mode?.physicalWidth}x" +
                "${inner?.mode?.physicalHeight} " +
                "innerState=${inner?.state} " +
                "coverLogical=${cover?.displayId} " +
                "coverMode=${cover?.mode?.physicalWidth}x" +
                "${cover?.mode?.physicalHeight} " +
                "coverState=${cover?.state} " +
                "defaultLogical=${Display.DEFAULT_DISPLAY} " +
                "hostLogical=${mirrorHost?.displayId} " +
                "hostUsable=${mirrorHost?.isUsable == true}",
        )

        if (activeCover == null) {
            _secondaryDisplayStatus.value =
                "Physical cover is transitioning; " +
                    "retaining the continuity host."

            com.duoopen.debug.DuoDiagnostics.event(
                "live-mirror",
                "cover transition; host retained " +
                    "reason=$reason " +
                    "coverLogical=${cover?.displayId}",
            )

            return
        }

        if (activeInner == null) {
            _secondaryDisplayStatus.value =
                "Physical inner display is transitioning; " +
                    "retaining the continuity host."

            com.duoopen.debug.DuoDiagnostics.event(
                "live-mirror",
                "inner transition; host retained " +
                    "reason=$reason " +
                    "innerLogical=${inner?.displayId}",
            )

            return
        }

        if (
            activeInner.displayId ==
                activeCover.displayId
        ) {
            _secondaryDisplayStatus.value =
                "Fold7 topology is remapping; " +
                    "waiting for distinct panel routes."

            com.duoopen.debug.DuoDiagnostics.event(
                "live-mirror",
                "same-logical-id-after-physical-resolve " +
                    "reason=$reason " +
                    "logical=${activeCover.displayId}",
            )

            return
        }

        val current =
            mirrorHost

        if (
            current != null &&
            current.displayId ==
                activeCover.displayId &&
            !current.isUsable &&
            mirrorHostCreatedUptime != 0L &&
            android.os.SystemClock.uptimeMillis() -
                mirrorHostCreatedUptime <
                    MIRROR_HOST_ATTACH_GRACE_MS
        ) {
            DuoDiagnostics.event(
                "live-mirror",
                "host attach pending retained " +
                    "reason=$reason display=${current.displayId}",
            )

            return
        }

        if (
            current == null ||
            current.displayId != activeCover.displayId ||
            !current.isUsable
        ) {
            current?.detach()

            mirrorHostCreatedUptime =
                android.os.SystemClock.uptimeMillis()

            mirrorHost =
                DisplayMirrorHost(
                    service = this,
                    display = activeCover,
                    scope = scope,
                    onStatus = { message ->
                        _secondaryDisplayStatus.value =
                            message
                    },
                ).also { host ->
                    val seedAngle =
                        hinge.lastAngle

                    if (seedAngle.isFinite()) {
                        host.onHinge(
                            seedAngle
                        )

                        com.duoopen.debug.DuoDiagnostics.event(
                            "live-mirror",
                            "host seeded hinge=$seedAngle",
                        )
                    }

                    host.attach()
                }

            com.duoopen.debug.DuoDiagnostics.event(
                "live-mirror",
                "physical cover host rebound " +
                    "reason=$reason " +
                    "innerLogical=${activeInner.displayId} " +
                    "coverLogical=${activeCover.displayId} " +
                    "coverIsDefault=" +
                    (
                        activeCover.displayId ==
                            Display.DEFAULT_DISPLAY
                    ),
            )

            return
        }

        current.refresh(
            "physical-stable:$reason"
        )
    }

    private fun safeToReleaseSecondaryPanel(): Boolean {
        val primary =
            displayManager.getDisplay(
                Display.DEFAULT_DISPLAY
            ) ?: return false

        val primaryMode =
            primary.mode

        val innerIsPrimary =
            primaryMode.physicalWidth ==
                1968 &&
                primaryMode.physicalHeight ==
                    2184

        val coverSecondary =
            displayManager.displays.any { display ->
                if (
                    display.displayId ==
                    Display.DEFAULT_DISPLAY
                ) {
                    false
                } else {
                    val mode =
                        display.mode

                    mode.physicalWidth ==
                        1080 &&
                        mode.physicalHeight ==
                            2520
                }
            }

        return innerIsPrimary &&
            coverSecondary
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

        private const val SECONDARY_DISPLAY_SAFETY_RESET_MS =
            90_000L

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

        private const val MIRROR_REBIND_DEBOUNCE_MS =
            16L

        private const val MIRROR_HOST_ATTACH_GRACE_MS =
            250L

        private const val COVER_WAKE_TRAVEL_DEG =
            7.0f

        private const val COVER_CLOSED_READY_MAX_DEG =
            12.0f

        private const val COVER_CLOSE_PREWARM_DEG =
            150.0f

        private const val COVER_CLOSE_VISUAL_START_DEG =
            135.0f

        private const val COVER_CLOSE_VISUAL_END_DEG =
            140.0f

        private const val COVER_INTENT_TRAVEL_DEG =
            4.0f

        private const val COVER_INTENT_SAMPLE_COUNT =
            3

        private const val COVER_INTENT_RESET_DEG =
            1.25f

        private const val COVER_INTENT_WINDOW_MS =
            1_800L

        private const val COVER_SAMPLE_EPSILON_DEG =
            0.35f

        private const val COVER_POWER_ASSERT_INTERVAL_MS =
            100L

        private const val COVER_RELEASE_OPEN_MIN_DEG =
            179.0f

        private const val COVER_RELEASE_CANCEL_DEG =
            178.0f

        private const val COVER_RELEASE_DWELL_MS =
            250L

        private const val COVER_NATIVE_HANDOFF_MAX_DEG =
            12.0f

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
