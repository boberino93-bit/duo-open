package com.duoopen.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ProductUiModelTest {
    @Test
    fun accessibilityMissingIsSetupState() {
        val state =
            productUiState(
                overlayEnabled = false,
                shizukuReady = true,
                hingeAngle = 120f,
                simulated = false,
            )

        assertFalse(state.ready)
        assertEquals("Setup required", state.headline)
        assertEquals("Finish setup", state.primaryAction)
    }

    @Test
    fun shizukuMissingIsPrecisionBridgeState() {
        val state =
            productUiState(
                overlayEnabled = true,
                shizukuReady = false,
                hingeAngle = 120f,
                simulated = false,
            )

        assertFalse(state.ready)
        assertEquals("Precision bridge offline", state.headline)
    }

    @Test
    fun missingHingeNeverClaimsReady() {
        val state =
            productUiState(
                overlayEnabled = true,
                shizukuReady = true,
                hingeAngle = Float.NaN,
                simulated = false,
            )

        assertFalse(state.ready)
        assertEquals("Waiting for hinge", state.headline)
        assertEquals("Open controls", state.primaryAction)
    }

    @Test
    fun liveGeometryProducesReadyState() {
        val state =
            productUiState(
                overlayEnabled = true,
                shizukuReady = true,
                hingeAngle = 133f,
                simulated = false,
            )

        assertTrue(state.ready)
        assertEquals("Continuity ready", state.headline)
        assertEquals("Test continuity", state.primaryAction)
    }

    @Test
    fun layoutThresholdKeepsCoverCompactAndInnerExpanded() {
        assertFalse(useExpandedProductLayout(699))
        assertTrue(useExpandedProductLayout(700))
        assertTrue(useExpandedProductLayout(900))
    }
}
