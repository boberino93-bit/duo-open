package com.duoopen.overlay

import android.accessibilityservice.AccessibilityService
import android.graphics.Bitmap
import android.os.Handler
import android.os.SystemClock
import android.util.Log
import android.view.Choreographer
import android.view.Display
import android.view.Surface
import android.view.WindowManager
import com.duoopen.fold.DuoShader
import com.duoopen.fold.Fold7VirtualHingeGen5
import com.duoopen.fold.Fold7VisualStateLut
import com.duoopen.fold.HingeAngleSource
import com.duoopen.fold.HingeTravel
import com.duoopen.fold.HingeTravelEstimator
import com.duoopen.fold.TiltFollower
import com.duoopen.fold.isInnerPanel
import com.duoopen.settings.DuoSettings
import com.duoopen.shell.ShizukuBridge
import android.view.SurfaceControl
import android.view.View
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * The fold effect on one lit display: screenshot → touch-transparent overlay
 * drawn through the shader → tracks the hinge → removed at rest.
 *
 * One engine runs per live built-in panel (see [FoldOverlayService]). On a
 * phone that only ever lights one panel (OnePlus Open) that's a single engine
 * whose display flips between the cover and inner modes mid-fold; on a phone
 * that keeps both panels on, the cover and inner engines run side by side and
 * the effect hands over with no gap.
 *
 * Opening: leaving closed → capture on the cover → frost sweeps in; the inner
 * panel lights up → capture (retried while the panel is still black) → frost
 * clears to flat. Closing is the reverse. A frozen snapshot for the fraction
 * of a second of a fold is invisible in practice; if the hinge stops partway
 * (tent) the overlay fades out so live content isn't hidden.
 *
 * On a stops-only hinge sensor (Galaxy Z Fold 7 and earlier: 0/90/180) the
 * overlay can't follow the hinge, so each stop change plays a timed ease
 * instead — the same path the close-onto-cover already uses.
 *
 * Two ways to draw ([FoldSurface]): a warped screenshot (default), or — when
 * [com.duoopen.settings.DuoConfig.liveBlur] is on and the system allows
 * cross-window blur — the system blur over the live screen, which needs no
 * capture at all and so starts the instant a phase begins.
 */
