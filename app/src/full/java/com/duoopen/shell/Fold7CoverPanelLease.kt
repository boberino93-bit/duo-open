package com.duoopen.shell

/**
 * Android-free model for explicit ownership of a Fold7 cover-panel prewarm.
 *
 * Gen3 adds exact compare-and-swap (CAS) ownership for prewarm/adoption.
 * Legacy V2/V3 callers remain supported through [beginPrewarm], but Gen3 must
 * use [beginPrewarmV4] so Binder arrival order can never transfer a lease.
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

    data class OwnerIdentity(
        val serviceEpoch: Long,
        val closeCycleId: Long,
        val transitionGeneration: Long,
    )

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
        val ownerServiceEpoch: Long = 0L,
        val ownerCloseCycleId: Long = 0L,
    ) {
        val ownerIdentity: OwnerIdentity?
            get() =
                if (
                    ownerGeneration >= 0L &&
                    ownerServiceEpoch >= 0L &&
                    ownerCloseCycleId >= 0L
                ) {
                    OwnerIdentity(
                        serviceEpoch = ownerServiceEpoch,
                        closeCycleId = ownerCloseCycleId,
                        transitionGeneration = ownerGeneration,
                    )
                } else {
                    null
                }
    }

    data class PrewarmV4Result(
        val accepted: Boolean,
        val stale: Boolean,
        val reason: String,
        val actions: List<Action>,
    )

    private var state = State.IDLE
    private var leaseId = 0L
    private var epoch = 0L
    private var ownerGeneration = -1L
    private var ownerServiceEpoch = -1L
    private var ownerCloseCycleId = -1L
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
        ownerServiceEpoch = ownerServiceEpoch,
        ownerCloseCycleId = ownerCloseCycleId,
    )

    /**
     * Legacy ownership transfer used by V2/V3 protocol compatibility only.
     */
    fun beginPrewarm(generation: Long): List<Action> {
        require(generation >= 0L)

        return when (state) {
            State.IDLE, State.UNKNOWN_RECOVERY -> {
                leaseId += 1L
                epoch += 1L
                setOwner(
                    OwnerIdentity(
                        serviceEpoch = 0L,
                        closeCycleId = 0L,
                        transitionGeneration = generation,
                    ),
                )
                physicalId = null
                pendingReleaseReason = null
                releaseRequestedDuringPrewarm = false
                state = State.PREWARM_IN_FLIGHT
                listOf(Action.PowerPhysicalCover(leaseId, epoch))
            }

            State.PREWARM_IN_FLIGHT -> {
                epoch += 1L
                setOwner(
                    OwnerIdentity(
                        serviceEpoch = 0L,
                        closeCycleId = 0L,
                        transitionGeneration = generation,
                    ),
                )
                releaseRequestedDuringPrewarm = false
                pendingReleaseReason = null
                emptyList()
            }

            State.HELD, State.RELEASE_PENDING, State.RELEASING -> {
                epoch += 1L
                setOwner(
                    OwnerIdentity(
                        serviceEpoch = 0L,
                        closeCycleId = 0L,
                        transitionGeneration = generation,
                    ),
                )
                pendingReleaseReason = null
                releaseRequestedDuringPrewarm = false
                state = State.HELD
                emptyList()
            }
        }
    }

    /**
     * Gen3 exact-CAS prewarm/adoption.
     *
     * Fresh acquisition is legal only while IDLE and only without an expected
     * token. Every adoption/reclose of an existing lease requires the exact
     * current leaseId + epoch + owner identity. A stale request is inert.
     */
    fun beginPrewarmV4(
        newOwner: OwnerIdentity,
        expectedLeaseId: Long,
        expectedEpoch: Long,
        expectedOwnerServiceEpoch: Long,
        expectedOwnerCloseCycleId: Long,
        expectedOwnerGeneration: Long,
    ): PrewarmV4Result {
        require(newOwner.serviceEpoch > 0L)
        require(newOwner.closeCycleId > 0L)
        require(newOwner.transitionGeneration >= 0L)

        val expectedProvided =
            expectedLeaseId > 0L &&
                expectedEpoch > 0L &&
                expectedOwnerServiceEpoch >= 0L &&
                expectedOwnerCloseCycleId >= 0L &&
                expectedOwnerGeneration >= 0L

        if (state == State.IDLE) {
            if (expectedProvided) {
                return rejected("expected-token-on-idle")
            }

            leaseId += 1L
            epoch += 1L
            setOwner(newOwner)
            physicalId = null
            pendingReleaseReason = null
            releaseRequestedDuringPrewarm = false
            state = State.PREWARM_IN_FLIGHT

            return PrewarmV4Result(
                accepted = true,
                stale = false,
                reason = "fresh-acquire",
                actions = listOf(Action.PowerPhysicalCover(leaseId, epoch)),
            )
        }

        if (state == State.UNKNOWN_RECOVERY) {
            return rejected("unknown-recovery-requires-reconcile")
        }

        if (
            !expectedProvided ||
            !matchesExpected(
                expectedLeaseId = expectedLeaseId,
                expectedEpoch = expectedEpoch,
                expectedOwnerServiceEpoch = expectedOwnerServiceEpoch,
                expectedOwnerCloseCycleId = expectedOwnerCloseCycleId,
                expectedOwnerGeneration = expectedOwnerGeneration,
            )
        ) {
            return rejected("stale-expected-token")
        }

        if (ownerIdentity() == newOwner) {
            return PrewarmV4Result(
                accepted = true,
                stale = false,
                reason = "idempotent-retry",
                actions = emptyList(),
            )
        }

        epoch += 1L
        setOwner(newOwner)
        pendingReleaseReason = null
        releaseRequestedDuringPrewarm = false

        if (state != State.PREWARM_IN_FLIGHT) {
            state = State.HELD
        }

        return PrewarmV4Result(
            accepted = true,
            stale = false,
            reason = "exact-adopt",
            actions = emptyList(),
        )
    }

    fun onPhysicalPrewarmResult(
        resultLeaseId: Long,
        resultEpoch: Long,
        success: Boolean,
        resolvedPhysicalId: Long?,
        topology: Topology,
    ): List<Action> {
        if (resultLeaseId != leaseId || state == State.IDLE) return emptyList()

        if (!success) {
            if (resultEpoch == epoch && state == State.PREWARM_IN_FLIGHT) {
                clear()
            }
            return emptyList()
        }

        physicalId = resolvedPhysicalId ?: physicalId

        val releaseWasRequested = releaseRequestedDuringPrewarm
        state = if (releaseWasRequested) State.RELEASE_PENDING else State.HELD

        return if (releaseWasRequested) reconcile(topology) else emptyList()
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

        if (state == State.RELEASING) return emptyList()

        state = State.RELEASE_PENDING
        return reconcile(topology)
    }

    fun onTopology(topology: Topology): List<Action> =
        when (state) {
            State.RELEASE_PENDING, State.UNKNOWN_RECOVERY -> reconcile(topology)
            else -> emptyList()
        }

    fun onPrivilegedDaemonRestart(topology: Topology): List<Action> {
        state = State.UNKNOWN_RECOVERY
        leaseId += 1L
        epoch += 1L
        ownerGeneration = -1L
        ownerServiceEpoch = -1L
        ownerCloseCycleId = -1L
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

    private fun rejected(reason: String) =
        PrewarmV4Result(
            accepted = false,
            stale = true,
            reason = reason,
            actions = emptyList(),
        )

    private fun ownerIdentity(): OwnerIdentity? =
        if (
            ownerGeneration >= 0L &&
            ownerServiceEpoch >= 0L &&
            ownerCloseCycleId >= 0L
        ) {
            OwnerIdentity(
                serviceEpoch = ownerServiceEpoch,
                closeCycleId = ownerCloseCycleId,
                transitionGeneration = ownerGeneration,
            )
        } else {
            null
        }

    private fun setOwner(owner: OwnerIdentity) {
        ownerServiceEpoch = owner.serviceEpoch
        ownerCloseCycleId = owner.closeCycleId
        ownerGeneration = owner.transitionGeneration
    }

    private fun matchesExpected(
        expectedLeaseId: Long,
        expectedEpoch: Long,
        expectedOwnerServiceEpoch: Long,
        expectedOwnerCloseCycleId: Long,
        expectedOwnerGeneration: Long,
    ): Boolean =
        leaseId == expectedLeaseId &&
            epoch == expectedEpoch &&
            ownerServiceEpoch == expectedOwnerServiceEpoch &&
            ownerCloseCycleId == expectedOwnerCloseCycleId &&
            ownerGeneration == expectedOwnerGeneration &&
            state != State.IDLE

    private fun reconcile(topology: Topology): List<Action> {
        if (state != State.RELEASE_PENDING && state != State.UNKNOWN_RECOVERY) {
            return emptyList()
        }

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
            if (state != State.UNKNOWN_RECOVERY) state = State.RELEASE_PENDING
            return emptyList()
        }

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
        ownerServiceEpoch = -1L
        ownerCloseCycleId = -1L
        physicalId = null
        pendingReleaseReason = null
        releaseRequestedDuringPrewarm = false
    }
}
