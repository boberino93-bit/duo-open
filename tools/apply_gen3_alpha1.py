#!/usr/bin/env python3
from pathlib import Path
import shutil

ROOT = Path(".")
HERE = Path(__file__).resolve().parent.parent


def once(path: str, old: str, new: str, label: str) -> None:
    p = ROOT / path
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"{label}: expected exactly one anchor in {path}, found {count}"
        )
    p.write_text(text.replace(old, new, 1))


def between(
    path: str,
    start: str,
    end: str,
    replacement: str,
    label: str,
) -> None:
    p = ROOT / path
    text = p.read_text()
    if text.count(start) != 1:
        raise SystemExit(
            f"{label}: start marker count={text.count(start)} in {path}"
        )
    start_i = text.index(start)
    end_i = text.find(end, start_i + len(start))
    if end_i < 0:
        raise SystemExit(f"{label}: end marker missing in {path}")
    p.write_text(
        text[:start_i] +
        replacement +
        text[end_i:]
    )


def copy_payload(name: str, destination: str) -> None:
    target = ROOT / destination
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        HERE / "payload" / name,
        target,
    )


def main() -> None:
    once(
        "app/build.gradle.kts",
        '        versionCode = 37\n        versionName = "2.0.2-zfold7-gen2-field1"\n',
        '        versionCode = 38\n        versionName = "3.0.0-alpha1-zfold7"\n',
        "Gen3 version",
    )

    for name in (
        "Fold7ContinuityPrimeOwner.kt",
        "Fold7CoverVisualAttemptOwner.kt",
        "Fold7CoverVisualHost.kt",
        "Fold7Gen3VisualCoordinator.kt",
    ):
        copy_payload(
            name,
            f"app/src/full/java/com/duoopen/overlay/{name}",
        )

    for name in (
        "Fold7ContinuityPrimeOwnerGen3Test.kt",
        "Fold7CoverVisualAttemptOwnerGen3Test.kt",
        "Fold7ContinuityFrameStoreGen3OrderingTest.kt",
    ):
        copy_payload(
            name,
            f"app/src/test/java/com/duoopen/overlay/{name}",
        )

    kernel = "app/src/full/java/com/duoopen/overlay/Fold7Gen2Kernel.kt"

    once(
        kernel,
        '''    val frames = Fold7ContinuityFrameStore<T>()

    val activeCycle: Fold7CycleEnvelope.CloseCycle?
''',
        '''    val frames = Fold7ContinuityFrameStore<T>()
    val primeOwner = Fold7ContinuityPrimeOwner()

    val activeCycle: Fold7CycleEnvelope.CloseCycle?
''',
        "kernel prime owner",
    )

    once(
        kernel,
        '''            val cycle = cycles.beginClose(nowUptimeMs)
            frames.beginCycle(cycle)
            return CycleChange(started = cycle)
''',
        '''            val cycle = cycles.beginClose(nowUptimeMs)
            frames.beginCycle(cycle)
            primeOwner.beginCycle(cycle)
            return CycleChange(started = cycle)
''',
        "kernel begin prime cycle",
    )

    once(
        kernel,
        '''            cycles.invalidateClose(current.closeCycleId)
            frames.invalidateCycle(current.serviceEpoch, current.closeCycleId)
            coverReadiness.invalidate(current.serviceEpoch, current.closeCycleId)
            return CycleChange(ended = current)
''',
        '''            cycles.invalidateClose(current.closeCycleId)
            frames.invalidateCycle(current.serviceEpoch, current.closeCycleId)
            primeOwner.invalidate(current)
            coverReadiness.invalidate(current.serviceEpoch, current.closeCycleId)
            return CycleChange(ended = current)
''',
        "kernel transition invalidation",
    )

    once(
        kernel,
        '''        cycles.invalidateClose(current.closeCycleId)
        frames.invalidateCycle(current.serviceEpoch, current.closeCycleId)
        coverReadiness.invalidate(current.serviceEpoch, current.closeCycleId)
        return current
''',
        '''        cycles.invalidateClose(current.closeCycleId)
        frames.invalidateCycle(current.serviceEpoch, current.closeCycleId)
        primeOwner.invalidate(current)
        coverReadiness.invalidate(current.serviceEpoch, current.closeCycleId)
        return current
''',
        "kernel explicit cancel",
    )

    store = "app/src/full/java/com/duoopen/overlay/Fold7ContinuityFrameStore.kt"

    once(
        store,
        '''    private var nextCaptureSequence = 0L
    private var nextContentLeaseId = 0L
    private var latest: FrameLease<T>? = null
''',
        '''    private var nextCaptureSequence = 0L
    private var newestStartedCaptureSequence = 0L
    private var nextContentLeaseId = 0L
    private var latest: FrameLease<T>? = null
''',
        "frame store newest started field",
    )

    once(
        store,
        '''        activeCycle = cycle
        nextCaptureSequence = 0L
        latest = null
''',
        '''        activeCycle = cycle
        nextCaptureSequence = 0L
        newestStartedCaptureSequence = 0L
        latest = null
''',
        "frame store begin cycle reset",
    )

    once(
        store,
        '''        activeCycle = null
        latest = null
''',
        '''        activeCycle = null
        newestStartedCaptureSequence = 0L
        latest = null
''',
        "frame store invalidate reset",
    )

    once(
        store,
        '''        latest = null

        return CaptureTicket(
            serviceEpoch = cycle.serviceEpoch,
            closeCycleId = cycle.closeCycleId,
            captureSequence = ++nextCaptureSequence,
''',
        '''        latest = null

        val sequence =
            ++nextCaptureSequence

        newestStartedCaptureSequence =
            sequence

        return CaptureTicket(
            serviceEpoch = cycle.serviceEpoch,
            closeCycleId = cycle.closeCycleId,
            captureSequence = sequence,
''',
        "frame store capture admission",
    )

    once(
        store,
        '''            ticket.captureSequence <= 0L ||
            completedUptimeMs < ticket.requestStartedUptimeMs ||
''',
        '''            ticket.captureSequence <= 0L ||
            ticket.captureSequence != newestStartedCaptureSequence ||
            completedUptimeMs < ticket.requestStartedUptimeMs ||
''',
        "frame store newest started fence",
    )

    panel = "app/src/full/java/com/duoopen/overlay/PanelEngine.kt"

    once(
        panel,
        '''    private val continuityFrames: Fold7ContinuityFrameStore<Bitmap>,
    private val activeCloseCycle: () -> Fold7CycleEnvelope.CloseCycle?,
) {
''',
        '''    private val continuityFrames: Fold7ContinuityFrameStore<Bitmap>,
    private val continuityPrimeOwner: Fold7ContinuityPrimeOwner,
    private val activeCloseCycle: () -> Fold7CycleEnvelope.CloseCycle?,
    private val onContinuityFrameChanged: (String) -> Unit,
) {
''',
        "PanelEngine Gen3 constructor",
    )

    once(
        panel,
        '''    /** Close cycle whose capture-only continuity prime has already been issued. */
    private var primedContinuityCycleId = -1L

''',
        '',
        "remove engine-local prime guard",
    )

    between(
        panel,
        '''    fun primeContinuityFrame(
''',
        '''    /**
     * Fold7 transitions must be deterministic: once a transition frame is
''',
        '''    fun primeContinuityFrame(
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

''',
        "replace PanelEngine prime",
    )

    between(
        panel,
        '''    private fun beginContinuityCapture(
''',
        '''    /** Live blur is intentionally disabled on Fold7. */
''',
        '''    private fun beginContinuityCapture(
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

''',
        "disable generic continuity ticket minting",
    )

    coordinator = "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"

    once(
        coordinator,
        '''    val state: Fold7ContinuityController.State
        get() = controller.state

    fun arm() {
''',
        '''    val state: Fold7ContinuityController.State
        get() = controller.state

    val generation: Long
        get() = controller.generation

    fun arm() {
''',
        "expose continuity generation",
    )

    once(
        coordinator,
        '''        renderOwnershipArmed = true
        ensureMirrorSession("arm")

        val angle =
''',
        '''        renderOwnershipArmed = true

        val angle =
''',
        "do not create legacy mirror session on arm",
    )

    once(
        coordinator,
        '''        if (visualMirrorActive) {
            mirrorHost?.onHinge(angle)
        }
''',
        '',
        "stop legacy mirror hinge delivery",
    )

    once(
        coordinator,
        '''        if (visualMirrorActive) {
            syncMirrorHost(
                reason = "fast:$reason",
                generation = mirrorGeneration,
            )
        }
''',
        '',
        "stop legacy topology mirror sync",
    )

    between(
        coordinator,
        '''    private fun showMirror(
''',
        '''    private fun hideMirror(
''',
        '''    private fun showMirror(
        generation: Long,
    ) {
        if (
            !controller.isGenerationCurrent(generation) ||
            controller.state != Fold7ContinuityController.State.COVER_VISUAL
        ) {
            return
        }

        /*
         * Gen3 interprets this as VISUAL DEMAND only.
         * Fold7Gen3VisualCoordinator owns the one privileged shader host.
         */
        mirrorRequested = true
        mirrorGeneration = generation

        val currentTopology =
            topology()

        if (
            currentTopology.innerActive &&
            !currentTopology.coverActive
        ) {
            ensureCoverRouteHeld(
                "state-show"
            )
        }

        DuoDiagnostics.event(
            "gen3-visual",
            "closing visual demand generation=$generation",
        )
    }

''',
        "Gen3 visual demand only",
    )

    once(
        coordinator,
        '''        gen2.coverAuthority.onConnectionEpoch(
            ShizukuBridge.connectionEpoch
        )
        ensureMirrorSession("shizuku-ready")
        reconcileCoverLease("shizuku-ready")
''',
        '''        gen2.coverAuthority.onConnectionEpoch(
            ShizukuBridge.connectionEpoch
        )
        reconcileCoverLease("shizuku-ready")
''',
        "no legacy mirror session on reconnect",
    )

    between(
        coordinator,
        '''    fun onPrivilegedUnavailable() {
''',
        '''    private fun apply(
''',
        '''    fun onPrivilegedUnavailable() {
        val previousState =
            controller.state

        hideMirror(
            generation = controller.generation,
            reason = "privilege-unavailable",
            stopShellMirror = false,
        )

        gen2.cancelActiveCycle()

        mirrorSession = 0L
        mirrorSessionOpening = false
        mirrorSequence.set(0L)
        coverRouteReassertInFlight = false
        prewarmInFlightGeneration = -1L
        prewarmInFlightConnectionEpoch = -1L

        gen2.coverAuthority.onConnectionEpoch(
            ShizukuBridge.connectionEpoch
        )

        gen2.coverReadiness.invalidate()

        val angle =
            currentHingeAngle()
                .takeIf { it.isFinite() }
                ?: inferredRestAngle()

        val reset =
            controller.reset(
                angle = angle,
                nowMs = SystemClock.uptimeMillis(),
                topology = topology(),
            )

        DuoDiagnostics.event(
            "gen3-recovery",
            "privilege lost state=$previousState -> ${reset.state} " +
                "generation=${reset.generation} angle=$angle; " +
                "cycle/readiness/visual authority revoked",
        )
    }

''',
        "privilege epoch recovery fence",
    )

    service = "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"

    once(
        service,
        '''    private lateinit var continuity: Fold7ContinuityCoordinator

    /**
''',
        '''    private lateinit var continuity: Fold7ContinuityCoordinator
    private lateinit var gen3Visual: Fold7Gen3VisualCoordinator

    /**
''',
        "service Gen3 visual field",
    )

    once(
        service,
        '''        angleFeed = WallpaperAngleFeed(
            context = this,
            mainHandler = handler,
            controlHandler = controlHandler,
            hinge = hinge,
        )

        deviceStateObserver =
''',
        '''        angleFeed = WallpaperAngleFeed(
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
''',
        "initialize Gen3 visual coordinator",
    )

    once(
        service,
        '''                if (
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
''',
        '''                if (
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
''',
        "semantic opening uses Gen3 visual owner",
    )

    once(
        service,
        '''        if (::continuity.isInitialized) {
            setEarlyOpeningVisualLatched(
                value = false,
                reason = "service-destroy",
            )

            continuity.destroy()
        }
''',
        '''        if (::gen3Visual.isInitialized) {
            gen3Visual.destroy()
        }

        if (::continuity.isInitialized) {
            setEarlyOpeningVisualLatched(
                value = false,
                reason = "service-destroy",
            )

            continuity.destroy()
        }
''',
        "destroy Gen3 visual owner",
    )

    between(
        service,
        '''    private fun onHinge(angle: Float) {
''',
        '''    /** Starts engines for panels that lit up, stops those that went dark, then lets each re-evaluate. */
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
            gen3Visual.beginOpening(
                generation = continuity.generation,
                reason = "precise-hinge-opening-edge",
            )
        }

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

''',
        "replace service hinge path",
    )

    once(
        service,
        '''                    cache = snapshots,
                    continuityFrames = gen2.frames,
                    activeCloseCycle = { gen2.activeCycle },
                )
''',
        '''                    cache = snapshots,
                    continuityFrames = gen2.frames,
                    continuityPrimeOwner = gen2.primeOwner,
                    activeCloseCycle = { gen2.activeCycle },
                    onContinuityFrameChanged = { frameReason ->
                        reconcileContinuityCoverRendering(
                            "continuity-frame:$frameReason"
                        )
                    },
                )
''',
        "PanelEngine service constructor",
    )

    between(
        service,
        '''    private fun primeContinuityFrameIfNeeded(
''',
        '''    private fun reconcileContinuityCoverRendering(
''',
        '''    private fun primeContinuityFrameIfNeeded(
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

''',
        "service stable prime admission",
    )

    between(
        service,
        '''    private fun reconcileContinuityCoverRendering(
''',
        '''    /** Samsung continuous angle via Shizuku + fold wallpaper, when everything lines up. */
''',
        '''    private fun reconcileContinuityCoverRendering(
        reason: String,
    ) {
        if (!::continuity.isInitialized) {
            return
        }

        val privilegedReady =
            ShizukuBridge.ready &&
                continuity.renderOwnershipEnabled

        for (
            engine in
            engines.values.toList()
        ) {
            val shouldOwnCover =
                privilegedReady &&
                    engine.isFold7CoverGeometryNow()

            engine.setContinuityCoverOwned(
                owned = shouldOwnCover,
                reason = "gen3:$reason",
            )

            engine.endContinuityOpeningVisual(
                "gen3-exclusive:$reason"
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
    }

''',
        "exclusive Gen3 cover visual reconciliation",
    )

    activity = "app/src/main/java/com/duoopen/MainActivity.kt"

    once(
        activity,
        '''    private val foldLine = MutableStateFlow<FoldLine?>(null)
    private lateinit var dualScreen: DualScreen
''',
        '''    private val foldLine = MutableStateFlow<FoldLine?>(null)
''',
        "remove activity DualScreen field",
    )

    once(
        activity,
        '''        dualScreen = DualScreen(this)
        setContent {
            MaterialTheme(colorScheme = darkColorScheme()) {
                DuoApp(foldLine, dualScreen)
            }
        }
''',
        '''        setContent {
            MaterialTheme(colorScheme = darkColorScheme()) {
                DuoApp(foldLine)
            }
        }
''',
        "remove activity DualScreen session",
    )

    app = "app/src/main/java/com/duoopen/ui/DuoApp.kt"

    once(
        app,
        '''import com.duoopen.DualScreen
''',
        '',
        "remove DuoApp DualScreen import",
    )

    once(
        app,
        '''fun DuoApp(
    foldLineFlow: StateFlow<FoldLine?>,
    dualScreen: DualScreen? = null,
) {
''',
        '''fun DuoApp(
    foldLineFlow: StateFlow<FoldLine?>,
) {
''',
        "remove DuoApp dual parameter",
    )

    between(
        app,
        '''    val dualStatus by
''',
        '''    val pickImage =
''',
        '''    val pickImage =
''',
        "remove DuoApp dual flows",
    )

    once(
        app,
        '''                liveBlurSupported =
                    liveBlurSupported,
                dualStatus =
                    dualStatus,
                shizukuAvailable =
''',
        '''                liveBlurSupported =
                    liveBlurSupported,
                shizukuAvailable =
''',
        "remove dualStatus ControlSheet arg",
    )

    once(
        app,
        '''                onOpenWallpaperSettings = {
                    openWallpaperSettings(
                        context
                    )
                },
                dualActive =
                    dualActive,
                onDualChange = { on ->
                    if (on) {
                        dualScreen?.start()
                    } else {
                        dualScreen?.stop()
                    }
                },
                onEnableOverlay = {
''',
        '''                onOpenWallpaperSettings = {
                    openWallpaperSettings(
                        context
                    )
                },
                onEnableOverlay = {
''',
        "remove dual execution callback",
    )

    sheet = "app/src/main/java/com/duoopen/ui/ControlSheet.kt"

    once(
        sheet,
        '''    liveBlurSupported: Boolean,
    dualStatus: String,
    dualActive: Boolean,
    onDualChange: (Boolean) -> Unit,
    shizukuAvailable: Boolean,
''',
        '''    liveBlurSupported: Boolean,
    shizukuAvailable: Boolean,
''',
        "remove ControlSheet dual parameters",
    )

    between(
        sheet,
        '''            Section(
                "Both screens at once (experimental)",
''',
        '''            Section(
                "Hinge sensor",
''',
        '''            Section(
                "Hinge sensor",
''',
        "remove experimental dual-screen section",
    )

    dual = ROOT / "app/src/main/java/com/duoopen/DualScreen.kt"

    if dual.exists():
        dual.unlink()

    print("DUO OPEN GEN3 ALPHA1 INTEGRATION PATCH: PASS")


if __name__ == "__main__":
    main()
