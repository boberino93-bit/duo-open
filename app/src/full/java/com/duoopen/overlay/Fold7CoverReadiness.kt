package com.duoopen.overlay

/**
 * Separates lease/mutation success from an app-visible cover destination that
 * is actually usable by continuity rendering.
 */
internal class Fold7CoverReadiness {
    enum class State {
        IDLE,
        WAITING_ROUTE,
        READY,
    }

    data class Demand(
        val serviceEpoch: Long,
        val closeCycleId: Long,
        val transitionGeneration: Long,
        val leaseToken: Fold7CoverLeaseSnapshotGate.LeaseToken,
        val expectedLogicalId: Int,
    )

    data class Topology(
        val innerActive: Boolean,
        val coverActive: Boolean,
        val innerIsDefault: Boolean,
        val coverIsDefault: Boolean,
        val coverLogicalId: Int?,
    )

    data class Result(
        val state: State,
        val becameReady: Boolean,
        val reason: String,
    )

    var state: State = State.IDLE
        private set

    private var demand: Demand? = null
    private var shellRouteReady = false

    val currentDemand: Demand?
        get() = demand

    val routeReadyFromShell: Boolean
        get() = shellRouteReady

    fun begin(
        demand: Demand,
        shellRouteReady: Boolean,
    ): Result {
        this.demand = demand
        this.shellRouteReady = shellRouteReady
        state = State.WAITING_ROUTE
        return Result(state, false, "demand-started")
    }

    fun updateShell(
        demand: Demand,
        shellRouteReady: Boolean,
        expectedLogicalId: Int,
    ): Result {
        val current = this.demand
            ?: return Result(state, false, "no-demand")

        if (
            current.serviceEpoch != demand.serviceEpoch ||
            current.closeCycleId != demand.closeCycleId ||
            current.transitionGeneration != demand.transitionGeneration ||
            current.leaseToken != demand.leaseToken
        ) {
            return Result(state, false, "stale-demand")
        }

        this.demand = current.copy(
            expectedLogicalId = expectedLogicalId,
        )
        this.shellRouteReady = shellRouteReady

        if (!shellRouteReady) {
            state = State.WAITING_ROUTE
        }

        return Result(state, false, "shell-updated")
    }

    fun observe(
        serviceEpoch: Long,
        closeCycleId: Long,
        topology: Topology,
    ): Result {
        val current = demand
            ?: return Result(state, false, "no-demand")

        if (
            current.serviceEpoch != serviceEpoch ||
            current.closeCycleId != closeCycleId
        ) {
            return Result(state, false, "stale-cycle")
        }

        val expectedLogical = current.expectedLogicalId
        val ready =
            shellRouteReady &&
                expectedLogical >= 0 &&
                topology.innerActive &&
                topology.coverActive &&
                topology.innerIsDefault &&
                !topology.coverIsDefault &&
                topology.coverLogicalId == expectedLogical

        if (!ready) {
            state = State.WAITING_ROUTE
            return Result(state, false, "topology-not-ready")
        }

        val changed = state != State.READY
        state = State.READY
        return Result(
            state = state,
            becameReady = changed,
            reason = if (changed) "ready" else "still-ready",
        )
    }

    fun invalidate(
        serviceEpoch: Long? = null,
        closeCycleId: Long? = null,
    ): Result {
        val current = demand
        if (
            current != null &&
            serviceEpoch != null &&
            current.serviceEpoch != serviceEpoch
        ) {
            return Result(state, false, "stale-invalidate-service")
        }
        if (
            current != null &&
            closeCycleId != null &&
            current.closeCycleId != closeCycleId
        ) {
            return Result(state, false, "stale-invalidate-cycle")
        }

        demand = null
        shellRouteReady = false
        state = State.IDLE
        return Result(state, false, "invalidated")
    }
}
