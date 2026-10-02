package com.duoopen.overlay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7GlassPrivacyPolicyTest {
    private val policy = Fold7GlassPrivacyPolicy()

    @Test
    fun ordinaryAppUsesPublicGlass() {
        val decision = policy.decide(
            Fold7AppPrivacySignals(
                packageName = "com.example.maps",
                appLabel = "Maps",
            ),
        )
        assertEquals(Fold7GlassMode.PUBLIC_GLASS, decision.mode)
        assertTrue(decision.captureAllowed)
        assertTrue(decision.cacheAllowed)
        assertFalse(decision.proceduralOnly)
    }

    @Test
    fun flagSecureForcesPrivateFrost() {
        assertPrivate(
            policy.decide(
                Fold7AppPrivacySignals(
                    packageName = "com.bank.secure",
                    isFlagSecure = true,
                ),
            ),
        )
    }

    @Test
    fun workProfileForcesPrivateFrost() {
        assertPrivate(
            policy.decide(
                Fold7AppPrivacySignals(
                    packageName = "com.work.mail",
                    isWorkProfile = true,
                ),
            ),
        )
    }

    @Test
    fun coastCapitalLabelForcesPrivateFrost() {
        assertPrivate(
            policy.decide(
                Fold7AppPrivacySignals(
                    packageName = "ca.example.mobile",
                    appLabel = "Coast Capital",
                ),
            ),
        )
    }

    private fun assertPrivate(decision: Fold7GlassDecision) {
        assertEquals(Fold7GlassMode.PRIVATE_FROST, decision.mode)
        assertFalse(decision.captureAllowed)
        assertFalse(decision.cacheAllowed)
        assertTrue(decision.proceduralOnly)
    }
}
