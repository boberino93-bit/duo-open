package com.duoopen.overlay

/**
 * Fold7 cover render arbitration.
 *
 * When privileged Gen2 continuity is available, autonomous cover PanelEngine
 * rendering is suppressed. Closing is owned by DisplayMirrorHost; opening from
 * fully closed is the one deliberate exception, driven explicitly from the
 * early device-state edge through topology-only handoff until true open.
 */
internal object Fold7CoverRenderPolicy {
    data class Decision(
        val gen2OwnsCover: Boolean,
        val runEarlyOpeningVisual: Boolean,
    )

    fun decide(
        privilegedGen2Ready: Boolean,
        openingFromClosedLatched: Boolean,
        state: Fold7ContinuityController.State,
    ): Decision {
        if (!privilegedGen2Ready) {
            return Decision(
                gen2OwnsCover = false,
                runEarlyOpeningVisual = false,
            )
        }

        return Decision(
            gen2OwnsCover = true,
            runEarlyOpeningVisual =
                openingFromClosedLatched &&
                    state in setOf(
                        Fold7ContinuityController.State.OPENING_FROM_CLOSED,
                        Fold7ContinuityController.State.INNER_HANDOFF,
                    ),
        )
    }
}
