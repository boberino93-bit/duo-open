#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = ROOT / path
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"{label}: expected exactly one anchor in {path}, found {count}"
        )
    p.write_text(text.replace(old, new, 1))
    print(f"patched {label}: {path}")

GRADLE = "app/build.gradle.kts"
BRIDGE = "app/src/full/java/com/duoopen/shell/ShizukuBridge.kt"
SHELL = "app/src/full/java/com/duoopen/shell/DuoShellService.kt"
COORD = "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"

replace_once(
    GRADLE,
    '''        versionCode = 32
        versionName = "1.3.27-zfold7-cover-route-fix"
''',
    '''        versionCode = 33
        versionName = "1.3.28-zfold7-cover-hold-fix"
''',
    "version bump",
)

replace_once(
    BRIDGE,
    '''    fun secondaryDisplayLeaseStatusV2(): Bundle? =
        call(ShellProtocol.COVER_PANEL_LEASE_V2) { parcel ->
            parcel.writeInt(4)
            parcel.writeLong(-1L)
            parcel.writeString("status")
        }

    fun requestDisplayPower(
''',
    '''    fun secondaryDisplayLeaseStatusV2(): Bundle? =
        call(ShellProtocol.COVER_PANEL_LEASE_V2) { parcel ->
            parcel.writeInt(4)
            parcel.writeLong(-1L)
            parcel.writeString("status")
        }

    /**
     * Reassert an already-owned Fold7 cover lease without changing ownership.
     */
    fun ensureSecondaryDisplayHeldV2(
        ownerGeneration: Long,
        reason: String,
    ): Bundle? =
        call(ShellProtocol.COVER_PANEL_LEASE_V2) { parcel ->
            parcel.writeInt(5)
            parcel.writeLong(ownerGeneration)
            parcel.writeString(reason)
        }

    fun requestDisplayPower(
''',
    "app bridge ensure-held operation",
)

replace_once(
    SHELL,
    '''                                3 -> reconcileCoverLeaseV2(reason)
                                4 -> coverLeaseBundle("status", true)
                                else -> Bundle().apply {
''',
    '''                                3 -> reconcileCoverLeaseV2(reason)
                                4 -> coverLeaseBundle("status", true)
                                5 -> ensureHeldCoverRouteV2(ownerGeneration, reason)
                                else -> Bundle().apply {
''',
    "shell dispatch ensure-held operation",
)

replace_once(
    SHELL,
    '''    private fun releaseCoverLeaseV2(
        ownerGeneration: Long,
        reason: String,
    ): Bundle {
''',
    '''    /**
     * Keep an existing HELD cover lease alive without transferring ownership.
     *
     * The caller must still own the exact HELD lease. The stable physical
     * cover id is taken from that lease, physical NORMAL is reasserted, and a
     * fresh non-default 1080x2520 logical route must map back to the same
     * physical id before enable / STATE_ON.
     */
    private fun ensureHeldCoverRouteV2(
        ownerGeneration: Long,
        reason: String,
    ): Bundle {
        val before =
            coverPanelLease.snapshot()

        if (
            before.state !=
                Fold7CoverPanelLease.State.HELD
        ) {
            return coverLeaseBundle(
                "ensure-held:$reason",
                false,
            ).apply {
                putBoolean("stale", true)
                putString(
                    "error",
                    "cover lease is ${before.state}, not HELD",
                )
            }
        }

        if (
            ownerGeneration < 0L ||
            ownerGeneration !=
                before.ownerGeneration
        ) {
            return coverLeaseBundle(
                "ensure-held:$reason",
                false,
            ).apply {
                putBoolean("stale", true)
                putString(
                    "error",
                    "cover lease owner changed",
                )
            }
        }

        val physicalId =
            before.physicalId
                ?: -1L

        val (
            physicalPowered,
            physicalError,
        ) =
            setPhysicalPowerNormal(
                physicalId
            )

        val activation =
            if (physicalPowered) {
                activateOwnedCoverRouteAfterPhysicalWake(
                    physicalId
                )
            } else {
                CoverRouteActivation(
                    logicalId = -1,
                    physicalId = physicalId,
                    routeEnabled = false,
                    logicalPowered = false,
                    stillSafe = false,
                    error =
                        physicalError
                            ?: "physical cover reassert failed",
                )
            }

        val ok =
            physicalPowered &&
                activation.ok

        return coverLeaseBundle(
            operation =
                "ensure-held:$reason",
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
                physicalPowered,
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
                "lease-owned Fold7 cover hold reassert",
            )
            putString(
                "error",
                activation.error
                    ?: physicalError,
            )
        }
    }

    private fun releaseCoverLeaseV2(
        ownerGeneration: Long,
        reason: String,
    ): Bundle {
''',
    "shell owner-scoped held-route reassert",
)

