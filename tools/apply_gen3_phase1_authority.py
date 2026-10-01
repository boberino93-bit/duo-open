#!/usr/bin/env python3
from pathlib import Path
import shutil

ROOT = Path(".")
HERE = Path(__file__).resolve().parent.parent

def once(path: str, old: str, new: str, label: str) -> None:
    p = ROOT / path
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor in {path}, found {count}")
    p.write_text(text.replace(old, new, 1))

def main() -> None:
    shutil.copy2(
        HERE / "payload/Fold7CoverPanelLease.kt",
        ROOT / "app/src/full/java/com/duoopen/shell/Fold7CoverPanelLease.kt",
    )
    shutil.copy2(
        HERE / "payload/Fold7CoverPanelLeaseV4Test.kt",
        ROOT / "app/src/test/java/com/duoopen/shell/Fold7CoverPanelLeaseV4Test.kt",
    )

    once(
        "app/src/full/java/com/duoopen/shell/ShellProtocol.kt",
        "    const val COVER_PANEL_LEASE_V3 = 16\n",
        "    const val COVER_PANEL_LEASE_V3 = 16\n    const val COVER_PANEL_LEASE_V4 = 17\n",
        "ShellProtocol V4",
    )

    gate = "app/src/full/java/com/duoopen/overlay/Fold7CoverLeaseSnapshotGate.kt"
    once(
        gate,
        '''    data class LeaseToken(
        val shellSession: Long,
        val leaseId: Long,
        val leaseEpoch: Long,
        val ownerGeneration: Long,
        val physicalDisplayId: Long,
    )
''',
        '''    data class LeaseToken(
        val shellSession: Long,
        val leaseId: Long,
        val leaseEpoch: Long,
        val ownerGeneration: Long,
        val ownerServiceEpoch: Long,
        val ownerCloseCycleId: Long,
        val physicalDisplayId: Long,
    )
''',
        "gate token identity",
    )
    once(
        gate,
        '''        val routeReady: Boolean,
        val ok: Boolean,
    ) {
''',
        '''        val routeReady: Boolean,
        val ok: Boolean,
        val ownerServiceEpoch: Long = 0L,
        val ownerCloseCycleId: Long = 0L,
    ) {
''',
        "gate snapshot identity",
    )
    once(
        gate,
        '''                        ownerGeneration = ownerGeneration,
                        physicalDisplayId = physicalDisplayId,
''',
        '''                        ownerGeneration = ownerGeneration,
                        ownerServiceEpoch = ownerServiceEpoch,
                        ownerCloseCycleId = ownerCloseCycleId,
                        physicalDisplayId = physicalDisplayId,
''',
        "gate token construction",
    )

    bridge = "app/src/full/java/com/duoopen/shell/ShizukuBridge.kt"
    anchor = '''    internal fun ensureSecondaryDisplayHeldV3(
'''
    v4_bridge = '''    internal fun prewarmSecondaryDisplayV4(
        ownerServiceEpoch: Long,
        ownerCloseCycleId: Long,
        ownerGeneration: Long,
        expectedToken: com.duoopen.overlay.Fold7CoverLeaseSnapshotGate.LeaseToken?,
        reason: String = "prewarm-v4",
    ): Bundle? =
        call(ShellProtocol.COVER_PANEL_LEASE_V4) { parcel ->
            parcel.writeInt(1)
            parcel.writeLong(expectedToken?.shellSession ?: 0L)
            parcel.writeLong(expectedToken?.leaseId ?: 0L)
            parcel.writeLong(expectedToken?.leaseEpoch ?: 0L)
            parcel.writeLong(expectedToken?.ownerServiceEpoch ?: -1L)
            parcel.writeLong(expectedToken?.ownerCloseCycleId ?: -1L)
            parcel.writeLong(expectedToken?.ownerGeneration ?: -1L)
            parcel.writeLong(ownerServiceEpoch)
            parcel.writeLong(ownerCloseCycleId)
            parcel.writeLong(ownerGeneration)
            parcel.writeString(reason)
        }

'''
    once(bridge, anchor, v4_bridge + anchor, "ShizukuBridge V4")

    shell = "app/src/full/java/com/duoopen/shell/DuoShellService.kt"
    once(
        shell,
        '''            putLong("ownerGeneration", snapshot.ownerGeneration)
            putLong("physicalDisplayId", snapshot.physicalId ?: -1L)
''',
        '''            putLong("ownerGeneration", snapshot.ownerGeneration)
            putLong("ownerServiceEpoch", snapshot.ownerServiceEpoch)
            putLong("ownerCloseCycleId", snapshot.ownerCloseCycleId)
            putLong("physicalDisplayId", snapshot.physicalId ?: -1L)
''',
        "coverLeaseBundle owner identity",
    )
    once(
        shell,
        '''        bundle.putLong("ownerGeneration", snapshot.ownerGeneration)
        bundle.putLong("physicalDisplayId", snapshot.physicalId ?: -1L)
''',
        '''        bundle.putLong("ownerGeneration", snapshot.ownerGeneration)
        bundle.putLong("ownerServiceEpoch", snapshot.ownerServiceEpoch)
        bundle.putLong("ownerCloseCycleId", snapshot.ownerCloseCycleId)
        bundle.putLong("physicalDisplayId", snapshot.physicalId ?: -1L)
''',
        "stamp owner identity",
    )

    v3_end = '''                out.writeNoException()
                out.writeBundle(result)
            }

            ShellProtocol.MIRROR_DISPLAY -> {
'''
    v4_branch = '''                out.writeNoException()
                out.writeBundle(result)
            }

            ShellProtocol.COVER_PANEL_LEASE_V4 -> {
                val operation = data.readInt()
                val requestShellSession = data.readLong()
                val requestLeaseId = data.readLong()
                val requestLeaseEpoch = data.readLong()
                val expectedOwnerServiceEpoch = data.readLong()
                val expectedOwnerCloseCycleId = data.readLong()
                val expectedOwnerGeneration = data.readLong()
                val newOwnerServiceEpoch = data.readLong()
                val newOwnerCloseCycleId = data.readLong()
                val newOwnerGeneration = data.readLong()
                val reason = data.readString() ?: "unspecified"
                val identity = clearCallingIdentity()
                val result =
                    try {
                        runCoverMutation {
                            val expectedTokenProvided =
                                requestLeaseId > 0L &&
                                    requestLeaseEpoch > 0L

                            val base =
                                if (operation != 1) {
                                    coverLeaseBundle(
                                        "v4-unsupported-operation:$operation",
                                        false,
                                    ).apply {
                                        putBoolean("stale", true)
                                        putString("error", "Gen3 V4 currently supports PREWARM only")
                                    }
                                } else if (
                                    expectedTokenProvided &&
                                    requestShellSession != shellSession
                                ) {
                                    coverLeaseBundle(
                                        "prewarm-v4-stale-session",
                                        false,
                                    ).apply {
                                        putBoolean("stale", true)
                                    }
                                } else {
                                    prewarmCoverLeaseV4(
                                        expectedLeaseId = requestLeaseId,
                                        expectedLeaseEpoch = requestLeaseEpoch,
                                        expectedOwnerServiceEpoch = expectedOwnerServiceEpoch,
                                        expectedOwnerCloseCycleId = expectedOwnerCloseCycleId,
                                        expectedOwnerGeneration = expectedOwnerGeneration,
                                        newOwnerServiceEpoch = newOwnerServiceEpoch,
                                        newOwnerCloseCycleId = newOwnerCloseCycleId,
                                        newOwnerGeneration = newOwnerGeneration,
                                        reason = reason,
                                    )
                                }

                            stampCoverLeaseV3(base)
                        }
                    } catch (t: Throwable) {
                        failureBundle("cover-lease-v4", t)
                    } finally {
                        restoreCallingIdentity(identity)
                    }

                out.writeNoException()
                out.writeBundle(result)
            }

            ShellProtocol.MIRROR_DISPLAY -> {
'''
    once(shell, v3_end, v4_branch, "DuoShellService V4 dispatch")

    prewarm_anchor = '''    /**
     * Keep an existing HELD cover lease alive without transferring ownership.
'''
    prewarm_v4 = '''    private fun prewarmCoverLeaseV4(
        expectedLeaseId: Long,
        expectedLeaseEpoch: Long,
        expectedOwnerServiceEpoch: Long,
        expectedOwnerCloseCycleId: Long,
        expectedOwnerGeneration: Long,
        newOwnerServiceEpoch: Long,
        newOwnerCloseCycleId: Long,
        newOwnerGeneration: Long,
        reason: String,
    ): Bundle {
        val decision =
            coverPanelLease.beginPrewarmV4(
                newOwner =
                    Fold7CoverPanelLease.OwnerIdentity(
                        serviceEpoch = newOwnerServiceEpoch,
                        closeCycleId = newOwnerCloseCycleId,
                        transitionGeneration = newOwnerGeneration,
                    ),
                expectedLeaseId = expectedLeaseId,
                expectedEpoch = expectedLeaseEpoch,
                expectedOwnerServiceEpoch = expectedOwnerServiceEpoch,
                expectedOwnerCloseCycleId = expectedOwnerCloseCycleId,
                expectedOwnerGeneration = expectedOwnerGeneration,
            )

        if (!decision.accepted) {
            return coverLeaseBundle(
                operation = "prewarm-v4:$reason",
                ok = false,
            ).apply {
                putBoolean("stale", decision.stale)
                putString("decision", decision.reason)
            }
        }

        var physicalOk = true
        var physicalError: String? = null

        for (action in decision.actions) {
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

        val snapshot = coverPanelLease.snapshot()
        val leaseHeld =
            snapshot.state != Fold7CoverPanelLease.State.IDLE

        val activation =
            if (physicalOk && leaseHeld) {
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
                    error = physicalError ?: "cover lease was not established",
                )
            }

        val ok =
            physicalOk &&
                leaseHeld &&
                activation.ok

        return coverLeaseBundle(
            operation = "prewarm-v4:$reason",
            ok = ok,
        ).apply {
            putBoolean("stale", false)
            putString("decision", decision.reason)
            putInt(
                "targetDisplayId",
                if (activation.stillSafe) activation.logicalId else -1,
            )
            putBoolean("physicalPowered", physicalOk)
            putBoolean("routeEnabled", activation.routeEnabled)
            putBoolean("logicalPowered", activation.logicalPowered)
            putBoolean("routeStillCover", activation.stillSafe)
            putString(
                "command",
                "Gen3 exact-CAS physical+logical Fold7 cover prewarm",
            )
            putString("error", activation.error ?: physicalError)
        }
    }

'''
    once(shell, prewarm_anchor, prewarm_v4 + prewarm_anchor, "DuoShellService V4 prewarm")

    coordinator = "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"
    once(
        coordinator,
        '''                ownerGeneration = result.getLong("ownerGeneration", -1L),
                physicalDisplayId = result.getLong("physicalDisplayId", -1L),
''',
        '''                ownerGeneration = result.getLong("ownerGeneration", -1L),
                physicalDisplayId = result.getLong("physicalDisplayId", -1L),
                ownerServiceEpoch = result.getLong("ownerServiceEpoch", 0L),
                ownerCloseCycleId = result.getLong("ownerCloseCycleId", 0L),
''',
        "coordinator snapshot owner identity",
    )
    once(
        coordinator,
        '''    @Volatile private var prewarmInFlightConnectionEpoch = -1L
    @Volatile private var destroyed = false
''',
        '''    @Volatile private var prewarmInFlightConnectionEpoch = -1L
    @Volatile private var prewarmRetryGeneration = -1L
    @Volatile private var prewarmRetryCount = 0
    @Volatile private var destroyed = false
''',
        "coordinator retry fields",
    )
    once(
        coordinator,
        '''        prewarmInFlightGeneration = -1L
        prewarmInFlightConnectionEpoch = -1L
        gen2.coverAuthority.onConnectionEpoch(
''',
        '''        prewarmInFlightGeneration = -1L
        prewarmInFlightConnectionEpoch = -1L
        prewarmRetryGeneration = -1L
        prewarmRetryCount = 0
        gen2.coverAuthority.onConnectionEpoch(
''',
        "coordinator retry reset",
    )
    once(
        coordinator,
        '''        val requestConnectionEpoch = ShizukuBridge.connectionEpoch
        if (
''',
        '''        if (prewarmRetryGeneration != generation) {
            prewarmRetryGeneration = generation
            prewarmRetryCount = 0
        }

        val requestConnectionEpoch = ShizukuBridge.connectionEpoch
        val expectedToken = gen2.coverAuthority.acceptedToken
        if (
''',
        "coordinator expected token capture",
    )
    once(
        coordinator,
        '''                    ShizukuBridge.prewarmSecondaryDisplayV3(generation)
''',
        '''                    ShizukuBridge.prewarmSecondaryDisplayV4(
                        ownerServiceEpoch = cycle.serviceEpoch,
                        ownerCloseCycleId = cycle.closeCycleId,
                        ownerGeneration = generation,
                        expectedToken = expectedToken,
                    )
''',
        "coordinator V4 call",
    )

    old_validation = '''                if (
                    !acceptance.accepted ||
                    snapshot == null ||
                    token == null ||
                    currentCycle == null ||
                    currentCycle != cycle ||
                    !snapshot.physicalLeaseHeld
                ) {
                    val decision =
                        controller.onPrewarmResult(
                            requestGeneration = generation,
                            ok = false,
                            nowMs = SystemClock.uptimeMillis(),
                            topology = topology(),
                        )
                    apply(decision)
                    return@post
                }

                val demand =
'''
    new_validation = '''                val ownsRequestedCycle =
                    token != null &&
                        token.ownerServiceEpoch == cycle.serviceEpoch &&
                        token.ownerCloseCycleId == cycle.closeCycleId &&
                        token.ownerGeneration == generation

                if (
                    acceptance.accepted &&
                    snapshot != null &&
                    currentCycle == cycle &&
                    result?.getBoolean("stale", false) == true &&
                    !ownsRequestedCycle &&
                    token != null &&
                    prewarmRetryCount < MAX_PREWARM_CAS_RETRIES
                ) {
                    prewarmRetryCount += 1
                    DuoDiagnostics.event(
                        "fold7-state",
                        "prewarm-v4 CAS retry generation=$generation " +
                            "serviceEpoch=${cycle.serviceEpoch} closeCycle=${cycle.closeCycleId} " +
                            "retry=$prewarmRetryCount tokenOwner=${token.ownerGeneration}",
                    )
                    beginPrewarm(generation)
                    return@post
                }

                if (
                    !acceptance.accepted ||
                    snapshot == null ||
                    token == null ||
                    currentCycle == null ||
                    currentCycle != cycle ||
                    !ownsRequestedCycle ||
                    !snapshot.physicalLeaseHeld
                ) {
                    val decision =
                        controller.onPrewarmResult(
                            requestGeneration = generation,
                            ok = false,
                            nowMs = SystemClock.uptimeMillis(),
                            topology = topology(),
                        )
                    apply(decision)
                    return@post
                }

                prewarmRetryCount = 0

                val demand =
'''
    once(coordinator, old_validation, new_validation, "coordinator exact owner validation")
    once(
        coordinator,
        '''        const val FROZEN_FRAME_MAX_AGE_MS = 10_000L
''',
        '''        const val FROZEN_FRAME_MAX_AGE_MS = 10_000L
        const val MAX_PREWARM_CAS_RETRIES = 2
''',
        "coordinator retry cap",
    )

    print("GEN3 PHASE 1 AUTHORITY PATCH: PASS")

if __name__ == "__main__":
    main()
