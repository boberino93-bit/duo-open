package com.duoopen.overlay

import android.accessibilityservice.AccessibilityService
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.Rect
import android.hardware.display.DisplayManager
import android.os.SystemClock
import android.view.Display
import android.view.Gravity
import android.view.SurfaceControl
import android.view.View
import android.view.WindowManager
import android.widget.FrameLayout
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
class DisplayMirrorHost(
    private val service: AccessibilityService,
    val display: Display,
    private val scope: CoroutineScope,
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
    private var latestHingeAngle = Float.NaN
    private var lastHingeTimeMs = 0L
    private var hingeVelocityDegPerSec = 0f
    private var hingeDirection = "steady"
    private var lastLoggedAngleBucket = Int.MIN_VALUE
    private var lastLoggedDirection = ""

    private val hostView =
        FrameLayout(context).apply {
            setBackgroundColor(Color.TRANSPARENT)
            importantForAccessibility =
                View.IMPORTANT_FOR_ACCESSIBILITY_NO

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

        scope.launch(Dispatchers.IO) {
            val result =
                ShizukuBridge.startDisplayMirror(
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
                            "source=${source.displayId} " +
                            "destination=$displayId error=$detail",
                    )
                    return@post
                }

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

        val sourceRect =
            Rect(
                0,
                0,
                paneWidth,
                paneHeight,
            )

        val scale =
            maxOf(
                destinationWidth.toFloat() /
                    paneWidth.toFloat(),
                destinationHeight.toFloat() /
                    paneHeight.toFloat(),
            )

        val drawnWidth =
            kotlin.math.ceil(
                paneWidth * scale
            ).toInt()

        val drawnHeight =
            kotlin.math.ceil(
                paneHeight * scale
            ).toInt()

        val left =
            (destinationWidth - drawnWidth) /
                2

        val top =
            (destinationHeight - drawnHeight) /
                2

        val destinationRect =
            Rect(
                left,
                top,
                left + drawnWidth,
                top + drawnHeight,
            )

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

            val queued =
                root.applyTransactionOnDraw(transaction)

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

    private fun releaseAppMirror() {
        val current =
            appMirror
                ?: return

        appMirror = null

        runCatching {
            current.release()
        }
    }

    fun detach() {
        generation++
        mirrorSourceKey = null
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
