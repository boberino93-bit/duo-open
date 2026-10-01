package com.duoopen.shell

/**
 * Android-free model for explicit ownership of a Fold7 cover-panel prewarm.
 *
 * The model never emits a raw physical OFF. A successful physical prewarm is
 * represented by a lease that remains owned until either:
 *  - Samsung is observed to have reclaimed the cover as native/default; or
 *  - a freshly validated non-default cover logical route is available and a
 *    framework power reset succeeds for that route.
 *
 * Every mutating command carries both leaseId and epoch. leaseId prevents one
 * prewarm cycle from affecting another. epoch prevents an older queued release
 * operation from mutating a lease that has since been re-adopted by a newer
 * close cycle.
 */
internal class Fold7CoverPanelLease {
    enum class State {
        IDLE,
        PREWARM_IN_FLIGHT,
        HELD,
        RELEASE_PENDING,
        RELEASING,
        UNKNOWN_RECOVERY,
    }

    data class Topology(
        val nativeCover: Boolean,
        val innerIsDefault: Boolean,
        val coverSecondaryLogicalId: Int?,
        val coverSecondaryPhysicalId: Long?,
    )

    sealed interface Action {
        val leaseId: Long
        val epoch: Long

        data class PowerPhysicalCover(
            override val leaseId: Long,
            override val epoch: Long,
        ) : Action

        data class ResetLogicalCoverPower(
            override val leaseId: Long,
            override val epoch: Long,
            val logicalId: Int,
        ) : Action
    }

    data class Snapshot(
        val state: State,
        val leaseId: Long,
        val epoch: Long,
        val ownerGeneration: Long,
        val physicalId: Long?,
        val pendingReleaseReason: String?,
    )

    private var state = State.IDLE
    private var leaseId = 0L
    private var epoch = 0L
    private var ownerGeneration = -1L
    private var physicalId: Long? = null
    private var pendingReleaseReason: String? = null
    private var releaseRequestedDuringPrewarm = false

    fun snapshot(): Snapshot = Snapshot(
        state = state,
        leaseId = leaseId,
        epoch = epoch,
        ownerGeneration = ownerGeneration,
        physicalId = physicalId,
        pendingReleaseReason = pendingReleaseReason,
    )

    /**
     * Begin or adopt a cover prewarm for a new transition generation.
     * Existing held/pending ownership is reused instead of issuing a duplicate
     * physical wake.
     */
    fun beginPrewarm(generation: Long): List<Action> {
        require(generation >= 0L)

        return when (state) {
            State.IDLE, State.UNKNOWN_RECOVERY -> {
                leaseId += 1L
                epoch += 1L
                ownerGeneration = generation
                physicalId = null
                pendingReleaseReason = null
                releaseRequestedDuringPrewarm = false
                state = State.PREWARM_IN_FLIGHT
                listOf(Action.PowerPhysicalCover(leaseId, epoch))
            }

            State.PREWARM_IN_FLIGHT -> {
                // Same physical operation remains authoritative; just transfer
                // transition ownership to the newest close cycle.
                epoch += 1L
                ownerGeneration = generation
                releaseRequestedDuringPrewarm = false
                pendingReleaseReason = null
                emptyList()
            }

            State.HELD, State.RELEASE_PENDING, State.RELEASING -> {
                // A new close supersedes a prior release intent. Incrementing
                // epoch makes any queued/late reset command stale.
                epoch += 1L
                ownerGeneration = generation
                pendingReleaseReason = null
                releaseRequestedDuringPrewarm = false
                state = State.HELD
                emptyList()
            }
        }
    }

