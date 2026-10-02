package com.duoopen.overlay

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Rect

/** Canonical Fold7 right pane: 936x2184 -> 1080x2520, exact 3:7 scale. */
internal object Fold7RightPaneComposer {
    const val RIGHT_PANE_LEFT = 984
    const val RIGHT_PANE_RIGHT = 1920
    const val INNER_WIDTH = 1968
    const val INNER_HEIGHT = 2184
    const val COVER_WIDTH = 1080
    const val COVER_HEIGHT = 2520

    fun fromInner(source: Bitmap): Bitmap? {
        if (source.width < RIGHT_PANE_RIGHT || source.height < INNER_HEIGHT) return null

        val result = Bitmap.createBitmap(
            COVER_WIDTH,
            COVER_HEIGHT,
            Bitmap.Config.ARGB_8888,
        )
        val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
        Canvas(result).drawBitmap(
            source,
            Rect(RIGHT_PANE_LEFT, 0, RIGHT_PANE_RIGHT, INNER_HEIGHT),
            Rect(0, 0, COVER_WIDTH, COVER_HEIGHT),
            paint,
        )
        return result
    }
}