replace_once(
    COORD,
    '''    @Volatile private var coverLeaseOwnerGeneration = -1L
    @Volatile private var destroyed = false
''',
    '''    @Volatile private var coverLeaseOwnerGeneration = -1L
    @Volatile private var coverRouteReassertInFlight = false
    @Volatile private var destroyed = false
''',
    "coordinator reassert in-flight guard",
)

replace_once(
    COORD,
    '''        apply(decision)
        reconcileCoverLease("topology:$reason")

        if (visualMirrorActive) {
''',
    '''        apply(decision)
        reconcileCoverLease("topology:$reason")

        val currentTopology =
            topology()

        if (
            (
                controller.state ==
                    Fold7ContinuityController.State.COVER_READY_HIDDEN ||
                controller.state ==
                    Fold7ContinuityController.State.COVER_VISUAL
                ) &&
            currentTopology.innerActive &&
            !currentTopology.coverActive
        ) {
            ensureCoverRouteHeld(
                "topology:$reason"
            )
        }

        if (visualMirrorActive) {
''',
    "topology-triggered cover hold reassert",
)

replace_once(
    COORD,
    '''        mirrorRequested = true
        mirrorGeneration = generation

        syncMirrorHost(
''',
    '''        mirrorRequested = true
        mirrorGeneration = generation

        val currentTopology =
            topology()

        if (
            currentTopology.innerActive &&
            !currentTopology.coverActive
        ) {
            ensureCoverRouteHeld(
                "state-show"
            )
        }

        syncMirrorHost(
''',
    "visual-threshold missed-route recovery",
)

