package com.duoopen.overlay

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.graphics.Bitmap
import android.hardware.display.DisplayManager
import android.os.Handler
import android.os.HandlerThread
import android.os.Looper
import android.os.SystemClock
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
    private val controlThread = HandlerThread("duo-fold7-angle-control").apply { start() }
    private val controlHandler = Handler(controlThread.looper)
    private val hingeIngress = Fold7HingeIngressBatch()
    private val scope = MainScope()
    private lateinit var hinge: HingeAngleSource
    private lateinit var displayManager: DisplayManager
    private val engines = LinkedHashMap<Int, PanelEngine>()
    private val snapshots = SnapshotCache(maxAgeMs = SNAPSHOT_MAX_AGE_MS)
    private val serviceEpoch =
        SystemClock.elapsedRealtimeNanos().takeIf { it > 0L } ?: 1L
    private val gen2 =
        Fold7Gen2Kernel<Bitmap>(serviceEpoch)
    private var angleFeed: WallpaperAngleFeed? = null

    private var deviceStateObserver:
        Fold7DeviceStateObserver? =
        null

    private lateinit var continuity: Fold7ContinuityCoordinator
    private lateinit var gen3Visual: Fold7Gen3VisualCoordinator

    /**
     * Semantic CLOSED -> OPEN visual latch.
     *
     * Topology can enter INNER_HANDOFF long before Samsung precise angle
     * resumes, so topology alone must not cancel the opening visual.
     *
     * This latch is one-shot per accepted opening edge. The renderer does not
     * own its lifetime: timeout/loss/manual-stop clear it here so a later
     * topology callback cannot accidentally restart the same opening visual.
     */
    private var earlyOpeningVisualLatched =
        false

    private var earlyOpeningVisualStarted =
        false

    private val earlyOpeningVisualTimeoutRunnable =
        Runnable {
            if (!earlyOpeningVisualLatched) {
                return@Runnable
            }

            setEarlyOpeningVisualLatched(
                value = false,
                reason = "safety-timeout",
            )

            reconcileContinuityCoverRendering(
                "opening-timeout"
            )
        }

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
                handleContinuityTopologyFastLane(
                    "display-added:$displayId"
                )
                scheduleDisplaySync(
                    "display-added:$displayId"
                )
            }

            override fun onDisplayRemoved(
                displayId: Int,
            ) {
                handleContinuityTopologyFastLane(
                    "display-removed:$displayId"
                )
                scheduleDisplaySync(
                    "display-removed:$displayId"
                )
            }

            override fun onDisplayChanged(
                displayId: Int,
            ) {
                handleContinuityTopologyFastLane(
                    "display-changed:$displayId"
                )
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
            serviceEpoch = serviceEpoch,
            gen2 = gen2,
            onStatus = { message -> _secondaryDisplayStatus.value = message },
        )
        displayManager.registerDisplayListener(displayListener, handler)
        hinge = HingeAngleSource(
            context = this,
            onAngle = { },
            onAuthoritativeSample = ::enqueueHingeFromControl,
            callbackHandler = controlHandler,
        )
        hinge.start()
        ShizukuBridge.init(this)
        angleFeed = WallpaperAngleFeed(
            context = this,
            mainHandler = handler,
            controlHandler = controlHandler,
            hinge = hinge,
        )

        gen3Visual =
            Fold7Gen3VisualCoordinator(
                service = this,
                displayManager = displayManager,
                handler = handler,
                serviceEpoch = serviceEpoch,
                gen2 = gen2,
                currentHingeAngle = {
                    hinge.lastAngle
                },
            )

        deviceStateObserver =
            Fold7DeviceStateObserver(
                context = this,
                handler = handler,
            ) {
                    previousStateId,
                    currentStateId,
                ->
                val reason =
                    "device-state:$previousStateId->$currentStateId"

                DuoDiagnostics.event(
                    "early-wake",
                    "opening edge reason=$reason " +
                        "continuity=${continuity.state} " +
                        "precise=${hinge.lastAngle}",
                )

                angleFeed
                    ?.kickBurst(
                        reason
                    )

                val beforeOpeningState =
                    continuity.state

                continuity
                    .onEarlyOpeningEdge(
                        reason
                    )

                if (
                    beforeOpeningState ==
                        Fold7ContinuityController.State.NATIVE_COVER &&
                    continuity.state ==
                        Fold7ContinuityController.State.OPENING_FROM_CLOSED
                ) {
                    gen3Visual.beginOpening(
                        generation = continuity.generation,
                        reason = "device-state:$reason",
                    )
                }

                reconcileContinuityCoverRendering(
                    "early-opening:$reason"
                )
            }.also {
                it.start()
            }

        DuoDiagnostics.event(
            "service-lifecycle",
            "accessibility-connected",
        )

        scope.launch {
            ShizukuBridge.state.collect { state ->
                DuoDiagnostics.event(
                    "service-lifecycle",
                    "shizuku-state=${state.javaClass.simpleName}",
                )

                syncAngleFeed()

                if (
                    state is ShizukuBridge.State.Ready &&
                    ShizukuBridge.ready
                ) {
                    continuity.onPrivilegedReady()
                    primeCoverRoute(
                        "shizuku-ready"
                    )
                } else {
                    setEarlyOpeningVisualLatched(
                        value = false,
                        reason = "shizuku-unavailable",
                    )

                    continuity.onPrivilegedUnavailable()
                }

                reconcileContinuityCoverRendering(
                    "shizuku-state:${state.javaClass.simpleName}"
                )
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
        DuoDiagnostics.event(
            "service-lifecycle",
            "accessibility-destroy begin",
        )

        instance = null

        deviceStateObserver
            ?.stop()

        deviceStateObserver =
            null

        if (::gen3Visual.isInitialized) {
            gen3Visual.destroy()
        }

        if (::continuity.isInitialized) {
            setEarlyOpeningVisualLatched(
                value = false,
                reason = "service-destroy",
            )

            continuity.destroy()
        }

        handler.removeCallbacks(
            earlyOpeningVisualTimeoutRunnable
        )

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
        hingeIngress.reset()
        controlThread.quitSafely()
        super.onDestroy()
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit
    override fun onInterrupt() = Unit

    /**
     * Ordered bridge from the serialized Fold7 control thread to main.
     * Semantic samples are replayed in source-observation order; render work is
     * intentionally collapsed to the final angle in each drain.
     */
    private fun enqueueHingeFromControl(
        sample: HingeAngleSource.AuthoritativeSample,
    ) {
        val shouldPost =
            hingeIngress.offer(
                angle = sample.angle,
                observedUptimeMs = sample.observedUptimeMs,
            )

        DuoDiagnostics.event(
            "angle-authority",
            "accepted source=${sample.source} angle=${sample.angle} " +
                "observed=${sample.observedUptimeMs} delivered=${sample.deliveredUptimeMs} " +
                "coarse=${sample.coarse} reason=${sample.reason}",
        )

        if (!shouldPost) return

        handler.post {
            drainHingeIngress()
        }
    }

    private fun drainHingeIngress() {
        val drain =
            hingeIngress.drain()

        if (drain.samples.isEmpty()) return

        val now = SystemClock.uptimeMillis()
        val first = drain.samples.first()
        val last = drain.samples.last()

        DuoDiagnostics.event(
            "hinge-ingress",
            "batch size=${drain.samples.size} overflow=${drain.overflowed} " +
                "dropped=${drain.droppedSamples} seq=${first.sequence}->${last.sequence} " +
                "oldestAgeMs=${(now - first.observedUptimeMs).coerceAtLeast(0L)} " +
                "newestAgeMs=${(now - last.observedUptimeMs).coerceAtLeast(0L)}",
        )

        if (drain.overflowed) {
            DuoDiagnostics.event(
                "hinge-ingress",
                "OVERFLOW fail-closed dropped=${drain.droppedSamples}; " +
                    "revoking temporary continuity authority and resyncing",
            )

            continuity.release("hinge-ingress-overflow")
            if (ShizukuBridge.ready) {
                continuity.arm()
            }

            primeContinuityFrameIfNeeded("hinge-overflow-resync")
            reconcileContinuityCoverRendering("hinge-overflow-resync")

            val latest = hinge.lastAngle
            if (latest.isFinite()) {
                gen3Visual.onHinge(latest)
                deviceStateObserver?.corroborateFoldedRest(
                    nativeCover =
                        continuity.state ==
                            Fold7ContinuityController.State.NATIVE_COVER,
                    preciseAngle = latest,
                )
                for (engine in engines.values.toList()) {
                    engine.onHinge(latest)
                }
            }
            return
        }

        for (sample in drain.samples) {
            val beforeState =
                continuity.state

            continuity.onHinge(
                angle = sample.angle,
                observedUptimeMs = sample.observedUptimeMs,
            )

            if (
                beforeState ==
                    Fold7ContinuityController.State.NATIVE_COVER &&
                continuity.state ==
                    Fold7ContinuityController.State.OPENING_FROM_CLOSED
            ) {
                gen3Visual.beginOpening(
                    generation = continuity.generation,
                    reason = "authoritative-hinge-opening-edge",
                )
            }
        }

        val angle = last.angle

        primeContinuityFrameIfNeeded(
            "hinge:$angle"
        )

        reconcileContinuityCoverRendering(
            "hinge:$angle"
        )

        gen3Visual.onHinge(
            angle
        )

        deviceStateObserver
            ?.corroborateFoldedRest(
                nativeCover =
                    continuity.state ==
                        Fold7ContinuityController.State.NATIVE_COVER,
                preciseAngle =
                    angle,
            )

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
                    continuityFrames = gen2.frames,
                    continuityPrimeOwner = gen2.primeOwner,
                    activeCloseCycle = { gen2.activeCycle },
                    onContinuityFrameChanged = { frameReason ->
                        reconcileContinuityCoverRendering(
                            "continuity-frame:$frameReason"
                        )
                    },
                )
            }
        }
        if (gone.isNotEmpty()) updateRunning()

        angleFeed?.onDisplayChanged()

        continuity.onTopologyChanged(
            "sync-displays"
        )

        primeContinuityFrameIfNeeded(
            "sync-displays"
        )

        reconcileContinuityCoverRendering(
            "sync-displays"
        )

        if (!continuity.visualMirrorActive) {
            for (e in engines.values.toList()) {
                e.evaluate()
            }
        }

        deviceStateObserver
            ?.corroborateFoldedRest(
                nativeCover =
                    continuity.state ==
                        Fold7ContinuityController.State.NATIVE_COVER,
                preciseAngle =
                    hinge.lastAngle,
            )
    }

    private fun setEarlyOpeningVisualLatched(
        value: Boolean,
        reason: String,
    ) {
        if (
            earlyOpeningVisualLatched ==
            value
        ) {
            return
        }

        earlyOpeningVisualLatched =
            value

        handler.removeCallbacks(
            earlyOpeningVisualTimeoutRunnable
        )

        if (value) {
            earlyOpeningVisualStarted =
                false

            handler.postDelayed(
                earlyOpeningVisualTimeoutRunnable,
                EARLY_OPENING_VISUAL_MAX_MS,
            )
        } else {
            earlyOpeningVisualStarted =
                false
        }

        DuoDiagnostics.event(
            "cover-opening-visual",
            "LATCH value=$value reason=$reason " +
                "state=${continuity.state} precise=${hinge.lastAngle}",
        )
    }

    private fun handleContinuityTopologyFastLane(
        reason: String,
    ) {
        if (!::continuity.isInitialized) return

        continuity.onTopologyFastLane(
            reason
        )

        primeContinuityFrameIfNeeded(
            "fast:$reason"
        )

        reconcileContinuityCoverRendering(
            "fast:$reason"
        )
    }

    private fun primeContinuityFrameIfNeeded(
        reason: String,
    ) {
        val cycle =
            gen2.activeCycle
                ?: return

        if (!ShizukuBridge.ready) {
            return
        }

        val engine =
            engines.values
                .firstOrNull {
                    it.isFold7InnerGeometryNow()
                }
                ?: return

        val attempt =
            gen2.primeOwner.reserve(
                cycle = cycle,
                requestedSource =
                    Fold7ContinuityPrimeOwner.Source.SHIZUKU,
            ) ?: return

        val started =
            engine.primeContinuityFrame(
                cycle = cycle,
                attempt = attempt,
                reason = reason,
            )

        if (!started) {
            gen2.primeOwner.markFailed(
                attempt,
                "source-rejected",
            )
        }
    }

    private fun reconcileContinuityCoverRendering(
        reason: String,
    ) {
        if (!::continuity.isInitialized) {
            return
        }

        val privilegedReady =
            ShizukuBridge.ready &&
                continuity.renderOwnershipEnabled

        /*
         * Alpha2 keeps Gen3 as the semantic/exact owner, but restores the
         * validated Fold7 snapshot/shader renderer for OPENING. The Alpha1
         * field trace showed its LiveBlur host failing to attach on every
         * accepted opening attempt.
         */
        for (engine in engines.values.toList()) {
            engine.setContinuityCoverOwned(
                owned =
                    privilegedReady &&
                        engine.isFold7CoverGeometryNow(),
                reason = "gen3:$reason",
            )
        }

        if (::gen3Visual.isInitialized) {
            gen3Visual.reconcile(
                state = continuity.state,
                closingVisible =
                    continuity.visualMirrorActive,
                privilegedReady =
                    privilegedReady,
                reason =
                    reason,
            )
        }

        val openingDemand =
            ::gen3Visual.isInitialized &&
                gen3Visual.openingVisualDemandActive

        val openingHostDisplayId =
            if (::gen3Visual.isInitialized) {
                gen3Visual.openingHostDisplayId
            } else {
                null
            }

        for (engine in engines.values.toList()) {
            val runOpeningRenderer =
                privilegedReady &&
                    openingDemand &&
                    engine.isFold7CoverGeometryNow() &&
                    engine.display.displayId ==
                        openingHostDisplayId

            if (runOpeningRenderer) {
                engine.beginContinuityOpeningVisual(
                    "gen3-opening-snapshot:$reason"
                )
            } else {
                engine.endContinuityOpeningVisual(
                    "gen3-opening-not-owner:$reason"
                )
            }
        }
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
        hinge.statusText() + " · " + (angleFeed?.status ?: "Reader idle")

    fun authoritativeHingeAngle(): Float =
        hinge.lastAngle

    fun hingeReport(): String =
        hinge.report()

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

                service.reconcileContinuityCoverRendering(
                    "user-arm"
                )
            } else {
                service.setEarlyOpeningVisualLatched(
                    value = false,
                    reason = "user-stop",
                )

                service.continuity.release(
                    "user-stop"
                )

                service.reconcileContinuityCoverRendering(
                    "user-stop"
                )
            }

            return true
        }

        private const val DISPLAY_SYNC_DEBOUNCE_MS =
            24L

        /** One semantic CLOSED -> OPEN visual attempt per opening edge. */
        private const val EARLY_OPENING_VISUAL_MAX_MS =
            2_500L

        /** How old a panel's last picture may be and still bridge the next fold. */
        private const val SNAPSHOT_MAX_AGE_MS = 15 * 60_000L

        /**
         * Continuity may reuse only a snapshot taken near the current physical
         * fold. This avoids showing a minutes-old app state on the cover.
         */
        private const val FOLD7_FROZEN_FRAME_MAX_AGE_MS =
            10_000L

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
