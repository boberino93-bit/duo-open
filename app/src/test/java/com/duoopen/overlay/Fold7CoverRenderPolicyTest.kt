package com.duoopen.overlay

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7CoverRenderPolicyTest {
    @Test
    fun noPrivilegedGen2_preservesLegacyCoverRendering() {
        val decision =
            Fold7CoverRenderPolicy.decide(
                privilegedGen2Ready = false,
                openingFromClosedLatched = false,
                state = Fold7ContinuityController.State.NATIVE_COVER,
            )

        assertFalse(decision.gen2OwnsCover)
        assertFalse(decision.runEarlyOpeningVisual)
    }

    @Test
    fun nativeCover_isOwnedButDoesNotAnimateUntilOpeningEdge() {
        val decision =
            Fold7CoverRenderPolicy.decide(
                privilegedGen2Ready = true,
                openingFromClosedLatched = false,
                state = Fold7ContinuityController.State.NATIVE_COVER,
            )

        assertTrue(decision.gen2OwnsCover)
        assertFalse(decision.runEarlyOpeningVisual)
    }

    @Test
    fun openingFromClosed_runsExplicitEarlyOpeningVisual() {
        val decision =
            Fold7CoverRenderPolicy.decide(
                privilegedGen2Ready = true,
                openingFromClosedLatched = true,
                state = Fold7ContinuityController.State.OPENING_FROM_CLOSED,
            )

        assertTrue(decision.gen2OwnsCover)
        assertTrue(decision.runEarlyOpeningVisual)
    }

    @Test
    fun latchedInnerHandoff_keepsOpeningVisualUntilOpenOrRouteLoss() {
        val decision =
            Fold7CoverRenderPolicy.decide(
                privilegedGen2Ready = true,
                openingFromClosedLatched = true,
                state = Fold7ContinuityController.State.INNER_HANDOFF,
            )

        assertTrue(decision.gen2OwnsCover)
        assertTrue(decision.runEarlyOpeningVisual)
    }

    @Test
    fun openInner_clearsOpeningVisualEvenIfCallerStillHasLatch() {
        val decision =
            Fold7CoverRenderPolicy.decide(
                privilegedGen2Ready = true,
                openingFromClosedLatched = true,
                state = Fold7ContinuityController.State.OPEN_INNER,
            )

        assertTrue(decision.gen2OwnsCover)
        assertFalse(decision.runEarlyOpeningVisual)
    }

    @Test
    fun closingStates_neverAllowAutonomousCoverPanelEngine() {
        for (
            state in
            listOf(
                Fold7ContinuityController.State.CLOSING_INTENT,
                Fold7ContinuityController.State.COVER_PREWARMING,
                Fold7ContinuityController.State.COVER_READY_HIDDEN,
                Fold7ContinuityController.State.COVER_VISUAL,
            )
        ) {
            val decision =
                Fold7CoverRenderPolicy.decide(
                    privilegedGen2Ready = true,
                    openingFromClosedLatched = false,
                    state = state,
                )

            assertTrue(decision.gen2OwnsCover)
            assertFalse(decision.runEarlyOpeningVisual)
        }
    }
}
