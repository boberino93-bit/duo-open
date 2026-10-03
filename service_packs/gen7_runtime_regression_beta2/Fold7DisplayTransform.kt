package com.duoopen.overlay

import com.duoopen.fold.FoldLine
import com.duoopen.settings.DuoConfig

/**
 * Rotation-aware Fold7 physical -> display coordinate transform.
 *
 * Rotation is represented with Android's conventional integer values:
 * 0, 1, 2, 3 == ROTATION_0/90/180/270. Keeping the core arithmetic free of
 * android.view.Surface makes it deterministic in local JVM tests.
 */
internal object Fold7DisplayTransform {
    const val ROTATION_0 = 0
    const val ROTATION_90 = 1
    const val ROTATION_180 = 2
    const val ROTATION_270 = 3

    const val INNER_WIDTH = 1968
    const val INNER_HEIGHT = 2184
    const val RIGHT_PANE_LEFT = 984
    const val RIGHT_PANE_RIGHT = 1920
    const val COVER_WIDTH = 1080
    const val COVER_HEIGHT = 2520

    data class Size(
        val width: Int,
        val height: Int,
    )

    data class Crop(
        val left: Int,
        val top: Int,
        val right: Int,
        val bottom: Int,
    ) {
        val width: Int get() = right - left
        val height: Int get() = bottom - top
    }

    fun normalizeRotation(rotation: Int): Int =
        ((rotation % 4) + 4) % 4

    fun innerCaptureSize(rotation: Int): Size =
        when (normalizeRotation(rotation)) {
            ROTATION_90,
            ROTATION_270,
            -> Size(INNER_HEIGHT, INNER_WIDTH)

            else -> Size(INNER_WIDTH, INNER_HEIGHT)
        }

    fun coverOutputSize(rotation: Int): Size =
        when (normalizeRotation(rotation)) {
            ROTATION_90,
            ROTATION_270,
            -> Size(COVER_HEIGHT, COVER_WIDTH)

            else -> Size(COVER_WIDTH, COVER_HEIGHT)
        }

    /**
     * The canonical physical right pane in current display coordinates.
     *
     * The crop intentionally removes the Fold7's outer 48 px from the right
     * physical pane, preserving the hinge edge and exact 3:7 aspect ratio.
     * Scaled captures are supported because live transition captures may be
     * lower-resolution than the panel's native mode.
     */
    fun canonicalRightPaneCrop(
        rotation: Int,
        sourceWidth: Int,
        sourceHeight: Int,
    ): Crop? {
        if (sourceWidth <= 1 || sourceHeight <= 1) return null

        val r = normalizeRotation(rotation)
        val expected = innerCaptureSize(r)
        val widthRatio = sourceWidth.toFloat() / expected.width.toFloat()
        val heightRatio = sourceHeight.toFloat() / expected.height.toFloat()

        // Reject unrelated content geometries instead of manufacturing a crop.
        if (
            kotlin.math.abs(widthRatio - heightRatio) > 0.08f ||
            widthRatio <= 0f ||
            heightRatio <= 0f
        ) {
            return null
        }

        fun sx(value: Int): Int =
            (value * widthRatio).toInt().coerceIn(0, sourceWidth)

        fun sy(value: Int): Int =
            (value * heightRatio).toInt().coerceIn(0, sourceHeight)

        val crop =
            when (r) {
                ROTATION_0 ->
                    Crop(
                        left = sx(RIGHT_PANE_LEFT),
                        top = 0,
                        right = sx(RIGHT_PANE_RIGHT),
                        bottom = sourceHeight,
                    )

                // Natural (x,y) -> clockwise: (H-y, x).
                ROTATION_90 ->
                    Crop(
                        left = 0,
                        top = sy(RIGHT_PANE_LEFT),
                        right = sourceWidth,
                        bottom = sy(RIGHT_PANE_RIGHT),
                    )

                ROTATION_180 ->
                    Crop(
                        left = sx(INNER_WIDTH - RIGHT_PANE_RIGHT),
                        top = 0,
                        right = sx(INNER_WIDTH - RIGHT_PANE_LEFT),
                        bottom = sourceHeight,
                    )

                // Natural (x,y) -> counter-clockwise: (y, W-x).
                else ->
                    Crop(
                        left = 0,
                        top = sy(INNER_WIDTH - RIGHT_PANE_RIGHT),
                        right = sourceWidth,
                        bottom = sy(INNER_WIDTH - RIGHT_PANE_LEFT),
                    )
            }

        return crop.takeIf {
            it.width > 0 &&
                it.height > 0 &&
                it.right <= sourceWidth &&
                it.bottom <= sourceHeight
        }
    }

    fun foldFor(
        innerPanel: Boolean,
        rotation: Int,
        width: Float,
        height: Float,
        config: DuoConfig,
    ): FoldLine =
        if (innerPanel) {
            innerFold(
                rotation = rotation,
                width = width,
                height = height,
                config = config,
            )
        } else {
            coverFold(
                rotation = rotation,
                width = width,
                height = height,
                config = config,
            )
        }

    fun innerFold(
        rotation: Int,
        width: Float,
        height: Float,
        config: DuoConfig,
    ): FoldLine {
        val r = normalizeRotation(rotation)
        val splitsX = r == ROTATION_0 || r == ROTATION_180
        val position = if (splitsX) width * 0.5f else height * 0.5f

        val naturalMovingSide = config.movingSide
        val transformedMovingSide =
            if (
                naturalMovingSide == 0 ||
                r == ROTATION_0 ||
                r == ROTATION_90
            ) {
                naturalMovingSide
            } else {
                -naturalMovingSide
            }

        return FoldLine(
            splitsX = splitsX,
            position = position,
            eyePos = position,
            movingSide = transformedMovingSide,
        )
    }

    fun coverFold(
        rotation: Int,
        width: Float,
        height: Float,
        config: DuoConfig,
    ): FoldLine {
        val r = normalizeRotation(rotation)

        // coverFrostFromRight=true means the natural physical hinge is on the
        // cover's left edge. Rotate that physical edge into display space.
        val naturalHingeAtStart = config.coverFrostFromRight

        val splitsX =
            r == ROTATION_0 ||
                r == ROTATION_180

        val hingeAtStart =
            when (r) {
                ROTATION_0 -> naturalHingeAtStart
                ROTATION_90 -> naturalHingeAtStart
                ROTATION_180 -> !naturalHingeAtStart
                else -> !naturalHingeAtStart
            }

        val axisLength = if (splitsX) width else height
        val position = if (hingeAtStart) 0f else axisLength

        return FoldLine(
            splitsX = splitsX,
            position = position,
            eyePos = axisLength * 0.5f,
            movingSide = if (hingeAtStart) 1 else -1,
        )
    }
}
