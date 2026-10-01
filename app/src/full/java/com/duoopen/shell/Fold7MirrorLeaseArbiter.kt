package com.duoopen.shell

/**
 * Pure identity/ordering model for the privileged Fold7 live-mirror singleton.
 * Android/SurfaceControl side effects stay in DuoShellService.
 */
internal class Fold7MirrorLeaseArbiter {
    enum class Desired { NONE, START, STOP }

    data class StartTicket(
        val session: Long,
        val sequence: Long,
        val leaseId: Long,
        val sourceDisplayId: Int,
    )

    data class Snapshot(
        val activeSession: Long,
        val lastSequence: Long,
        val desired: Desired,
        val currentLeaseId: Long?,
        val currentSourceDisplayId: Int?,
    )

    data class SessionResult(
        val session: Long,
        val previousLeaseId: Long?,
    )

    data class CommitResult(
        val accepted: Boolean,
        val previousLeaseId: Long?,
        val reason: String,
    )

    data class StopResult(
        val accepted: Boolean,
        val releaseCurrent: Boolean,
        val previousLeaseId: Long?,
        val reason: String,
    )

    private var nextSession = 0L
    private var activeSession = 0L
    private var lastSequence = 0L
    private var desired = Desired.NONE
    private var currentLeaseId: Long? = null
    private var currentSourceDisplayId: Int? = null

    @Synchronized
    fun openSession(): SessionResult {
        val previous = currentLeaseId
        nextSession += 1L
        activeSession = nextSession
        lastSequence = 0L
        desired = Desired.NONE
        currentLeaseId = null
        currentSourceDisplayId = null
        return SessionResult(activeSession, previous)
    }

    @Synchronized
    fun reserveStart(
        session: Long,
        sequence: Long,
        leaseId: Long,
        sourceDisplayId: Int,
    ): StartTicket? {
        if (session != activeSession || session <= 0L) return null
        if (sequence <= lastSequence || sequence <= 0L) return null
        if (leaseId <= 0L || sourceDisplayId < 0) return null
        lastSequence = sequence
        desired = Desired.START
        return StartTicket(session, sequence, leaseId, sourceDisplayId)
    }

    @Synchronized
    fun commitStart(ticket: StartTicket): CommitResult {
        val current =
            ticket.session == activeSession &&
                ticket.sequence == lastSequence &&
                desired == Desired.START

        if (!current) {
            return CommitResult(false, currentLeaseId, "stale-start")
        }

        val previous = currentLeaseId
        currentLeaseId = ticket.leaseId
        currentSourceDisplayId = ticket.sourceDisplayId
        return CommitResult(true, previous, "start-swap")
    }

    /** Candidate failure fences older intent but deliberately preserves current ownership. */
    @Synchronized
    fun failStart(ticket: StartTicket): Boolean =
        ticket.session == activeSession &&
            ticket.sequence == lastSequence &&
            desired == Desired.START

    @Synchronized
    fun stop(
        session: Long,
        sequence: Long,
        leaseId: Long,
    ): StopResult {
        if (session != activeSession || session <= 0L) {
            return StopResult(false, false, currentLeaseId, "stale-session")
        }
        if (sequence <= lastSequence || sequence <= 0L) {
            return StopResult(false, false, currentLeaseId, "stale-sequence")
        }
        if (leaseId <= 0L) {
            return StopResult(false, false, currentLeaseId, "invalid-lease")
        }

        lastSequence = sequence
        desired = Desired.STOP

        if (currentLeaseId != leaseId) {
            return StopResult(true, false, currentLeaseId, "lease-mismatch")
        }

        val previous = currentLeaseId
        currentLeaseId = null
        currentSourceDisplayId = null
        return StopResult(true, true, previous, "stop-release")
    }

    @Synchronized
    fun forceStop(
        session: Long,
        sequence: Long,
    ): StopResult {
        if (session != activeSession || session <= 0L) {
            return StopResult(false, false, currentLeaseId, "stale-session")
        }
        if (sequence <= lastSequence || sequence <= 0L) {
            return StopResult(false, false, currentLeaseId, "stale-sequence")
        }

        lastSequence = sequence
        desired = Desired.STOP
        val previous = currentLeaseId
        currentLeaseId = null
        currentSourceDisplayId = null
        return StopResult(true, previous != null, previous, "force-stop")
    }

    @Synchronized
    fun snapshot(): Snapshot =
        Snapshot(
            activeSession = activeSession,
            lastSequence = lastSequence,
            desired = desired,
            currentLeaseId = currentLeaseId,
            currentSourceDisplayId = currentSourceDisplayId,
        )
}
