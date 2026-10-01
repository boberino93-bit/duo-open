#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def replace_once(path, old, new, label):
    p = ROOT / path
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor in {p}, found {count}")
    p.write_text(text.replace(old, new, 1))
    print(f"patched {label}: {p}")

shell = "app/src/full/java/com/duoopen/shell/DuoShellService.kt"
gradle = "app/build.gradle.kts"

old = r'''    private fun prewarmCoverLeaseV2(
        ownerGeneration: Long,
    ): Bundle {
        if (ownerGeneration < 0L) {
            return coverLeaseBundle("prewarm", false)
        }

        val actions = coverPanelLease.beginPrewarm(ownerGeneration)
        var physicalOk = true

        for (action in actions) {
            if (action is Fold7CoverPanelLease.Action.PowerPhysicalCover) {
                val physicalId = resolveFold7CoverPhysicalDisplayId(-1)
                val (powered, _) = setPhysicalPowerNormal(physicalId)
                physicalOk = powered
                val followUp = coverPanelLease.onPhysicalPrewarmResult(
                    action.leaseId,
                    action.epoch,
                    powered,
                    physicalId.takeIf { it >= 0L },
                    coverLeaseTopology(),
                )
                executeCoverLeaseActions(followUp)
            }
        }

        val snapshot = coverPanelLease.snapshot()
        val adopted = actions.isEmpty() && snapshot.state != Fold7CoverPanelLease.State.IDLE
        return coverLeaseBundle("prewarm", physicalOk || adopted)
    }
'''

