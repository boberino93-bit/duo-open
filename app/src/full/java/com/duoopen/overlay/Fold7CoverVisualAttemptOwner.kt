package com.duoopen.overlay

internal class Fold7CoverVisualAttemptOwner {
    enum class Direction { OPENING, CLOSING }
    enum class ContentKind { LIVE_COVER, FROZEN_RIGHT_PANE }
    enum class State { IDLE, WAITING_CONTENT, WAITING_HOST, READY_HIDDEN, VISIBLE_REQUESTED, ACTIVE }

    data class Movement(
        val serviceEpoch: Long,
        val movementId: Long,
        val generation: Long,
        val direction: Direction,
    )

    data class Content(
        val kind: ContentKind,
        val contentLeaseId: Long,
        val captureSequence: Long,
    )

    data class Host(
        val hostEpoch: Long,
        val logicalDisplayId: Int,
    )

    data class AttemptToken(
        val movement: Movement,
        val attemptSequence: Long,
        val hostEpoch: Long,
        val contentLeaseId: Long,
    )

    data class Snapshot(
        val state: State,
        val movement: Movement?,
        val content: Content?,
        val host: Host?,
        val visibleDemand: Boolean,
        val attemptSequence: Long,
    )

    private var movement: Movement? = null
    private var content: Content? = null
    private var host: Host? = null
    private var visibleDemand = false
    private var attemptSequence = 0L
    private var state = State.IDLE

    fun begin(next: Movement) {
        if (movement == next) return
        movement = next
        content = null
        host = null
        visibleDemand = false
        attemptSequence = 0L
        state = State.WAITING_CONTENT
    }

    fun bindContent(expected: Movement, next: Content): Boolean {
        if (movement != expected) return false
        if (content != next && state == State.ACTIVE) {
            state = State.VISIBLE_REQUESTED
        }
        content = next
        reconcile()
        return true
    }

    fun bindHost(expected: Movement, next: Host): Boolean {
        if (movement != expected) return false
        if (host != next) {
            host = next
            if (state == State.ACTIVE) state = State.VISIBLE_REQUESTED
        }
        reconcile()
        return true
    }

    fun hostLost(expectedHostEpoch: Long) {
        if (host?.hostEpoch != expectedHostEpoch) return
        host = null
        reconcile()
    }

    fun setVisible(expected: Movement, visible: Boolean): Boolean {
        if (movement != expected) return false
        visibleDemand = visible
        reconcile()
        return true
    }

    fun reserveAttach(expected: Movement): AttemptToken? {
        if (movement != expected || !visibleDemand || content == null || host == null) return null
        if (state == State.ACTIVE) return null
        attemptSequence += 1L
        state = State.VISIBLE_REQUESTED
        return AttemptToken(
            movement = expected,
            attemptSequence = attemptSequence,
            hostEpoch = host!!.hostEpoch,
            contentLeaseId = content!!.contentLeaseId,
        )
    }

    fun markActive(token: AttemptToken): Boolean {
        val currentMovement = movement ?: return false
        val currentContent = content ?: return false
        val currentHost = host ?: return false
        if (
            token.movement != currentMovement ||
            token.attemptSequence != attemptSequence ||
            token.hostEpoch != currentHost.hostEpoch ||
            token.contentLeaseId != currentContent.contentLeaseId ||
            !visibleDemand
        ) return false
        state = State.ACTIVE
        return true
    }

    fun isCurrent(token: AttemptToken): Boolean {
        val currentMovement = movement ?: return false
        val currentContent = content ?: return false
        val currentHost = host ?: return false
        return token.movement == currentMovement &&
            token.attemptSequence == attemptSequence &&
            token.hostEpoch == currentHost.hostEpoch &&
            token.contentLeaseId == currentContent.contentLeaseId
    }

    fun end(expected: Movement? = movement) {
        if (expected != null && movement != expected) return
        movement = null
        content = null
        host = null
        visibleDemand = false
        attemptSequence = 0L
        state = State.IDLE
    }

    fun snapshot(): Snapshot = Snapshot(state, movement, content, host, visibleDemand, attemptSequence)

    private fun reconcile() {
        if (movement == null) {
            state = State.IDLE
            return
        }
        state = when {
            content == null -> State.WAITING_CONTENT
            host == null -> State.WAITING_HOST
            !visibleDemand -> State.READY_HIDDEN
            state == State.ACTIVE -> State.ACTIVE
            else -> State.VISIBLE_REQUESTED
        }
    }
}
