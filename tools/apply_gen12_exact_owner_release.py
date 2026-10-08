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


BRIDGE = "app/src/full/java/com/duoopen/shell/ShizukuBridge.kt"
SERVICE = "app/src/full/java/com/duoopen/shell/DuoShellService.kt"
COORDINATOR = "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"

# Gen4 already carries owner identity on the wire. Stop discarding it for RETURN.
replace_once(
    BRIDGE,
    '''    internal fun returnCoverPanelGen4(
        serviceEpoch: Long,
        intentSequence: Long,
        reason: String,
    ): Bundle? =
        coverPanelGen4(
            operation = 4,
            serviceEpoch = serviceEpoch,
            closeCycleId = 0L,
            transitionGeneration = -1L,
            intentSequence = intentSequence,
            reason = reason,
        )
''',
    '''    internal fun returnCoverPanelGen4(
        serviceEpoch: Long,
        closeCycleId: Long,
        transitionGeneration: Long,
        intentSequence: Long,
        reason: String,
    ): Bundle? =
        coverPanelGen4(
            operation = 4,
            serviceEpoch = serviceEpoch,
            closeCycleId = closeCycleId,
            transitionGeneration = transitionGeneration,
            intentSequence = intentSequence,
            reason = reason,
        )
''',
)

# Feed the parsed owner identity into the daemon return path.
replace_once(
    SERVICE,
    '''            4 ->
                returnCoverPanelGen4(
                    serviceEpoch = serviceEpoch,
                    intentSequence = intentSequence,
                    reason = reason,
                )
''',
    '''            4 ->
                returnCoverPanelGen4(
                    serviceEpoch = serviceEpoch,
                    closeCycleId = closeCycleId,
                    transitionGeneration = transitionGeneration,
                    intentSequence = intentSequence,
                    reason = reason,
                )
''',
)

replace_once(
    SERVICE,
    '''    private fun returnCoverPanelGen4(
        serviceEpoch: Long,
        intentSequence: Long,
        reason: String,
    ): Bundle {
        gen4PanelAuthority.beginRelease(
            serviceEpoch = serviceEpoch,
            intentSequence = intentSequence,
        )

        val cleanup =
            normalizeGen4SecondaryRoute(
                "return:$reason"
            )

        gen4PanelAuthority.completeRelease(
            intentSequence = intentSequence,
            success = cleanup.ok,
            nativeCover = cleanup.nativeCover,
        )

        return gen4PanelBundle(
            operation = "return:$reason",
            ok = cleanup.ok,
            decision = if (cleanup.ok) "native-authority-restored" else "release-pending",
            error = cleanup.error,
        )
    }
''',
    '''    private fun returnCoverPanelGen4(
        serviceEpoch: Long,
        closeCycleId: Long,
        transitionGeneration: Long,
        intentSequence: Long,
        reason: String,
    ): Bundle {
        val expectedOwner =
            Fold7PanelAuthorityGen4.Owner(
                serviceEpoch = serviceEpoch,
                closeCycleId = closeCycleId,
                transitionGeneration = transitionGeneration,
            )

        val release =
            gen4PanelAuthority.beginReleaseOwned(
                serviceEpoch = serviceEpoch,
                intentSequence = intentSequence,
                expectedOwner = expectedOwner,
            )

        if (!release.accepted) {
            return gen4PanelBundle(
                operation = "return:$reason",
                ok = false,
                stale = release.stale,
                decision = release.reason,
            )
        }

        val cleanup =
            normalizeGen4SecondaryRoute(
                "return:$reason"
            )

        gen4PanelAuthority.completeRelease(
            intentSequence = intentSequence,
            success = cleanup.ok,
            nativeCover = cleanup.nativeCover,
        )

        return gen4PanelBundle(
            operation = "return:$reason",
            ok = cleanup.ok,
            decision = if (cleanup.ok) "native-authority-restored" else "release-pending",
            error = cleanup.error,
        )
    }
''',
)

# Reconcile is the deliberate force/current-owner recovery path; recover its owner
# from daemon state rather than bypassing the compare-and-release rule.
replace_once(
    SERVICE,
    '''            Fold7PanelAuthorityGen4.Phase.RELEASE_PENDING ->
                returnCoverPanelGen4(
                    serviceEpoch = serviceEpoch,
                    intentSequence = intentSequence,
                    reason = "reconcile:$reason",
                )
''',
    '''            Fold7PanelAuthorityGen4.Phase.RELEASE_PENDING -> {
                val owner =
                    before.owner
                        ?: return gen4PanelBundle(
                            operation = "reconcile:$reason",
                            ok = false,
                            decision = "release-pending-without-owner",
                        )

                returnCoverPanelGen4(
                    serviceEpoch = owner.serviceEpoch,
                    closeCycleId = owner.closeCycleId,
                    transitionGeneration = owner.transitionGeneration,
                    intentSequence = intentSequence,
                    reason = "reconcile:$reason",
                )
            }
''',
)

