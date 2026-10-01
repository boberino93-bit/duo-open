package com.duoopen.overlay

/**
 * App-side acceptance gate for COVER_PANEL_LEASE_V3 snapshots.
 *
 * connectionEpoch belongs to the app-side Shizuku binding lifetime.
 * shellSession belongs to one DuoShellService process.
 * shellRevision is monotonically stamped by the serialized shell mutation
 * executor. leaseId/leaseEpoch/ownerGeneration identify exact mutation authority.
 */
internal class Fold7CoverLeaseSnapshotGate {
    data class LeaseToken(
        val shellSession: Long,
        val leaseId: Long,
        val leaseEpoch: Long,
        val ownerGeneration: Long,
        val physicalDisplayId: Long,
    )

    data class Snapshot(
        val connectionEpoch: Long,
        val shellSession: Long,
        val shellRevision: Long,
        val leaseState: String,
        val leaseId: Long,
        val leaseEpoch: Long,
        val ownerGeneration: Long,
        val physicalDisplayId: Long,
        val targetLogicalId: Int,
        val physicalLeaseHeld: Boolean,
        val routeReady: Boolean,
        val ok: Boolean,
    ) {
        val token: LeaseToken?
            get() =
                if (
                    leaseState != "IDLE" &&
                    shellSession > 0L &&
                    leaseId > 0L &&
                    leaseEpoch > 0L &&
                    ownerGeneration >= 0L &&
                    physicalDisplayId >= 0L
                ) {
                    LeaseToken(
                        shellSession = shellSession,
                        leaseId = leaseId,
                        leaseEpoch = leaseEpoch,
                        ownerGeneration = ownerGeneration,
                        physicalDisplayId = physicalDisplayId,
                    )
                } else {
                    null
                }
    }

    data class Acceptance(
        val accepted: Boolean,
        val reason: String,
        val token: LeaseToken?,
        val snapshot: Snapshot?,
    )

    private var connectionEpoch = 0L
    private var shellSession = 0L
    private var lastShellRevision = 0L
    private var currentToken: LeaseToken? = null
    private var currentSnapshot: Snapshot? = null

    val acceptedToken: LeaseToken?
        get() = currentToken

    val acceptedSnapshot: Snapshot?
        get() = currentSnapshot

    fun onConnectionEpoch(
        epoch: Long,
    ) {
        if (epoch == connectionEpoch) return
        connectionEpoch = epoch
        shellSession = 0L
        lastShellRevision = 0L
        currentToken = null
        currentSnapshot = null
    }

    fun invalidate() {
        connectionEpoch += 1L
        shellSession = 0L
        lastShellRevision = 0L
        currentToken = null
        currentSnapshot = null
    }

    fun accept(
        snapshot: Snapshot,
    ): Acceptance {
        if (snapshot.connectionEpoch != connectionEpoch) {
            return rejected("stale-connection-epoch")
        }
        if (snapshot.shellSession <= 0L) {
            return rejected("invalid-shell-session")
        }
        if (snapshot.shellRevision <= 0L) {
            return rejected("invalid-shell-revision")
        }

        if (
            shellSession != 0L &&
            snapshot.shellSession != shellSession
        ) {
            // A different shell process is authoritative. Forget all old authority
            // before considering its first revision.
            shellSession = 0L
            lastShellRevision = 0L
            currentToken = null
            currentSnapshot = null
        }

        if (snapshot.shellRevision <= lastShellRevision) {
            return rejected("stale-shell-revision")
        }

        val token = snapshot.token
        if (snapshot.leaseState != "IDLE" && token == null) {
            return rejected("invalid-non-idle-token")
        }

        shellSession = snapshot.shellSession
        lastShellRevision = snapshot.shellRevision
        currentToken = token
        currentSnapshot = snapshot

        return Acceptance(
            accepted = true,
            reason = "accepted",
            token = token,
            snapshot = snapshot,
        )
    }

    fun ownsExactly(
        token: LeaseToken,
    ): Boolean =
        currentToken == token

    private fun rejected(
        reason: String,
    ): Acceptance =
        Acceptance(
            accepted = false,
            reason = reason,
            token = currentToken,
            snapshot = currentSnapshot,
        )
}