internal class PanelEngine(
    private val service: AccessibilityService,
    val display: Display,
    private val hinge: HingeAngleSource,
    private val handler: Handler,
    private val scope: CoroutineScope,
    /** True when another engine is live on an inner panel right now. */
    private val hasLiveInnerElsewhere: () -> Boolean,
    private val onShowingChanged: () -> Unit,
    /** Last capture of each panel kind, shared by all engines (see [SnapshotCache]). */
    private val cache: SnapshotCache,
    /** Exact-cycle Fold7 continuity authority; separate from generic visual bridging. */
    private val continuityFrames: Fold7ContinuityFrameStore<Bitmap>,
    private val continuityPrimeOwner: Fold7ContinuityPrimeOwner,
    private val activeCloseCycle: () -> Fold7CycleEnvelope.CloseCycle?,
    private val onContinuityFrameChanged: (String) -> Unit,
) {
    private enum class Phase { IDLE, CAPTURING, SHOWING }

    private val displayId = display.displayId
    private val windowManager: WindowManager by lazy {
        service.createDisplayContext(display)
            .createWindowContext(WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY, null)
            .getSystemService(WindowManager::class.java)
    }

    private var phase = Phase.IDLE
    private var surface: FoldSurface? = null
    private var follower: TiltFollower? = null

    /** Which panel this display is driving; the effect restarts whenever it flips mid-fold. */
    var innerPanel = display.isInnerPanel()
        private set
    /** Set at a rest pose so leaving it plays once. */
    private var restArmed = true
    private var panelSwitched = false
    private var lastHingeMoveMs = 0L
    private var demoRunning = false
    /** Bumped per capture so a late or hung screenshot can't act on a newer phase. */
    private var captureGen = 0
    /** Attempt number of the capture in flight, so only its own timeout can give up. */
    private var captureAttempt = 0
    /** Overlay is resolving on a timer, ignoring the hinge (see [show]). */
    private var timedResolve = false
    /** Showing a cached picture of this panel while a fresh capture is in flight. */
    private var bridging = false
    /** Live re-capture loop (Shizuku mode) is scheduled. */
    private var liveLoop = false

    private var innerOpenLatched = false

    /** Gen2 owns Fold7 cover presentation while privileged continuity is armed. */
    private var continuityCoverOwned = false

    /** Explicit CLOSED -> OPEN visual started from the device-state opening edge. */
    private var continuityOpeningVisual = false

    /** Gen5 is visual-only: it never owns continuity state or panel authority. */
    private val gen5VirtualHinge = Fold7VirtualHingeGen5()
    private val gen5VisualLut = Fold7VisualStateLut()
    private var gen5FramePosted = false
    private var gen5FrameCount = 0L
    private var gen5LastMode: Fold7VirtualHingeGen5.Mode? = null
    private var gen5RefreshRoot: SurfaceControl? = null
    private var gen5OwnedOpeningBitmap: Bitmap? = null

    private val gen5FrameCallback =
        object : Choreographer.FrameCallback {
            override fun doFrame(frameTimeNanos: Long) {
                if (
                    !continuityOpeningVisual ||
                    phase != Phase.SHOWING ||
                    !isFold7CoverGeometryNow()
                ) {
                    gen5FramePosted = false
                    return
                }

                val nowNs = SystemClock.uptimeMillis() * 1_000_000L
                val effectiveHz =
                    runCatching { display.mode.refreshRate }
                        .getOrDefault(60f)
                        .takeIf { it.isFinite() && it >= 30f }
                        ?: 60f
                val frameNs = (1_000_000_000.0 / effectiveHz).toLong()
                val target = gen5VirtualHinge.targetForFrame(
                    callbackTimeNs = nowNs,
                    expectedPresentationTimeNs = nowNs + frameNs,
                )
                val visual = gen5VisualLut.stateFor(target.angleDegrees)
                val tilt =
                    (visual.rightPaneTiltDegrees *
                        DuoSettings.config.value.intensity.coerceAtMost(1f))
                        .coerceIn(0f, DuoShader.MAX_TILT)

                surface?.tilt = tilt
                gen5FrameCount++

                if (
                    gen5LastMode != target.mode ||
                    target.slewLimited ||
                    gen5FrameCount % GEN5_TELEMETRY_EVERY_N_FRAMES == 0L
                ) {
                    com.duoopen.debug.DuoDiagnostics.event(
                        "gen5-virtual-hinge",
                        "frame=$gen5FrameCount physical=${hinge.lastAngle} " +
                            "virtual=${target.angleDegrees} desired=${target.desiredAngleDegrees} " +
                            "tilt=$tilt mode=${target.mode} confidence=${target.confidence} " +
                            "ageMs=${target.measurementAgeMs} correction=${target.correctionDegrees} " +
                            "slewLimited=${target.slewLimited} leadNs=${target.predictedLeadNs} " +
                            "requestedHz=$GEN5_REQUESTED_HZ effectiveHz=$effectiveHz",
                    )
                }
                gen5LastMode = target.mode

                Choreographer.getInstance().postFrameCallback(this)
            }
        }

    /** Stable opening/closing state, resistant to tiny hinge jitter. */
    private val travelEstimator =
        HingeTravelEstimator()

    private var travel =
        HingeTravel.UNKNOWN

    /** Last raw hinge sample, used only to detect meaningful resumed motion. */
    private var lastRawHingeAngle =
        Float.NaN

    val showing: Boolean get() = phase == Phase.SHOWING

    private val settleCheck = object : Runnable {
        override fun run() {
            val o = surface ?: return
            if (o.tilt < DuoShader.FLAT_EPSILON) return
            if (!demoRunning && SystemClock.uptimeMillis() - lastHingeMoveMs >= SETTLE_TIMEOUT_MS) {
                dismiss(fadeMs = FADE_OUT_STALLED_MS)
            } else {
                handler.postDelayed(this, 100)
            }
        }
    }

    /** A timed frost-up that no panel swap has replaced: the fold stalled, let the live screen through. */
    private val peakHold = Runnable {
        if (timedResolve && !demoRunning) dismiss(fadeMs = FADE_OUT_STALLED_MS)
    }

    init {
        // A panel that lights up mid-fold is the second half of a fold in
        // progress; one that is already at rest just waits to leave it.
        val tilt = currentTilt()
        panelSwitched = tilt >= DuoShader.FLAT_EPSILON
        restArmed = !panelSwitched
        Log.i(TAG, "engine display=$displayId inner=$innerPanel midFold=$panelSwitched")
    }

    /** Whether this cover panel is lit alongside an inner panel (no swap will hand over). */
    private fun concurrentCover(): Boolean = !innerPanel && hasLiveInnerElsewhere()

    private fun tiltFor(angle: Float): Float {
        if (angle.isNaN()) return 0f
        val config = DuoSettings.config.value
        return when {
            innerPanel -> DuoShader.tiltForHinge(angle, config)
            concurrentCover() -> DuoShader.concurrentCoverTiltForHinge(angle, config)
            else -> DuoShader.coverTiltForHinge(angle, config)
        }
    }

    private fun currentTilt(): Float = tiltFor(hinge.lastAngle)

    fun onHinge(
        angle: Float,
        observedUptimeMs: Long = SystemClock.uptimeMillis(),
    ) {
        /*
         * Fold7 cover rendering has one owner at a time.
         *
         * While privileged Gen2 owns the cover, autonomous PanelEngine hinge
         * rendering is disabled. The only exception is the explicit early
         * opening visual, which is started from DeviceStateManager rather than
         * waiting for Samsung's precise angle stream to resume.
         */
        if (
            isFold7CoverGeometryNow() &&
            continuityCoverOwned
        ) {
            lastRawHingeAngle = angle
            val deliveredUptimeMs = SystemClock.uptimeMillis()
            lastHingeMoveMs = deliveredUptimeMs

            if (continuityOpeningVisual && angle.isFinite()) {
                val result = gen5VirtualHinge.addSample(
                    Fold7VirtualHingeGen5.Sample(
                        sourceTimeNs = observedUptimeMs.coerceAtMost(deliveredUptimeMs) * 1_000_000L,
                        deliveryTimeNs = deliveredUptimeMs * 1_000_000L,
                        angleDegrees = angle,
                    )
                )
                if (result.reversal || result.oscillationGuardEntered || result.reacquiring) {
                    com.duoopen.debug.DuoDiagnostics.event(
                        "gen5-virtual-hinge",
                        "sample angle=$angle observed=$observedUptimeMs delivered=$deliveredUptimeMs " +
                            "reversal=${result.reversal} oscillation=${result.oscillationGuardEntered} " +
                            "reacquiring=${result.reacquiring}",
                    )
                }
            }

            if (
                !continuityOpeningVisual &&
                phase != Phase.IDLE
            ) {
                captureGen++
                removeOverlay()
            }
            return
        }

        val previousRaw =
            lastRawHingeAngle

        lastRawHingeAngle =
            angle

        if (innerPanel) {
            if (angle >= INNER_OPEN_LATCH_DEG) {
                if (!innerOpenLatched) {
                    com.duoopen.debug.DuoDiagnostics.event(
                        "inner-open",
                        "latched angle=$angle; removing flat overlay without fade",
                    )
                }
                innerOpenLatched = true
                restArmed = true
                panelSwitched = false
                if (phase != Phase.IDLE) removeOverlay()
                return
            }

            if (innerOpenLatched) {
                if (angle > INNER_OPEN_REARM_DEG) return
                innerOpenLatched = false
                restArmed = true
                panelSwitched = false
            }
        }

        val previousTravel =
            travel

        travel =
            travelEstimator.update(
                angle
            )

        lastHingeMoveMs =
            SystemClock.uptimeMillis()

        evaluate()

        val tilt =
            tiltFor(
                angle
            )

        /*
         * If a partial fold paused long enough for the overlay to settle away,
         * meaningful resumed motion should re-enter the effect from the current
         * physical hinge position. This also makes an OPENING→CLOSING reversal
         * feel like the same physical pane running backward rather than a new
         * canned animation.
         */
        val resumedMidFold =
            phase == Phase.IDLE &&
                !demoRunning &&
                !restArmed &&
                !panelSwitched &&
                tilt >= REST_LEAVE_TILT &&
                !previousRaw.isNaN() &&
                kotlin.math.abs(
                    angle -
                        previousRaw
                ) >= RESUME_MOTION_DEG &&
                travel != HingeTravel.UNKNOWN

        if (resumedMidFold) {
            Log.i(
                TAG,
                "display $displayId: resumed mid-fold " +
                    "travel=$travel previousTravel=$previousTravel " +
                    "hinge=$angle tilt=$tilt"
            )

            startEffect(
                afterSwap = false,
                startTilt = tilt,
            )
        }

        if (
            tilt < DuoShader.FLAT_EPSILON &&
            phase == Phase.SHOWING &&
            !demoRunning
        ) {
            val f =
                follower

            if (
                timedResolve &&
                hinge.isCoarse &&
                f != null &&
                f.current > DuoShader.FLAT_EPSILON
            ) {
                handler.removeCallbacks(
                    peakHold
                )

                f.tauS =
                    COARSE_CLEAR_TAU_S

                f.setTarget(
                    0f
                )
            } else {
                dismiss(
                    fadeMs =
                        FADE_OUT_FLAT_MS
                )
            }
        } else if (!timedResolve) {
            follower?.setTarget(
                tilt
            )
        }
    }

    /**
     * Drives the effect from two signals: which panel this display shows and
     * the hinge angle. The picture is flat at the panel's rest pose and fully
     * frosted at the swap, so an open or a close is one continuous frost-up on
     * the first panel and frost-down on the second. A capture starts on
     * leaving rest and again on each swap.
     */
    fun evaluate() {
        if (demoRunning) return
        val inner = display.isInnerPanel()
        if (inner != innerPanel) {
            innerPanel = inner
            panelSwitched = true
            if (phase != Phase.IDLE) removeOverlay() // old panel's snapshot is meaningless now
        }

        if (
            isFold7CoverGeometryNow() &&
            continuityCoverOwned
        ) {
            if (
                !continuityOpeningVisual &&
                phase != Phase.IDLE
            ) {
                captureGen++
                removeOverlay()
            }
            return
        }

        val angle = hinge.lastAngle
        if (angle.isNaN()) return
        val tilt = tiltFor(angle)
        if (tilt < DuoShader.FLAT_EPSILON) {
            restArmed = true
            panelSwitched = false
            return
        }
        if (phase != Phase.IDLE) return

        val leaveThreshold =
            if (!innerPanel) {
                COVER_OPEN_IMMEDIATE_TILT
            } else {
                REST_LEAVE_TILT
            }

        when {
            panelSwitched -> {
                panelSwitched = false
                restArmed = false
                Log.i(TAG, "display $displayId: panel swapped (inner=$inner) at hinge=$angle")
                // The fresh panel may still be lighting up: retry if black.
                startEffect(afterSwap = true)
            }
            restArmed && tilt >= leaveThreshold -> {
                restArmed = false
                Log.i(TAG, "display $displayId: leaving rest (inner=$inner) at hinge=$angle")
                startEffect(afterSwap = false)
            }
        }
    }

    fun isFold7CoverGeometryNow(): Boolean {
        val mode =
            runCatching {
                display.mode
            }.getOrNull()
                ?: return false

        return (
            mode.physicalWidth == 1080 &&
                mode.physicalHeight == 2520
            )
    }

    fun isFold7InnerGeometryNow(): Boolean {
        val mode =
            runCatching {
                display.mode
            }.getOrNull()
                ?: return false

        return (
            mode.physicalWidth == 1968 &&
                mode.physicalHeight == 2184
            )
    }

    fun setContinuityCoverOwned(
        owned: Boolean,
        reason: String,
    ) {
        if (
            owned &&
            !isFold7CoverGeometryNow()
        ) {
            return
        }

        if (continuityCoverOwned == owned) {
            if (
                owned &&
                !continuityOpeningVisual &&
                phase != Phase.IDLE
            ) {
                captureGen++
                removeOverlay()
            }
            return
        }

        continuityCoverOwned = owned

        com.duoopen.debug.DuoDiagnostics.event(
            "cover-render-owner",
            "display=$displayId owned=$owned reason=$reason " +
                "phase=$phase openingVisual=$continuityOpeningVisual",
        )

        if (!owned) {
            if (continuityOpeningVisual) {
                endContinuityOpeningVisual(
                    "owner-released:$reason"
                )
            }
            return
        }

        if (
            !continuityOpeningVisual &&
            phase != Phase.IDLE
        ) {
            captureGen++
            removeOverlay()
        }
    }

    fun beginContinuityOpeningVisual(
        reason: String,
    ) {
        if (
            !isFold7CoverGeometryNow() ||
            !continuityCoverOwned ||
            continuityOpeningVisual
        ) {
            return
        }

        continuityOpeningVisual = true
        captureGen++

        if (
            phase != Phase.IDLE ||
            surface != null
        ) {
            removeOverlay()
        }

        restArmed = false
        panelSwitched = false

        val nowNs = SystemClock.uptimeMillis() * 1_000_000L
        val seed =
            hinge.lastAngle
                .takeIf { it.isFinite() && it <= Fold7VirtualHingeGen5.BLIND_SEED_MAX_DEG }
                ?: Fold7VirtualHingeGen5.CLOSED_SEED_DEG
        gen5VirtualHinge.startOpening(nowNs, seed)
        gen5FrameCount = 0L
        gen5LastMode = null

        com.duoopen.debug.DuoDiagnostics.event(
            "cover-opening-visual",
            "START display=$displayId reason=$reason precise=${hinge.lastAngle} seed=$seed gen5=true",
        )

        recycleGen5OpeningBitmap()
        val cachedInner =
            cache.get(
                innerPanel = true,
                width = Fold7RightPaneComposer.INNER_WIDTH,
                height = Fold7RightPaneComposer.INNER_HEIGHT,
            )
        val canonicalRight =
            cachedInner?.let(Fold7RightPaneComposer::fromInner)

        if (canonicalRight != null) {
            gen5OwnedOpeningBitmap = canonicalRight
            phase = Phase.CAPTURING
            present(
                bitmap = canonicalRight,
                afterSwap = false,
                startTilt = COVER_OPEN_IMMEDIATE_TILT,
                t0 = SystemClock.uptimeMillis(),
            )
            com.duoopen.debug.DuoDiagnostics.event(
                "gen5-split-pane",
                "opening bootstrap uses cached canonical right pane " +
                    "crop=${Fold7RightPaneComposer.RIGHT_PANE_LEFT}..${Fold7RightPaneComposer.RIGHT_PANE_RIGHT}",
            )
        } else {
            startEffect(
                afterSwap = false,
                startTilt = COVER_OPEN_IMMEDIATE_TILT,
            )
            com.duoopen.debug.DuoDiagnostics.event(
                "gen5-split-pane",
                "canonical right pane unavailable; falling back to current cover capture",
            )
        }
    }

    fun endContinuityOpeningVisual(
        reason: String,
    ) {
        if (!continuityOpeningVisual) {
            return
        }

        continuityOpeningVisual = false
        captureGen++
        stopGen5OpeningClock()

        if (
            phase != Phase.IDLE ||
            surface != null
        ) {
            removeOverlay()
        }

        restArmed = true
        panelSwitched = false
        recycleGen5OpeningBitmap()

        com.duoopen.debug.DuoDiagnostics.event(
            "cover-opening-visual",
            "END display=$displayId reason=$reason precise=${hinge.lastAngle} gen5=true",
        )
    }

    fun primeContinuityFrame(
        cycle: Fold7CycleEnvelope.CloseCycle,
        attempt: Fold7ContinuityPrimeOwner.AttemptToken,
        reason: String,
    ): Boolean {
        if (
            !isFold7InnerGeometryNow() ||
            !deterministicFrozenFrameMode() ||
            !ShizukuBridge.ready ||
            activeCloseCycle() != cycle ||
            !continuityPrimeOwner.isCurrent(attempt)
        ) {
            return false
        }

        val mode =
            runCatching {
                display.mode
            }.getOrNull()
                ?: return false

        val startedUptimeMs =
            SystemClock.uptimeMillis()

        val ticket =
            continuityFrames.beginCapture(
                cycle = cycle,
                width = mode.physicalWidth,
                height = mode.physicalHeight,
                requestStartedUptimeMs = startedUptimeMs,
                source = Fold7ContinuityFrameStore.Source.SHIZUKU,
            )
                ?: run {
                    continuityPrimeOwner.markFailed(
                        attempt,
                        "frame-ticket-unavailable",
                    )
                    return false
                }

        com.duoopen.debug.DuoDiagnostics.event(
            "snapshot-transition",
            "Gen3 continuity prime START serviceEpoch=${cycle.serviceEpoch} " +
                "closeCycle=${cycle.closeCycleId} attempt=${attempt.attemptSequence} " +
                "capture=${ticket.captureSequence} hinge=${hinge.lastAngle} reason=$reason",
        )

        scope.launch {
            val bitmap =
                withContext(Dispatchers.IO) {
                    ShizukuBridge.capture(
                        displayId,
                        excludedLayers(),
                        INITIAL_SHELL_SCALE,
                    )
                }

            if (
                activeCloseCycle() != cycle ||
                !continuityPrimeOwner.isCurrent(attempt)
            ) {
                bitmap?.let {
                    runCatching {
                        it.recycle()
                    }
                }
                return@launch
            }

            if (bitmap == null) {
                continuityPrimeOwner.markFailed(
                    attempt,
                    "capture-null",
                )

                com.duoopen.debug.DuoDiagnostics.event(
                    "snapshot-transition",
                    "Gen3 continuity prime FAILED serviceEpoch=${cycle.serviceEpoch} " +
                        "closeCycle=${cycle.closeCycleId} attempt=${attempt.attemptSequence} " +
                        "latencyMs=${SystemClock.uptimeMillis() - startedUptimeMs}",
                )

                onContinuityFrameChanged(
                    "prime-failed"
                )
                return@launch
            }

            val lease =
                continuityFrames.publish(
                    ticket = ticket,
                    capturedUptimeMs = startedUptimeMs,
                    completedUptimeMs = SystemClock.uptimeMillis(),
                    timestampQuality =
                        Fold7ContinuityFrameStore.TimestampQuality.REQUEST_BOUNDED,
                    payload = bitmap,
                )

            if (lease == null) {
                runCatching {
                    bitmap.recycle()
                }

                continuityPrimeOwner.markFailed(
                    attempt,
                    "frame-publish-rejected",
                )

                com.duoopen.debug.DuoDiagnostics.event(
                    "snapshot-transition",
                    "Gen3 continuity prime REJECTED closeCycle=${cycle.closeCycleId} " +
                        "attempt=${attempt.attemptSequence} capture=${ticket.captureSequence}",
                )

                onContinuityFrameChanged(
                    "prime-rejected"
                )
                return@launch
            }

            if (
                !continuityPrimeOwner.markReady(
                    attempt
                )
            ) {
                return@launch
            }

            cache.put(
                true,
                bitmap,
            )

            com.duoopen.debug.DuoDiagnostics.event(
                "snapshot-transition",
                "Gen3 continuity prime READY serviceEpoch=${lease.serviceEpoch} " +
                    "closeCycle=${lease.closeCycleId} attempt=${attempt.attemptSequence} " +
                    "capture=${lease.captureSequence} content=${lease.contentLeaseId} " +
                    "latencyMs=${SystemClock.uptimeMillis() - startedUptimeMs}",
            )

            onContinuityFrameChanged(
                "prime-ready"
            )
        }

        return true
    }

    /**
     * Fold7 transitions must be deterministic: once a transition frame is
     * captured, changing app/system pixels underneath it must not change what
     * the user sees while the hinge is stationary.
     *
     * Other device geometries keep the existing live-blur option.
     */
    private fun deterministicFrozenFrameMode(): Boolean {
        val mode =
            runCatching {
                display.mode
            }.getOrNull()
                ?: return false

        return (
            mode.physicalWidth == 1968 &&
                mode.physicalHeight == 2184
            ) ||
            (
                mode.physicalWidth == 1080 &&
                    mode.physicalHeight == 2520
                )
    }

    private fun beginContinuityCapture(
        source: Fold7ContinuityFrameStore.Source,
        requestStartedUptimeMs: Long,
    ): Fold7ContinuityFrameStore.CaptureTicket? {
        /*
         * Gen3 exact-cycle continuity capture admission is service-stable and
         * Shizuku-authorized through Fold7ContinuityPrimeOwner. Generic
         * PanelEngine captures remain valid for ordinary rendering/cache use,
         * but they are never allowed to publish into the privileged continuity
         * frame store.
         */
        return null
    }

    /** Live blur is intentionally disabled on Fold7. */
    private fun liveMode(): Boolean =
        !deterministicFrozenFrameMode() &&
            DuoSettings.config.value.liveBlur &&
            runCatching { windowManager.isCrossWindowBlurEnabled }.getOrDefault(false)

    private fun startEffect(afterSwap: Boolean, startTilt: Float? = null) {
        if (liveMode()) {
            phase = Phase.CAPTURING // same gate as a capture in flight, resolved synchronously
            present(bitmap = null, afterSwap = afterSwap, startTilt = startTilt, t0 = SystemClock.uptimeMillis())
            return
        }
        // A panel that has just switched on takes ~0.3 s to screenshot. Start
        // at once with the picture it showed last time and swap in the fresh
        // capture when it lands — the frost hides the difference.
        if (afterSwap && startTilt == null && DuoSettings.config.value.instantStart) {
            val bounds = windowManager.maximumWindowMetrics.bounds
            val stale = cache.get(innerPanel, bounds.width(), bounds.height())
            if (stale != null) {
                phase = Phase.CAPTURING
                Log.i(TAG, "display $displayId: bridging with a ${cache.ageMs(innerPanel)}ms-old snapshot")
                present(stale, afterSwap = true, startTilt = null, t0 = SystemClock.uptimeMillis())
                bridging = phase == Phase.SHOWING
            }
        }
        startCapture(afterSwap, startTilt)
    }

    private fun startCapture(afterSwap: Boolean, startTilt: Float? = null) {
        if (!bridging) phase = Phase.CAPTURING
        capture(gen = ++captureGen, attempt = 1, afterSwap = afterSwap, startTilt = startTilt)
    }

    private fun capture(gen: Int, attempt: Int, afterSwap: Boolean, startTilt: Float?) {
        val t0 = SystemClock.uptimeMillis()
        captureAttempt = attempt
        fun stale() = gen != captureGen || (phase != Phase.CAPTURING && !bridging)
        // The framework refuses captures closer than ~333 ms apart, measured
        // from the previous request — so a slow capture costs no extra wait.
        fun retry() {
            val wait = (t0 + SCREENSHOT_MIN_INTERVAL_MS - SystemClock.uptimeMillis()).coerceAtLeast(0L)
            handler.postDelayed({ if (!stale()) capture(gen, attempt + 1, afterSwap, startTilt) }, wait)
        }
        // A screenshot requested as a panel switches off may never call back.
        // Only the latest attempt's timeout counts: an earlier one must not
        // give up on behalf of a retry that is still in flight.
        handler.postDelayed({
            if (!stale() && captureAttempt == attempt) {
                Log.w(TAG, "display $displayId: capture $attempt timed out; giving up")
                if (bridging) {
                    bridging = false // keep playing on the stale picture
                } else {
                    phase = Phase.IDLE
                    demoRunning = false
                }
            }
        }, CAPTURE_TIMEOUT_MS)
        // Shizuku mode: the shell-side capture has no rate limit and takes
        // ~50 ms even on a waking panel. Falls back to the accessibility
        // screenshot if it fails.
        if (shellCapture()) {
            val continuityTicket =
                beginContinuityCapture(
                    source = Fold7ContinuityFrameStore.Source.SHIZUKU,
                    requestStartedUptimeMs = t0,
                )
            scope.launch {
                val bitmap = withContext(Dispatchers.IO) {
                    ShizukuBridge.capture(displayId, excludedLayers(), INITIAL_SHELL_SCALE)
                }
                if (stale()) return@launch
                if (bitmap == null) {
                    Log.i(TAG, "display $displayId: shell capture unavailable; using accessibility screenshot")
                    accessibilityCapture(gen, attempt, afterSwap, startTilt, t0, ::retry, ::stale)
                    return@launch
                }
                if (afterSwap && attempt < MAX_CAPTURE_ATTEMPTS) {
                    val black = withContext(Dispatchers.Default) { isMostlyBlack(bitmap) }
                    if (stale()) return@launch
                    if (black && !demoRunning) {
                        Log.i(TAG, "display $displayId: shell capture $attempt is black after ${SystemClock.uptimeMillis() - t0}ms; retrying")
                        handler.postDelayed({ if (!stale()) capture(gen, attempt + 1, afterSwap, startTilt) }, SHELL_RETRY_MS)
                        return@launch
                    }
                }
                onCaptured(
                    bitmap = bitmap,
                    afterSwap = afterSwap,
                    startTilt = startTilt,
                    t0 = t0,
                    continuityTicket = continuityTicket,
                    capturedUptimeMs = t0,
                    timestampQuality = Fold7ContinuityFrameStore.TimestampQuality.REQUEST_BOUNDED,
                )
            }
            return
        }
        accessibilityCapture(gen, attempt, afterSwap, startTilt, t0, ::retry, ::stale)
    }

    private fun shellCapture(): Boolean = ShizukuBridge.ready

    /** Our own overlay's layer, so a capture taken while it's up sees the screen beneath it. */
    private fun excludedLayers(): List<SurfaceControl> {
        val view = (surface as? SnapshotSurface)?.view ?: return emptyList()
        return listOfNotNull(rootSurfaceControl(view))
    }

    private fun accessibilityCapture(
        gen: Int,
        attempt: Int,
        afterSwap: Boolean,
        startTilt: Float?,
        t0: Long,
        retry: () -> Unit,
        stale: () -> Boolean,
    ) {
        val continuityRequestStarted = SystemClock.uptimeMillis()
        val continuityTicket =
            beginContinuityCapture(
                source = Fold7ContinuityFrameStore.Source.ACCESSIBILITY,
                requestStartedUptimeMs = continuityRequestStarted,
            )
        service.takeScreenshot(displayId, service.mainExecutor, object : AccessibilityService.TakeScreenshotCallback {
            override fun onSuccess(result: AccessibilityService.ScreenshotResult) {
                val buffer = result.hardwareBuffer
                val bitmap = Bitmap.wrapHardwareBuffer(buffer, result.colorSpace)
                buffer.close()
                if (stale()) {
                    Log.i(TAG, "display $displayId: stale capture after ${SystemClock.uptimeMillis() - t0}ms; dropped")
                    bitmap?.recycle()
                    return
                }
                if (bitmap == null) {
                    Log.w(TAG, "display $displayId: screenshot buffer could not be wrapped")
                    if (bridging) bridging = false else phase = Phase.IDLE
                    return
                }
                if (!afterSwap || attempt >= MAX_CAPTURE_ATTEMPTS) {
                    onCaptured(
                        bitmap = bitmap,
                        afterSwap = afterSwap,
                        startTilt = startTilt,
                        t0 = t0,
                        continuityTicket = continuityTicket ?: beginContinuityCapture(
                            source = Fold7ContinuityFrameStore.Source.ACCESSIBILITY,
                            requestStartedUptimeMs = continuityRequestStarted,
                        ),
                        capturedUptimeMs = result.timestamp,
                        timestampQuality = Fold7ContinuityFrameStore.TimestampQuality.EXACT_CAPTURE,
                    )
                    return
                }
                scope.launch {
                    val black = withContext(Dispatchers.Default) { isMostlyBlack(bitmap) }
                    if (stale()) {
                        bitmap.recycle()
                        return@launch
                    }
                    if (black && !demoRunning) {
                        bitmap.recycle()
                        Log.i(TAG, "display $displayId: capture $attempt is black after ${SystemClock.uptimeMillis() - t0}ms; retrying")
                        retry()
                    } else {
                        onCaptured(
                        bitmap = bitmap,
                        afterSwap = afterSwap,
                        startTilt = startTilt,
                        t0 = t0,
                        continuityTicket = continuityTicket ?: beginContinuityCapture(
                            source = Fold7ContinuityFrameStore.Source.ACCESSIBILITY,
                            requestStartedUptimeMs = continuityRequestStarted,
                        ),
                        capturedUptimeMs = result.timestamp,
                        timestampQuality = Fold7ContinuityFrameStore.TimestampQuality.EXACT_CAPTURE,
                    )
                    }
                }
            }

            override fun onFailure(errorCode: Int) {
                if (stale()) return
                // Secure content (banking, DRM video) and rate limits land here.
                Log.w(TAG, "display $displayId: screenshot failed: $errorCode")
                if (errorCode == AccessibilityService.ERROR_TAKE_SCREENSHOT_INTERVAL_TIME_SHORT &&
                    attempt < MAX_CAPTURE_ATTEMPTS
                ) {
                    retry()
                } else if (bridging) {
                    bridging = false // secure content etc.: keep playing on the stale picture
                } else {
                    phase = Phase.IDLE
                    demoRunning = false
                }
            }
        })
    }

    private fun onCaptured(
        bitmap: Bitmap,
        afterSwap: Boolean,
        startTilt: Float?,
        t0: Long,
        continuityTicket: Fold7ContinuityFrameStore.CaptureTicket?,
        capturedUptimeMs: Long,
        timestampQuality: Fold7ContinuityFrameStore.TimestampQuality,
    ) {
        cache.put(innerPanel, bitmap)

        if (continuityTicket != null) {
            val lease =
                continuityFrames.publish(
                    ticket = continuityTicket,
                    capturedUptimeMs = capturedUptimeMs,
                    completedUptimeMs = SystemClock.uptimeMillis(),
                    timestampQuality = timestampQuality,
                    payload = bitmap,
                )

            com.duoopen.debug.DuoDiagnostics.event(
                "snapshot-transition",
                if (lease != null) {
                    "Gen2 continuity frame published " +
                        "serviceEpoch=${lease.serviceEpoch} closeCycle=${lease.closeCycleId} " +
                        "capture=${lease.captureSequence} content=${lease.contentLeaseId} " +
                        "source=${lease.source} quality=${lease.timestampQuality}"
                } else {
                    "Gen2 continuity frame rejected as stale " +
                        "serviceEpoch=${continuityTicket.serviceEpoch} " +
                        "closeCycle=${continuityTicket.closeCycleId} " +
                        "capture=${continuityTicket.captureSequence}"
                },
            )
        }
        if (bridging) {
            bridging = false
            val s = surface as? SnapshotSurface
            if (s != null && phase == Phase.SHOWING) {
                Log.i(TAG, "display $displayId: fresh capture (${SystemClock.uptimeMillis() - t0}ms) replaces the bridge at tilt=${s.tilt}")
                s.replaceSnapshot(bitmap)
            }
            return
        }
        present(bitmap, afterSwap, startTilt, t0)
    }

    /**
     * Puts the effect on screen: [bitmap] through the shader, or with no
     * bitmap the live blur over whatever is there.
     */
    private fun present(bitmap: Bitmap?, afterSwap: Boolean, startTilt: Float?, t0: Long) {
        if (phase != Phase.CAPTURING) {
            return
        }
        val angle = hinge.lastAngle
        val live = startTilt == null
        val coarse = live && hinge.isCoarse
        val peak = DuoShader.MAX_TILT * DuoSettings.config.value.intensity.coerceAtMost(1f)
        // A stops-only sensor can't be followed. Between stops the fold is in
        // motion, so: frost in on leaving rest and hold; on the fresh panel
        // start frosted and hold; clear only when the rest stop arrives (see
        // onHinge) or the hold cap expires.
        val tilt = startTilt ?: if (coarse) (if (afterSwap) peak else DuoShader.FLAT_EPSILON * 1.2f) else currentTilt()
        // A capture lands late; the live blur is instant, so it's never "too late".
        val nearlyDone = bitmap != null && afterSwap && live &&
            if (innerPanel) angle > SKIP_INNER_ABOVE_HINGE else angle < SKIP_COVER_BELOW_HINGE
        if (tilt < DuoShader.FLAT_EPSILON || nearlyDone) {
            // Too late to be worth a pop-in: the fold is (almost) over.
            Log.i(TAG, "display $displayId: hinge=$angle by capture time (${SystemClock.uptimeMillis() - t0}ms); skipping")
            phase = Phase.IDLE
            return
        }
        // Closing onto a cover that only lights after the swap: the hinge HAL
        // goes quiet around 30°, so the overlay would never hear "closed".
        // Resolve on a timer instead — by the time this capture lands the
        // phone is shut anyway, so it reads as the cover settling into focus.
        // A cover lit alongside the inner panel keeps hearing the hinge.
        val easeTo = when {
            coarse -> peak
            afterSwap && !innerPanel && !concurrentCover() && live -> 0f
            else -> null
        }
        val how = if (bitmap != null) "${bitmap.width}x${bitmap.height} snapshot (capture ${SystemClock.uptimeMillis() - t0}ms)" else "live blur"
        Log.i(TAG, "display $displayId: showing $how at tilt=$tilt${easeTo?.let { " easing to $it" } ?: ""}${if (bitmap != null && shellCapture()) " [shizuku]" else ""}")
        show(bitmap, tilt, fadeIn = afterSwap, easeTo = easeTo)
    }

    /** Samples a coarse grid; true when nothing on screen is brighter than near-black. */
    private fun isMostlyBlack(hw: Bitmap): Boolean {
        val sw = runCatching { hw.copy(Bitmap.Config.ARGB_8888, false) }.getOrNull() ?: return false
        try {
            val n = 24
            var maxSum = 0
            for (iy in 0 until n) {
                val y = ((iy + 0.5f) * sw.height / n).toInt()
                for (ix in 0 until n) {
                    val x = ((ix + 0.5f) * sw.width / n).toInt()
                    val c = sw.getPixel(x, y)
                    val sum = ((c shr 16) and 0xFF) + ((c shr 8) and 0xFF) + (c and 0xFF)
                    if (sum > maxSum) maxSum = sum
                }
            }
            return maxSum < BLACK_THRESHOLD
        } finally {
            sw.recycle()
        }
    }

    /**
     * [easeTo] non-null plays a timed ease to that tilt, ignoring the hinge
     * until it's back at rest; easing up to a frosted peak holds there
     * briefly, then fades unless a panel swap has replaced it.
     */
    private fun show(bitmap: Bitmap?, startTilt: Float, fadeIn: Boolean = false, easeTo: Float? = null) {
        val inner = innerPanel
        val config = DuoSettings.config.value
        val foldLine = { w: Float, h: Float, c: com.duoopen.settings.DuoConfig -> DuoShader.foldFor(inner, w, h, c) }
        val created: FoldSurface? = if (bitmap != null) {
            SnapshotSurface(service, windowManager, bitmap, config, foldLine).takeIf { it.attached }
        } else {
            LiveBlurSurface(service, windowManager, config, DuoShader.pxPerMm(service.createDisplayContext(display)), foldLine)
                .takeIf { it.attached }
        }
        if (created == null) {
            Log.e(TAG, "display $displayId: could not attach overlay")
            phase = Phase.IDLE
            return
        }
        created.tilt = startTilt
        surface = created
        if (
            bitmap != null &&
            shellCapture()
        ) {
            if (
                deterministicFrozenFrameMode()
            ) {
                com.duoopen.debug.DuoDiagnostics.event(
                    "snapshot-transition",
                    "frozen frame display=$displayId inner=$innerPanel " +
                        "size=${bitmap.width}x${bitmap.height}; live recapture suppressed",
                )
            } else {
                startLiveLoop()
            }
        }
        phase = Phase.SHOWING
        onShowingChanged()
        if (fadeIn) {
            // Content was already live on this panel; ease the frost in.
            created.fadeIn(FADE_IN_MS)
        }
        val explicitOpeningVisual =
            continuityOpeningVisual &&
                isFold7CoverGeometryNow()

        if (explicitOpeningVisual) {
            follower?.cancel()
            follower = null
            startGen5OpeningFrameLoop()
            (created as? SnapshotSurface)?.let(::requestGen5RefreshRate)
        } else {
            follower = TiltFollower { t ->
                created.tilt = t
                if (t < DuoShader.FLAT_EPSILON && !demoRunning) dismiss(fadeMs = FADE_OUT_FLAT_MS)
            }.also {
                it.snap(startTilt)

                if (
                    hinge.externalActive &&
                    easeTo == null
                ) {
                    it.tauS =
                        SAMSUNG_LIVE_TAU_S
                }
            }
        }
        lastHingeMoveMs = SystemClock.uptimeMillis()

        timedResolve =
            easeTo != null ||
                explicitOpeningVisual

        when {
            explicitOpeningVisual -> {
                /*
                 * Gen5 renders directly at vsync from the visual-only virtual
                 * hinge. Do not feed the predicted angle back through the
                 * legacy TiltFollower; double smoothing would reintroduce the
                 * latency this path is designed to remove.
                 */
            }

            easeTo != null -> {
                follower?.tauS =
                    if (hinge.isCoarse) {
                        COARSE_EASE_TAU_S
                    } else {
                        TIMED_RESOLVE_TAU_S
                    }

                follower?.setTarget(
                    easeTo
                )

                if (
                    easeTo >
                    DuoShader.FLAT_EPSILON
                ) {
                    handler.postDelayed(
                        peakHold,
                        if (hinge.isCoarse) {
                            COARSE_PEAK_HOLD_MS
                        } else {
                            PEAK_HOLD_MS
                        },
                    )
                }
            }

            else -> {
                handler.postDelayed(
                    settleCheck,
                    SETTLE_TIMEOUT_MS,
                )
            }
        }
    }

    private fun dismiss(fadeMs: Long) {
        val s = surface ?: return
        Log.i(TAG, "display $displayId: dismiss (fade ${fadeMs}ms) at tilt=${s.tilt}")
        clearOverlayState()
        s.fadeOut(fadeMs) { s.detach() }
    }

    private fun removeOverlay() {
        phase = Phase.IDLE
        timedResolve = false
        val s = surface ?: return
        clearOverlayState()
        s.detach()
    }

    /**
     * Shizuku mode: keep re-capturing the screen beneath the overlay at a
     * reduced scale, so the picture under the frost is live instead of frozen.
     */
    private fun startLiveLoop() {
        if (liveLoop) return

        liveLoop = true

        val myGen =
            captureGen

        var frames = 0

        fun tick() {
            if (
                !liveLoop ||
                phase != Phase.SHOWING ||
                myGen != captureGen
            ) {
                liveLoop = false
                return
            }

            val s =
                surface as?
                    SnapshotSurface

            if (
                s == null ||
                s.tilt <
                DuoShader.FLAT_EPSILON
            ) {
                handler.postDelayed(
                    { tick() },
                    LIVE_RETRY_MS,
                )
                return
            }

            val excluded =
                excludedLayers()

            if (excluded.isEmpty()) {
                handler.postDelayed(
                    { tick() },
                    LIVE_RETRY_MS,
                )
                return
            }

            val frameStarted =
                SystemClock.uptimeMillis()

            scope.launch {
                val frame =
                    withContext(
                        Dispatchers.IO,
                    ) {
                        ShizukuBridge.capture(
                            displayId,
                            excluded,
                            LIVE_SHELL_SCALE,
                        )
                    }

                if (
                    liveLoop &&
                    phase ==
                    Phase.SHOWING &&
                    myGen ==
                    captureGen &&
                    frame != null &&
                    !bridging
                ) {
                    (
                        surface as?
                            SnapshotSurface
                    )?.replaceSnapshot(
                        frame,
                    )

                    frames++

                    if (
                        frames == 1 ||
                        frames % 25 == 0
                    ) {
                        Log.i(
                            TAG,
                            "display $displayId: " +
                                "live frame $frames " +
                                "(${frame.width}x${frame.height})",
                        )
                    }
                }

                val nextDelay =
                    if (frame == null) {
                        LIVE_RETRY_MS
                    } else {
                        (
                            frameStarted +
                                LIVE_FRAME_PERIOD_MS -
                                SystemClock.uptimeMillis()
                            )
                            .coerceAtLeast(
                                0L,
                            )
                    }

                handler.postDelayed(
                    { tick() },
                    nextDelay,
                )
            }
        }

        handler.postDelayed(
            { tick() },
            LIVE_START_DELAY_MS,
        )
    }


    private fun startGen5OpeningFrameLoop() {
        if (gen5FramePosted) return
        gen5FramePosted = true
        Choreographer.getInstance().postFrameCallback(gen5FrameCallback)
    }

    private fun stopGen5OpeningClock() {
        if (gen5FramePosted) {
            Choreographer.getInstance().removeFrameCallback(gen5FrameCallback)
        }
        gen5FramePosted = false
        gen5VirtualHinge.stop()
        clearGen5RefreshRate()
    }

    private fun requestGen5RefreshRate(snapshot: SnapshotSurface) {
        snapshot.view.post {
            if (!continuityOpeningVisual) return@post
            val root = rootSurfaceControl(snapshot.view)
            if (root == null) {
                com.duoopen.debug.DuoDiagnostics.event(
                    "gen5-refresh",
                    "request skipped display=$displayId rootSurfaceControl=null",
                )
                return@post
            }

            val supported =
                runCatching {
                    display.supportedModes.joinToString(",") {
                        "${it.modeId}:${it.refreshRate}"
                    }
                }.getOrDefault("unknown")

            runCatching {
                SurfaceControl.Transaction()
                    .setFrameRate(
                        root,
                        GEN5_REQUESTED_HZ,
                        Surface.FRAME_RATE_COMPATIBILITY_DEFAULT,
                        Surface.CHANGE_FRAME_RATE_ONLY_IF_SEAMLESS,
                    )
                    .apply()
                gen5RefreshRoot = root
            }.onSuccess {
                com.duoopen.debug.DuoDiagnostics.event(
                    "gen5-refresh",
                    "requested=$GEN5_REQUESTED_HZ seamlessOnly=true " +
                        "effective=${display.mode.refreshRate} supported=[$supported]",
                )
            }.onFailure {
                com.duoopen.debug.DuoDiagnostics.event(
                    "gen5-refresh",
                    "request failed error=${it.javaClass.simpleName}:${it.message} " +
                        "effective=${display.mode.refreshRate} supported=[$supported]",
                )
            }
        }
    }

    private fun clearGen5RefreshRate() {
        val root = gen5RefreshRoot ?: return
        gen5RefreshRoot = null
        runCatching {
            SurfaceControl.Transaction()
                .setFrameRate(
                    root,
                    0f,
                    Surface.FRAME_RATE_COMPATIBILITY_DEFAULT,
                    Surface.CHANGE_FRAME_RATE_ONLY_IF_SEAMLESS,
                )
                .apply()
        }
        com.duoopen.debug.DuoDiagnostics.event(
            "gen5-refresh",
            "cleared requestedHz=$GEN5_REQUESTED_HZ effective=${runCatching { display.mode.refreshRate }.getOrNull()}",
        )
    }

    private fun recycleGen5OpeningBitmap() {
        val bitmap = gen5OwnedOpeningBitmap
        gen5OwnedOpeningBitmap = null
        if (bitmap != null && !bitmap.isRecycled) {
            runCatching { bitmap.recycle() }
        }
    }

    private fun clearOverlayState() {
        liveLoop = false
        handler.removeCallbacks(settleCheck)
        handler.removeCallbacks(peakHold)
        follower?.cancel()
        follower = null
        surface = null
        timedResolve = false
        bridging = false
        phase = Phase.IDLE
        onShowingChanged()
    }

    /** The display went away or the service is stopping. */
    fun destroy() {
        captureGen++ // orphan any capture in flight
        stopGen5OpeningClock()
        removeOverlay()
        recycleGen5OpeningBitmap()
        Log.i(TAG, "engine display=$displayId destroyed")
    }

    /**
     * Manual check without folding: snapshot the screen and play what this
     * panel shows during a fold. Inner panel: an unfold from full frost to
     * flat. Cover panel: frost sweeping in (opening) then back out (closing).
     */
    fun playDemo(durationMs: Long = 1400) {
        if (phase != Phase.IDLE || demoRunning) return
        demoRunning = true
        val inner = innerPanel
        val peak = DuoShader.MAX_TILT * DuoSettings.config.value.intensity.coerceAtMost(1f)
        // Frost at the very start so the overlay is visibly there; on the
        // cover it starts flat and sweeps in first.
        startEffect(afterSwap = false, startTilt = if (inner) peak else 0.06f)
        handler.postDelayed({
            val f = follower
            if (f == null) {
                demoRunning = false
                return@postDelayed
            }
            // Slow ease so the demo reads as a fold rather than a snap.
            f.tauS = durationMs / 4000f
            if (inner) {
                f.setTarget(0f)
                handler.postDelayed({
                    demoRunning = false
                    dismiss(fadeMs = FADE_OUT_FLAT_MS)
                }, durationMs)
            } else {
                f.setTarget(peak)
                handler.postDelayed({ f.setTarget(0f) }, durationMs)
                handler.postDelayed({
                    demoRunning = false
                    dismiss(fadeMs = FADE_OUT_FLAT_MS)
                }, durationMs * 2)
            }
        }, 450)
    }

    private companion object {
        const val TAG = "DuoOverlay"
        /** The framework rejects screenshots closer together than ~333 ms. */
        const val SCREENSHOT_MIN_INTERVAL_MS = 340L
        const val MAX_CAPTURE_ATTEMPTS = 3
        /** A screenshot of a panel that is still lighting up can take most of a second. */
        const val CAPTURE_TIMEOUT_MS = 1_100L
        const val BLACK_THRESHOLD = 30
        /** Ease time constant for the timed resolve (≈ 250 ms to settle). */
        const val TIMED_RESOLVE_TAU_S = 0.07f
        /** Slower ease for stops-only sensors, so a frost-in reads as a fold (≈ 450 ms). */
        const val COARSE_EASE_TAU_S = 0.12f
        /** Clear-out once a stops-only sensor reports the rest stop (≈ 300 ms). */
        const val COARSE_CLEAR_TAU_S = 0.08f
        /** How long a timed frost-up stays before it fades, absent a panel swap. */
        const val PEAK_HOLD_MS = 1_200L
        /** Stops-only sensors: hold the frost between stops, but not forever (flex mode). */
        const val COARSE_PEAK_HOLD_MS = 2_500L
        /** Tilt hysteresis for leaving a rest pose, so hinge jitter doesn't fire. */
        const val REST_LEAVE_TILT = 2f
        const val COVER_OPEN_IMMEDIATE_TILT = 0.15f
        const val GEN5_REQUESTED_HZ = 120f
        const val GEN5_TELEMETRY_EVERY_N_FRAMES = 4L
        const val INNER_OPEN_LATCH_DEG = 172f
        const val INNER_OPEN_REARM_DEG = 166f
        /** After a swap, don't bother if the fold is nearly finished by capture time. */
        const val SKIP_INNER_ABOVE_HINGE = 135f
        const val SKIP_COVER_BELOW_HINGE = 10f
        const val SETTLE_TIMEOUT_MS = 700L
        const val FADE_IN_MS = 140L
        const val FADE_OUT_FLAT_MS = 120L
        const val FADE_OUT_STALLED_MS = 300L
        /**
         * Full resolution for the initial frame.
         *
         * Live frames trade some resolution for latency because
         * they are visible only briefly under the fold shader.
         */
        const val INITIAL_SHELL_SCALE = 1f

        const val LIVE_SHELL_SCALE = 0.40f

        // Target roughly 20 fps. Actual cadence naturally falls
        // back to capture speed if the device cannot sustain it.
        const val LIVE_FRAME_PERIOD_MS = 48L

        const val LIVE_START_DELAY_MS = 12L

        const val LIVE_RETRY_MS = 80L

        // Lower latency tracking for Samsung continuous angles.
        const val SAMSUNG_LIVE_TAU_S = 0.028f

        const val SHELL_RETRY_MS = 60L
        /** Minimum real hinge motion before a settled mid-fold effect resumes. */
        const val RESUME_MOTION_DEG = 0.75f

        /**
         * The window's root layer (hidden `ViewRootImpl.getSurfaceControl`),
         * needed to exclude our overlay from a display capture. Null if the
         * hidden-API exemption isn't in place.
         */
        fun rootSurfaceControl(view: View): SurfaceControl? = runCatching {
            val root = view.rootView.parent ?: return null
            val sc = root.javaClass.getMethod("getSurfaceControl").invoke(root) as? SurfaceControl
            sc?.takeIf { it.isValid }
        }.getOrNull()
    }
}
