package com.duoopen.shell

/**
 * Pure ownership model for Gen4 Fold7 panel authority.
 *
 * The Shizuku daemon is the only component allowed to mutate the physical or
 * logical cover route. App-side callers provide a serviceEpoch and a strictly
 * increasing intentSequence. A newer app lifetime cannot inherit a prepared
 * route from an older service lifetime; it must first normalize that route.
 */
internal class Fold7PanelAuthorityGen4 {
    enum class Phase {
        RECOVERING,
        INNER_NATIVE,
        COVER_PREPARING,
        COVER_READY_HIDDEN,
        NATIVE_COVER,
        RELEASE_PENDING,
    }

    data class Owner(
        val serviceEpoch: Long,
        val closeCycleId: Long,
        val transitionGeneration: Long,
    )

    data class Snapshot(
        val phase: Phase,
        val recoveryReady: Boolean,
        val activeServiceEpoch: Long,
        val lastIntentSequence: Long,
        val owner: Owner?,
        val physicalDisplayId: Long?,
        val logicalDisplayId: Int?,
        val physicalHeld: Boolean,
        val routeReady: Boolean,
    )

    data class Admission(
        val accepted: Boolean,
        val stale: Boolean,
        val cleanupRequired: Boolean,
        val reason: String,
    )

    data class ReleaseAdmission(
        val accepted: Boolean,
        val stale: Boolean,
        val reason: String,
    )

    sealed interface RecoveryPlan {
        data object ReadyInner : RecoveryPlan
        data object ReadyNativeCover : RecoveryPlan
        data class ResetSecondaryRoute(val logicalId: Int) : RecoveryPlan
        data object RetryAmbiguous : RecoveryPlan
    }

    private var phase = Phase.RECOVERING
    private var recoveryReady = false
    private var activeServiceEpoch = 0L
    private var lastIntentSequence = 0L
    private var owner: Owner? = null
    private var physicalDisplayId: Long? = null
    private var logicalDisplayId: Int? = null
    private var physicalHeld = false
    private var routeReady = false

    fun snapshot(): Snapshot =
        Snapshot(
            phase = phase,
            recoveryReady = recoveryReady,
            activeServiceEpoch = activeServiceEpoch,
            lastIntentSequence = lastIntentSequence,
            owner = owner,
            physicalDisplayId = physicalDisplayId,
            logicalDisplayId = logicalDisplayId,
            physicalHeld = physicalHeld,
            routeReady = routeReady,
        )

    fun recoveryPlan(
        nativeCover: Boolean,
        innerIsDefault: Boolean,
        coverSecondaryLogicalId: Int?,
    ): RecoveryPlan =
        when {
            nativeCover -> RecoveryPlan.ReadyNativeCover
            !innerIsDefault -> RecoveryPlan.RetryAmbiguous
            coverSecondaryLogicalId != null && coverSecondaryLogicalId >= 0 ->
                RecoveryPlan.ResetSecondaryRoute(coverSecondaryLogicalId)
            else -> RecoveryPlan.ReadyInner
        }

    fun completeRecovery(
        nativeCover: Boolean,
    ) {
        recoveryReady = true
        owner = null
        physicalDisplayId = null
        logicalDisplayId = null
        physicalHeld = false
        routeReady = false
        phase = if (nativeCover) Phase.NATIVE_COVER else Phase.INNER_NATIVE
    }

    fun recoveryFailed() {
        recoveryReady = false
        phase = Phase.RECOVERING
        routeReady = false
    }

    /**
     * Admits one app-side privileged intent.
     *
     * serviceEpoch is monotonic for one device boot. A higher epoch represents
     * a replacement accessibility-service process. If the older process had a
     * prepared cover route, the daemon requires cleanup before switching owner.
     */
    fun admit(
        serviceEpoch: Long,
        intentSequence: Long,
    ): Admission {
        if (!recoveryReady) {
            return rejected("startup-recovery-required")
        }
        if (serviceEpoch <= 0L || intentSequence <= 0L) {
            return rejected("invalid-intent-identity")
        }
        if (activeServiceEpoch > 0L && serviceEpoch < activeServiceEpoch) {
            return Admission(false, true, false, "older-service-epoch")
        }
        if (serviceEpoch == activeServiceEpoch && intentSequence <= lastIntentSequence) {
            return Admission(false, true, false, "stale-intent-sequence")
        }

        if (serviceEpoch > activeServiceEpoch) {
            val needsCleanup =
                activeServiceEpoch > 0L &&
                    phase in setOf(
                        Phase.COVER_PREPARING,
                        Phase.COVER_READY_HIDDEN,
                        Phase.RELEASE_PENDING,
                    )

            if (needsCleanup) {
                return Admission(
                    accepted = false,
                    stale = false,
                    cleanupRequired = true,
                    reason = "new-service-requires-route-normalization",
                )
            }

            activeServiceEpoch = serviceEpoch
            lastIntentSequence = 0L
            owner = null
            physicalDisplayId = null
            logicalDisplayId = null
            routeReady = false
        }

        lastIntentSequence = intentSequence
        return Admission(true, false, false, "accepted")
    }

