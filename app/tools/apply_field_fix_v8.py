#!/usr/bin/env python3
from pathlib import Path


def once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"{label}: expected anchor exactly once in {path}, found {count}"
        )
    p.write_text(text.replace(old, new, 1))


def main() -> None:
    gradle = "app/build.gradle.kts"
    once(gradle, "versionCode = 36", "versionCode = 37", "versionCode")
    once(
        gradle,
        'versionName = "2.0.1-zfold7-gen2-audit1"',
        'versionName = "2.0.2-zfold7-gen2-field1"',
        "versionName",
    )

    policy_path = Path(
        "app/src/full/java/com/duoopen/overlay/Fold7CoverRenderPolicy.kt"
    )
    if policy_path.exists():
        raise SystemExit(f"{policy_path}: already exists")

    policy_path.write_text(
        '''package com.duoopen.overlay

/**
 * Fold7 cover render arbitration.
 *
 * When privileged Gen2 continuity is available, autonomous cover PanelEngine
 * rendering is suppressed. Closing is owned by DisplayMirrorHost; opening from
 * fully closed is the one deliberate exception, driven explicitly from the
 * early device-state edge through topology-only handoff until true open.
 */
internal object Fold7CoverRenderPolicy {
    data class Decision(
        val gen2OwnsCover: Boolean,
        val runEarlyOpeningVisual: Boolean,
    )

    fun decide(
        privilegedGen2Ready: Boolean,
        openingFromClosedLatched: Boolean,
        state: Fold7ContinuityController.State,
    ): Decision {
        if (!privilegedGen2Ready) {
            return Decision(
                gen2OwnsCover = false,
                runEarlyOpeningVisual = false,
            )
        }

        return Decision(
            gen2OwnsCover = true,
            runEarlyOpeningVisual =
                openingFromClosedLatched &&
                    state in setOf(
                        Fold7ContinuityController.State.OPENING_FROM_CLOSED,
                        Fold7ContinuityController.State.INNER_HANDOFF,
                    ),
        )
    }
}
'''
    )

    test_path = Path(
        "app/src/test/java/com/duoopen/overlay/Fold7CoverRenderPolicyTest.kt"
    )
    if test_path.exists():
        raise SystemExit(f"{test_path}: already exists")

    test_path.write_text(
        '''package com.duoopen.overlay

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7CoverRenderPolicyTest {
    @Test
    fun noPrivilegedGen2_preservesLegacyCoverRendering() {
        val decision =
            Fold7CoverRenderPolicy.decide(
                privilegedGen2Ready = false,
                openingFromClosedLatched = false,
                state = Fold7ContinuityController.State.NATIVE_COVER,
            )

        assertFalse(decision.gen2OwnsCover)
        assertFalse(decision.runEarlyOpeningVisual)
    }

    @Test
    fun nativeCover_isOwnedButDoesNotAnimateUntilOpeningEdge() {
        val decision =
            Fold7CoverRenderPolicy.decide(
                privilegedGen2Ready = true,
                openingFromClosedLatched = false,
                state = Fold7ContinuityController.State.NATIVE_COVER,
            )

        assertTrue(decision.gen2OwnsCover)
        assertFalse(decision.runEarlyOpeningVisual)
    }

    @Test
    fun openingFromClosed_runsExplicitEarlyOpeningVisual() {
        val decision =
            Fold7CoverRenderPolicy.decide(
                privilegedGen2Ready = true,
                openingFromClosedLatched = true,
                state = Fold7ContinuityController.State.OPENING_FROM_CLOSED,
            )

        assertTrue(decision.gen2OwnsCover)
        assertTrue(decision.runEarlyOpeningVisual)
    }

    @Test
    fun latchedInnerHandoff_keepsOpeningVisualUntilOpenOrRouteLoss() {
        val decision =
            Fold7CoverRenderPolicy.decide(
                privilegedGen2Ready = true,
                openingFromClosedLatched = true,
                state = Fold7ContinuityController.State.INNER_HANDOFF,
            )

        assertTrue(decision.gen2OwnsCover)
        assertTrue(decision.runEarlyOpeningVisual)
    }

    @Test
    fun openInner_clearsOpeningVisualEvenIfCallerStillHasLatch() {
        val decision =
            Fold7CoverRenderPolicy.decide(
                privilegedGen2Ready = true,
                openingFromClosedLatched = true,
                state = Fold7ContinuityController.State.OPEN_INNER,
            )

        assertTrue(decision.gen2OwnsCover)
        assertFalse(decision.runEarlyOpeningVisual)
    }

    @Test
    fun closingStates_neverAllowAutonomousCoverPanelEngine() {
        for (
            state in
            listOf(
                Fold7ContinuityController.State.CLOSING_INTENT,
                Fold7ContinuityController.State.COVER_PREWARMING,
                Fold7ContinuityController.State.COVER_READY_HIDDEN,
                Fold7ContinuityController.State.COVER_VISUAL,
            )
        ) {
            val decision =
                Fold7CoverRenderPolicy.decide(
                    privilegedGen2Ready = true,
                    openingFromClosedLatched = false,
                    state = state,
                )

            assertTrue(decision.gen2OwnsCover)
            assertFalse(decision.runEarlyOpeningVisual)
        }
    }
}
'''
    )

    panel = "app/src/full/java/com/duoopen/overlay/PanelEngine.kt"

    once(
        panel,
        '''    private var innerOpenLatched = false

    /** Stable opening/closing state, resistant to tiny hinge jitter. */
''',
        '''    private var innerOpenLatched = false

    /** Gen2 owns Fold7 cover presentation while privileged continuity is armed. */
    private var continuityCoverOwned = false

    /** Explicit CLOSED -> OPEN visual started from the device-state opening edge. */
    private var continuityOpeningVisual = false

    /** Close cycle whose capture-only continuity prime has already been issued. */
    private var primedContinuityCycleId = -1L

    /** Stable opening/closing state, resistant to tiny hinge jitter. */
''',
        "PanelEngine Gen2 render state",
    )

    once(
        panel,
        '''    fun onHinge(angle: Float) {
        val previousRaw =
            lastRawHingeAngle
''',
        '''    fun onHinge(angle: Float) {
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
            lastHingeMoveMs = SystemClock.uptimeMillis()

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
''',
        "PanelEngine cover ownership hinge gate",
    )

    once(
        panel,
        '''    fun evaluate() {
        if (demoRunning) return
        val inner = display.isInnerPanel()
        if (inner != innerPanel) {
            innerPanel = inner
            panelSwitched = true
            if (phase != Phase.IDLE) removeOverlay() // old panel's snapshot is meaningless now
        }
        val angle = hinge.lastAngle
''',
        '''    fun evaluate() {
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
''',
        "PanelEngine cover ownership evaluate gate",
    )

    once(
        panel,
        '''    /**
     * Fold7 transitions must be deterministic: once a transition frame is
''',
        '''    fun isFold7CoverGeometryNow(): Boolean {
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

        com.duoopen.debug.DuoDiagnostics.event(
            "cover-opening-visual",
            "START display=$displayId reason=$reason precise=${hinge.lastAngle}",
        )

        startEffect(
            afterSwap = false,
            startTilt = COVER_OPEN_IMMEDIATE_TILT,
        )
    }

    fun endContinuityOpeningVisual(
        reason: String,
    ) {
        if (!continuityOpeningVisual) {
            return
        }

        continuityOpeningVisual = false
        captureGen++

        if (
            phase != Phase.IDLE ||
            surface != null
        ) {
            removeOverlay()
        }

        restArmed = true
        panelSwitched = false

        com.duoopen.debug.DuoDiagnostics.event(
            "cover-opening-visual",
            "END display=$displayId reason=$reason precise=${hinge.lastAngle}",
        )
    }

    fun primeContinuityFrame(
        cycle: Fold7CycleEnvelope.CloseCycle,
        reason: String,
    ): Boolean {
        if (
            !isFold7InnerGeometryNow() ||
            !deterministicFrozenFrameMode() ||
            !ShizukuBridge.ready ||
            activeCloseCycle() != cycle ||
            primedContinuityCycleId == cycle.closeCycleId
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
            ) ?: return false

        primedContinuityCycleId =
            cycle.closeCycleId

        com.duoopen.debug.DuoDiagnostics.event(
            "snapshot-transition",
            "Gen2 continuity prime START serviceEpoch=${cycle.serviceEpoch} " +
                "closeCycle=${cycle.closeCycleId} capture=${ticket.captureSequence} " +
                "hinge=${hinge.lastAngle} reason=$reason",
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
                primedContinuityCycleId != cycle.closeCycleId
            ) {
                bitmap?.let {
                    runCatching {
                        it.recycle()
                    }
                }
                return@launch
            }

            if (bitmap == null) {
                primedContinuityCycleId = -1L

                com.duoopen.debug.DuoDiagnostics.event(
                    "snapshot-transition",
                    "Gen2 continuity prime FAILED serviceEpoch=${cycle.serviceEpoch} " +
                        "closeCycle=${cycle.closeCycleId} " +
                        "latencyMs=${SystemClock.uptimeMillis() - startedUptimeMs}",
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

                com.duoopen.debug.DuoDiagnostics.event(
                    "snapshot-transition",
                    "Gen2 continuity prime REJECTED closeCycle=${cycle.closeCycleId} " +
                        "capture=${ticket.captureSequence}",
                )
                return@launch
            }

            cache.put(
                true,
                bitmap,
            )

            com.duoopen.debug.DuoDiagnostics.event(
                "snapshot-transition",
                "Gen2 continuity prime READY serviceEpoch=${lease.serviceEpoch} " +
                    "closeCycle=${lease.closeCycleId} capture=${lease.captureSequence} " +
                    "content=${lease.contentLeaseId} " +
                    "latencyMs=${SystemClock.uptimeMillis() - startedUptimeMs}",
            )
        }

        return true
    }

    /**
     * Fold7 transitions must be deterministic: once a transition frame is
''',
        "PanelEngine Gen2 render/capture API",
    )

    once(
        panel,
        '''        if (!innerPanel || !deterministicFrozenFrameMode()) return null
        val cycle = activeCloseCycle() ?: return null
        val mode = runCatching { display.mode }.getOrNull() ?: return null
        return continuityFrames.beginCapture(
''',
        '''        if (!innerPanel || !deterministicFrozenFrameMode()) return null
        val cycle = activeCloseCycle() ?: return null

        if (
            primedContinuityCycleId ==
            cycle.closeCycleId
        ) {
            return null
        }

        val mode = runCatching { display.mode }.getOrNull() ?: return null
        return continuityFrames.beginCapture(
''',
        "PanelEngine prime ownership in generic capture",
    )

    once(
        panel,
        '''        lastHingeMoveMs = SystemClock.uptimeMillis()
        timedResolve = easeTo != null
        if (easeTo != null) {
            follower?.tauS = if (hinge.isCoarse) COARSE_EASE_TAU_S else TIMED_RESOLVE_TAU_S
            follower?.setTarget(easeTo)
            if (easeTo > DuoShader.FLAT_EPSILON) {
                handler.postDelayed(peakHold, if (hinge.isCoarse) COARSE_PEAK_HOLD_MS else PEAK_HOLD_MS)
            }
        } else {
            handler.postDelayed(settleCheck, SETTLE_TIMEOUT_MS)
        }
''',
        '''        lastHingeMoveMs = SystemClock.uptimeMillis()

        val explicitOpeningVisual =
            continuityOpeningVisual &&
                isFold7CoverGeometryNow()

        val explicitOpeningPeak =
            DuoShader.MAX_TILT *
                config.intensity.coerceAtMost(1f)

        timedResolve =
            easeTo != null ||
                explicitOpeningVisual

        when {
            explicitOpeningVisual -> {
                follower?.tauS =
                    CONTINUITY_OPENING_TAU_S

                follower?.setTarget(
                    explicitOpeningPeak
                )

                /*
                 * Lifetime is owned by FoldOverlayService, not this renderer.
                 * The service owns the semantic opening latch and its one-shot
                 * timeout, so display callbacks cannot restart a timed-out
                 * animation behind our back.
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
''',
        "PanelEngine explicit opening animation drive",
    )

    once(
        panel,
        '''        const val COVER_OPEN_IMMEDIATE_TILT = 0.15f
        const val INNER_OPEN_LATCH_DEG = 172f
''',
        '''        const val COVER_OPEN_IMMEDIATE_TILT = 0.15f
        const val CONTINUITY_OPENING_TAU_S = 0.09f
        const val INNER_OPEN_LATCH_DEG = 172f
''',
        "PanelEngine opening constants",
    )

    coordinator = "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"

    once(
        coordinator,
        """    @Volatile private var prewarmInFlightConnectionEpoch = -1L
    @Volatile private var destroyed = false

    val visualMirrorActive: Boolean
""",
        """    @Volatile private var prewarmInFlightConnectionEpoch = -1L
    @Volatile private var destroyed = false
    @Volatile private var renderOwnershipArmed = false

    val renderOwnershipEnabled: Boolean
        get() = renderOwnershipArmed && !destroyed

    val visualMirrorActive: Boolean
""",
        "coordinator render ownership state",
    )

    once(
        coordinator,
        """    fun arm() {
        gen2.cancelActiveCycle()
        destroyed = false
        ensureMirrorSession("arm")
""",
        """    fun arm() {
        gen2.cancelActiveCycle()
        destroyed = false
        renderOwnershipArmed = true
        ensureMirrorSession("arm")
""",
        "coordinator arm ownership",
    )

    once(
        coordinator,
        """    fun release(reason: String) {
        gen2.cancelActiveCycle()
        val generation = controller.generation
""",
        """    fun release(reason: String) {
        renderOwnershipArmed = false
        gen2.cancelActiveCycle()
        val generation = controller.generation
""",
        "coordinator release ownership",
    )

    once(
        coordinator,
        """    fun destroy() {
        destroyed = true
        hideMirror(
""",
        """    fun destroy() {
        destroyed = true
        renderOwnershipArmed = false
        hideMirror(
""",
        "coordinator destroy ownership",
    )

    service = "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"

    once(
        service,
        """    private var continuityAutoArmAttempted =
        false

    private var pendingProbeReason =
""",
        """    private var continuityAutoArmAttempted =
        false

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
""",
        "service semantic opening latch",
    )

    once(
        service,
        '''                if (::continuity.isInitialized) {
                    continuity.onTopologyFastLane(
                        "display-added:$displayId"
                    )
                }
                scheduleDisplaySync(
''',
        '''                handleContinuityTopologyFastLane(
                    "display-added:$displayId"
                )
                scheduleDisplaySync(
''',
        "service display-added fast lane",
    )
    once(
        service,
        '''                if (::continuity.isInitialized) {
                    continuity.onTopologyFastLane(
                        "display-removed:$displayId"
                    )
                }
                scheduleDisplaySync(
''',
        '''                handleContinuityTopologyFastLane(
                    "display-removed:$displayId"
                )
                scheduleDisplaySync(
''',
        "service display-removed fast lane",
    )
    once(
        service,
        '''                if (::continuity.isInitialized) {
                    continuity.onTopologyFastLane(
                        "display-changed:$displayId"
                    )
                }
                scheduleDisplaySync(
''',
        '''                handleContinuityTopologyFastLane(
                    "display-changed:$displayId"
                )
                scheduleDisplaySync(
''',
        "service display-changed fast lane",
    )

    once(
        service,
        '''                continuity
                    .onEarlyOpeningEdge(
                        reason
                    )
''',
        '''                val beforeOpeningState =
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
                    setEarlyOpeningVisualLatched(
                        value = true,
                        reason = "device-state:$reason",
                    )
                }

                reconcileContinuityCoverRendering(
                    "early-opening:$reason"
                )
''',
        "service early opening visual trigger",
    )

    once(
        service,
        '''                } else {
                    continuity.onPrivilegedUnavailable()
                }
            }
''',
        '''                } else {
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
''',
        "service Shizuku render ownership",
    )

    once(
        service,
        '''    private fun onHinge(angle: Float) {
        continuity.onHinge(angle)

        deviceStateObserver
''',
        '''    private fun onHinge(angle: Float) {
        val beforeState =
            continuity.state

        continuity.onHinge(angle)

        if (
            beforeState ==
                Fold7ContinuityController.State.NATIVE_COVER &&
            continuity.state ==
                Fold7ContinuityController.State.OPENING_FROM_CLOSED
        ) {
            setEarlyOpeningVisualLatched(
                value = true,
                reason = "precise-hinge-opening-edge",
            )
        }

        primeContinuityFrameIfNeeded(
            "hinge:$angle"
        )

        reconcileContinuityCoverRendering(
            "hinge:$angle"
        )

        deviceStateObserver
''',
        "service hinge arbitration",
    )

    once(
        service,
        '''        if (gone.isNotEmpty()) updateRunning()
        if (!continuity.visualMirrorActive) {
            for (e in engines.values.toList()) {
                e.evaluate()
            }
        }

        angleFeed?.onDisplayChanged()

        continuity.onTopologyChanged(
            "sync-displays"
        )

        deviceStateObserver
''',
        '''        if (gone.isNotEmpty()) updateRunning()

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
''',
        "service syncDisplays arbitration",
    )

    once(
        service,
        '''    /** Samsung continuous angle via Shizuku + fold wallpaper, when everything lines up. */
    private fun syncAngleFeed() {
''',
        '''    private fun setEarlyOpeningVisualLatched(
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

        engines.values
            .firstOrNull {
                it.isFold7InnerGeometryNow()
            }
            ?.primeContinuityFrame(
                cycle = cycle,
                reason = reason,
            )
    }

    private fun reconcileContinuityCoverRendering(
        reason: String,
    ) {
        if (!::continuity.isInitialized) return

        if (
            !ShizukuBridge.ready ||
            !continuity.renderOwnershipEnabled ||
            continuity.state !in
                setOf(
                    Fold7ContinuityController.State.OPENING_FROM_CLOSED,
                    Fold7ContinuityController.State.INNER_HANDOFF,
                )
        ) {
            setEarlyOpeningVisualLatched(
                value = false,
                reason = "state-or-ownership:$reason",
            )
        }

        val coverEngines =
            engines.values
                .filter {
                    it.isFold7CoverGeometryNow()
                }

        if (
            earlyOpeningVisualLatched &&
            coverEngines.isEmpty()
        ) {
            setEarlyOpeningVisualLatched(
                value = false,
                reason = "cover-route-missing:$reason",
            )
        }

        val policy =
            Fold7CoverRenderPolicy.decide(
                privilegedGen2Ready =
                    ShizukuBridge.ready &&
                        continuity.renderOwnershipEnabled,
                openingFromClosedLatched =
                    earlyOpeningVisualLatched,
                state =
                    continuity.state,
            )

        for (
            engine in
            engines.values.toList()
        ) {
            /*
             * Fold7 logical display IDs can remap between physical panels.
             * Render ownership follows fresh geometry, never cached innerPanel.
             */
            val shouldOwnCover =
                policy.gen2OwnsCover &&
                    engine.isFold7CoverGeometryNow()

            engine.setContinuityCoverOwned(
                owned =
                    shouldOwnCover,
                reason =
                    reason,
            )

            if (
                shouldOwnCover &&
                policy.runEarlyOpeningVisual
            ) {
                if (!earlyOpeningVisualStarted) {
                    engine.beginContinuityOpeningVisual(
                        reason
                    )

                    earlyOpeningVisualStarted =
                        true
                }
            } else {
                engine.endContinuityOpeningVisual(
                    reason
                )
            }
        }
    }

    /** Samsung continuous angle via Shizuku + fold wallpaper, when everything lines up. */
    private fun syncAngleFeed() {
''',
        "service helper insertion",
    )

    once(
        service,
        """        if (::continuity.isInitialized) {
            continuity.destroy()
        }

        handler.removeCallbacks(
            displayProbeRunnable
        )
""",
        """        if (::continuity.isInitialized) {
            setEarlyOpeningVisualLatched(
                value = false,
                reason = \"service-destroy\",
            )

            continuity.destroy()
        }

        handler.removeCallbacks(
            earlyOpeningVisualTimeoutRunnable
        )

        handler.removeCallbacks(
            displayProbeRunnable
        )
""",
        "service destroy opening cleanup",
    )

    once(
        service,
        """            if (enable) {
                service.continuity.arm()
            } else {
                service.continuity.release(
                    \"user-stop\"
                )
            }

            return true
""",
        """            if (enable) {
                service.continuity.arm()

                service.reconcileContinuityCoverRendering(
                    \"user-arm\"
                )
            } else {
                service.setEarlyOpeningVisualLatched(
                    value = false,
                    reason = \"user-stop\",
                )

                service.continuity.release(
                    \"user-stop\"
                )

                service.reconcileContinuityCoverRendering(
                    \"user-stop\"
                )
            }

            return true
""",
        "manual continuity ownership reconcile",
    )

    once(
        service,
        """        private const val DISPLAY_SYNC_DEBOUNCE_MS =
            24L

        /** How old a panel's last picture may be and still bridge the next fold. */
""",
        """        private const val DISPLAY_SYNC_DEBOUNCE_MS =
            24L

        /** One semantic CLOSED -> OPEN visual attempt per opening edge. */
        private const val EARLY_OPENING_VISUAL_MAX_MS =
            2_500L

        /** How old a panel's last picture may be and still bridge the next fold. */
""",
        "service opening timeout constant",
    )

    # Remove the previous package accidentally uploaded under /app. The V8
    # workflow validates exact known blobs before the patcher is allowed to run.
    for stale in (
        Path("app/.github/workflows/apply-gen2-field-fix-v7.yml"),
        Path("app/tools/apply_field_fix_v7.py"),
        Path("app/README.md"),
        Path("app/SHA256SUMS.txt"),
    ):
        if stale.exists():
            stale.unlink()

    for empty_dir in (
        Path("app/.github/workflows"),
        Path("app/.github"),
        Path("app/tools"),
    ):
        if empty_dir.exists():
            try:
                empty_dir.rmdir()
            except OSError:
                pass

    print("FIELD LOG V8 SOURCE PATCH: PASS")


if __name__ == "__main__":
    main()
