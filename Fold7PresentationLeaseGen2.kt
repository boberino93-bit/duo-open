package rnd.fold7

enum class PresentationPath {
    FROZEN_VIEW,
    LIVE_MIRROR,
}

data class PresentationIdentity(
    val serviceEpoch: Long,
    val closeCycleId: Long,
    val hostEpoch: Long,
    val contentLeaseId: Long,
    val attemptSequence: Long,
)

data class PresentationSnapshot(
    val identity: PresentationIdentity,
    val path: PresentationPath,
    val drawObserved: Boolean,
    val frameCommitted: Boolean,
    val transactionCommitted: Boolean,
    val transactionPresented: Boolean,
    val presentTimeNs: Long?,
    val confirmed: Boolean,
    val cancelled: Boolean,
)

/**
 * Reduced model of the CURRENT frozen-frame success semantic: binding a valid
 * bitmap is treated as success immediately after VISIBLE + invalidate(), with
 * no proof that a frame containing that bitmap committed or was presented.
 */
class BaselineFrozenPresentationModel {
    var bound = false
        private set

    fun bindValidBitmap(): Boolean {
        bound = true
        return true
    }
}

/**
 * Reduced model of the CURRENT Transition Lab correlation semantic: a late
 * transaction callback is correlated against the latest global hinge/context,
 * not identity captured when the transaction was instrumented.
 */
class BaselineLatestContextCorrelation {
    var currentGeneration: Long = -1L
    var lastAttributedGeneration: Long? = null
        private set

    fun onTransactionCallback() {
        lastAttributedGeneration = currentGeneration
    }
}

/**
 * Generation-2 presentation ownership model.
 *
 * Frozen View content requires three facts from the same attempt before the
 * attempt is presentation-confirmed:
 *  1. the intended content actually participated in onDraw;
 *  2. ViewTreeObserver frame-commit confirms that rendered frame was submitted
 *     to the swap chain;
 *  3. an identity-bearing SurfaceControl marker transaction, queued via
 *     AttachedSurfaceControl.applyTransactionOnDraw(), reaches transaction
 *     completion/presentation.
 *
 * Live mirror content is itself a SurfaceControl transaction path, so the
 * identity-bearing transaction-presented callback is sufficient.
 *
 * All callbacks are idempotent. Callbacks for a non-current identity can be
 * logged by the caller, but cannot mutate current presentation authority.
 */
class PresentationLeaseStore(
    private val serviceEpoch: Long,
) {
    private data class MutableAttempt(
        val identity: PresentationIdentity,
        val path: PresentationPath,
        var drawObserved: Boolean = false,
        var frameCommitted: Boolean = false,
        var transactionCommitted: Boolean = false,
        var transactionPresented: Boolean = false,
        var presentTimeNs: Long? = null,
        var confirmed: Boolean = false,
        var cancelled: Boolean = false,
    )

    private var active: MutableAttempt? = null
    private var lastAttemptSequence = Long.MIN_VALUE

    var staleCallbackCount: Long = 0L
        private set

    var confirmedCount: Long = 0L
        private set

    fun begin(
        identity: PresentationIdentity,
        path: PresentationPath,
    ): Boolean {
        if (identity.serviceEpoch != serviceEpoch) return false
        if (identity.attemptSequence <= lastAttemptSequence) return false
        active?.cancelled = true
        active = MutableAttempt(identity = identity, path = path)
        lastAttemptSequence = identity.attemptSequence
        return true
    }

    fun onDraw(identity: PresentationIdentity): Boolean =
        mutate(identity) { attempt ->
            if (attempt.path == PresentationPath.FROZEN_VIEW) {
                attempt.drawObserved = true
            }
        }

    fun onFrameCommitted(identity: PresentationIdentity): Boolean =
        mutate(identity) { attempt ->
            if (attempt.path == PresentationPath.FROZEN_VIEW) {
                attempt.frameCommitted = true
            }
        }

    fun onTransactionCommitted(identity: PresentationIdentity): Boolean =
        mutate(identity) { attempt ->
            attempt.transactionCommitted = true
        }

    fun onTransactionPresented(
        identity: PresentationIdentity,
        presentTimeNs: Long? = null,
    ): Boolean =
        mutate(identity) { attempt ->
            attempt.transactionPresented = true
            if (presentTimeNs != null) {
                attempt.presentTimeNs = presentTimeNs
            }
        }

    fun cancel(identity: PresentationIdentity): Boolean =
        mutate(identity, evaluate = false) { attempt ->
            attempt.cancelled = true
            attempt.confirmed = false
        }

    fun invalidateCurrent() {
        active?.apply {
            cancelled = true
            confirmed = false
        }
        active = null
    }

    fun snapshot(): PresentationSnapshot? =
        active?.let { attempt ->
            PresentationSnapshot(
                identity = attempt.identity,
                path = attempt.path,
                drawObserved = attempt.drawObserved,
                frameCommitted = attempt.frameCommitted,
                transactionCommitted = attempt.transactionCommitted,
                transactionPresented = attempt.transactionPresented,
                presentTimeNs = attempt.presentTimeNs,
                confirmed = attempt.confirmed,
                cancelled = attempt.cancelled,
            )
        }

    private inline fun mutate(
        identity: PresentationIdentity,
        evaluate: Boolean = true,
        block: (MutableAttempt) -> Unit,
    ): Boolean {
        val attempt = active
        if (
            attempt == null ||
            attempt.identity != identity ||
            identity.serviceEpoch != serviceEpoch ||
            attempt.cancelled
        ) {
            staleCallbackCount++
            return false
        }

        val wasConfirmed = attempt.confirmed
        block(attempt)
        if (evaluate) evaluateConfirmation(attempt)
        if (!wasConfirmed && attempt.confirmed) confirmedCount++
        return true
    }

    private fun evaluateConfirmation(attempt: MutableAttempt) {
        if (attempt.cancelled || attempt.confirmed) return

        attempt.confirmed =
            when (attempt.path) {
                PresentationPath.FROZEN_VIEW ->
                    attempt.drawObserved &&
                        attempt.frameCommitted &&
                        attempt.transactionPresented

                PresentationPath.LIVE_MIRROR ->
                    attempt.transactionPresented
            }
    }
}
