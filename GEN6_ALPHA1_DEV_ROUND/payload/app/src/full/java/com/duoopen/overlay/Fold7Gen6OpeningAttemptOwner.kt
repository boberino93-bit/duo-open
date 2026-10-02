package com.duoopen.overlay

/**
 * Gen6 Slice A opening-attempt identity only.
 *
 * This owner has no hinge angle, display-route, panel-power, task-migration,
 * renderer, or native-handoff authority. It exists only to assign one stable
 * attempt id to an opening that begins from a validated wake hint and to attach
 * later semantic-generation telemetry when the existing controller accepts it.
 */
internal class Fold7Gen6OpeningAttemptOwner(
    private val serviceEpoch: Long,
) {
    data class Attempt(
        val id: Long,
        val serviceEpoch: Long,
        val startedUptimeMs: Long,
        val previousStateId: Int,
        val currentStateId: Int,
        val semanticGeneration: Long? = null,
    )

    data class Terminal(
        val attempt: Attempt,
        val reason: String,
        val finishedUptimeMs: Long,
    )

    private var sequence = 0L
    private var active: Attempt? = null

    fun current(): Attempt? = active

    fun onWakeHint(
        previousStateId: Int,
        currentStateId: Int,
        nowUptimeMs: Long,
    ): Attempt? {
        if (previousStateId == currentStateId || active != null) return null
        val created =
            Attempt(
                id = ++sequence,
                serviceEpoch = serviceEpoch,
                startedUptimeMs = nowUptimeMs,
                previousStateId = previousStateId,
                currentStateId = currentStateId,
            )
        active = created
        return created
    }

    fun markSemanticAccepted(
        transitionGeneration: Long,
    ): Attempt? {
        val current = active ?: return null
        if (current.semanticGeneration == transitionGeneration) return null
        val updated = current.copy(semanticGeneration = transitionGeneration)
        active = updated
        return updated
    }

    fun finish(
        reason: String,
        nowUptimeMs: Long,
    ): Terminal? {
        val current = active ?: return null
        active = null
        return Terminal(current, reason, nowUptimeMs)
    }
}
