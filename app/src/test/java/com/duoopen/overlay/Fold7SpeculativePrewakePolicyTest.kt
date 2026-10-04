package com.duoopen.overlay

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7SpeculativePrewakePolicyTest {
    @Test
    fun acceptsNativeClosedToTentOnly() {
        assertTrue(
            Fold7SpeculativePrewakePolicy.shouldPrewake(
                previousStateId = 0,
                currentStateId = 1,
                previousFolded = true,
                currentFolded = true,
            )
        )
    }

    @Test
    fun rejectsClosingTentToClosed() {
        assertFalse(
            Fold7SpeculativePrewakePolicy.shouldPrewake(
                previousStateId = 1,
                currentStateId = 0,
                previousFolded = true,
                currentFolded = true,
            )
        )
    }

    @Test
    fun rejectsConcurrentOuterSyntheticTransitions() {
        assertFalse(
            Fold7SpeculativePrewakePolicy.shouldPrewake(0, 5, true, true)
        )
        assertFalse(
            Fold7SpeculativePrewakePolicy.shouldPrewake(5, 0, true, true)
        )
    }

    @Test
    fun rejectsHalfOpenedToClosedRefold() {
        assertFalse(
            Fold7SpeculativePrewakePolicy.shouldPrewake(2, 0, true, true)
        )
    }

    @Test
    fun rejectsUnknownFoldTruth() {
        assertFalse(
            Fold7SpeculativePrewakePolicy.shouldPrewake(0, 1, null, true)
        )
        assertFalse(
            Fold7SpeculativePrewakePolicy.shouldPrewake(0, 1, true, null)
        )
    }
}
