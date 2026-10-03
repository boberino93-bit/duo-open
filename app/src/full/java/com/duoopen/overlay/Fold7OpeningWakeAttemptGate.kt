package com.duoopen.overlay

/**
 * Small exact-lifetime fence for privileged INNER wake work.
 *
 * Controller generation is intentionally not the identity here: ordinary
 * OPENING_FROM_CLOSED -> INNER_HANDOFF advances generation and must not retire
 * the accepted opening. A new semantic opening gets a new sequence. True
 * terminal/cancel states revoke the active key.
 */
internal class Fold7OpeningWakeAttemptGate(
    private val serviceEpoch: Long,
) {
    data class Key(
        val serviceEpoch: Long,
        val openingAttemptSequence: Long,
        val acceptedGeneration: Long,
    )

    private val lock = Any()
    private var nextSequence = 1L
    private var active: Key? = null

    fun onTransition(
        from: Fold7ContinuityController.State,
        to: Fold7ContinuityController.State,
        generation: Long,
    ): Key? =
        synchronized(lock) {
            when {
                to == Fold7ContinuityController.State.OPENING_FROM_CLOSED &&
                    from != Fold7ContinuityController.State.OPENING_FROM_CLOSED -> {
                    active =
                        Key(
                            serviceEpoch = serviceEpoch,
                            openingAttemptSequence = nextSequence++,
                            acceptedGeneration = generation,
                        )
                }

                to in TERMINAL_OR_CANCEL_STATES -> {
                    active = null
                }

                // INNER_HANDOFF is ordinary forward opening progress. Keep the
                // same semantic opening identity even though generation moved.
                else -> Unit
            }
            active
        }

    fun current(): Key? =
        synchronized(lock) {
            active
        }

    fun isCurrent(key: Key): Boolean =
        synchronized(lock) {
            active == key
        }

    fun invalidate() {
        synchronized(lock) {
            active = null
        }
    }

    private companion object {
        val TERMINAL_OR_CANCEL_STATES =
            setOf(
                Fold7ContinuityController.State.NATIVE_COVER,
                Fold7ContinuityController.State.OPEN_INNER,
                Fold7ContinuityController.State.CLOSING_INTENT,
                Fold7ContinuityController.State.COVER_PREWARMING,
                Fold7ContinuityController.State.COVER_READY_HIDDEN,
                Fold7ContinuityController.State.COVER_VISUAL,
            )
    }
}
