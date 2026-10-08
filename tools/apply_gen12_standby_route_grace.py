#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, found {count}")
    file.write_text(text.replace(old, new, 1))
    print(f"patched {path}")


COORDINATOR = "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"

replace_once(
    COORDINATOR,
    '''    private val mirrorSequence = AtomicLong(0L)
    private val mirrorLeaseCounter = AtomicLong(0L)
    private val panelIntentSequence = AtomicLong(0L)
''',
    '''    private val mirrorSequence = AtomicLong(0L)
    private val mirrorLeaseCounter = AtomicLong(0L)
    private val panelIntentSequence = AtomicLong(0L)
    private val standbyRouteLease = Fold7StandbyRouteLease()
''',
)

replace_once(
    COORDINATOR,
    '''    fun arm() {
        armRequested = true
        destroyed = false
        renderOwnershipArmed = false

        if (!ShizukuBridge.ready) {
''',
    '''    fun arm() {
        armRequested = true
        destroyed = false
        renderOwnershipArmed = false
        cancelStandbyRoute("arm")

        if (!ShizukuBridge.ready) {
''',
)

replace_once(
    COORDINATOR,
    '''    fun release(reason: String) {
        armRequested = false
        renderOwnershipArmed = false
        val releaseOwner = currentCoverReleaseOwner()
        gen2.cancelActiveCycle()
''',
    '''    fun release(reason: String) {
        armRequested = false
        renderOwnershipArmed = false
        val releaseOwner = currentCoverReleaseOwner()
        cancelStandbyRoute("manual-release:$reason")
        gen2.cancelActiveCycle()
''',
)

replace_once(
    COORDINATOR,
    '''    fun destroy() {
        destroyed = true
        armRequested = false
        renderOwnershipArmed = false
        hideMirror(
''',
    '''    fun destroy() {
        destroyed = true
        armRequested = false
        renderOwnershipArmed = false
        cancelStandbyRoute("destroy")
        hideMirror(
''',
)

replace_once(
    COORDINATOR,
    '''        gen4AdmissionInFlight = false
        gen4StartupRetryCount = 0

        hideMirror(
''',
    '''        gen4AdmissionInFlight = false
        gen4StartupRetryCount = 0
        cancelStandbyRoute("privilege-unavailable")

        hideMirror(
''',
)

replace_once(
    COORDINATOR,
    '''        val releaseOwner = currentCoverReleaseOwner()

        // Hiding is local and immediate. The privileged release is exact-owner
        // compare-and-release so an obsolete transition cannot tear down a newer route.
        hideMirror(
            generation = generation,
            reason = "release-secondary",
            stopShellMirror = true,
        )

        releaseCoverLease(
            reason = "secondary-release:generation=$generation",
            expectedOwner = releaseOwner,
        )
''',
    '''        val releaseOwner = currentCoverReleaseOwner()

        // Visibility ends immediately. Opening-side reversals retain the exact
        // old route hidden for a short grace so a quick re-close can adopt it
        // instead of paying a cold Samsung route-publication penalty again.
        hideMirror(
            generation = generation,
            reason = "release-secondary",
            stopShellMirror = true,
        )

        val openingSide =
            controller.state in setOf(
                Fold7ContinuityController.State.INNER_HANDOFF,
                Fold7ContinuityController.State.OPEN_INNER,
            )

        if (openingSide && releaseOwner != null) {
            retainStandbyRoute(
                owner = releaseOwner,
                generation = generation,
            )
            return
        }

        cancelStandbyRoute("immediate-secondary-release:generation=$generation")
        releaseCoverLease(
            reason = "secondary-release:generation=$generation",
            expectedOwner = releaseOwner,
        )
''',
)

replace_once(
    COORDINATOR,
    '''    private data class CoverReleaseOwner(
        val serviceEpoch: Long,
        val closeCycleId: Long,
        val transitionGeneration: Long,
    )

    private fun currentCoverReleaseOwner(): CoverReleaseOwner? {
''',
    '''    private data class CoverReleaseOwner(
        val serviceEpoch: Long,
        val closeCycleId: Long,
        val transitionGeneration: Long,
    )

    private fun CoverReleaseOwner.toStandbyOwner() =
        Fold7StandbyRouteLease.Owner(
            serviceEpoch = serviceEpoch,
            closeCycleId = closeCycleId,
            transitionGeneration = transitionGeneration,
        )

    private fun Fold7StandbyRouteLease.Owner.toReleaseOwner() =
        CoverReleaseOwner(
            serviceEpoch = serviceEpoch,
            closeCycleId = closeCycleId,
            transitionGeneration = transitionGeneration,
        )

    private fun retainStandbyRoute(
        owner: CoverReleaseOwner,
        generation: Long,
    ) {
        val ticket = standbyRouteLease.retain(owner.toStandbyOwner())

        DuoDiagnostics.event(
            "gen4-standby",
            "retained generation=$generation owner=$owner graceMs=$COVER_STANDBY_GRACE_MS",
        )

        handler.postDelayed(
            {
                if (destroyed) return@postDelayed

                if (!standbyRouteLease.consumeExpiry(ticket)) {
                    DuoDiagnostics.event(
                        "gen4-standby",
                        "expiry inert ticket=${ticket.epoch} owner=${ticket.owner}",
                    )
                    return@postDelayed
                }

                val expectedOwner = ticket.owner.toReleaseOwner()
                val latestOwner = currentCoverReleaseOwner()
                if (latestOwner != null && latestOwner != expectedOwner) {
                    DuoDiagnostics.event(
                        "gen4-standby",
                        "expiry superseded expected=$expectedOwner latest=$latestOwner",
                    )
                    return@postDelayed
                }

                DuoDiagnostics.event(
                    "gen4-standby",
                    "expired owner=$expectedOwner; returning native authority",
                )
                releaseCoverLease(
                    reason = "standby-expired:generation=$generation",
                    expectedOwner = expectedOwner,
                )
            },
            COVER_STANDBY_GRACE_MS,
        )
    }

    private fun cancelStandbyRoute(
        reason: String,
    ) {
        val cancelled = standbyRouteLease.cancel() ?: return
        DuoDiagnostics.event(
            "gen4-standby",
            "cancelled reason=$reason owner=$cancelled",
        )
    }

    private fun currentCoverReleaseOwner(): CoverReleaseOwner? {
''',
)

replace_once(
    COORDINATOR,
    '''        val token = gen2.coverAuthority.acceptedToken ?: return null
''',
    '''        standbyRouteLease.owner()?.let { retained ->
            return retained.toReleaseOwner()
        }

        val token = gen2.coverAuthority.acceptedToken ?: return null
''',
)

replace_once(
    COORDINATOR,
    '''        cycleChange.started?.let { cycle ->
            DuoDiagnostics.event(
''',
    '''        cycleChange.started?.let { cycle ->
            cancelStandbyRoute(
                "new-close:cycle=${cycle.closeCycleId}:generation=${transition.generation}"
            )
            DuoDiagnostics.event(
''',
)

replace_once(
    COORDINATOR,
    '''        const val READINESS_WATCHDOG_MS = 80L
        const val FROZEN_FRAME_MAX_AGE_MS = 10_000L
''',
    '''        const val READINESS_WATCHDOG_MS = 80L
        const val COVER_STANDBY_GRACE_MS = 1_800L
        const val FROZEN_FRAME_MAX_AGE_MS = 10_000L
''',
)

print("Gen12 standby route grace patch applied successfully")
