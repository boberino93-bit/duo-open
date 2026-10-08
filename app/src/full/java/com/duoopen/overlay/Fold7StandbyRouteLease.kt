package com.duoopen.overlay

/**
 * Tiny race gate for retaining an already-prepared Fold7 cover route while an
 * opening reversal settles.
 *
 * The retained owner is exact and immutable. A newer close, manual release,
 * privilege loss, or destroy cancels the ticket by advancing [epoch]. A late
 * timer can therefore never acquire authority over a replacement route.
 */
internal class Fold7StandbyRouteLease {
    data class Owner(
        val serviceEpoch: Long,
        val closeCycleId: Long,
        val transitionGeneration: Long,
    )

    data class Ticket(
        val epoch: Long,
        val owner: Owner,
    )

    private var epoch = 0L
    private var retainedOwner: Owner? = null

    @Synchronized
    fun retain(owner: Owner): Ticket {
        require(owner.serviceEpoch > 0L)
        require(owner.closeCycleId > 0L)
        require(owner.transitionGeneration >= 0L)

        epoch += 1L
        retainedOwner = owner
        return Ticket(epoch = epoch, owner = owner)
    }

    @Synchronized
    fun cancel(): Owner? {
        val previous = retainedOwner
        epoch += 1L
        retainedOwner = null
        return previous
    }

    @Synchronized
    fun owner(): Owner? = retainedOwner

    @Synchronized
    fun isCurrent(ticket: Ticket): Boolean =
        ticket.epoch == epoch &&
            retainedOwner == ticket.owner

    /**
     * Consumes an expiry ticket exactly once. The caller may perform the
     * privileged exact-owner release only when this returns true.
     */
    @Synchronized
    fun consumeExpiry(ticket: Ticket): Boolean {
        if (!isCurrentLocked(ticket)) return false
        epoch += 1L
        retainedOwner = null
        return true
    }

    private fun isCurrentLocked(ticket: Ticket): Boolean =
        ticket.epoch == epoch &&
            retainedOwner == ticket.owner
}