new = r'''    private data class CoverRouteActivation(
        val logicalId: Int,
        val physicalId: Long,
        val routeEnabled: Boolean,
        val logicalPowered: Boolean,
        val stillSafe: Boolean,
        val error: String?,
    ) {
        val ok: Boolean
            get() =
                stillSafe &&
                    (routeEnabled || logicalPowered)
    }

    /**
     * Physical NORMAL is only the first half of a Fold7 cover prewarm.
     *
     * Samsung can expose the 1080x2520 cover as a disabled logical route after
     * the physical panel wakes. The legacy working path immediately enabled
     * that route and requested STATE_ON. Gen2 ownership originally stopped
     * after physical NORMAL, which left the lease HELD but gave Android no
     * active destination for DisplayMirrorHost.
     *
     * Resolve the logical route fresh, require that it still maps to the exact
     * physical cover owned by the lease, enable it, re-resolve/revalidate, then
     * request logical STATE_ON. No logical display id is retained.
     */
    private fun activateOwnedCoverRouteAfterPhysicalWake(
        ownedPhysicalId: Long,
    ): CoverRouteActivation {
        if (ownedPhysicalId < 0L) {
            return CoverRouteActivation(
                logicalId = -1,
                physicalId = ownedPhysicalId,
                routeEnabled = false,
                logicalPowered = false,
                stillSafe = false,
                error = "owned physical cover id unavailable",
            )
        }

        var route: Pair<Int, Long>? = null

        // Give Samsung a small bounded window to publish the disabled logical
        // route after physical NORMAL. This runs on the serialized cover
        // mutation executor, never on the app main thread.
        for (attempt in 0 until 6) {
            val candidate =
                runCatching {
                    directCoverRoute()
                }.getOrNull()

            if (
                candidate != null &&
                candidate.first != Display.DEFAULT_DISPLAY &&
                candidate.second == ownedPhysicalId
            ) {
                route = candidate
                break
            }

            if (attempt < 5) {
                Thread.sleep(8L)
            }
        }

        val resolved =
            route
                ?: return CoverRouteActivation(
                    logicalId = -1,
                    physicalId = ownedPhysicalId,
                    routeEnabled = false,
                    logicalPowered = false,
                    stillSafe = false,
                    error = "physical cover woke but no matching 1080x2520 logical route appeared",
                )

        val logicalId = resolved.first

        var routeEnabled = false
        var routeError: String? = null

        runCatching {
            enableConnectedDisplayInternal(logicalId)
            routeEnabled = true
        }.onFailure { error ->
            routeError =
                "${error.javaClass.simpleName}: ${error.message}"
        }

        // Never trust the logical id after a mutating display-manager call.
        // Samsung may remap it synchronously.
        val after =
            runCatching {
                directCoverRoute()
            }.getOrNull()

        val innerStillDefault =
            directGeometry(Display.DEFAULT_DISPLAY) ==
                (1968 to 2184)

        val stillSafe =
            innerStillDefault &&
                after?.first == logicalId &&
                after.second == ownedPhysicalId

        val logicalPowered =
            if (stillSafe) {
                runCatching {
                    requestDisplayPowerInternal(
                        logicalId,
                        Display.STATE_ON,
                    )
                }.getOrElse { error ->
                    routeError =
                        listOfNotNull(
                            routeError,
                            "${error.javaClass.simpleName}: ${error.message}",
                        ).joinToString(" | ")
                    false
                }
            } else {
                false
            }

        return CoverRouteActivation(
            logicalId = logicalId,
            physicalId = ownedPhysicalId,
            routeEnabled = routeEnabled,
            logicalPowered = logicalPowered,
            stillSafe = stillSafe,
            error =
                when {
                    !stillSafe ->
                        "cover logical route remapped before STATE_ON"
                    routeError != null ->
                        routeError
                    else ->
                        null
                },
        )
    }

    private fun prewarmCoverLeaseV2(
        ownerGeneration: Long,
    ): Bundle {
        if (ownerGeneration < 0L) {
            return coverLeaseBundle("prewarm", false)
        }

        val actions =
            coverPanelLease.beginPrewarm(ownerGeneration)

        var physicalOk = true
        var physicalError: String? = null

        for (action in actions) {
            if (action is Fold7CoverPanelLease.Action.PowerPhysicalCover) {
                val physicalId =
                    resolveFold7CoverPhysicalDisplayId(-1)

                val (powered, error) =
                    setPhysicalPowerNormal(physicalId)

                physicalOk = powered
                physicalError = error

                val followUp =
                    coverPanelLease.onPhysicalPrewarmResult(
                        action.leaseId,
                        action.epoch,
                        powered,
                        physicalId.takeIf { it >= 0L },
                        coverLeaseTopology(),
                    )

                executeCoverLeaseActions(followUp)
            }
        }

        val snapshot =
            coverPanelLease.snapshot()

        val leaseHeld =
            snapshot.state !=
                Fold7CoverPanelLease.State.IDLE

        val activation =
            if (
                physicalOk &&
                leaseHeld
            ) {
                activateOwnedCoverRouteAfterPhysicalWake(
                    snapshot.physicalId ?: -1L
                )
            } else {
                CoverRouteActivation(
                    logicalId = -1,
                    physicalId = snapshot.physicalId ?: -1L,
                    routeEnabled = false,
                    logicalPowered = false,
                    stillSafe = false,
                    error =
                        physicalError
                            ?: "cover lease was not established",
                )
            }

        /*
         * A physical-only success is not enough for the app continuity path:
         * DisplayMirrorHost needs a usable logical cover destination.
         *
         * If Samsung publishes the logical route a few milliseconds late,
         * this call remains bounded and the controller may retry without
         * issuing another physical wake because beginPrewarm() adopts HELD
         * ownership.
         */
        val ok =
            physicalOk &&
                leaseHeld &&
                activation.ok

        return coverLeaseBundle(
            operation = "prewarm",
            ok = ok,
        ).apply {
            putInt(
                "targetDisplayId",
                if (activation.stillSafe) {
                    activation.logicalId
                } else {
                    -1
                },
            )
            putBoolean(
                "physicalPowered",
                physicalOk,
            )
            putBoolean(
                "routeEnabled",
                activation.routeEnabled,
            )
            putBoolean(
                "logicalPowered",
                activation.logicalPowered,
            )
            putBoolean(
                "routeStillCover",
                activation.stillSafe,
            )
            putString(
                "command",
                "lease-owned physical+logical Fold7 cover prewarm",
            )
            putString(
                "error",
                activation.error
                    ?: physicalError,
            )
        }
    }
'''

replace_once(shell, old, new, "lease-owned cover logical-route activation")

replace_once(
    gradle,
    '''        versionCode = 31
        versionName = "1.3.26-zfold7-gen2-ownership"
''',
    '''        versionCode = 32
        versionName = "1.3.27-zfold7-cover-route-fix"
''',
    "1.3.27 cover-route regression version",
)

shell_text = (ROOT / shell).read_text()
for required in (
    "activateOwnedCoverRouteAfterPhysicalWake(",
    "enableConnectedDisplayInternal(logicalId)",
    "requestDisplayPowerInternal(",
    "Display.STATE_ON",
    "candidate.second == ownedPhysicalId",
    "after.second == ownedPhysicalId",
    "lease-owned physical+logical Fold7 cover prewarm",
):
    if required not in shell_text:
        raise SystemExit(f"missing postcondition: {required}")

gradle_text = (ROOT / gradle).read_text()
if 'versionCode = 32' not in gradle_text:
    raise SystemExit("versionCode 32 missing")
if 'versionName = "1.3.27-zfold7-cover-route-fix"' not in gradle_text:
    raise SystemExit("versionName missing")

print("Fold7 1.3.27 cover-route regression patch complete.")
