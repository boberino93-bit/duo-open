package com.duoopen.overlay

import android.accessibilityservice.AccessibilityService
import android.hardware.display.DisplayManager
import android.os.Handler
import android.os.SystemClock
import android.view.Display
import com.duoopen.debug.DuoDiagnostics
import com.duoopen.shell.ShizukuBridge
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import java.util.concurrent.atomic.AtomicLong

/**
 * Android/Fold7 orchestration around [Fold7ContinuityController].
 *
 * The controller owns legal state transitions. This coordinator owns side
 * effects: a one-shot cover prewarm, mirror lifecycle, and releasing the
 * temporary secondary route. Logical display ids are resolved from current
 * geometry immediately before use and are never retained as physical identity.
 */
internal class Fold7ContinuityCoordinator(
    private val service: AccessibilityService,
    private val displayManager: DisplayManager,
    private val handler: Handler,
    private val scope: CoroutineScope,
    private val currentHingeAngle: () -> Float,
    private val gen2: Fold7Gen2Kernel<android.graphics.Bitmap>,
    private val onStatus: (String) -> Unit,
) {
    private val controller =
        Fold7ContinuityController(
            onTransition = ::logTransition,
        )

    private var mirrorRequested = false
    private var mirrorGeneration = -1L
    private var mirrorHost: DisplayMirrorHost? = null

    @Volatile private var mirrorSession = 0L
    @Volatile private var mirrorSessionOpening = false
    private val mirrorSequence = AtomicLong(0L)
    private val mirrorLeaseCounter = AtomicLong(0L)

    @Volatile private var coverLeaseOwnerGeneration = -1L
    @Volatile private var coverRouteReassertInFlight = false
    @Volatile private var prewarmInFlightGeneration = -1L
    @Volatile private var prewarmInFlightConnectionEpoch = -1L
    @Volatile private var prewarmRetryGeneration = -1L
    @Volatile private var prewarmRetryCount = 0
    @Volatile private var destroyed = false
    @Volatile private var renderOwnershipArmed = false

    val renderOwnershipEnabled: Boolean
        get() = renderOwnershipArmed && !destroyed

    val visualMirrorActive: Boolean
        get() =
            mirrorRequested &&
                controller.state == Fold7ContinuityController.State.COVER_VISUAL

    val state: Fold7ContinuityController.State
        get() = controller.state

    val generation: Long
        get() = controller.generation

    fun arm() {
        gen2.cancelActiveCycle()
        destroyed = false
        renderOwnershipArmed = true

        val angle =
            currentHingeAngle()
                .takeIf { it.isFinite() }
                ?: inferredRestAngle()

        val result =
            controller.reset(
                angle = angle,
                nowMs = SystemClock.uptimeMillis(),
                topology = topology(),
            )

        onStatus("Fold7 continuity armed: ${result.state}.")

        // Clear any stale mirror left by a previous service generation. Do not
        // issue a power command here: CLOSED -> OPEN must remain purely local.
        hideMirror(
            generation = result.generation,
            reason = "arm",
            stopShellMirror = true,
        )
    }

    fun onHinge(
        angle: Float,
        observedUptimeMs: Long = SystemClock.uptimeMillis(),
    ) {
        val decision =
            controller.onHinge(
                angle = angle,
                nowMs = observedUptimeMs,
                topology = topology(),
            )

        apply(decision)

    }

    /**
     * Wake-only ingress from DeviceStateManager.
     *
     * The controller refuses this unless native cover ownership is currently
     * confirmed. No synthetic hinge value is generated.
     */
    fun onEarlyOpeningEdge(
        reason: String,
    ) {
        val decision =
            controller.onEarlyOpeningEdge(
                nowMs =
                    SystemClock.uptimeMillis(),
                topology =
                    topology(),
            )

        if (
            decision.actions.isNotEmpty()
        ) {
            DuoDiagnostics.event(
                "early-wake",
                "accepted reason=$reason generation=${decision.generation} " +
                    "precise=${currentHingeAngle()}",
            )
        } else {
            DuoDiagnostics.event(
                "early-wake",
                "ignored reason=$reason state=${controller.state} " +
                    "precise=${currentHingeAngle()}",
            )
        }

        apply(decision)
    }

    fun onTopologyFastLane(reason: String) {
        val angle =
            currentHingeAngle()
                .takeIf { it.isFinite() }
                ?: inferredRestAngle()

        val decision =
            controller.onTopology(
                angle = angle,
                nowMs = SystemClock.uptimeMillis(),
                topology = topology(),
            )

        apply(decision)
        observeCoverReadiness("fast:$reason")

        if (
            controller.state in setOf(
                Fold7ContinuityController.State.COVER_PREWARMING,
                Fold7ContinuityController.State.COVER_READY_HIDDEN,
                Fold7ContinuityController.State.COVER_VISUAL,
            ) &&
            gen2.coverReadiness.state != Fold7CoverReadiness.State.READY
        ) {
            ensureCoverRouteHeld("fast:$reason")
        }

    }

    fun onTopologyChanged(reason: String) {
        onTopologyFastLane(reason)
        reconcileCoverLease("topology:$reason")
    }

    fun release(reason: String) {
        renderOwnershipArmed = false
        gen2.cancelActiveCycle()
        val generation = controller.generation

        hideMirror(
            generation = generation,
            reason = reason,
            stopShellMirror = true,
        )

        releaseCoverLease(reason)
    }

    fun destroy() {
        destroyed = true
        renderOwnershipArmed = false
        hideMirror(
            generation = controller.generation,
            reason = "destroy",
            stopShellMirror = true,
        )
        val coverToken = gen2.coverAuthority.acceptedToken
        val coverShellSession =
            gen2.coverAuthority.acceptedSnapshot?.shellSession ?: 0L
        if (ShizukuBridge.ready) {
            Thread(
                {
                    runCatching {
                        if (coverToken != null) {
                            ShizukuBridge.releaseSecondaryDisplayV3(coverToken, "destroy")
                        } else {
                            ShizukuBridge.reconcileSecondaryDisplayLeaseV3(
                                coverShellSession,
                                "destroy",
                            )
                        }
                    }
                },
                "duo-cover-lease-destroy",
            ).apply { isDaemon = true }.start()
        }
        gen2.destroy()

        val session = mirrorSession
        if (session > 0L) {
            val sequence = mirrorSequence.incrementAndGet()
            Thread(
                {
                    runCatching {
                        ShizukuBridge.forceStopDisplayMirrorV2(
                            session = session,
                            sequence = sequence,
                        )
                    }
                },
                "duo-mirror-force-stop",
            ).apply { isDaemon = true }.start()
        }
    }

    fun onPrivilegedReady() {
        if (destroyed) return
        gen2.coverAuthority.onConnectionEpoch(
            ShizukuBridge.connectionEpoch
        )
        reconcileCoverLease("shizuku-ready")

        if (
            controller.state ==
                Fold7ContinuityController.State.COVER_PREWARMING &&
            gen2.activeCycle != null
        ) {
            beginPrewarm(controller.generation)
        }
    }

    fun onPrivilegedUnavailable() {
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

    private fun apply(
        decision: Fold7ContinuityController.Decision,
    ) {
        for (action in decision.actions) {
            when (action) {
                is Fold7ContinuityController.Action.BeginPrewarm ->
                    beginPrewarm(action.generation)

                is Fold7ContinuityController.Action.WakeInner ->
                    wakeInner(action.generation)

                is Fold7ContinuityController.Action.ShowMirror ->
                    showMirror(action.generation)

                is Fold7ContinuityController.Action.HideMirror ->
                    hideMirror(
                        generation = action.generation,
                        reason = "state-hide",
                        stopShellMirror = true,
                    )

                is Fold7ContinuityController.Action.ReleaseSecondary ->
                    releaseSecondary(action.generation)
            }
        }
    }

    private fun wakeInner(
        generation: Long,
    ) {
        if (
            !controller.isGenerationCurrent(generation) ||
            !ShizukuBridge.ready
        ) {
            return
        }

        val queuedAtNs =
            SystemClock.elapsedRealtimeNanos()

        scope.launch(Dispatchers.IO) {
            val startedAtNs =
                SystemClock.elapsedRealtimeNanos()

            if (!controller.isGenerationCurrent(generation)) {
                return@launch
            }

            val result =
                runCatching {
                    ShizukuBridge.wakeInnerDisplay()
                }.getOrNull()

            val completedAtNs =
                SystemClock.elapsedRealtimeNanos()

            val queueMs =
                (startedAtNs - queuedAtNs) /
                    1_000_000.0

            val totalMs =
                (completedAtNs - queuedAtNs) /
                    1_000_000.0

            DuoDiagnostics.event(
                "fold7-state",
                "inner-wake generation=$generation " +
                    "ok=${result?.getBoolean("ok", false) == true} " +
                    "physical=${result?.getLong("physicalDisplayId", -1L) ?: -1L} " +
                    "queueMs=${"%.3f".format(queueMs)} " +
                    "shellLatencyMs=${result?.getLong("latencyMs", -1L) ?: -1L} " +
                    "totalMs=${"%.3f".format(totalMs)} " +
                    "error=${result?.getString("error")}",
            )
        }
    }

    private fun beginPrewarm(
        generation: Long,
    ) {
        if (!controller.isGenerationCurrent(generation)) return

        val cycle = gen2.activeCycle
        if (!ShizukuBridge.ready || cycle == null) {
            val decision =
                controller.onPrewarmResult(
                    requestGeneration = generation,
                    ok = false,
                    nowMs = SystemClock.uptimeMillis(),
                    topology = topology(),
                )
            apply(decision)
            return
        }

        if (prewarmRetryGeneration != generation) {
            prewarmRetryGeneration = generation
            prewarmRetryCount = 0
        }

        val requestConnectionEpoch = ShizukuBridge.connectionEpoch
        val expectedToken = gen2.coverAuthority.acceptedToken
        if (
            prewarmInFlightGeneration == generation &&
            prewarmInFlightConnectionEpoch == requestConnectionEpoch
        ) {
            return
        }
        prewarmInFlightGeneration = generation
        prewarmInFlightConnectionEpoch = requestConnectionEpoch

        onStatus("Fold7 cover prewarming; mirror remains hidden.")

        scope.launch(Dispatchers.IO) {
            if (!controller.isGenerationCurrent(generation)) {
                DuoDiagnostics.event(
                    "fold7-state",
                    "prewarm-stale-before-shell generation=$generation " +
                        "current=${controller.generation}",
                )
                handler.post {
                    if (
                        prewarmInFlightGeneration == generation &&
                        prewarmInFlightConnectionEpoch == requestConnectionEpoch
                    ) {
                        prewarmInFlightGeneration = -1L
                        prewarmInFlightConnectionEpoch = -1L
                    }
                }
                return@launch
            }

            val result =
                runCatching {
                    ShizukuBridge.prewarmSecondaryDisplayV4(
                        ownerServiceEpoch = cycle.serviceEpoch,
                        ownerCloseCycleId = cycle.closeCycleId,
                        ownerGeneration = generation,
                        expectedToken = expectedToken,
                    )
                }.getOrNull()

            handler.post {
                if (
                    prewarmInFlightGeneration == generation &&
                    prewarmInFlightConnectionEpoch == requestConnectionEpoch
                ) {
                    prewarmInFlightGeneration = -1L
                    prewarmInFlightConnectionEpoch = -1L
                }

                if (!controller.isGenerationCurrent(generation)) {
                    return@post
                }

                val acceptance =
                    acceptCoverLeaseSnapshot(
                        result = result,
                        connectionEpoch = requestConnectionEpoch,
                        reason = "prewarm",
                    )

                val snapshot = acceptance.snapshot
                val token = acceptance.token
                val currentCycle = gen2.activeCycle

                val ownsRequestedCycle =
                    token != null &&
                        token.ownerServiceEpoch == cycle.serviceEpoch &&
                        token.ownerCloseCycleId == cycle.closeCycleId &&
                        token.ownerGeneration == generation

                if (
                    acceptance.accepted &&
                    snapshot != null &&
                    currentCycle == cycle &&
                    result?.getBoolean("stale", false) == true &&
                    !ownsRequestedCycle &&
                    token != null &&
                    prewarmRetryCount < MAX_PREWARM_CAS_RETRIES
                ) {
                    prewarmRetryCount += 1
                    DuoDiagnostics.event(
                        "fold7-state",
                        "prewarm-v4 CAS retry generation=$generation " +
                            "serviceEpoch=${cycle.serviceEpoch} closeCycle=${cycle.closeCycleId} " +
                            "retry=$prewarmRetryCount tokenOwner=${token.ownerGeneration}",
                    )
                    beginPrewarm(generation)
                    return@post
                }

                if (
                    !acceptance.accepted ||
                    snapshot == null ||
                    token == null ||
                    currentCycle == null ||
                    currentCycle != cycle ||
                    !ownsRequestedCycle ||
                    !snapshot.physicalLeaseHeld
                ) {
                    val decision =
                        controller.onPrewarmResult(
                            requestGeneration = generation,
                            ok = false,
                            nowMs = SystemClock.uptimeMillis(),
                            topology = topology(),
                        )
                    apply(decision)
                    return@post
                }

                prewarmRetryCount = 0

                val demand =
                    Fold7CoverReadiness.Demand(
                        serviceEpoch = currentCycle.serviceEpoch,
                        closeCycleId = currentCycle.closeCycleId,
                        transitionGeneration = generation,
                        leaseToken = token,
                        expectedLogicalId = snapshot.targetLogicalId,
                    )

                gen2.coverReadiness.begin(
                    demand = demand,
                    shellRouteReady = snapshot.routeReady,
                )

                observeCoverReadiness("prewarm-result")

                if (
                    controller.state ==
                        Fold7ContinuityController.State.COVER_PREWARMING &&
                    gen2.coverReadiness.state != Fold7CoverReadiness.State.READY
                ) {
                    scheduleReadinessWatchdog(currentCycle.closeCycleId)
                }
            }
        }
    }

    private fun showMirror(
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

    private fun hideMirror(
        generation: Long,
        reason: String,
        stopShellMirror: Boolean,
    ) {
        mirrorRequested = false
        mirrorGeneration = -1L

        val old = mirrorHost
        mirrorHost = null

        runCatching {
            old?.detach()
        }.onFailure { error ->
            DuoDiagnostics.event(
                "fold7-state",
                "mirror detach failed reason=$reason generation=$generation " +
                    "error=${error.javaClass.simpleName}:${error.message}",
            )
        }

        if (stopShellMirror && old == null) {
            // V2 ownership is host-scoped. A missing host has no lease to stop;
            // service/session cleanup uses FORCE_STOP explicitly.
            DuoDiagnostics.event(
                "fold7-state",
                "mirror stop skipped no-host generation=$generation reason=$reason",
            )
        }
    }

    private fun releaseSecondary(
        generation: Long,
    ) {
        /*
         * A queued release from an older close/open cycle must never reset a
         * cover route that belongs to a newer generation.
         */
        if (!controller.isGenerationCurrent(generation)) {
            DuoDiagnostics.event(
                "fold7-state",
                "secondary-release-stale generation=$generation " +
                    "current=${controller.generation}",
            )
            return
        }

        // Hiding is local and immediate. The privileged release is best effort
        // and resolves a fresh current cover route internally.
        hideMirror(
            generation = generation,
            reason = "release-secondary",
            stopShellMirror = true,
        )

        releaseCoverLease("secondary-release:generation=$generation")
    }

    private fun syncMirrorHost(
        reason: String,
        generation: Long,
    ) {
        if (
            !mirrorRequested ||
            !controller.isGenerationCurrent(generation) ||
            controller.state != Fold7ContinuityController.State.COVER_VISUAL
        ) {
            return
        }

        val session = mirrorSession
        if (session <= 0L) {
            ensureMirrorSession("mirror:$reason")
            return
        }

        val snapshot = topologySnapshot()
        val activeInner = snapshot.inner?.takeIf(::isActive)
        val activeCover = snapshot.cover?.takeIf(::isActive)

        if (activeInner == null || activeCover == null) {
            DuoDiagnostics.event(
                "fold7-state",
                "mirror wait reason=$reason generation=$generation " +
                    "inner=${snapshot.inner?.displayId}:${snapshot.inner?.state} " +
                    "cover=${snapshot.cover?.displayId}:${snapshot.cover?.state}",
            )
            return
        }

        if (activeInner.displayId == activeCover.displayId) {
            DuoDiagnostics.event(
                "fold7-state",
                "mirror wait same-logical-id reason=$reason id=${activeCover.displayId}",
            )
            return
        }

        val current = mirrorHost

        if (
            current != null &&
            current.displayId == activeCover.displayId &&
            current.isUsable
        ) {
            runCatching {
                current.refresh("stable:$reason")
            }
            return
        }

        runCatching {
            current?.detach()
        }
        mirrorHost = null

        // Samsung may invalidate/remap the Display between lookup and context
        // construction. Catch the whole constructor/attach path.
        val created =
            runCatching {
                DisplayMirrorHost(
                    service = service,
                    display = activeCover,
                    scope = scope,
                    mirrorSession = session,
                    mirrorLeaseId = mirrorLeaseCounter.incrementAndGet(),
                    nextMirrorSequence = { mirrorSequence.incrementAndGet() },
                    frozenFrameProvider = { width, height ->
                        gen2.activeCycle?.let { cycle ->
                            gen2.frames.current(
                                cycle = cycle,
                                nowUptimeMs = SystemClock.uptimeMillis(),
                                maxAgeMs = FROZEN_FRAME_MAX_AGE_MS,
                                width = width,
                                height = height,
                            )
                        }
                    },
                    currentCycle = { gen2.activeCycle },
                    onStatus = onStatus,
                )
            }.onFailure { error ->
                DuoDiagnostics.event(
                    "fold7-state",
                    "mirror host construction failed reason=$reason " +
                        "generation=$generation logical=${activeCover.displayId} " +
                        "error=${error.javaClass.simpleName}:${error.message}",
                )
            }.getOrNull()
                ?: return

        if (
            !mirrorRequested ||
            !controller.isGenerationCurrent(generation) ||
            controller.state != Fold7ContinuityController.State.COVER_VISUAL
        ) {
            runCatching { created.detach() }
            return
        }

        val attached =
            runCatching {
                val seed = currentHingeAngle()
                if (seed.isFinite()) created.onHinge(seed)
                created.attach()
                true
            }.onFailure { error ->
                DuoDiagnostics.event(
                    "fold7-state",
                    "mirror host attach failed reason=$reason " +
                        "generation=$generation logical=${activeCover.displayId} " +
                        "error=${error.javaClass.simpleName}:${error.message}",
                )
            }.getOrDefault(false)

        if (!attached) {
            runCatching { created.detach() }
            return
        }

        if (
            !mirrorRequested ||
            !controller.isGenerationCurrent(generation)
        ) {
            runCatching { created.detach() }
            return
        }

        mirrorHost = created

        DuoDiagnostics.event(
            "fold7-state",
            "mirror host created reason=$reason generation=$generation " +
                "inner=${activeInner.displayId} cover=${activeCover.displayId}",
        )
    }

    private fun ensureMirrorSession(
        reason: String,
    ) {
        if (destroyed || !ShizukuBridge.ready) return
        if (mirrorSession > 0L || mirrorSessionOpening) return

        mirrorSessionOpening = true
        val requestConnectionEpoch = ShizukuBridge.connectionEpoch
        scope.launch(Dispatchers.IO) {
            val result =
                runCatching {
                    ShizukuBridge.openDisplayMirrorSession()
                }.getOrNull()
            val session = result?.getLong("mirrorSession", 0L) ?: 0L

            handler.post {
                mirrorSessionOpening = false
                if (destroyed) return@post
                if (requestConnectionEpoch != ShizukuBridge.connectionEpoch) {
                    DuoDiagnostics.event(
                        "live-mirror",
                        "stale session-open result reason=$reason " +
                            "requestConnection=$requestConnectionEpoch " +
                            "currentConnection=${ShizukuBridge.connectionEpoch}",
                    )
                    return@post
                }
                if (session <= 0L) {
                    DuoDiagnostics.event(
                        "live-mirror",
                        "session open failed reason=$reason error=${result?.getString("error")}",
                    )
                    return@post
                }

                mirrorSession = session
                mirrorSequence.set(0L)
                DuoDiagnostics.event(
                    "live-mirror",
                    "session opened reason=$reason session=$session",
                )

                if (visualMirrorActive) {
                    syncMirrorHost(
                        reason = "session-open:$reason",
                        generation = mirrorGeneration,
                    )
                }
            }
        }
    }

    private fun acceptCoverLeaseSnapshot(
        result: android.os.Bundle?,
        connectionEpoch: Long,
        reason: String,
    ): Fold7CoverLeaseSnapshotGate.Acceptance {
        if (result == null) {
            return Fold7CoverLeaseSnapshotGate.Acceptance(
                accepted = false,
                reason = "null-result",
                token = gen2.coverAuthority.acceptedToken,
                snapshot = gen2.coverAuthority.acceptedSnapshot,
            )
        }

        val snapshot =
            Fold7CoverLeaseSnapshotGate.Snapshot(
                connectionEpoch = connectionEpoch,
                shellSession = result.getLong("shellSession", 0L),
                shellRevision = result.getLong("shellRevision", 0L),
                leaseState = result.getString("leaseState") ?: "UNKNOWN",
                leaseId = result.getLong("leaseId", -1L),
                leaseEpoch = result.getLong("leaseEpoch", -1L),
                ownerGeneration = result.getLong("ownerGeneration", -1L),
                physicalDisplayId = result.getLong("physicalDisplayId", -1L),
                ownerServiceEpoch = result.getLong("ownerServiceEpoch", 0L),
                ownerCloseCycleId = result.getLong("ownerCloseCycleId", 0L),
                targetLogicalId = result.getInt("targetDisplayId", -1),
                physicalLeaseHeld = result.getBoolean("physicalLeaseHeld", false),
                routeReady = result.getBoolean("routeReady", false),
                ok = result.getBoolean("ok", false),
            )

        val acceptance =
            gen2.coverAuthority.accept(snapshot)

        coverLeaseOwnerGeneration =
            acceptance.token?.ownerGeneration ?: -1L

        DuoDiagnostics.event(
            "fold7-state",
            "cover-lease-v3 reason=$reason accepted=${acceptance.accepted} " +
                "decision=${acceptance.reason} state=${snapshot.leaseState} " +
                "connection=${snapshot.connectionEpoch} shell=${snapshot.shellSession} " +
                "revision=${snapshot.shellRevision} lease=${snapshot.leaseId} " +
                "epoch=${snapshot.leaseEpoch} owner=${snapshot.ownerGeneration} " +
                "physical=${snapshot.physicalDisplayId} logical=${snapshot.targetLogicalId} " +
                "held=${snapshot.physicalLeaseHeld} routeReady=${snapshot.routeReady}",
        )

        if (acceptance.accepted) {
            val demand = gen2.coverReadiness.currentDemand
            val token = acceptance.token
            if (
                demand != null &&
                token != null &&
                demand.leaseToken == token
            ) {
                gen2.coverReadiness.updateShell(
                    demand = demand,
                    shellRouteReady = snapshot.routeReady,
                    expectedLogicalId = snapshot.targetLogicalId,
                )
            }
        }

        return acceptance
    }

    private fun observeCoverReadiness(
        reason: String,
    ) {
        val cycle = gen2.activeCycle ?: return
        val demand = gen2.coverReadiness.currentDemand ?: return

        val t = topology()
        val result =
            gen2.coverReadiness.observe(
                serviceEpoch = cycle.serviceEpoch,
                closeCycleId = cycle.closeCycleId,
                topology =
                    Fold7CoverReadiness.Topology(
                        innerActive = t.innerActive,
                        coverActive = t.coverActive,
                        innerIsDefault = t.innerIsDefault,
                        coverIsDefault = t.coverIsDefault,
                        coverLogicalId = t.coverLogicalId,
                    ),
            )

        DuoDiagnostics.event(
            "fold7-readiness",
            "reason=$reason state=${result.state} decision=${result.reason} " +
                "serviceEpoch=${cycle.serviceEpoch} closeCycle=${cycle.closeCycleId} " +
                "generation=${demand.transitionGeneration} expectedLogical=${demand.expectedLogicalId} " +
                "coverLogical=${t.coverLogicalId} coverActive=${t.coverActive}",
        )

        if (
            result.becameReady &&
            controller.state == Fold7ContinuityController.State.COVER_PREWARMING &&
            controller.isGenerationCurrent(demand.transitionGeneration)
        ) {
            val decision =
                controller.onPrewarmResult(
                    requestGeneration = demand.transitionGeneration,
                    ok = true,
                    nowMs = SystemClock.uptimeMillis(),
                    topology = t,
                )
            apply(decision)
        }
    }

    private fun scheduleReadinessWatchdog(
        closeCycleId: Long,
    ) {
        handler.postDelayed(
            {
                val cycle = gen2.activeCycle
                if (
                    destroyed ||
                    cycle == null ||
                    cycle.closeCycleId != closeCycleId ||
                    controller.state != Fold7ContinuityController.State.COVER_PREWARMING ||
                    gen2.coverReadiness.state == Fold7CoverReadiness.State.READY
                ) {
                    return@postDelayed
                }

                observeCoverReadiness("watchdog")
                if (gen2.coverReadiness.state != Fold7CoverReadiness.State.READY) {
                    ensureCoverRouteHeld("readiness-watchdog")
                }
            },
            READINESS_WATCHDOG_MS,
        )
    }

    private fun ensureCoverRouteHeld(
        reason: String,
    ) {
        if (
            destroyed ||
            !ShizukuBridge.ready ||
            coverRouteReassertInFlight
        ) {
            return
        }

        if (
            controller.state !in setOf(
                Fold7ContinuityController.State.COVER_PREWARMING,
                Fold7ContinuityController.State.COVER_READY_HIDDEN,
                Fold7ContinuityController.State.COVER_VISUAL,
            )
        ) {
            return
        }

        val token =
            gen2.coverAuthority.acceptedToken
                ?: run {
                    DuoDiagnostics.event(
                        "fold7-state",
                        "cover-route-reassert skipped reason=$reason token=none",
                    )
                    return
                }

        val requestGeneration = controller.generation
        val requestConnectionEpoch = ShizukuBridge.connectionEpoch
        coverRouteReassertInFlight = true

        scope.launch(Dispatchers.IO) {
            val result =
                runCatching {
                    ShizukuBridge.ensureSecondaryDisplayHeldV3(
                        token = token,
                        reason = reason,
                    )
                }.getOrNull()

            handler.post {
                coverRouteReassertInFlight = false

                if (
                    destroyed ||
                    requestConnectionEpoch != ShizukuBridge.connectionEpoch
                ) {
                    return@post
                }

                val acceptance =
                    acceptCoverLeaseSnapshot(
                        result = result,
                        connectionEpoch = requestConnectionEpoch,
                        reason = "route-reassert:$reason",
                    )

                DuoDiagnostics.event(
                    "fold7-state",
                    "cover-route-reassert complete reason=$reason " +
                        "generation=$requestGeneration currentGeneration=${controller.generation} " +
                        "accepted=${acceptance.accepted} decision=${acceptance.reason}",
                )

                if (acceptance.accepted) {
                    observeCoverReadiness("route-reassert:$reason")
                }
            }
        }
    }

    private fun releaseCoverLease(
        reason: String,
    ) {
        if (!ShizukuBridge.ready) return
        val token = gen2.coverAuthority.acceptedToken
        val shellSession =
            gen2.coverAuthority.acceptedSnapshot?.shellSession ?: 0L
        val requestConnectionEpoch = ShizukuBridge.connectionEpoch

        scope.launch(Dispatchers.IO) {
            val result =
                if (token != null) {
                    ShizukuBridge.releaseSecondaryDisplayV3(token, reason)
                } else {
                    ShizukuBridge.reconcileSecondaryDisplayLeaseV3(
                        shellSession,
                        reason,
                    )
                }

            handler.post {
                if (requestConnectionEpoch != ShizukuBridge.connectionEpoch) {
                    return@post
                }
                acceptCoverLeaseSnapshot(
                    result = result,
                    connectionEpoch = requestConnectionEpoch,
                    reason = reason,
                )
            }
        }
    }

    private fun reconcileCoverLease(
        reason: String,
    ) {
        if (destroyed || !ShizukuBridge.ready) return
        val shellSession =
            gen2.coverAuthority.acceptedSnapshot?.shellSession ?: 0L
        val requestConnectionEpoch = ShizukuBridge.connectionEpoch

        scope.launch(Dispatchers.IO) {
            val result =
                ShizukuBridge.reconcileSecondaryDisplayLeaseV3(
                    shellSession,
                    reason,
                )
                    ?: ShizukuBridge.secondaryDisplayLeaseStatusV3(shellSession)

            handler.post {
                if (requestConnectionEpoch != ShizukuBridge.connectionEpoch) {
                    return@post
                }
                val acceptance =
                    acceptCoverLeaseSnapshot(
                        result = result,
                        connectionEpoch = requestConnectionEpoch,
                        reason = reason,
                    )
                if (acceptance.accepted) {
                    observeCoverReadiness("reconcile:$reason")
                }
            }
        }
    }

    private data class DisplaySnapshot(
        val inner: Display?,
        val cover: Display?,
    )

    private fun topologySnapshot(): DisplaySnapshot {
        var inner: Display? = null
        var cover: Display? = null

        for (candidate in displayManager.displays) {
            val mode =
                runCatching { candidate.mode }
                    .getOrNull()
                    ?: continue

            when {
                mode.physicalWidth == INNER_WIDTH &&
                    mode.physicalHeight == INNER_HEIGHT ->
                    inner = candidate

                mode.physicalWidth == COVER_WIDTH &&
                    mode.physicalHeight == COVER_HEIGHT ->
                    cover = candidate
            }
        }

        return DisplaySnapshot(
            inner = inner,
            cover = cover,
        )
    }

    private fun topology(): Fold7ContinuityController.Topology {
        val snapshot = topologySnapshot()
        val inner = snapshot.inner
        val cover = snapshot.cover

        return Fold7ContinuityController.Topology(
            innerLogicalId = inner?.displayId,
            coverLogicalId = cover?.displayId,
            innerActive = inner?.let(::isActive) == true,
            coverActive = cover?.let(::isActive) == true,
            innerIsDefault = inner?.displayId == Display.DEFAULT_DISPLAY,
            coverIsDefault = cover?.displayId == Display.DEFAULT_DISPLAY,
        )
    }

    private fun isActive(display: Display): Boolean =
        display.state != Display.STATE_OFF &&
            display.state != Display.STATE_UNKNOWN

    private fun inferredRestAngle(): Float {
        val t = topology()
        return if (t.nativeCover) 0f else 180f
    }

    private fun logTransition(
        transition: Fold7ContinuityController.Transition,
    ) {
        val cycleChange =
            gen2.onTransition(
                from = transition.from,
                to = transition.to,
                nowUptimeMs = SystemClock.uptimeMillis(),
            )

        cycleChange.started?.let { cycle ->
            DuoDiagnostics.event(
                "fold7-cycle",
                "START serviceEpoch=${cycle.serviceEpoch} " +
                    "closeCycle=${cycle.closeCycleId} generation=${transition.generation}",
            )
        }
        cycleChange.ended?.let { cycle ->
            DuoDiagnostics.event(
                "fold7-cycle",
                "END serviceEpoch=${cycle.serviceEpoch} " +
                    "closeCycle=${cycle.closeCycleId} generation=${transition.generation} " +
                    "target=${transition.to}",
            )
        }

        val t = transition.topology

        DuoDiagnostics.event(
            "fold7-state",
            "STATE ${transition.from} -> ${transition.to} " +
                "generation=${transition.generation} " +
                "hinge=${transition.angle} " +
                "direction=${transition.direction} " +
                "coverLogical=${t.coverLogicalId} " +
                "innerLogical=${t.innerLogicalId} " +
                "coverActive=${t.coverActive} " +
                "innerActive=${t.innerActive} " +
                "coverDefault=${t.coverIsDefault} " +
                "innerDefault=${t.innerIsDefault} " +
                "mirrorRequested=$mirrorRequested " +
                "mirrorHost=${mirrorHost?.displayId} " +
                "reason=${transition.reason}",
        )
    }

    private companion object {
        const val INNER_WIDTH = 1968
        const val INNER_HEIGHT = 2184
        const val COVER_WIDTH = 1080
        const val COVER_HEIGHT = 2520
        const val READINESS_WATCHDOG_MS = 80L
        const val FROZEN_FRAME_MAX_AGE_MS = 10_000L
        const val MAX_PREWARM_CAS_RETRIES = 2
    }
}
