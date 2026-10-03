package com.duoopen.overlay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

class Fold7DisplayTransformTest {
    @Test
    fun portraitRightPaneIsCanonical() {
        val crop = Fold7DisplayTransform.canonicalRightPaneCrop(
            Fold7DisplayTransform.ROTATION_0,
            1968,
            2184,
        )
        assertNotNull(crop)
        assertEquals(984, crop!!.left)
        assertEquals(1920, crop.right)
        assertEquals(2184, crop.height)
    }

    @Test
    fun landscapeClockwiseMovesRightPaneToBottom() {
        val crop = Fold7DisplayTransform.canonicalRightPaneCrop(
            Fold7DisplayTransform.ROTATION_90,
            2184,
            1968,
        )!!
        assertEquals(0, crop.left)
        assertEquals(984, crop.top)
        assertEquals(2184, crop.width)
        assertEquals(1920, crop.bottom)
        assertEquals(
            Fold7DisplayTransform.Size(2520, 1080),
            Fold7DisplayTransform.coverOutputSize(1),
        )
    }

    @Test
    fun upsideDownMovesPhysicalRightPaneToLeft() {
        val crop = Fold7DisplayTransform.canonicalRightPaneCrop(
            Fold7DisplayTransform.ROTATION_180,
            1968,
            2184,
        )!!
        assertEquals(48, crop.left)
        assertEquals(984, crop.right)
    }

    @Test
    fun landscapeCounterClockwiseMovesRightPaneToTop() {
        val crop = Fold7DisplayTransform.canonicalRightPaneCrop(
            Fold7DisplayTransform.ROTATION_270,
            2184,
            1968,
        )!!
        assertEquals(48, crop.top)
        assertEquals(984, crop.bottom)
    }

    @Test
    fun scaledLiveCaptureKeepsSamePhysicalCrop() {
        val crop = Fold7DisplayTransform.canonicalRightPaneCrop(
            Fold7DisplayTransform.ROTATION_0,
            984,
            1092,
        )!!
        assertEquals(492, crop.left)
        assertEquals(960, crop.right)
    }
}
