package com.duoopen.overlay

/**
 * Exact ownership for one content/host presentation attempt.
 *
 * Callback ordering is not assumed. Each callback must carry the immutable
 * Identity that was captured when the attempt was created; stale callbacks are
 * rejected after host/cycle invalidation or a newer attempt.
 */
internal class Fold7PresentationLease {
    enum class RenderPath {
        FROZEN_VIEW,
        LIVE_MIRROR,
    }

    data class Identity(
        val serviceEpoch: Long,
        val closeCycleId: Long,
        val contentLeaseId: Long,
        val hostEpoch: Long,
        val attemptSequence: Long,
        val renderPath: RenderPath,
    )

    data class Snapshot(
        val identity: Identity,
        val drewContent: Boolean,
        val frameCommitted: Boolean,
        val transactionCommitted: Boolean,
        val presented: Boolean,
    )

    private var hostEpoch = 0L
    private var nextAttemptSequence = 0L
    private var current: Snapshot? = null

    fun openHost(): Long {
        hostEpoch += 1L
        current = null
        return hostEpoch
    }

    fun invalidateHost(
        expectedHostEpoch: Long? = null,
    ) {
        if (
            expectedHostEpoch != null &&
            expectedHostEpoch != hostEpoch
        ) {
            return
        }
        hostEpoch += 1L
        current = null
    }

    fun begin(
        serviceEpoch: Long,
        closeCycleId: Long,
        contentLeaseId: Long,
        renderPath: RenderPath,
    ): Identity {
        val identity =
            Identity(
                serviceEpoch = serviceEpoch,
                closeCycleId = closeCycleId,
                contentLeaseId = contentLeaseId,
                hostEpoch = hostEpoch,
                attemptSequence = ++nextAttemptSequence,
                renderPath = renderPath,
            )
        current =
            Snapshot(
                identity = identity,
                drewContent = false,
                frameCommitted = false,
                transactionCommitted = false,
                presented = false,
            )
        return identity
    }

    fun onDraw(
        identity: Identity,
    ): Boolean = update(identity) { copy(drewContent = true) }

    fun onFrameCommit(
        identity: Identity,
    ): Boolean = update(identity) { copy(frameCommitted = true) }

    fun onTransactionCommit(
        identity: Identity,
    ): Boolean = update(identity) { copy(transactionCommitted = true) }

    fun onPresented(
        identity: Identity,
    ): Boolean = update(identity) { copy(presented = true) }

    fun invalidateAttempt(
        expected: Identity? = null,
    ) {
        val existing = current ?: return
        if (expected != null && existing.identity != expected) return
        current = null
    }

    fun snapshot(): Snapshot? = current

    fun isCurrent(
        identity: Identity,
    ): Boolean =
        current?.identity == identity &&
            identity.hostEpoch == hostEpoch

    private fun update(
        identity: Identity,
        transform: Snapshot.() -> Snapshot,
    ): Boolean {
        val existing = current ?: return false
        if (
            existing.identity != identity ||
            identity.hostEpoch != hostEpoch
        ) {
            return false
        }
        current = existing.transform()
        return true
    }
}
