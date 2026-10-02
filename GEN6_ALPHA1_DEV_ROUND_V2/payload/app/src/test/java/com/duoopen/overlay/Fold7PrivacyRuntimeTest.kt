package com.duoopen.overlay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7PrivacyRuntimeTest {
    @Test
    fun captureDenialIsStickyForCurrentPackageOnly() {
        val runtime = Fold7PrivacyRuntime()
        runtime.onForegroundApp("com.example.normal", "Normal", false)
        assertEquals(Fold7GlassMode.PUBLIC_GLASS, runtime.current().decision.mode)

        val denied = runtime.markCaptureDenied("accessibility-error:5")
        assertTrue(denied.becamePrivate)
        assertEquals(Fold7GlassMode.PRIVATE_FROST, runtime.current().decision.mode)

        runtime.onForegroundApp("com.example.other", "Other", false)
        assertEquals(Fold7GlassMode.PUBLIC_GLASS, runtime.current().decision.mode)
        assertFalse(runtime.current().decision.proceduralOnly)
    }

    @Test
    fun workProfileStartsPrivateWithoutCaptureAttempt() {
        val runtime = Fold7PrivacyRuntime()
        runtime.onForegroundApp("com.example.work", "Work App", true)
        assertEquals(Fold7GlassMode.PRIVATE_FROST, runtime.current().decision.mode)
        assertFalse(runtime.current().decision.captureAllowed)
    }
}