# Track the exact owner a transition is allowed to release. In-flight ownership is
# preferred over an older accepted receipt because a new PREPARE may not have
# returned its snapshot yet.
replace_once(
    COORDINATOR,
    '''    @Volatile private var prewarmInFlightGeneration = -1L
    @Volatile private var prewarmInFlightConnectionEpoch = -1L
''',
    '''    @Volatile private var prewarmInFlightGeneration = -1L
    @Volatile private var prewarmInFlightConnectionEpoch = -1L
    @Volatile private var prewarmInFlightOwner: CoverReleaseOwner? = null
''',
)

replace_once(
    COORDINATOR,
    '''    fun release(reason: String) {
        armRequested = false
        renderOwnershipArmed = false
        gen2.cancelActiveCycle()
        val generation = controller.generation

        hideMirror(
            generation = generation,
            reason = reason,
            stopShellMirror = true,
        )

        releaseCoverLease(reason)
    }
''',
    '''    fun release(reason: String) {
        armRequested = false
        renderOwnershipArmed = false
        val releaseOwner = currentCoverReleaseOwner()
        gen2.cancelActiveCycle()
        val generation = controller.generation

        hideMirror(
            generation = generation,
            reason = reason,
            stopShellMirror = true,
        )

        releaseCoverLease(reason, releaseOwner)
    }
''',
)

# Destroy is an explicit service-lifetime cleanup, so use RECONCILE (operation 5)
# rather than pretending it owns an arbitrary transition generation.
replace_once(
    COORDINATOR,
    '''                        ShizukuBridge.returnCoverPanelGen4(
                            serviceEpoch = serviceEpoch,
                            intentSequence = intentSequence,
                            reason = "destroy",
                        )
''',
    '''                        ShizukuBridge.reconcileCoverPanelGen4(
                            serviceEpoch = serviceEpoch,
                            intentSequence = intentSequence,
                            reason = "destroy",
                        )
''',
)

replace_once(
    COORDINATOR,
    '''        prewarmInFlightGeneration = -1L
        prewarmInFlightConnectionEpoch = -1L

        gen2.coverAuthority.onConnectionEpoch(
''',
    '''        prewarmInFlightGeneration = -1L
        prewarmInFlightConnectionEpoch = -1L
        prewarmInFlightOwner = null

        gen2.coverAuthority.onConnectionEpoch(
''',
)

replace_once(
    COORDINATOR,
    '''        prewarmInFlightGeneration = generation
        prewarmInFlightConnectionEpoch = requestConnectionEpoch

        val intentSequence = panelIntentSequence.incrementAndGet()
''',
    '''        prewarmInFlightGeneration = generation
        prewarmInFlightConnectionEpoch = requestConnectionEpoch
        prewarmInFlightOwner =
            CoverReleaseOwner(
                serviceEpoch = cycle.serviceEpoch,
                closeCycleId = cycle.closeCycleId,
                transitionGeneration = generation,
            )

        val intentSequence = panelIntentSequence.incrementAndGet()
''',
)

replace_once(
    COORDINATOR,
    '''                if (
                    prewarmInFlightGeneration == generation &&
                    prewarmInFlightConnectionEpoch == requestConnectionEpoch
                ) {
                    prewarmInFlightGeneration = -1L
                    prewarmInFlightConnectionEpoch = -1L
                }
''',
    '''                if (
                    prewarmInFlightGeneration == generation &&
                    prewarmInFlightConnectionEpoch == requestConnectionEpoch
                ) {
                    prewarmInFlightGeneration = -1L
                    prewarmInFlightConnectionEpoch = -1L
                    prewarmInFlightOwner = null
                }
''',
)

replace_once(
    COORDINATOR,
    '''        // Hiding is local and immediate. The privileged release is best effort
        // and resolves a fresh current cover route internally.
        hideMirror(
            generation = generation,
            reason = "release-secondary",
            stopShellMirror = true,
        )

        releaseCoverLease("secondary-release:generation=$generation")
''',
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
)