    fun completeServiceRollover(
        serviceEpoch: Long,
        intentSequence: Long,
        nativeCover: Boolean,
    ) {
        require(serviceEpoch > activeServiceEpoch)
        require(intentSequence > 0L)
        activeServiceEpoch = serviceEpoch
        lastIntentSequence = intentSequence
        owner = null
        physicalDisplayId = null
        logicalDisplayId = null
        physicalHeld = false
        routeReady = false
        recoveryReady = true
        phase = if (nativeCover) Phase.NATIVE_COVER else Phase.INNER_NATIVE
    }

    fun beginPrepare(
        owner: Owner,
        intentSequence: Long,
    ) {
        require(recoveryReady)
        require(owner.serviceEpoch == activeServiceEpoch)
        require(intentSequence == lastIntentSequence)
        this.owner = owner
        physicalDisplayId = null
        logicalDisplayId = null
        physicalHeld = false
        routeReady = false
        phase = Phase.COVER_PREPARING
    }

    fun completePrepare(
        intentSequence: Long,
        success: Boolean,
        physicalDisplayId: Long?,
        logicalDisplayId: Int?,
        routeReady: Boolean,
    ) {
        if (intentSequence != lastIntentSequence) return
        this.physicalDisplayId = physicalDisplayId?.takeIf { it >= 0L }
        this.logicalDisplayId = logicalDisplayId?.takeIf { it >= 0 }
        this.physicalHeld = success && this.physicalDisplayId != null
        this.routeReady = this.physicalHeld && routeReady
        phase =
            if (this.routeReady) {
                Phase.COVER_READY_HIDDEN
            } else {
                Phase.COVER_PREPARING
            }
    }

    /**
     * Begins a normal current-owner release. Callers that are reacting to an
     * asynchronous transition must prefer [beginReleaseOwned] so a delayed
     * release cannot tear down a route already transferred to a newer cycle.
     */
    fun beginRelease(
        serviceEpoch: Long,
        intentSequence: Long,
    ) {
        require(recoveryReady)
        require(serviceEpoch == activeServiceEpoch)
        require(intentSequence == lastIntentSequence)
        phase = Phase.RELEASE_PENDING
        routeReady = false
    }

    /**
     * Compare-and-release for transition-driven teardown.
     *
     * Intent ordering alone is insufficient: an old generation can be queued,
     * receive a numerically newer intentSequence when it finally runs, and
     * otherwise tear down the route now owned by a newer close cycle. The
     * expected owner is therefore part of the mutation authority.
     */
    fun beginReleaseOwned(
        serviceEpoch: Long,
        intentSequence: Long,
        expectedOwner: Owner,
    ): ReleaseAdmission {
        if (!recoveryReady) {
            return ReleaseAdmission(false, false, "startup-recovery-required")
        }
        if (
            serviceEpoch != activeServiceEpoch ||
            intentSequence != lastIntentSequence
        ) {
            return ReleaseAdmission(false, true, "stale-release-intent")
        }

        val currentOwner = owner
        if (currentOwner != expectedOwner) {
            return ReleaseAdmission(false, true, "stale-release-owner")
        }

        phase = Phase.RELEASE_PENDING
        routeReady = false
        return ReleaseAdmission(true, false, "accepted")
    }

    fun completeRelease(
        intentSequence: Long,
        success: Boolean,
        nativeCover: Boolean,
    ) {
        if (intentSequence != lastIntentSequence) return
        if (!success) {
            phase = Phase.RELEASE_PENDING
            routeReady = false
            return
        }
        owner = null
        physicalDisplayId = null
        logicalDisplayId = null
        physicalHeld = false
        routeReady = false
        phase = if (nativeCover) Phase.NATIVE_COVER else Phase.INNER_NATIVE
    }

    fun markNativeCover() {
        if (!recoveryReady) return
        owner = null
        physicalDisplayId = null
        logicalDisplayId = null
        physicalHeld = false
        routeReady = false
        phase = Phase.NATIVE_COVER
    }

    private fun rejected(reason: String) =
        Admission(
            accepted = false,
            stale = false,
            cleanupRequired = false,
            reason = reason,
        )
}