replace_once(
    COORD,
    '''    private fun releaseCoverLease(
        reason: String,
    ) {
''',
    '''    private fun ensureCoverRouteHeld(
        reason: String,
    ) {
        if (
            destroyed ||
            !ShizukuBridge.ready ||
            coverRouteReassertInFlight
        ) {
            return
        }

        if (
            controller.state !=
                Fold7ContinuityController.State.COVER_READY_HIDDEN &&
            controller.state !=
                Fold7ContinuityController.State.COVER_VISUAL
        ) {
            return
        }

        val owner =
            coverLeaseOwnerGeneration

        if (owner < 0L) {
            DuoDiagnostics.event(
                "fold7-state",
                "cover-route-reassert skipped reason=$reason owner=none",
            )
            return
        }

        val requestGeneration =
            controller.generation

        coverRouteReassertInFlight =
            true

        DuoDiagnostics.event(
            "fold7-state",
            "cover-route-reassert begin reason=$reason " +
                "generation=$requestGeneration owner=$owner",
        )

        scope.launch(
            Dispatchers.IO
        ) {
            val result =
                runCatching {
                    ShizukuBridge
                        .ensureSecondaryDisplayHeldV2(
                            ownerGeneration = owner,
                            reason = reason,
                        )
                }.getOrNull()

            handler.post {
                coverRouteReassertInFlight =
                    false

                updateCoverLeaseSnapshot(
                    result,
                    "route-reassert:$reason",
                )

                val ok =
                    result?.getBoolean(
                        "ok",
                        false,
                    ) == true

                val target =
                    result?.getInt(
                        "targetDisplayId",
                        -1,
                    ) ?: -1

                DuoDiagnostics.event(
                    "fold7-state",
                    "cover-route-reassert complete reason=$reason " +
                        "generation=$requestGeneration owner=$owner " +
                        "currentGeneration=${controller.generation} " +
                        "ok=$ok logical=$target " +
                        "routeEnabled=${result?.getBoolean("routeEnabled", false) == true} " +
                        "logicalPowered=${result?.getBoolean("logicalPowered", false) == true} " +
                        "stale=${result?.getBoolean("stale", false) == true} " +
                        "error=${result?.getString("error")}",
                )

                if (
                    !destroyed &&
                    ok &&
                    controller.isGenerationCurrent(
                        requestGeneration
                    ) &&
                    controller.state ==
                        Fold7ContinuityController.State.COVER_VISUAL
                ) {
                    handler.postDelayed(
                        {
                            if (
                                !destroyed &&
                                visualMirrorActive
                            ) {
                                syncMirrorHost(
                                    reason =
                                        "route-reassert:$reason",
                                    generation =
                                        mirrorGeneration,
                                )
                            }
                        },
                        COVER_ROUTE_REASSERT_SETTLE_MS,
                    )
                }
            }
        }
    }

    private fun releaseCoverLease(
        reason: String,
    ) {
''',
    "coordinator lease-scoped reassert implementation",
)

replace_once(
    COORD,
    '''    fun onPrivilegedUnavailable() {
        mirrorSession = 0L
        mirrorSessionOpening = false
        mirrorSequence.set(0L)
    }
''',
    '''    fun onPrivilegedUnavailable() {
        mirrorSession = 0L
        mirrorSessionOpening = false
        mirrorSequence.set(0L)
        coverRouteReassertInFlight = false
    }
''',
    "reassert reset on privileged loss",
)

replace_once(
    COORD,
    '''        const val COVER_WIDTH = 1080
        const val COVER_HEIGHT = 2520
    }
}
''',
    '''        const val COVER_WIDTH = 1080
        const val COVER_HEIGHT = 2520
        const val COVER_ROUTE_REASSERT_SETTLE_MS = 32L
    }
}
''',
    "reassert settle constant",
)

gradle_text = (ROOT / GRADLE).read_text()
bridge_text = (ROOT / BRIDGE).read_text()
shell_text = (ROOT / SHELL).read_text()
coord_text = (ROOT / COORD).read_text()

required = {
    GRADLE: [
        'versionCode = 33',
        'versionName = "1.3.28-zfold7-cover-hold-fix"',
    ],
    BRIDGE: [
        'fun ensureSecondaryDisplayHeldV2(',
        'parcel.writeInt(5)',
    ],
    SHELL: [
        '5 -> ensureHeldCoverRouteV2(ownerGeneration, reason)',
        'private fun ensureHeldCoverRouteV2(',
        'Fold7CoverPanelLease.State.HELD',
        'before.ownerGeneration',
        'lease-owned Fold7 cover hold reassert',
    ],
    COORD: [
        'coverRouteReassertInFlight',
        'private fun ensureCoverRouteHeld(',
        'ensureSecondaryDisplayHeldV2(',
        'cover-route-reassert begin',
        'cover-route-reassert complete',
        'COVER_ROUTE_REASSERT_SETTLE_MS = 32L',
    ],
}

texts = {
    GRADLE: gradle_text,
    BRIDGE: bridge_text,
    SHELL: shell_text,
    COORD: coord_text,
}

for path, needles in required.items():
    for needle in needles:
        if needle not in texts[path]:
            raise SystemExit(f"{path}: missing postcondition {needle!r}")

print("Fold7 1.3.28 cover-hold fix patch complete.")