    fun onPhysicalPrewarmResult(
        resultLeaseId: Long,
        resultEpoch: Long,
        success: Boolean,
        resolvedPhysicalId: Long?,
        topology: Topology,
    ): List<Action> {
        if (resultLeaseId != leaseId || state == State.IDLE) return emptyList()

        // The physical command may have completed after a newer transition
        // adopted this lease. It still belongs to the same leaseId, so record
        // the physical result, but never restore the old epoch/owner.
        if (!success) {
            if (resultEpoch == epoch && state == State.PREWARM_IN_FLIGHT) {
                clear()
            }
            return emptyList()
        }

        physicalId = resolvedPhysicalId ?: physicalId

        val releaseWasRequested = releaseRequestedDuringPrewarm
        state = if (releaseWasRequested) State.RELEASE_PENDING else State.HELD

        return if (releaseWasRequested) {
            reconcile(topology)
        } else {
            emptyList()
        }
    }

    fun requestRelease(
        generation: Long,
        reason: String,
        topology: Topology,
    ): List<Action> {
        if (state == State.IDLE) return emptyList()
        if (generation != ownerGeneration) return emptyList()

        pendingReleaseReason = reason

        if (state == State.PREWARM_IN_FLIGHT) {
            releaseRequestedDuringPrewarm = true
            return emptyList()
        }

        if (state == State.RELEASING) {
            // A reset command for this exact lease/epoch is already in flight.
            // Do not create duplicate privileged mutations.
            return emptyList()
        }

        state = State.RELEASE_PENDING
        return reconcile(topology)
    }

    /**
     * Re-evaluate a pending release when DisplayManager topology changes.
     */
    fun onTopology(topology: Topology): List<Action> {
        return when (state) {
            State.RELEASE_PENDING, State.UNKNOWN_RECOVERY -> reconcile(topology)
            else -> emptyList()
        }
    }

    /**
     * Called when the privileged daemon restarted and in-memory lease ownership
     * is lost. This deliberately does not infer that Duo owns any physical panel.
     */
    fun onPrivilegedDaemonRestart(topology: Topology): List<Action> {
        state = State.UNKNOWN_RECOVERY
        leaseId += 1L
        epoch += 1L
        ownerGeneration = -1L
        physicalId = null
        pendingReleaseReason = "privileged-daemon-restart"
        releaseRequestedDuringPrewarm = false
        return reconcile(topology)
    }

    fun onLogicalResetResult(
        resultLeaseId: Long,
        resultEpoch: Long,
        logicalId: Int,
        success: Boolean,
    ): List<Action> {
        if (
            resultLeaseId != leaseId ||
            resultEpoch != epoch ||
            state != State.RELEASING
        ) {
            return emptyList()
        }

        if (success) {
            clear()
            return emptyList()
        }

        state = State.RELEASE_PENDING
        pendingReleaseReason = pendingReleaseReason ?: "logical-reset-failed:$logicalId"
        return emptyList()
    }

    private fun reconcile(topology: Topology): List<Action> {
        if (state != State.RELEASE_PENDING && state != State.UNKNOWN_RECOVERY) {
            return emptyList()
        }

        // Samsung-native/default cover ownership is authoritative. No raw
        // physical OFF or extra logical reset is needed or safe here.
        if (topology.nativeCover) {
            clear()
            return emptyList()
        }

        val logicalId = topology.coverSecondaryLogicalId
        val routePhysicalId = topology.coverSecondaryPhysicalId

        val routeIsSafe =
            topology.innerIsDefault &&
                logicalId != null &&
                logicalId >= 0 &&
                routePhysicalId != null &&
                (physicalId == null || routePhysicalId == physicalId)

        if (!routeIsSafe) {
            if (state != State.UNKNOWN_RECOVERY) {
                state = State.RELEASE_PENDING
            }
            return emptyList()
        }

        // UNKNOWN_RECOVERY is allowed to issue a framework reset only because
        // the route is freshly validated as the non-default cover while the
        // inner panel is default. This asks Android to restore its intended
        // state; it is not a raw physical power-off.
        state = State.RELEASING
        epoch += 1L
        return listOf(
            Action.ResetLogicalCoverPower(
                leaseId = leaseId,
                epoch = epoch,
                logicalId = logicalId!!,
            )
        )
    }

    private fun clear() {
        state = State.IDLE
        epoch += 1L
        ownerGeneration = -1L
        physicalId = null
        pendingReleaseReason = null
        releaseRequestedDuringPrewarm = false
    }
}
