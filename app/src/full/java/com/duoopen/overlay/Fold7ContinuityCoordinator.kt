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
    private val frozenInnerFrame: () -> android.graphics.Bitmap?,
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
    @Volatile private var destroyed = false

    val visualMirrorActive: Boolean
        get() =
            mirrorRequested &&
                controller.state == Fold7ContinuityController.State.COVER_VISUAL

    val state: Fold7ContinuityController.State
        get() = controller.state

    fun arm() {
        destroyed = false
        ensureMirrorSession("arm")

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

    fun onHinge(angle: Float) {
        val decision =
            controller.onHinge(
                angle = angle,
                nowMs = SystemClock.uptimeMillis(),
                topology = topology(),
            )

        apply(decision)

        if (visualMirrorActive) {
            mirrorHost?.onHinge(angle)
        }
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

    fun onTopologyChanged(reason: String) {
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
        reconcileCoverLease("topology:$reason")

        val currentTopology =
            topology()

        if (
            (
                controller.state ==
                    Fold7ContinuityController.State.COVER_READY_HIDDEN ||
                controller.state ==
                    Fold7ContinuityController.State.COVER_VISUAL
                ) &&
            currentTopology.innerActive &&
            !currentTopology.coverActive
        ) {
            ensureCoverRouteHeld(
                "topology:$reason"
            )
        }

        if (visualMirrorActive) {
            syncMirrorHost(
                reason = "topology:$reason",
                generation = mirrorGeneration,
            )
        }
    }

    fun release(reason: String) {
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
        hideMirror(
            generation = controller.generation,
            reason = "destroy",
            stopShellMirror = true,
        )
        val coverOwner = coverLeaseOwnerGeneration
        if (ShizukuBridge.ready) {
            Thread(
                {
                    runCatching {
                        if (coverOwner >= 0L) {
                            ShizukuBridge.releaseSecondaryDisplayV2(coverOwner, "destroy")
                        } else {
                            ShizukuBridge.reconcileSecondaryDisplayLeaseV2("destroy")
                        }
                    }
                },
                "duo-cover-lease-destroy",
            ).apply { isDaemon = true }.start()
        }

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
        ensureMirrorSession("shizuku-ready")
        reconcileCoverLease("shizuku-ready")
    }

    fun onPrivilegedUnavailable() {
        mirrorSession = 0L
        mirrorSessionOpening = false
        mirrorSequence.set(0L)
        coverRouteReassertInFlight = false
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

        scope.launch(Dispatchers.IO) {
            if (!controller.isGenerationCurrent(generation)) {
                return@launch
            }

            val result =
                runCatching {
                    ShizukuBridge.wakeInnerDisplay()
                }.getOrNull()

            DuoDiagnostics.event(
                "fold7-state",
                "inner-wake generation=$generation " +
                    "ok=${result?.getBoolean("ok", false) == true} " +
                    "physical=${result?.getLong("physicalDisplayId", -1L) ?: -1L} " +
                    "error=${result?.getString("error")}",
            )
        }
    }

    private fun beginPrewarm(
        generation: Long,
    ) {
        if (!controller.isGenerationCurrent(generation)) return

        if (!ShizukuBridge.ready) {
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

        onStatus("Fold7 cover prewarming; mirror remains hidden.")

        scope.launch(Dispatchers.IO) {
            /*
             * The state may have reversed while this coroutine waited for an
             * IO thread. Never let an obsolete prewarm generation reach the
             * privileged shell and wake/reset a panel for a newer transition.
             */
            if (!controller.isGenerationCurrent(generation)) {
                DuoDiagnostics.event(
                    "fold7-state",
                    "prewarm-stale-before-shell generation=$generation " +
                        "current=${controller.generation}",
                )
                return@launch
            }

            val result =
                runCatching {
                    ShizukuBridge.prewarmSecondaryDisplayV2(generation)
                        ?: ShizukuBridge.enableSecondaryDisplay(-1)
                }.getOrNull()

            val ok =
                result?.getBoolean(
                    "ok",
                    false,
                ) == true

            val target =
                result?.getInt(
                    "targetDisplayId",
                    -1,
                ) ?: -1

            val physicalId =
                result?.getLong(
                    "physicalDisplayId",
                    -1L,
                ) ?: -1L

            val leaseOwner =
                result?.getLong(
                    "ownerGeneration",
                    -1L,
                ) ?: -1L

            if (leaseOwner >= 0L) {
                coverLeaseOwnerGeneration = leaseOwner
            }

            DuoDiagnostics.event(
                "fold7-state",
                "prewarm-complete generation=$generation ok=$ok " +
                    "logical=$target physical=$physicalId",
            )

            handler.post {
                val decision =
                    controller.onPrewarmResult(
                        requestGeneration = generation,
                        ok = ok,
                        nowMs = SystemClock.uptimeMillis(),
                        topology = topology(),
                    )

                apply(decision)
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

        syncMirrorHost(
            reason = "state-show",
            generation = generation,
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
                    frozenFrameProvider = frozenInnerFrame,
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
        scope.launch(Dispatchers.IO) {
            val result =
                runCatching {
                    ShizukuBridge.openDisplayMirrorSession()
                }.getOrNull()
            val session = result?.getLong("mirrorSession", 0L) ?: 0L

            handler.post {
                mirrorSessionOpening = false
                if (destroyed) return@post
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

    private fun updateCoverLeaseSnapshot(
        result: android.os.Bundle?,
        reason: String,
    ) {
        if (result == null) return
        val state = result.getString("leaseState")
        val owner = result.getLong("ownerGeneration", -1L)
        coverLeaseOwnerGeneration =
            if (state == "IDLE") -1L else owner

        DuoDiagnostics.event(
            "fold7-state",
            "cover-lease reason=$reason state=$state " +
                "owner=$owner lease=${result.getLong("leaseId", -1L)} " +
                "epoch=${result.getLong("leaseEpoch", -1L)} " +
                "pending=${result.getBoolean("releasePending", false)} " +
                "released=${result.getBoolean("released", false)}",
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
            controller.state !=
                Fold7ContinuityController.State.COVER_READY_HIDDEN &&
            controller.state !=
                Fold7ContinuityController.State.COVER_VISUAL
        ) {
            return
        }

        val owner =
            coverLeaseOwnerGeneration

        if (owner < 0L) {
            DuoDiagnostics.event(
                "fold7-state",
                "cover-route-reassert skipped reason=$reason owner=none",
            )
            return
        }

        val requestGeneration =
            controller.generation

        coverRouteReassertInFlight =
            true

        DuoDiagnostics.event(
            "fold7-state",
            "cover-route-reassert begin reason=$reason " +
                "generation=$requestGeneration owner=$owner",
        )

        scope.launch(
            Dispatchers.IO
        ) {
            val result =
                runCatching {
                    ShizukuBridge
                        .ensureSecondaryDisplayHeldV2(
                            ownerGeneration = owner,
                            reason = reason,
                        )
                }.getOrNull()

            handler.post {
                coverRouteReassertInFlight =
                    false

                updateCoverLeaseSnapshot(
                    result,
                    "route-reassert:$reason",
                )

                val ok =
                    result?.getBoolean(
                        "ok",
                        false,
                    ) == true

                val target =
                    result?.getInt(
                        "targetDisplayId",
                        -1,
                    ) ?: -1

                DuoDiagnostics.event(
                    "fold7-state",
                    "cover-route-reassert complete reason=$reason " +
                        "generation=$requestGeneration owner=$owner " +
                        "currentGeneration=${controller.generation} " +
                        "ok=$ok logical=$target " +
                        "routeEnabled=${result?.getBoolean("routeEnabled", false) == true} " +
                        "logicalPowered=${result?.getBoolean("logicalPowered", false) == true} " +
                        "stale=${result?.getBoolean("stale", false) == true} " +
                        "error=${result?.getString("error")}",
                )

                if (
                    !destroyed &&
                    ok &&
                    controller.isGenerationCurrent(
                        requestGeneration
                    ) &&
                    controller.state ==
                        Fold7ContinuityController.State.COVER_VISUAL
                ) {
                    handler.postDelayed(
                        {
                            if (
                                !destroyed &&
                                visualMirrorActive
                            ) {
                                syncMirrorHost(
                                    reason =
                                        "route-reassert:$reason",
                                    generation =
                                        mirrorGeneration,
                                )
                            }
                        },
                        COVER_ROUTE_REASSERT_SETTLE_MS,
                    )
                }
            }
        }
    }

    private fun releaseCoverLease(
        reason: String,
    ) {
        if (!ShizukuBridge.ready) return
        val owner = coverLeaseOwnerGeneration
        scope.launch(Dispatchers.IO) {
            val result =
                if (owner >= 0L) {
                    ShizukuBridge.releaseSecondaryDisplayV2(owner, reason)
                        ?: ShizukuBridge.resetSecondaryDisplay(-1)
                } else {
                    ShizukuBridge.reconcileSecondaryDisplayLeaseV2(reason)
                        ?: ShizukuBridge.resetSecondaryDisplay(-1)
                }
            handler.post { updateCoverLeaseSnapshot(result, reason) }
        }
    }

    private fun reconcileCoverLease(
        reason: String,
    ) {
        if (destroyed || !ShizukuBridge.ready) return
        scope.launch(Dispatchers.IO) {
            val result =
                ShizukuBridge.reconcileSecondaryDisplayLeaseV2(reason)
                    ?: ShizukuBridge.secondaryDisplayLeaseStatusV2()
            handler.post { updateCoverLeaseSnapshot(result, reason) }
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
        const val COVER_ROUTE_REASSERT_SETTLE_MS = 32L
    }
}
