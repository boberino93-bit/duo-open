package com.duoopen.overlay

import android.accessibilityservice.AccessibilityService
import android.graphics.Bitmap
import android.hardware.display.DisplayManager
import android.os.Handler
import android.os.SystemClock
import android.view.Display
import com.duoopen.debug.DuoDiagnostics
import com.duoopen.lab.TransitionLab

/**
 * Gen3 Fold7 privileged cover visual composition.
 *
 * The existing continuity coordinator owns transition policy and privileged
 * cover-route authority. This coordinator owns only the exact visual attempt:
 * movement, content binding, cover-host binding and renderer lifetime.
 */
internal class Fold7Gen3VisualCoordinator(
    private val service: AccessibilityService,
    private val displayManager: DisplayManager,
    private val handler: Handler,
    private val serviceEpoch: Long,
    private val gen2: Fold7Gen2Kernel<Bitmap>,
    private val currentHingeAngle: () -> Float,
) {
    private val owner =
        Fold7CoverVisualAttemptOwner()

    private var currentMovement:
        Fold7CoverVisualAttemptOwner.Movement? =
        null

    private var currentHost:
        Fold7CoverVisualHost? =
        null

    private var currentHostToken:
        Fold7CoverVisualAttemptOwner.AttemptToken? =
        null

    private var hostEpoch =
        0L

    private var openingSequence =
        0L

    private var lastAttachFailureUptimeMs =
        0L

    /**
     * Alpha2: exact Gen3 ownership remains authoritative while the physical
     * Fold7 opening renderer is delegated to the proven PanelEngine
     * snapshot/shader backend.
     */
    val openingVisualDemandActive: Boolean
        get() =
            currentMovement?.direction ==
                Fold7CoverVisualAttemptOwner.Direction.OPENING &&
                owner.snapshot().visibleDemand

    val openingHostDisplayId: Int?
        get() =
            owner.snapshot()
                .host
                ?.logicalDisplayId

    fun beginOpening(
        generation: Long,
        reason: String,
    ) {
        val existing =
            currentMovement

        if (
            existing != null &&
            existing.direction ==
                Fold7CoverVisualAttemptOwner.Direction.OPENING
        ) {
            return
        }

        endCurrent(
            "replace-with-opening:$reason"
        )

        val movement =
            Fold7CoverVisualAttemptOwner.Movement(
                serviceEpoch = serviceEpoch,
                movementId = -(++openingSequence),
                generation = generation,
                direction =
                    Fold7CoverVisualAttemptOwner.Direction.OPENING,
            )

        currentMovement =
            movement

        owner.begin(
            movement
        )

        owner.bindContent(
            movement,
            Fold7CoverVisualAttemptOwner.Content(
                kind =
                    Fold7CoverVisualAttemptOwner.ContentKind.LIVE_COVER,
                contentLeaseId =
                    movement.movementId,
                captureSequence =
                    0L,
            ),
        )

        owner.setVisible(
            movement,
            true,
        )

        recordStage(
            type =
                "gen3-opening-visual-demand",
            movement =
                movement,
            reason =
                reason,
        )

        handler.postDelayed(
            {
                if (
                    currentMovement ==
                    movement
                ) {
                    endCurrent(
                        "opening-safety-timeout"
                    )
                }
            },
            OPENING_VISUAL_MAX_MS,
        )
    }

    fun reconcile(
        state: Fold7ContinuityController.State,
        closingVisible: Boolean,
        privilegedReady: Boolean,
        reason: String,
    ) {
        if (!privilegedReady) {
            endCurrent(
                "privilege-or-ownership-lost:$reason"
            )
            return
        }

        val existing =
            currentMovement

        if (
            existing != null &&
            existing.direction ==
                Fold7CoverVisualAttemptOwner.Direction.OPENING
        ) {
            if (
                state !in
                OPENING_STATES
            ) {
                endCurrent(
                    "opening-state-ended:$reason"
                )
                return
            }

            owner.setVisible(
                existing,
                true,
            )

            bindCurrentCoverHost(
                existing,
                reason,
            )

            /*
             * Alpha1 used LiveBlurSurface here. Fold7 field evidence shows
             * that backend failing attachment on accepted opening attempts,
             * while the last validated Fold7 implementation explicitly
             * disabled live blur and used the snapshot/fold shader path.
             *
             * Keep exact attempt/host ownership here, but let
             * FoldOverlayService bind this exact host to the current
             * PanelEngine snapshot renderer. This also lets a replacement
             * cover engine rebind the same semantic attempt after remap.
             */
            detachRenderer(
                "opening-snapshot-backend:$reason"
            )

            recordStage(
                type =
                    "gen3-opening-render-delegated",
                movement =
                    existing,
                hostEpoch =
                    owner.snapshot()
                        .host
                        ?.hostEpoch,
                reason =
                    reason,
            )
            return
        }

        val cycle =
            gen2.activeCycle

        val closingState =
            cycle != null &&
                state in
                CLOSING_STATES

        if (!closingState) {
            if (
                existing?.direction ==
                Fold7CoverVisualAttemptOwner.Direction.CLOSING
            ) {
                endCurrent(
                    "closing-state-ended:$reason"
                )
            }
            return
        }

        val movement =
            (
                existing
                    ?.takeIf {
                        it.direction ==
                            Fold7CoverVisualAttemptOwner.Direction.CLOSING &&
                            it.movementId ==
                            cycle!!.closeCycleId &&
                            it.serviceEpoch ==
                            cycle.serviceEpoch
                    }
                )
                ?: run {
                    endCurrent(
                        "new-close-cycle:$reason"
                    )

                    Fold7CoverVisualAttemptOwner.Movement(
                        serviceEpoch =
                            cycle!!.serviceEpoch,
                        movementId =
                            cycle.closeCycleId,
                        generation =
                            cycle.closeCycleId,
                        direction =
                            Fold7CoverVisualAttemptOwner.Direction.CLOSING,
                    ).also {
                        currentMovement =
                            it
                        owner.begin(
                            it
                        )
                    }
                }

        val frame =
            gen2.frames.current(
                cycle =
                    cycle!!,
                nowUptimeMs =
                    SystemClock.uptimeMillis(),
                maxAgeMs =
                    FROZEN_FRAME_MAX_AGE_MS,
                width =
                    INNER_WIDTH,
                height =
                    INNER_HEIGHT,
            )

        if (frame != null) {
            owner.bindContent(
                movement,
                Fold7CoverVisualAttemptOwner.Content(
                    kind =
                        Fold7CoverVisualAttemptOwner.ContentKind.FROZEN_RIGHT_PANE,
                    contentLeaseId =
                        frame.contentLeaseId,
                    captureSequence =
                        frame.captureSequence,
                ),
            )
        }

        owner.setVisible(
            movement,
            closingVisible &&
                state ==
                Fold7ContinuityController.State.COVER_VISUAL,
        )

        bindCurrentCoverHost(
            movement,
            reason,
        )

        if (
            owner.snapshot()
                .visibleDemand
        ) {
            ensureRenderer(
                movement,
                frame,
                reason,
            )
        } else {
            detachRenderer(
                "ready-hidden:$reason"
            )
        }
    }

    fun onHinge(
        angle: Float,
    ) {
        currentHost
            ?.onHinge(
                angle
            )
    }

    fun destroy() {
        endCurrent(
            "service-destroy"
        )
    }

    private fun bindCurrentCoverHost(
        movement: Fold7CoverVisualAttemptOwner.Movement,
        reason: String,
    ) {
        val display =
            currentCoverDisplay()

        if (display == null) {
            val oldEpoch =
                owner.snapshot()
                    .host
                    ?.hostEpoch

            if (oldEpoch != null) {
                owner.hostLost(
                    oldEpoch
                )
            }

            detachRenderer(
                "cover-route-missing:$reason"
            )
            return
        }

        val existingHost =
            owner.snapshot()
                .host

        if (
            existingHost != null &&
            existingHost.logicalDisplayId ==
                display.displayId
        ) {
            return
        }

        if (existingHost != null) {
            owner.hostLost(
                existingHost.hostEpoch
            )
        }

        detachRenderer(
            "cover-host-remap:$reason"
        )

        owner.bindHost(
            movement,
            Fold7CoverVisualAttemptOwner.Host(
                hostEpoch =
                    ++hostEpoch,
                logicalDisplayId =
                    display.displayId,
            ),
        )

        recordStage(
            type =
                "gen3-cover-host-bound",
            movement =
                movement,
            hostEpoch =
                hostEpoch,
            reason =
                "$reason display=${display.displayId}",
        )
    }

    private fun ensureRenderer(
        movement: Fold7CoverVisualAttemptOwner.Movement,
        frame: Fold7ContinuityFrameStore.FrameLease<Bitmap>?,
        reason: String,
    ) {
        val activeToken =
            currentHostToken

        if (
            currentHost != null &&
            activeToken != null &&
            owner.isCurrent(
                activeToken
            )
        ) {
            return
        }

        detachRenderer(
            "replace-renderer:$reason"
        )

        if (
            SystemClock.uptimeMillis() -
            lastAttachFailureUptimeMs <
            ATTACH_RETRY_BACKOFF_MS
        ) {
            return
        }

        val snapshot =
            owner.snapshot()

        val hostBinding =
            snapshot.host
                ?: return

        val display =
            displayManager.getDisplay(
                hostBinding.logicalDisplayId
            ) ?: return

        val token =
            owner.reserveAttach(
                movement
            ) ?: return

        val created =
            Fold7CoverVisualHost(
                service =
                    service,
                display =
                    display,
                token =
                    token,
                direction =
                    movement.direction,
                frozenFrame =
                    frame,
                onFrameCommit = { committed ->
                    if (
                        owner.isCurrent(
                            committed
                        )
                    ) {
                        recordStage(
                            type =
                                "gen3-cover-frame-commit",
                            movement =
                                committed.movement,
                            hostEpoch =
                                committed.hostEpoch,
                            attemptSequence =
                                committed.attemptSequence,
                            contentLeaseId =
                                committed.contentLeaseId,
                            reason =
                                "view-frame-commit",
                        )
                    }
                },
            )

        val attached =
            runCatching {
                created.attach(
                    currentHingeAngle()
                )
            }.getOrDefault(false)

        if (
            !attached ||
            !owner.markActive(
                token
            )
        ) {
            created.detach()
            owner.hostLost(
                token.hostEpoch
            )
            lastAttachFailureUptimeMs =
                SystemClock.uptimeMillis()

            recordStage(
                type =
                    "gen3-cover-render-degraded",
                movement =
                    movement,
                hostEpoch =
                    token.hostEpoch,
                attemptSequence =
                    token.attemptSequence,
                contentLeaseId =
                    token.contentLeaseId,
                reason =
                    "attach-failed:$reason",
            )
            return
        }

        currentHost =
            created

        currentHostToken =
            token

        recordStage(
            type =
                "gen3-cover-render-active",
            movement =
                movement,
            hostEpoch =
                token.hostEpoch,
            attemptSequence =
                token.attemptSequence,
            contentLeaseId =
                token.contentLeaseId,
            reason =
                reason,
        )
    }

    private fun detachRenderer(
        reason: String,
    ) {
        val old =
            currentHost

        currentHost =
            null

        currentHostToken =
            null

        runCatching {
            old?.detach()
        }.onFailure {
            DuoDiagnostics.event(
                "gen3-visual",
                "renderer detach failed reason=$reason " +
                    "error=${it.javaClass.simpleName}:${it.message}",
            )
        }
    }

    private fun endCurrent(
        reason: String,
    ) {
        val movement =
            currentMovement

        detachRenderer(
            reason
        )

        if (movement != null) {
            recordStage(
                type =
                    "gen3-visual-ended",
                movement =
                    movement,
                reason =
                    reason,
            )

            owner.end(
                movement
            )
        } else {
            owner.end()
        }

        currentMovement =
            null
    }

    private fun currentCoverDisplay(): Display? =
        displayManager.displays
            .firstOrNull { display ->
                if (
                    display.state ==
                    Display.STATE_OFF
                ) {
                    return@firstOrNull false
                }

                val mode =
                    runCatching {
                        display.mode
                    }.getOrNull()
                        ?: return@firstOrNull false

                mode.physicalWidth ==
                    COVER_WIDTH &&
                    mode.physicalHeight ==
                    COVER_HEIGHT
            }

    private fun recordStage(
        type: String,
        movement: Fold7CoverVisualAttemptOwner.Movement,
        hostEpoch: Long? = null,
        attemptSequence: Long? = null,
        contentLeaseId: Long? = null,
        reason: String,
    ) {
        TransitionLab.recordIngressStage(
            type = type,
            serviceEpoch =
                movement.serviceEpoch,
            closeCycleId =
                movement.movementId
                    .takeIf {
                        movement.direction ==
                            Fold7CoverVisualAttemptOwner.Direction.CLOSING
                    },
            hostEpoch =
                hostEpoch,
            presentationAttemptSequence =
                attemptSequence,
            contentLeaseId =
                contentLeaseId,
            renderPath =
                when (
                    movement.direction
                ) {
                    Fold7CoverVisualAttemptOwner.Direction.CLOSING ->
                        "GEN3_FROZEN_SHADER"

                    Fold7CoverVisualAttemptOwner.Direction.OPENING ->
                        "GEN3_OPENING_SNAPSHOT_SHADER"
                },
            reason =
                reason,
        )

        DuoDiagnostics.event(
            "gen3-visual",
            "$type movement=${movement.movementId} " +
                "direction=${movement.direction} " +
                "host=$hostEpoch attempt=$attemptSequence " +
                "content=$contentLeaseId reason=$reason",
        )
    }

    private companion object {
        const val INNER_WIDTH = 1968
        const val INNER_HEIGHT = 2184
        const val COVER_WIDTH = 1080
        const val COVER_HEIGHT = 2520

        const val FROZEN_FRAME_MAX_AGE_MS =
            10_000L

        const val OPENING_VISUAL_MAX_MS =
            2_500L

        const val ATTACH_RETRY_BACKOFF_MS =
            120L

        private val OPENING_STATES =
            setOf(
                Fold7ContinuityController.State.OPENING_FROM_CLOSED,
                Fold7ContinuityController.State.INNER_HANDOFF,
            )

        private val CLOSING_STATES =
            setOf(
                Fold7ContinuityController.State.CLOSING_INTENT,
                Fold7ContinuityController.State.COVER_PREWARMING,
                Fold7ContinuityController.State.COVER_READY_HIDDEN,
                Fold7ContinuityController.State.COVER_VISUAL,
            )
    }
}
