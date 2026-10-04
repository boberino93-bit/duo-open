package com.duoopen.overlay

/**
 * Field-validated admission rule for speculative inner-panel prewake on Fold7.
 *
 * S1L demonstrated that Samsung's physical CLOSED(0) -> TENT(1) transition
 * arrives early enough to hide the ~160-200ms inner-panel power cost. S1M
 * demonstrated that learned/synthetic DeviceState transitions are not safe
 * prewake signals: state overrides can introduce 0<->5/2->0 transitions while
 * closing and cause Duo Open to fight Samsung's display routing.
 *
 * Keep speculative power strictly tied to the one native physical transition
 * proven in field evidence. This policy must not be broadened from learned state
 * sets or synthetic override states without new isolated evidence.
 */
internal object Fold7SpeculativePrewakePolicy {
    const val CLOSED_STATE_ID = 0
    const val TENT_STATE_ID = 1

    fun shouldPrewake(
        previousStateId: Int?,
        currentStateId: Int,
        previousFolded: Boolean?,
        currentFolded: Boolean?,
    ): Boolean =
        previousStateId == CLOSED_STATE_ID &&
            currentStateId == TENT_STATE_ID &&
            previousFolded == true &&
            currentFolded == true
}
