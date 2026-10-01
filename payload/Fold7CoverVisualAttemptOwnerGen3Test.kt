package com.duoopen.overlay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7CoverVisualAttemptOwnerGen3Test {
    private fun closing() =
        Fold7CoverVisualAttemptOwner.Movement(
            serviceEpoch = 7L,
            movementId = 11L,
            generation = 20L,
            direction =
                Fold7CoverVisualAttemptOwner.Direction.CLOSING,
        )

    @Test
    fun contentAndHostReadinessRemainHiddenWithoutVisibleDemand() {
        val owner =
            Fold7CoverVisualAttemptOwner()

        val movement =
            closing()

        owner.begin(
            movement
        )

        owner.bindContent(
            movement,
            Fold7CoverVisualAttemptOwner.Content(
                kind =
                    Fold7CoverVisualAttemptOwner.ContentKind.FROZEN_RIGHT_PANE,
                contentLeaseId = 3L,
                captureSequence = 2L,
            ),
        )

        owner.bindHost(
            movement,
            Fold7CoverVisualAttemptOwner.Host(
                hostEpoch = 1L,
                logicalDisplayId = 5,
            ),
        )

        assertEquals(
            Fold7CoverVisualAttemptOwner.State.READY_HIDDEN,
            owner.snapshot().state,
        )
    }

    @Test
    fun hostRemapPreservesDemandAndRejectsOldHostCallback() {
        val owner =
            Fold7CoverVisualAttemptOwner()

        val movement =
            closing()

        owner.begin(
            movement
        )

        owner.bindContent(
            movement,
            Fold7CoverVisualAttemptOwner.Content(
                kind =
                    Fold7CoverVisualAttemptOwner.ContentKind.FROZEN_RIGHT_PANE,
                contentLeaseId = 3L,
                captureSequence = 2L,
            ),
        )

        owner.bindHost(
            movement,
            Fold7CoverVisualAttemptOwner.Host(
                hostEpoch = 1L,
                logicalDisplayId = 5,
            ),
        )

        owner.setVisible(
            movement,
            true,
        )

        val old =
            owner.reserveAttach(
                movement
            )!!

        assertTrue(
            owner.markActive(
                old
            )
        )

        owner.hostLost(
            1L
        )

        assertTrue(
            owner.snapshot()
                .visibleDemand
        )

        owner.bindHost(
            movement,
            Fold7CoverVisualAttemptOwner.Host(
                hostEpoch = 2L,
                logicalDisplayId = 9,
            ),
        )

        val replacement =
            owner.reserveAttach(
                movement
            )

        assertNotNull(
            replacement
        )

        assertFalse(
            owner.markActive(
                old
            )
        )

        assertTrue(
            owner.markActive(
                replacement!!
            )
        )
    }

    @Test
    fun replacingContentDemotesActiveBindingUntilReattached() {
        val owner =
            Fold7CoverVisualAttemptOwner()

        val movement =
            closing()

        owner.begin(
            movement
        )

        owner.bindContent(
            movement,
            Fold7CoverVisualAttemptOwner.Content(
                kind =
                    Fold7CoverVisualAttemptOwner.ContentKind.FROZEN_RIGHT_PANE,
                contentLeaseId = 3L,
                captureSequence = 2L,
            ),
        )

        owner.bindHost(
            movement,
            Fold7CoverVisualAttemptOwner.Host(
                hostEpoch = 1L,
                logicalDisplayId = 5,
            ),
        )

        owner.setVisible(
            movement,
            true,
        )

        val first =
            owner.reserveAttach(
                movement
            )!!

        assertTrue(
            owner.markActive(
                first
            )
        )

        owner.bindContent(
            movement,
            Fold7CoverVisualAttemptOwner.Content(
                kind =
                    Fold7CoverVisualAttemptOwner.ContentKind.FROZEN_RIGHT_PANE,
                contentLeaseId = 4L,
                captureSequence = 3L,
            ),
        )

        assertEquals(
            Fold7CoverVisualAttemptOwner.State.VISIBLE_REQUESTED,
            owner.snapshot().state,
        )

        assertFalse(
            owner.isCurrent(
                first
            )
        )
    }
}
