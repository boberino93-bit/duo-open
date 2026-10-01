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
    private val onStatus: (String) -> Unit,
) {
    private val controller =
        Fold7ContinuityController(
            onTransition = ::logTransition,
        )

    private var mirrorRequested = false
    private var mirrorGeneration = -1L
    private var mirrorHost: DisplayMirrorHost? = null

    val visualMirrorActive: Boolean
        get() =
            mirrorRequested &&
                controller.state == Fold7ContinuityController.State.COVER_VISUAL

    val state: Fold7ContinuityController.State
        get() = controller.state

    fun arm() {
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

        scope.launch(Dispatchers.IO) {
            val result =
                runCatching {
                    ShizukuBridge.resetSecondaryDisplay(-1)
                }.getOrNull()

            DuoDiagnostics.event(
                "fold7-state",
                "release reason=$reason ok=${result?.getBoolean("ok", false) == true} " +
                    "target=${result?.getInt("targetDisplayId", -1) ?: -1}",
            )
        }
    }

    fun destroy() {
        hideMirror(
            generation = controller.generation,
            reason = "destroy",
            stopShellMirror = true,
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
                    // -1 means: resolve the current inactive 1080x2520 Fold7
                    // route inside the privileged service immediately before
                    // the one-shot operation. Never reuse a prior logical id.
                    ShizukuBridge.enableSecondaryDisplay(-1)
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

        if (stopShellMirror) {
            scope.launch(Dispatchers.IO) {
                /*
                 * Shell mirror ownership is global inside DuoShellService.
                 * Do not let an obsolete hide race with a newer ShowMirror.
                 * The local host has already been detached synchronously.
                 */
                if (!controller.isGenerationCurrent(generation)) {
                    DuoDiagnostics.event(
                        "fold7-state",
                        "mirror-stop-stale generation=$generation " +
                            "current=${controller.generation} reason=$reason",
                    )
                    return@launch
                }

                runCatching {
                    ShizukuBridge.stopDisplayMirror()
                }
            }
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

        scope.launch(Dispatchers.IO) {
            if (!controller.isGenerationCurrent(generation)) {
                DuoDiagnostics.event(
                    "fold7-state",
                    "secondary-release-stale-before-shell generation=$generation " +
                        "current=${controller.generation}",
                )
                return@launch
            }

            val result =
                runCatching {
                    ShizukuBridge.resetSecondaryDisplay(-1)
                }.getOrNull()

            DuoDiagnostics.event(
                "fold7-state",
                "secondary-release generation=$generation " +
                    "ok=${result?.getBoolean("ok", false) == true} " +
                    "target=${result?.getInt("targetDisplayId", -1) ?: -1}",
            )
        }
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
    }
}
