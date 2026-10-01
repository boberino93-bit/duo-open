package com.duoopen.overlay

import android.accessibilityservice.AccessibilityService
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.Rect
import android.hardware.SyncFence
import android.hardware.display.DisplayManager
import android.os.Build
import android.os.SystemClock
import android.view.Display
import android.view.Gravity
import android.view.SurfaceControl
import android.view.View
import android.view.WindowManager
import android.widget.FrameLayout
import com.duoopen.lab.TransitionLab
import com.duoopen.shell.ShizukuBridge
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * Fold7 continuity host.
 *
 * Android's own MirrorSurfaceTest applies Transaction.setGeometry() directly
 * to the SurfaceControl returned by mirrorDisplay(). That is the operation
 * used here: sourceRect selects only the LEFT half of the 1968x2184 inner
 * display and destinationRect scales that pane to fill the 1080x2520 cover.
 *
 * No setCrop()/container-layer approximation is used in this pass.
 */
internal class DisplayMirrorHost(
    private val service: AccessibilityService,
    val display: Display,
    private val scope: CoroutineScope,
    private val mirrorSession: Long,
    private val mirrorLeaseId: Long,
    private val nextMirrorSequence: () -> Long,
    private val frozenFrameProvider: (Int, Int) -> Fold7ContinuityFrameStore.FrameLease<Bitmap>?,
    private val currentCycle: () -> Fold7CycleEnvelope.CloseCycle?,
    private val onStatus: (String) -> Unit,
) {
    val displayId: Int = display.displayId

    val isUsable: Boolean
        get() = attached && hostView.isAttachedToWindow

    private val displayManager =
        service.getSystemService(DisplayManager::class.java)

    private val context =
        service
            .createDisplayContext(display)
            .createWindowContext(
                WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                null,
            )

    private val windowManager =
        context.getSystemService(WindowManager::class.java)

    private var attached = false
    private var generation = 0
    private var mirrorSourceKey: String? = null
    private var appMirror: SurfaceControl? = null
    @Volatile private var shellStopRequested = false
    private var latestHingeAngle = Float.NaN
    private var lastHingeTimeMs = 0L
    private var hingeVelocityDegPerSec = 0f
    private var hingeDirection = "steady"
    private var lastLoggedAngleBucket = Int.MIN_VALUE
    private var lastLoggedDirection = ""

    /**
     * Snapshot path for Fold7 continuity.
     *
     * The bitmap is normally owned by SnapshotCache, so this host never
     * recycles it. The reference is dropped on detach.
     */
    private var frozenFrame: Bitmap? = null
    private var frozenFrameLease: Fold7ContinuityFrameStore.FrameLease<Bitmap>? = null
    private val presentationLease = Fold7PresentationLease()
    private val hostEpoch = presentationLease.openHost()
    private var activePresentation: Fold7PresentationLease.Identity? = null

    private val frozenPaint =
        Paint(
            Paint.ANTI_ALIAS_FLAG or
                Paint.FILTER_BITMAP_FLAG
        )

    private val frozenPaneView =
        object : View(context) {
            override fun onDraw(
                canvas: Canvas,
            ) {
                drawFrozenFrame(
                    canvas
                )

                activePresentation?.let { identity ->
                    val accepted = presentationLease.onDraw(identity)
                    recordPresentationStage(
                        type = "presentation-draw",
                        identity = identity,
                        accepted = accepted,
                    )
                }
            }
        }.apply {
            visibility =
                View.GONE
            importantForAccessibility =
                View.IMPORTANT_FOR_ACCESSIBILITY_NO
        }

    private val hostView =
        FrameLayout(context).apply {
            setBackgroundColor(Color.TRANSPARENT)
            importantForAccessibility =
                View.IMPORTANT_FOR_ACCESSIBILITY_NO

            addView(
                frozenPaneView,
                FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.MATCH_PARENT,
                    FrameLayout.LayoutParams.MATCH_PARENT,
                ),
            )

            addOnAttachStateChangeListener(
                object : View.OnAttachStateChangeListener {
                    override fun onViewAttachedToWindow(v: View) {
                        attached = true
                        v.post { bind("window-attached") }
                    }

                    override fun onViewDetachedFromWindow(v: View) {
                        attached = false
                        generation++
                        mirrorSourceKey = null
                        clearFrozenFrame()
                        releaseAppMirror()

                        com.duoopen.debug.DuoDiagnostics.event(
                            "live-mirror",
                            "geometry host detached display=$displayId " +
                                "hinge=$latestHingeAngle direction=$hingeDirection",
                        )
                    }
                }
            )

            addOnLayoutChangeListener {
                    _,
                    left,
                    top,
                    right,
                    bottom,
                    oldLeft,
                    oldTop,
                    oldRight,
                    oldBottom,
                ->
                val width = right - left
                val height = bottom - top
                val oldWidth = oldRight - oldLeft
                val oldHeight = oldBottom - oldTop

                if (
                    width > 0 &&
                    height > 0 &&
                    (width != oldWidth || height != oldHeight)
                ) {
                    post { refresh("host-layout ${width}x$height") }
                }
            }
        }

    fun attach() {
        if (isUsable) {
            refresh("already-attached")
            return
        }

        if (attached) {
            return
        }

        val params =
            WindowManager.LayoutParams(
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                    WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
                    WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS or
                    WindowManager.LayoutParams.FLAG_HARDWARE_ACCELERATED,
                PixelFormat.TRANSLUCENT,
            ).apply {
                gravity = Gravity.TOP or Gravity.START
                layoutInDisplayCutoutMode =
                    WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_ALWAYS
                fitInsetsTypes = 0
                title = "DuoOpenGeometryMirror"
            }

        attached =
            runCatching {
                windowManager.addView(hostView, params)
            }.onFailure { error ->
                onStatus(
                    "Could not attach geometry mirror window: ${error.message}"
                )

                com.duoopen.debug.DuoDiagnostics.event(
                    "live-mirror",
                    "geometry host add failed display=$displayId " +
                        "error=${error.javaClass.simpleName}:${error.message}",
                )
            }.isSuccess
    }

    fun refresh(reason: String) {
        if (!isUsable) {
            return
        }
        bind(reason)
    }

    fun onHinge(angle: Float) {
        val now = SystemClock.uptimeMillis()
        val previousAngle = latestHingeAngle
        val previousTime = lastHingeTimeMs

        if (!previousAngle.isNaN() && previousTime > 0L) {
            val elapsedSeconds =
                (now - previousTime)
                    .coerceAtLeast(1L)
                    .toFloat() /
                    1000f

            val sampleVelocity =
                (angle - previousAngle) /
                    elapsedSeconds

            hingeVelocityDegPerSec =
                hingeVelocityDegPerSec * 0.60f +
                    sampleVelocity * 0.40f

            hingeDirection =
                when {
                    kotlin.math.abs(hingeVelocityDegPerSec) < 2.0f ->
                        "steady"
                    hingeVelocityDegPerSec > 0f ->
                        "opening"
                    else ->
                        "closing"
                }
        }

        latestHingeAngle = angle
        lastHingeTimeMs = now

        val bucket = (angle / 10f).toInt()

        if (
            bucket != lastLoggedAngleBucket ||
            hingeDirection != lastLoggedDirection
        ) {
            lastLoggedAngleBucket = bucket
            lastLoggedDirection = hingeDirection

            com.duoopen.debug.DuoDiagnostics.event(
                "live-mirror",
                "hinge angle=$angle display=$displayId " +
                    "direction=$hingeDirection " +
                    "velocityDegPerSec=$hingeVelocityDegPerSec " +
                    "mirrorValid=${appMirror?.isValid == true}",
            )
        }
    }

    /**
     * Draw the same canonical left-pane crop used by setGeometry:
     * 1968x2184 inner -> left 984px pane -> crop outer edge to 936x2184,
     * which is exactly the cover's 3:7 aspect ratio.
     */
    private fun drawFrozenFrame(
        canvas: Canvas,
    ) {
        val bitmap =
            frozenFrame
                ?.takeIf {
                    !it.isRecycled
                }
                ?: return

        val destinationWidth =
            frozenPaneView.width

        val destinationHeight =
            frozenPaneView.height

        if (
            destinationWidth <= 0 ||
            destinationHeight <= 0
        ) {
            return
        }

        val paneWidth =
            (bitmap.width / 2)
                .coerceAtLeast(1)

        val paneHeight =
            bitmap.height
                .coerceAtLeast(1)

        val canonicalPaneWidth =
            (
                paneHeight.toLong() *
                    destinationWidth.toLong() /
                    destinationHeight.toLong()
                )
                .toInt()
                .coerceIn(
                    1,
                    paneWidth,
                )

        val sourceLeft =
            paneWidth -
                canonicalPaneWidth

        val sourceRect =
            Rect(
                sourceLeft,
                0,
                paneWidth,
                paneHeight,
            )

        val destinationRect =
            Rect(
                0,
                0,
                destinationWidth,
                destinationHeight,
            )

        canvas.drawBitmap(
            bitmap,
            sourceRect,
            destinationRect,
            frozenPaint,
        )
    }

    private fun clearFrozenFrame() {
        activePresentation?.let(presentationLease::invalidateAttempt)
        frozenFrame =
            null
        frozenFrameLease =
            null
        activePresentation =
            null

        frozenPaneView.visibility =
            View.GONE

        frozenPaneView.invalidate()
    }

    private fun tryBindFrozenFrame(
        sourceKey: String,
        sourceWidth: Int,
        sourceHeight: Int,
        reason: String,
    ): Boolean {
        val candidate =
            runCatching {
                frozenFrameProvider(sourceWidth, sourceHeight)
            }.getOrNull()
                ?: return false

        val candidateBitmap = candidate.payload

        if (
            candidateBitmap.isRecycled ||
            candidateBitmap.width !=
                sourceWidth ||
            candidateBitmap.height !=
                sourceHeight
        ) {
            com.duoopen.debug.DuoDiagnostics.event(
                "snapshot-transition",
                "continuity frame rejected reason=$reason " +
                    "expected=${sourceWidth}x$sourceHeight " +
                    "actual=${candidateBitmap.width}x${candidateBitmap.height} " +
                    "recycled=${candidateBitmap.isRecycled}",
            )
            return false
        }

        if (appMirror != null) {
            requestShellStop(
                "promote-frozen:$reason"
            )
            releaseAppMirror()
        }

        frozenFrame =
            candidateBitmap
        frozenFrameLease =
            candidate

        mirrorSourceKey =
            sourceKey

        frozenPaneView.visibility =
            View.VISIBLE

        val presentation =
            presentationLease.begin(
                serviceEpoch = candidate.serviceEpoch,
                closeCycleId = candidate.closeCycleId,
                contentLeaseId = candidate.contentLeaseId,
                renderPath = Fold7PresentationLease.RenderPath.FROZEN_VIEW,
            )
        activePresentation = presentation
        recordPresentationStage(
            type = "presentation-attempt",
            identity = presentation,
            accepted = true,
        )
        frozenPaneView.viewTreeObserver.registerFrameCommitCallback {
            frozenPaneView.post {
                val accepted = presentationLease.onFrameCommit(presentation)
                recordPresentationStage(
                    type = "presentation-frame-commit",
                    identity = presentation,
                    accepted = accepted,
                )
            }
        }

        frozenPaneView.invalidate()

        onStatus(
            "FROZEN LEFT PANE: inner snapshot → cover $displayId."
        )

        com.duoopen.debug.DuoDiagnostics.event(
            "snapshot-transition",
            "continuity frozen frame bound reason=$reason " +
                "source=${candidateBitmap.width}x${candidateBitmap.height} " +
                "destination=$displayId hinge=$latestHingeAngle",
        )

        return true
    }

    private fun findInnerDisplay(): Display? =
        displayManager.displays
            .firstOrNull { candidate ->
                val mode = candidate.mode
                mode.physicalWidth == INNER_WIDTH &&
                    mode.physicalHeight == INNER_HEIGHT
            }

    private fun bind(reason: String) {
        val root = hostView.rootSurfaceControl

        if (root == null) {
            onStatus(
                "Geometry mirror window is attached, but its root SurfaceControl is not ready."
            )
            return
        }

        val source = findInnerDisplay()

        if (source == null) {
            onStatus("Waiting for the Fold7 inner display.")

            com.duoopen.debug.DuoDiagnostics.event(
                "live-mirror",
                "inner source missing reason=$reason " +
                    "destination=$displayId hinge=$latestHingeAngle " +
                    "direction=$hingeDirection",
            )
            return
        }

        if (source.displayId == displayId) {
            onStatus(
                "Mirror source and cover destination resolved to the same logical display; refusing to bind."
            )

            com.duoopen.debug.DuoDiagnostics.event(
                "live-mirror",
                "same-display guard source=${source.displayId} " +
                    "destination=$displayId reason=$reason",
            )
            return
        }

        val sourceMode = source.mode
        val sourceWidth = sourceMode.physicalWidth
        val sourceHeight = sourceMode.physicalHeight

        val sourceKey =
            "inner=${source.displayId}:${sourceWidth}x$sourceHeight;" +
                "cover=$displayId"

        val existingFrozen =
            frozenFrame

        if (
            mirrorSourceKey ==
                sourceKey &&
            existingFrozen != null &&
            !existingFrozen.isRecycled
        ) {
            frozenPaneView.invalidate()
            return
        }

        if (
            frozenFrame != null &&
            mirrorSourceKey !=
                sourceKey
        ) {
            clearFrozenFrame()
        }

        /*
         * Deterministic Fold7 path. The snapshot was captured by PanelEngine
         * near the start of hinge travel, before Samsung can continue mutating
         * the live inner composition underneath a stationary fold.
         *
         * If no fresh snapshot exists, retain the old live mirror path as a
         * compatibility fallback (secure-content/capture failure).
         */
        if (
            tryBindFrozenFrame(
                sourceKey = sourceKey,
                sourceWidth = sourceWidth,
                sourceHeight = sourceHeight,
                reason = reason,
            )
        ) {
            return
        }

        com.duoopen.debug.DuoDiagnostics.event(
            "snapshot-transition",
            "continuity frozen frame unavailable; " +
                "falling back to live mirror reason=$reason",
        )

        val current = appMirror

        if (
            mirrorSourceKey == sourceKey &&
            current != null &&
            current.isValid
        ) {
            applyGeometry(
                mirror = current,
                sourceWidth = sourceWidth,
                sourceHeight = sourceHeight,
                reason = "reuse:$reason",
                initialReparent = false,
            )
            return
        }

        val localGeneration = ++generation
        mirrorSourceKey = null

        onStatus(
            "Creating AOSP geometry mirror: " +
                "inner ${source.displayId} " +
                "${sourceWidth}×$sourceHeight → " +
                "cover $displayId…"
        )

        val mirrorSequence = nextMirrorSequence()
        scope.launch(Dispatchers.IO) {
            val result =
                ShizukuBridge.startDisplayMirrorV2(
                    session = mirrorSession,
                    sequence = mirrorSequence,
                    leaseId = mirrorLeaseId,
                    sourceDisplayId = source.displayId,
                )

            val ok =
                result?.getBoolean("ok", false) == true

            val error =
                result?.getString("error")

            val mirror =
                if (ok) {
                    result?.getParcelable(
                        "mirrorSurface",
                        SurfaceControl::class.java,
                    )
                } else {
                    null
                }

            hostView.post {
                if (localGeneration != generation) {
                    mirror?.release()
                    return@post
                }

                if (
                    !isUsable ||
                    !ok ||
                    mirror == null ||
                    !mirror.isValid
                ) {
                    mirror?.release()
                    mirrorSourceKey = null

                    val detail =
                        error
                            ?: "shell returned no valid mirror SurfaceControl"

                    onStatus("Geometry mirror failed: $detail")

                    com.duoopen.debug.DuoDiagnostics.event(
                        "live-mirror",
                        "geometry bind failed reason=$reason " +
                            "session=$mirrorSession lease=$mirrorLeaseId " +
                            "source=${source.displayId} " +
                            "destination=$displayId error=$detail",
                    )
                    return@post
                }

                clearFrozenFrame()
                releaseAppMirror()
                appMirror = mirror
                mirrorSourceKey = sourceKey

                val applied =
                    applyGeometry(
                        mirror = mirror,
                        sourceWidth = sourceWidth,
                        sourceHeight = sourceHeight,
                        reason = "new:$reason",
                        initialReparent = true,
                    )

                if (!applied) {
                    releaseAppMirror()
                    mirrorSourceKey = null
                    requestShellStop("geometry-apply-failed")
                    return@post
                }

                onStatus(
                    "LEFT PANE GEOMETRY LIVE: inner ${source.displayId} → cover $displayId."
                )
            }
        }
    }

    private fun applyGeometry(
        mirror: SurfaceControl,
        sourceWidth: Int,
        sourceHeight: Int,
        reason: String,
        initialReparent: Boolean,
    ): Boolean {
        val root =
            hostView.rootSurfaceControl
                ?: return false

        val destinationMode = display.mode

        val destinationWidth =
            hostView.width
                .takeIf { it > 0 }
                ?: destinationMode.physicalWidth

        val destinationHeight =
            hostView.height
                .takeIf { it > 0 }
                ?: destinationMode.physicalHeight

        if (
            destinationWidth <= 0 ||
            destinationHeight <= 0
        ) {
            onStatus("Waiting for non-zero cover bounds.")
            return false
        }

        val paneWidth =
            (sourceWidth / 2)
                .coerceAtLeast(1)

        val paneHeight = sourceHeight

        /*
         * Canonical projection: preserve the hinge edge and crop only the
         * outer edge of the left inner pane so source and cover have exactly
         * the same aspect ratio. On Fold7 this is 936x2184 -> 1080x2520,
         * both exactly 3:7. No destination overscan or non-uniform stretch.
         */
        val canonicalPaneWidth =
            (
                paneHeight.toLong() *
                    destinationWidth.toLong() /
                    destinationHeight.toLong()
                ).toInt()
                .coerceIn(1, paneWidth)

        val sourceLeft =
            paneWidth - canonicalPaneWidth

        val sourceRect =
            Rect(
                sourceLeft,
                0,
                paneWidth,
                paneHeight,
            )

        val destinationRect =
            Rect(
                0,
                0,
                destinationWidth,
                destinationHeight,
            )

        val scale =
            destinationHeight.toFloat() /
                paneHeight.toFloat()

        val transaction =
            if (initialReparent) {
                root.buildReparentTransaction(mirror)
            } else {
                SurfaceControl.Transaction()
            }

        if (transaction == null) {
            onStatus(
                "Android could not create the geometry transaction."
            )
            return false
        }

        return try {
            runCatching {
                org.lsposed.hiddenapibypass.HiddenApiBypass
                    .addHiddenApiExemptions(
                        "Landroid/view/SurfaceControl\$Transaction;"
                    )
            }

            val setGeometry =
                transaction.javaClass
                    .getDeclaredMethod(
                        "setGeometry",
                        SurfaceControl::class.java,
                        Rect::class.java,
                        Rect::class.java,
                        java.lang.Integer.TYPE,
                    )
                    .apply {
                        isAccessible = true
                    }

            setGeometry.invoke(
                transaction,
                mirror,
                sourceRect,
                destinationRect,
                0,
            )

            transaction
                .setLayer(mirror, 10_000)
                .setAlpha(mirror, 1f)
                .setVisibility(mirror, true)

            val presentation =
                currentCycle()?.let { cycle ->
                    presentationLease.begin(
                        serviceEpoch = cycle.serviceEpoch,
                        closeCycleId = cycle.closeCycleId,
                        contentLeaseId = mirrorLeaseId,
                        renderPath = Fold7PresentationLease.RenderPath.LIVE_MIRROR,
                    )
                }

            if (presentation != null) {
                activePresentation = presentation
                recordPresentationStage(
                    type = "presentation-attempt",
                    identity = presentation,
                    accepted = true,
                )

                if (Build.VERSION.SDK_INT >= 33) {
                    transaction.addTransactionCommittedListener(
                        service.mainExecutor,
                    ) {
                        hostView.post {
                            val accepted =
                                presentationLease.onTransactionCommit(presentation)
                            recordPresentationStage(
                                type = "presentation-transaction-commit",
                                identity = presentation,
                                accepted = accepted,
                            )
                        }
                    }
                }

                if (Build.VERSION.SDK_INT >= 35) {
                    transaction.addTransactionCompletedListener(
                        service.mainExecutor,
                    ) { stats ->
                        val fence = stats.presentFence
                        var presented = false
                        try {
                            if (fence.isValid) {
                                val signal = fence.signalTime
                                presented =
                                    signal != SyncFence.SIGNAL_TIME_INVALID &&
                                        signal != SyncFence.SIGNAL_TIME_PENDING
                            }
                        } finally {
                            fence.close()
                        }

                        hostView.post {
                            val accepted =
                                if (presented) {
                                    presentationLease.onPresented(presentation)
                                } else {
                                    presentationLease.isCurrent(presentation)
                                }
                            recordPresentationStage(
                                type = if (presented) {
                                    "presentation-presented"
                                } else {
                                    "presentation-completed-no-present-fence"
                                },
                                identity = presentation,
                                accepted = accepted,
                            )
                        }
                    }
                }
            }

            val labToken =
                TransitionLab
                    .instrumentTransaction(
                        transaction
                    )

            val queued =
                root.applyTransactionOnDraw(transaction)

            TransitionLab
                .markTransactionSubmitted(
                    token =
                        labToken,
                    accepted =
                        queued,
                )

            hostView.invalidate()

            com.duoopen.debug.DuoDiagnostics.event(
                "live-mirror",
                "setGeometry ok reason=$reason " +
                    "sourceDisplay=${sourceWidth}x$sourceHeight " +
                    "sourceRect=${sourceRect.left},${sourceRect.top}," +
                    "${sourceRect.right},${sourceRect.bottom} " +
                    "destination=${destinationWidth}x$destinationHeight " +
                    "destRect=${destinationRect.left},${destinationRect.top}," +
                    "${destinationRect.right},${destinationRect.bottom} " +
                    "scale=$scale queuedOnDraw=$queued " +
                    "hinge=$latestHingeAngle direction=$hingeDirection " +
                    "velocityDegPerSec=$hingeVelocityDegPerSec",
            )

            true
        } catch (t: Throwable) {
            runCatching {
                transaction.close()
            }

            val detail =
                "${t.javaClass.simpleName}: ${t.message}"

            onStatus("setGeometry failed: $detail")

            com.duoopen.debug.DuoDiagnostics.event(
                "live-mirror",
                "setGeometry exception reason=$reason error=$detail",
            )

            false
        }
    }

    private fun recordPresentationStage(
        type: String,
        identity: Fold7PresentationLease.Identity,
        accepted: Boolean,
    ) {
        TransitionLab.recordIngressStage(
            type = type,
            serviceEpoch = identity.serviceEpoch,
            closeCycleId = identity.closeCycleId,
            contentLeaseId = identity.contentLeaseId,
            hostEpoch = identity.hostEpoch,
            presentationAttemptSequence = identity.attemptSequence,
            renderPath = identity.renderPath.name,
            staleAtCallback = !accepted,
            rejectionReason = if (accepted) null else "stale-presentation-attempt",
        )

        com.duoopen.debug.DuoDiagnostics.event(
            "presentation",
            "$type accepted=$accepted " +
                "serviceEpoch=${identity.serviceEpoch} closeCycle=${identity.closeCycleId} " +
                "content=${identity.contentLeaseId} host=${identity.hostEpoch} " +
                "attempt=${identity.attemptSequence} path=${identity.renderPath}",
        )
    }

    private fun releaseAppMirror() {
        val current =
            appMirror
                ?: return

        appMirror = null

        runCatching {
            current.release()
        }
    }

    private fun requestShellStop(
        reason: String,
    ) {
        if (shellStopRequested) return
        shellStopRequested = true

        val sequence = nextMirrorSequence()
        scope.launch(Dispatchers.IO) {
            val result =
                runCatching {
                    ShizukuBridge.stopDisplayMirrorV2(
                        session = mirrorSession,
                        sequence = sequence,
                        leaseId = mirrorLeaseId,
                    )
                }.getOrNull()

            com.duoopen.debug.DuoDiagnostics.event(
                "live-mirror",
                "lease stop reason=$reason session=$mirrorSession " +
                    "sequence=$sequence lease=$mirrorLeaseId " +
                    "decision=${result?.getString("decision")}",
            )
        }
    }

    fun detach() {
        presentationLease.invalidateHost(hostEpoch)
        activePresentation = null
        requestShellStop("host-detach")
        generation++
        mirrorSourceKey = null
        clearFrozenFrame()
        releaseAppMirror()

        if (!attached) {
            return
        }

        attached = false

        runCatching {
            windowManager.removeViewImmediate(hostView)
        }

        com.duoopen.debug.DuoDiagnostics.event(
            "live-mirror",
            "geometry host removed display=$displayId " +
                "hinge=$latestHingeAngle direction=$hingeDirection",
        )
    }

    private companion object {
        const val INNER_WIDTH = 1968
        const val INNER_HEIGHT = 2184
    }
}
