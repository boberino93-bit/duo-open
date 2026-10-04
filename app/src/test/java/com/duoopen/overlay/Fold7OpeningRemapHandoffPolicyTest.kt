package com.duoopen.overlay

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7OpeningRemapHandoffPolicyTest {
    @Test
    fun transfersAcceptedOpeningWhenLogicalDisplayMorphsCoverToInner() {
        assertTrue(
            Fold7OpeningRemapHandoffPolicy.shouldTransferToInner(
                openingVisualActive = true,
                previousCoverOwned = true,
                coverGeometryNow = false,
                innerGeometryNow = true,
                privilegedCaptureReady = true,
            )
        )
    }

    @Test
    fun doesNotTransferWhileStillOnCoverGeometry() {
        assertFalse(
            Fold7OpeningRemapHandoffPolicy.shouldTransferToInner(
                openingVisualActive = true,
                previousCoverOwned = true,
                coverGeometryNow = true,
                innerGeometryNow = false,
                privilegedCaptureReady = true,
            )
        )
    }

    @Test
    fun doesNotTransferWithoutAnActiveAcceptedOpening() {
        assertFalse(
            Fold7OpeningRemapHandoffPolicy.shouldTransferToInner(
                openingVisualActive = false,
                previousCoverOwned = true,
                coverGeometryNow = false,
                innerGeometryNow = true,
                privilegedCaptureReady = true,
            )
        )
    }

    @Test
    fun doesNotTransferWhenPrivilegedCaptureIsUnavailable() {
        assertFalse(
            Fold7OpeningRemapHandoffPolicy.shouldTransferToInner(
                openingVisualActive = true,
                previousCoverOwned = true,
                coverGeometryNow = false,
                innerGeometryNow = true,
                privilegedCaptureReady = false,
            )
        )
    }
}