replace_once(
    COORDINATOR,
    '''    private fun releaseCoverLease(
        reason: String,
    ) {
        if (!ShizukuBridge.ready) return
        val requestConnectionEpoch = ShizukuBridge.connectionEpoch
        val intentSequence = panelIntentSequence.incrementAndGet()

        scope.launch(Dispatchers.IO) {
            val result =
                ShizukuBridge.returnCoverPanelGen4(
                    serviceEpoch = serviceEpoch,
                    intentSequence = intentSequence,
                    reason = reason,
                )

            handler.post {
                if (requestConnectionEpoch != ShizukuBridge.connectionEpoch) {
                    return@post
                }

                val acceptance =
                    acceptCoverLeaseSnapshot(
                        result = result,
                        connectionEpoch = requestConnectionEpoch,
                        reason = "gen4-return:$reason",
                    )

                val pending =
                    acceptance.accepted &&
                        acceptance.snapshot?.leaseState == "RELEASE_PENDING"

                if (pending && gen4ReleaseRetryCount < MAX_GEN4_RELEASE_RETRIES) {
                    gen4ReleaseRetryCount += 1
                    handler.postDelayed(
                        {
                            reconcileCoverLease(
                                "release-retry-$gen4ReleaseRetryCount:$reason"
                            )
                        },
                        GEN4_RELEASE_RETRY_MS,
                    )
                } else if (!pending) {
                    gen4ReleaseRetryCount = 0
                }
            }
        }
    }
''',
    '''    private data class CoverReleaseOwner(
        val serviceEpoch: Long,
        val closeCycleId: Long,
        val transitionGeneration: Long,
    )

    private fun currentCoverReleaseOwner(): CoverReleaseOwner? {
        val inFlight = prewarmInFlightOwner
        if (
            inFlight != null &&
            prewarmInFlightConnectionEpoch == ShizukuBridge.connectionEpoch &&
            inFlight.transitionGeneration == prewarmInFlightGeneration
        ) {
            return inFlight
        }

        val token = gen2.coverAuthority.acceptedToken ?: return null
        if (
            token.ownerServiceEpoch <= 0L ||
            token.ownerCloseCycleId <= 0L ||
            token.ownerGeneration < 0L
        ) {
            return null
        }

        return CoverReleaseOwner(
            serviceEpoch = token.ownerServiceEpoch,
            closeCycleId = token.ownerCloseCycleId,
            transitionGeneration = token.ownerGeneration,
        )
    }

    private fun releaseCoverLease(
        reason: String,
        expectedOwner: CoverReleaseOwner? = currentCoverReleaseOwner(),
    ) {
        if (!ShizukuBridge.ready) return

        if (expectedOwner == null) {
            DuoDiagnostics.event(
                "gen4-authority",
                "return skipped no-owner reason=$reason",
            )
            return
        }

        val requestConnectionEpoch = ShizukuBridge.connectionEpoch

        scope.launch(Dispatchers.IO) {
            if (
                requestConnectionEpoch != ShizukuBridge.connectionEpoch ||
                !ShizukuBridge.ready
            ) {
                return@launch
            }

            val latestOwner = currentCoverReleaseOwner()
            if (latestOwner != null && latestOwner != expectedOwner) {
                DuoDiagnostics.event(
                    "gen4-authority",
                    "return stale-before-rpc reason=$reason expected=$expectedOwner latest=$latestOwner",
                )
                return@launch
            }

            // Allocate ordering identity at execution time, not queue time. A stale
            // worker that is discarded above therefore cannot consume a newer RPC id.
            val intentSequence = panelIntentSequence.incrementAndGet()
            val result =
                ShizukuBridge.returnCoverPanelGen4(
                    serviceEpoch = expectedOwner.serviceEpoch,
                    closeCycleId = expectedOwner.closeCycleId,
                    transitionGeneration = expectedOwner.transitionGeneration,
                    intentSequence = intentSequence,
                    reason = reason,
                )

            handler.post {
                if (requestConnectionEpoch != ShizukuBridge.connectionEpoch) {
                    return@post
                }

                val acceptance =
                    acceptCoverLeaseSnapshot(
                        result = result,
                        connectionEpoch = requestConnectionEpoch,
                        reason = "gen4-return:$reason",
                    )

                val pending =
                    acceptance.accepted &&
                        acceptance.snapshot?.leaseState == "RELEASE_PENDING"

                if (pending && gen4ReleaseRetryCount < MAX_GEN4_RELEASE_RETRIES) {
                    gen4ReleaseRetryCount += 1
                    handler.postDelayed(
                        {
                            reconcileCoverLease(
                                "release-retry-$gen4ReleaseRetryCount:$reason"
                            )
                        },
                        GEN4_RELEASE_RETRY_MS,
                    )
                } else if (!pending) {
                    gen4ReleaseRetryCount = 0
                }
            }
        }
    }
''',
)

print("Gen12 exact-owner release patch applied successfully")
