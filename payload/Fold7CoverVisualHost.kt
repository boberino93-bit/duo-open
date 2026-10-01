package com.duoopen.overlay

import android.accessibilityservice.AccessibilityService
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Rect
import android.view.Display
import android.view.WindowManager
import com.duoopen.fold.DuoShader
import com.duoopen.fold.TiltFollower
import com.duoopen.settings.DuoSettings

/**
 * One Android cover-effect surface for one exact Gen3 visual binding.
 *
 * It never acquires content and never decides visibility. It only renders the
 * content/direction authorized by Fold7CoverVisualAttemptOwner.
 */
internal class Fold7CoverVisualHost(
    private val service: AccessibilityService,
    val display: Display,
    private val token: Fold7CoverVisualAttemptOwner.AttemptToken,
    private val direction: Fold7CoverVisualAttemptOwner.Direction,
    private val frozenFrame:
        Fold7ContinuityFrameStore.FrameLease<Bitmap>?,
    private val onFrameCommit:
        (Fold7CoverVisualAttemptOwner.AttemptToken) -> Unit,
) {
    private val displayContext =
        service.createDisplayContext(display)

    private val windowContext =
        displayContext.createWindowContext(
            WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
            null,
        )

    private val windowManager =
        windowContext.getSystemService(
            WindowManager::class.java
        )

    private var surface:
        FoldSurface? =
        null

    private var follower:
        TiltFollower? =
        null

    private var ownedCoverBitmap:
        Bitmap? =
        null

    val displayId: Int
        get() = display.displayId

    val attached: Boolean
        get() = surface != null

    fun attach(
        initialAngle: Float,
    ): Boolean {
        if (surface != null) {
            return true
        }

        val config =
            DuoSettings.config.value

        val created =
            when (direction) {
                Fold7CoverVisualAttemptOwner.Direction.CLOSING -> {
                    val source =
                        frozenFrame?.payload
                            ?: return false

                    val coverBitmap =
                        buildCanonicalRightPane(
                            source
                        ) ?: return false

                    ownedCoverBitmap =
                        coverBitmap

                    SnapshotSurface(
                        context = windowContext,
                        windowManager = windowManager,
                        bitmap = coverBitmap,
                        config = config,
                        foldLine = DuoShader::coverFold,
                    ).takeIf {
                        it.attached
                    }
                }

                Fold7CoverVisualAttemptOwner.Direction.OPENING -> {
                    if (
                        !runCatching {
                            windowManager
                                .isCrossWindowBlurEnabled
                        }.getOrDefault(false)
                    ) {
                        null
                    } else {
                        LiveBlurSurface(
                            context = windowContext,
                            windowManager = windowManager,
                            config = config,
                            pxPerMm =
                                DuoShader.pxPerMm(
                                    displayContext
                                ),
                            foldLine =
                                DuoShader::coverFold,
                        ).takeIf {
                            it.attached
                        }
                    }
                }
            }
                ?: run {
                    recycleOwnedBitmap()
                    return false
                }

        val startTilt =
            initialTilt(
                initialAngle
            )

        created.tilt =
            startTilt

        surface =
            created

        follower =
            TiltFollower { tilt ->
                surface?.tilt =
                    tilt
            }.also {
                it.snap(
                    startTilt
                )

                it.tauS =
                    if (
                        direction ==
                        Fold7CoverVisualAttemptOwner.Direction.OPENING
                    ) {
                        OPENING_TAU_S
                    } else {
                        CLOSING_TAU_S
                    }

                if (
                    direction ==
                        Fold7CoverVisualAttemptOwner.Direction.OPENING &&
                    (
                        !initialAngle.isFinite() ||
                            initialAngle <
                            PRECISE_OPENING_MIN_DEG
                        )
                ) {
                    it.setTarget(
                        peakTilt()
                    )
                }
            }

        (
            created as?
                SnapshotSurface
            )?.view
            ?.viewTreeObserver
            ?.registerFrameCommitCallback {
                onFrameCommit(
                    token
                )
            }

        return true
    }

    fun onHinge(
        angle: Float,
    ) {
        if (
            !angle.isFinite() ||
            surface == null
        ) {
            return
        }

        val target =
            when (direction) {
                Fold7CoverVisualAttemptOwner.Direction.CLOSING ->
                    DuoShader.concurrentCoverTiltForHinge(
                        angle,
                        DuoSettings.config.value,
                    )

                Fold7CoverVisualAttemptOwner.Direction.OPENING ->
                    if (
                        angle <
                        PRECISE_OPENING_MIN_DEG
                    ) {
                        peakTilt()
                    } else {
                        DuoShader.concurrentCoverTiltForHinge(
                            angle,
                            DuoSettings.config.value,
                        )
                    }
            }

        follower?.setTarget(
            target
        )
    }

    fun detach() {
        follower?.cancel()
        follower = null

        runCatching {
            surface?.detach()
        }

        surface = null

        recycleOwnedBitmap()
    }

    private fun initialTilt(
        angle: Float,
    ): Float =
        when (direction) {
            Fold7CoverVisualAttemptOwner.Direction.CLOSING ->
                if (angle.isFinite()) {
                    DuoShader.concurrentCoverTiltForHinge(
                        angle,
                        DuoSettings.config.value,
                    )
                } else {
                    DuoShader.FLAT_EPSILON *
                        1.2f
                }

            Fold7CoverVisualAttemptOwner.Direction.OPENING ->
                if (
                    angle.isFinite() &&
                    angle >=
                    PRECISE_OPENING_MIN_DEG
                ) {
                    DuoShader.concurrentCoverTiltForHinge(
                        angle,
                        DuoSettings.config.value,
                    )
                } else {
                    COVER_OPEN_IMMEDIATE_TILT
                }
        }

    private fun peakTilt(): Float =
        (
            DuoShader.MAX_TILT *
                DuoSettings.config.value
                    .intensity
                    .coerceAtMost(1f)
            )
            .coerceIn(
                0f,
                DuoShader.MAX_TILT,
            )

    private fun buildCanonicalRightPane(
        source: Bitmap,
    ): Bitmap? {
        if (
            source.width <
                RIGHT_PANE_RIGHT ||
            source.height <
                INNER_HEIGHT
        ) {
            return null
        }

        val result =
            Bitmap.createBitmap(
                COVER_WIDTH,
                COVER_HEIGHT,
                Bitmap.Config.ARGB_8888,
            )

        val paint =
            Paint(
                Paint.ANTI_ALIAS_FLAG or
                    Paint.FILTER_BITMAP_FLAG
            )

        Canvas(result)
            .drawBitmap(
                source,
                Rect(
                    RIGHT_PANE_LEFT,
                    0,
                    RIGHT_PANE_RIGHT,
                    INNER_HEIGHT,
                ),
                Rect(
                    0,
                    0,
                    COVER_WIDTH,
                    COVER_HEIGHT,
                ),
                paint,
            )

        return result
    }

    private fun recycleOwnedBitmap() {
        val bitmap =
            ownedCoverBitmap

        ownedCoverBitmap =
            null

        if (
            bitmap != null &&
            !bitmap.isRecycled
        ) {
            runCatching {
                bitmap.recycle()
            }
        }
    }

    private companion object {
        const val RIGHT_PANE_LEFT = 984
        const val RIGHT_PANE_RIGHT = 1920
        const val INNER_HEIGHT = 2184
        const val COVER_WIDTH = 1080
        const val COVER_HEIGHT = 2520

        const val COVER_OPEN_IMMEDIATE_TILT =
            0.15f

        const val PRECISE_OPENING_MIN_DEG =
            3f

        const val OPENING_TAU_S =
            0.09f

        const val CLOSING_TAU_S =
            0.028f
    }
}
