package com.duoopen.overlay

/**
 * Startup barrier between one app/accessibility-service lifetime and the
 * independently-lived Shizuku daemon-side cover lease.
 *
 * A fresh app process must not inherit non-IDLE privileged cover authority
 * from another serviceEpoch. The gate classifies accepted shell snapshots,
 * requests one exact cleanup for foreign ownership, and becomes READY only
 * when startup authority is proven safe.
 */
internal class Fold7ProcessRecoveryGate(
    private val serviceEpoch: Long,
) {
    enum class Phase {
        RECOVERING,
        READY,
    }

    sealed interface Action {
        data object None : Action
        data object Arm : Action

        data class ReleaseForeign(
            val token: Fold7CoverLeaseSnapshotGate.LeaseToken,
        ) : Action
    }

    data class Decision(
        val phase: Phase,
        val reason: String,
        val action: Action,
    )

    init {
        require(serviceEpoch > 0L)
    }

    private var currentPhase = Phase.RECOVERING

    private var releaseRequestedFor:
        Fold7CoverLeaseSnapshotGate.LeaseToken? = null

    val phase: Phase
        get() = currentPhase

    val ready: Boolean
        get() = currentPhase == Phase.READY

    fun observe(
        snapshot: Fold7CoverLeaseSnapshotGate.Snapshot,
        token: Fold7CoverLeaseSnapshotGate.LeaseToken?,
    ): Decision {
        if (currentPhase == Phase.READY) {
            return decision(
                reason = "already-ready",
                action = Action.None,
            )
        }

        if (snapshot.leaseState == "IDLE") {
            currentPhase = Phase.READY
            releaseRequestedFor = null
            return decision(
                reason = "shell-idle",
                action = Action.Arm,
            )
        }

        val exactToken =
            token
                ?: return decision(
                    reason = "non-idle-without-exact-token",
                    action = Action.None,
                )

        if (exactToken.ownerServiceEpoch == serviceEpoch) {
            currentPhase = Phase.READY
            releaseRequestedFor = null
            return decision(
                reason = "same-service-authority",
                action = Action.Arm,
            )
        }

        if (
            snapshot.leaseState == "RELEASE_PENDING" ||
            snapshot.leaseState == "RELEASING" ||
            snapshot.leaseState == "UNKNOWN_RECOVERY"
        ) {
            return decision(
                reason = "foreign-cleanup-pending:${snapshot.leaseState}",
                action = Action.None,
            )
        }

        if (releaseRequestedFor == exactToken) {
            return decision(
                reason = "foreign-release-already-requested",
                action = Action.None,
            )
        }

        releaseRequestedFor = exactToken

        return decision(
            reason = "foreign-prior-service:${exactToken.ownerServiceEpoch}",
            action = Action.ReleaseForeign(exactToken),
        )
    }

    private fun decision(
        reason: String,
        action: Action,
    ) =
        Decision(
            phase = currentPhase,
            reason = reason,
            action = action,
        )
}
