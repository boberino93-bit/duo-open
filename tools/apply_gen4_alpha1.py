#!/usr/bin/env python3
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def fail(msg: str):
    raise SystemExit(f"ERROR: {msg}")


def replace_exact(path: Path, old: str, new: str, count: int = 1):
    text = path.read_text()
    found = text.count(old)
    if found != count:
        fail(f"{path}: expected {count} occurrences, found {found}: {old[:180]!r}")
    path.write_text(text.replace(old, new, count))


def replace_between(path: Path, start: str, end: str, replacement: str):
    text = path.read_text()
    if text.count(start) != 1:
        fail(f"{path}: expected exactly one start marker {start!r}")
    if text.count(end) != 1:
        fail(f"{path}: expected exactly one end marker {end!r}")
    a = text.index(start)
    b = text.index(end, a + len(start))
    path.write_text(text[:a] + replacement + text[b:])


def insert_after(path: Path, marker: str, addition: str):
    text = path.read_text()
    if text.count(marker) != 1:
        fail(f"{path}: expected exactly one marker for insert: {marker[:180]!r}")
    path.write_text(text.replace(marker, marker + addition, 1))


def require(path: Path, needle: str, count: int | None = None):
    text = path.read_text()
    actual = text.count(needle)
    if count is None:
        if actual == 0:
            fail(f"{path}: missing required text {needle!r}")
    elif actual != count:
        fail(f"{path}: expected {count} occurrences of {needle!r}, found {actual}")


def forbid(path: Path, needle: str):
    if needle in path.read_text():
        fail(f"{path}: forbidden text survived: {needle!r}")


def copy_payload(src_rel: str, dst_rel: str):
    src = ROOT / "payload_gen4" / src_rel
    dst = ROOT / dst_rel
    if not src.is_file():
        fail(f"missing payload {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


# ---------------------------------------------------------------------------
# New pure daemon-owned panel authority model and tests.
# ---------------------------------------------------------------------------
copy_payload(
    "app/src/full/java/com/duoopen/shell/Fold7PanelAuthorityGen4.kt",
    "app/src/full/java/com/duoopen/shell/Fold7PanelAuthorityGen4.kt",
)
copy_payload(
    "app/src/test/java/com/duoopen/shell/Fold7PanelAuthorityGen4Test.kt",
    "app/src/test/java/com/duoopen/shell/Fold7PanelAuthorityGen4Test.kt",
)

# ---------------------------------------------------------------------------
# Protocol: one Gen4 cover-panel command surface. Gen2/Gen3 protocol constants
# remain for source compatibility but are rejected by the Gen4 shell binary.
# ---------------------------------------------------------------------------
p = ROOT / "app/src/full/java/com/duoopen/shell/ShellProtocol.kt"
replace_exact(
    p,
    """    const val COVER_PANEL_LEASE_V4 = 17\n\n    const val CB_ANGLE = 1\n""",
    """    const val COVER_PANEL_LEASE_V4 = 17\n\n    // Gen4: daemon-owned Fold7 panel authority. App-side code sends semantic\n    // intents; only DuoShellService mutates cover power/routes.\n    const val COVER_PANEL_GEN4 = 18\n\n    const val CB_ANGLE = 1\n""",
)

# ---------------------------------------------------------------------------
# App-side bridge: semantic Gen4 panel intents. No lease token is supplied by
# the app; daemon serviceEpoch + intentSequence ordering owns mutation safety.
# ---------------------------------------------------------------------------
p = ROOT / "app/src/full/java/com/duoopen/shell/ShizukuBridge.kt"
bridge_marker = """    fun secondaryDisplayLeaseStatusV3(\n        shellSession: Long,\n    ): Bundle? =\n        call(ShellProtocol.COVER_PANEL_LEASE_V3) { parcel ->\n            parcel.writeInt(4)\n            parcel.writeLong(shellSession)\n            parcel.writeLong(0L)\n            parcel.writeLong(0L)\n            parcel.writeLong(-1L)\n            parcel.writeString(\"status\")\n        }\n\n"""
bridge_addition = """    private fun coverPanelGen4(\n        operation: Int,\n        serviceEpoch: Long,\n        closeCycleId: Long,\n        transitionGeneration: Long,\n        intentSequence: Long,\n        reason: String,\n    ): Bundle? =\n        call(ShellProtocol.COVER_PANEL_GEN4) { parcel ->\n            parcel.writeInt(operation)\n            parcel.writeLong(serviceEpoch)\n            parcel.writeLong(closeCycleId)\n            parcel.writeLong(transitionGeneration)\n            parcel.writeLong(intentSequence)\n            parcel.writeString(reason)\n        }\n\n    internal fun coverPanelStatusGen4(\n        serviceEpoch: Long,\n        intentSequence: Long,\n        reason: String,\n    ): Bundle? =\n        coverPanelGen4(\n            operation = 1,\n            serviceEpoch = serviceEpoch,\n            closeCycleId = 0L,\n            transitionGeneration = -1L,\n            intentSequence = intentSequence,\n            reason = reason,\n        )\n\n    internal fun prepareCoverPanelGen4(\n        serviceEpoch: Long,\n        closeCycleId: Long,\n        transitionGeneration: Long,\n        intentSequence: Long,\n        reason: String,\n    ): Bundle? =\n        coverPanelGen4(\n            operation = 2,\n            serviceEpoch = serviceEpoch,\n            closeCycleId = closeCycleId,\n            transitionGeneration = transitionGeneration,\n            intentSequence = intentSequence,\n            reason = reason,\n        )\n\n    internal fun reassertCoverPanelGen4(\n        serviceEpoch: Long,\n        closeCycleId: Long,\n        transitionGeneration: Long,\n        intentSequence: Long,\n        reason: String,\n    ): Bundle? =\n        coverPanelGen4(\n            operation = 3,\n            serviceEpoch = serviceEpoch,\n            closeCycleId = closeCycleId,\n            transitionGeneration = transitionGeneration,\n            intentSequence = intentSequence,\n            reason = reason,\n        )\n\n    internal fun returnCoverPanelGen4(\n        serviceEpoch: Long,\n        intentSequence: Long,\n        reason: String,\n    ): Bundle? =\n        coverPanelGen4(\n            operation = 4,\n            serviceEpoch = serviceEpoch,\n            closeCycleId = 0L,\n            transitionGeneration = -1L,\n            intentSequence = intentSequence,\n            reason = reason,\n        )\n\n    internal fun reconcileCoverPanelGen4(\n        serviceEpoch: Long,\n        intentSequence: Long,\n        reason: String,\n    ): Bundle? =\n        coverPanelGen4(\n            operation = 5,\n            serviceEpoch = serviceEpoch,\n            closeCycleId = 0L,\n            transitionGeneration = -1L,\n            intentSequence = intentSequence,\n            reason = reason,\n        )\n\n"""
insert_after(p, bridge_marker, bridge_addition)

# ---------------------------------------------------------------------------
# Shell daemon: Gen4 owns physical/logical cover mutations and fences the old
# cover lease APIs. Startup recovery is based on actual topology, never on a
# prior process's in-memory lease object.
# ---------------------------------------------------------------------------
p = ROOT / "app/src/full/java/com/duoopen/shell/DuoShellService.kt"

replace_exact(
    p,
    """    private val coverPanelLease =\n        Fold7CoverPanelLease()\n\n    private val shellSession =\n""",
    """    private val coverPanelLease =\n        Fold7CoverPanelLease()\n\n    private val gen4PanelAuthority =\n        Fold7PanelAuthorityGen4()\n\n    private val shellSession =\n""",
)

# Best-effort graceful normalization before the Shizuku user service exits.
replace_exact(
    p,
    """            mirrorMutationExecutor.shutdownNow()\n            coverMutationExecutor.shutdownNow()\n            System.exit(0)\n""",
    """            mirrorMutationExecutor.shutdownNow()\n            runCatching {\n                coverMutationExecutor.submit {\n                    gen4ShutdownCleanup()\n                }.get(1, TimeUnit.SECONDS)\n            }\n            coverMutationExecutor.shutdownNow()\n            System.exit(0)\n""",
)

# In a Gen4 binary, old cover mutation entry points are no longer authoritative.
replace_exact(
    p,
    """        val out = reply ?: return false\n        when (code) {\n""",
    """        val out = reply ?: return false\n\n        if (\n            code == ShellProtocol.ENABLE_SECONDARY_DISPLAY ||\n            code == ShellProtocol.RESET_SECONDARY_DISPLAY ||\n            code == ShellProtocol.COVER_PANEL_LEASE_V2 ||\n            code == ShellProtocol.COVER_PANEL_LEASE_V3 ||\n            code == ShellProtocol.COVER_PANEL_LEASE_V4\n        ) {\n            out.writeNoException()\n            out.writeBundle(\n                Bundle().apply {\n                    putBoolean(\"ok\", false)\n                    putBoolean(\"stale\", true)\n                    putString(\"error\", \"legacy cover mutation rejected: Gen4 panel authority is active\")\n                }\n            )\n            return true\n        }\n\n        when (code) {\n""",
)

# Insert Gen4 transaction immediately before legacy mirror handling.
gen4_handler = """            ShellProtocol.COVER_PANEL_GEN4 -> {\n                val operation = data.readInt()\n                val serviceEpoch = data.readLong()\n                val closeCycleId = data.readLong()\n                val transitionGeneration = data.readLong()\n                val intentSequence = data.readLong()\n                val reason = data.readString() ?: \"unspecified\"\n                val identity = clearCallingIdentity()\n\n                val result =\n                    try {\n                        runCoverMutation {\n                            handleGen4PanelCommand(\n                                operation = operation,\n                                serviceEpoch = serviceEpoch,\n                                closeCycleId = closeCycleId,\n                                transitionGeneration = transitionGeneration,\n                                intentSequence = intentSequence,\n                                reason = reason,\n                            )\n                        }\n                    } catch (t: Throwable) {\n                        failureBundle(\"cover-panel-gen4\", t)\n                    } finally {\n                        restoreCallingIdentity(identity)\n                    }\n\n                out.writeNoException()\n                out.writeBundle(result)\n            }\n\n"""
replace_exact(
    p,
    """            ShellProtocol.MIRROR_DISPLAY -> {\n""",
    gen4_handler + """            ShellProtocol.MIRROR_DISPLAY -> {\n""",
)

# Gen4 hardware/authority implementation. Reuses the already field-proven
# physical wake + fresh-route activation helpers, but daemon state now owns
# sequencing, process rollover, cleanup, and receipts.
insert_marker = """    private fun prewarmCoverLeaseV2(\n        ownerGeneration: Long,\n    ): Bundle {\n"""
gen4_impl = r'''    private data class Gen4CleanupResult(
        val ok: Boolean,
        val nativeCover: Boolean,
        val error: String? = null,
    )

    private fun ensureGen4StartupRecovered(
        reason: String,
    ): Boolean {
        if (gen4PanelAuthority.snapshot().recoveryReady) return true

        repeat(GEN4_RECOVERY_ATTEMPTS) { attempt ->
            val topology = coverLeaseTopology()
            when (
                val plan = gen4PanelAuthority.recoveryPlan(
                    nativeCover = topology.nativeCover,
                    innerIsDefault = topology.innerIsDefault,
                    coverSecondaryLogicalId = topology.coverSecondaryLogicalId,
                )
            ) {
                Fold7PanelAuthorityGen4.RecoveryPlan.ReadyInner -> {
                    gen4PanelAuthority.completeRecovery(nativeCover = false)
                    return true
                }

                Fold7PanelAuthorityGen4.RecoveryPlan.ReadyNativeCover -> {
                    gen4PanelAuthority.completeRecovery(nativeCover = true)
                    return true
                }

                is Fold7PanelAuthorityGen4.RecoveryPlan.ResetSecondaryRoute -> {
                    val reset = secondaryDisplayCommand(false, plan.logicalId)
                    if (reset.getBoolean("ok", false)) {
                        gen4PanelAuthority.completeRecovery(nativeCover = false)
                        return true
                    }
                }

                Fold7PanelAuthorityGen4.RecoveryPlan.RetryAmbiguous -> Unit
            }

            if (attempt + 1 < GEN4_RECOVERY_ATTEMPTS) {
                Thread.sleep(GEN4_RECOVERY_RETRY_MS)
            }
        }

        gen4PanelAuthority.recoveryFailed()
        return false
    }

    private fun normalizeGen4SecondaryRoute(
        reason: String,
    ): Gen4CleanupResult {
        var lastError: String? = null

        repeat(GEN4_RECOVERY_ATTEMPTS) { attempt ->
            val topology = coverLeaseTopology()

            if (topology.nativeCover) {
                return Gen4CleanupResult(
                    ok = true,
                    nativeCover = true,
                )
            }

            if (topology.innerIsDefault) {
                val logicalId = topology.coverSecondaryLogicalId
                if (logicalId == null || logicalId < 0) {
                    return Gen4CleanupResult(
                        ok = true,
                        nativeCover = false,
                    )
                }

                val reset = secondaryDisplayCommand(false, logicalId)
                if (reset.getBoolean("ok", false)) {
                    return Gen4CleanupResult(
                        ok = true,
                        nativeCover = false,
                    )
                }

                lastError = reset.getString("error") ?: reset.getString("commandOutput")
            } else {
                lastError = "ambiguous Fold7 topology during $reason"
            }

            if (attempt + 1 < GEN4_RECOVERY_ATTEMPTS) {
                Thread.sleep(GEN4_RECOVERY_RETRY_MS)
            }
        }

        return Gen4CleanupResult(
            ok = false,
            nativeCover = false,
            error = lastError ?: "cover route normalization failed",
        )
    }

    private fun handleGen4PanelCommand(
        operation: Int,
        serviceEpoch: Long,
        closeCycleId: Long,
        transitionGeneration: Long,
        intentSequence: Long,
        reason: String,
    ): Bundle {
        if (!ensureGen4StartupRecovered(reason)) {
            return gen4PanelBundle(
                operation = "startup-recovery:$reason",
                ok = false,
                decision = "startup-recovery-pending",
                error = "daemon could not prove a safe Fold7 topology",
            )
        }

        var admission =
            gen4PanelAuthority.admit(
                serviceEpoch = serviceEpoch,
                intentSequence = intentSequence,
            )

        if (admission.cleanupRequired) {
            val cleanup =
                normalizeGen4SecondaryRoute(
                    "service-rollover:$reason"
                )

            if (!cleanup.ok) {
                return gen4PanelBundle(
                    operation = "service-rollover:$reason",
                    ok = false,
                    decision = admission.reason,
                    cleanupRequired = true,
                    error = cleanup.error,
                )
            }

            gen4PanelAuthority.completeServiceRollover(
                serviceEpoch = serviceEpoch,
                intentSequence = intentSequence,
                nativeCover = cleanup.nativeCover,
            )

            admission =
                Fold7PanelAuthorityGen4.Admission(
                    accepted = true,
                    stale = false,
                    cleanupRequired = false,
                    reason = "service-rollover-clean",
                )
        }

        if (!admission.accepted) {
            return gen4PanelBundle(
                operation = "rejected:$reason",
                ok = false,
                stale = admission.stale,
                cleanupRequired = admission.cleanupRequired,
                decision = admission.reason,
            )
        }

        return when (operation) {
            1 ->
                admitPanelSessionGen4(
                    serviceEpoch = serviceEpoch,
                    intentSequence = intentSequence,
                    reason = reason,
                )

            2 ->
                prepareCoverPanelGen4(
                    serviceEpoch = serviceEpoch,
                    closeCycleId = closeCycleId,
                    transitionGeneration = transitionGeneration,
                    intentSequence = intentSequence,
                    reason = reason,
                )

            3 ->
                reassertCoverPanelGen4(
                    serviceEpoch = serviceEpoch,
                    closeCycleId = closeCycleId,
                    transitionGeneration = transitionGeneration,
                    intentSequence = intentSequence,
                    reason = reason,
                )

            4 ->
                returnCoverPanelGen4(
                    serviceEpoch = serviceEpoch,
                    intentSequence = intentSequence,
                    reason = reason,
                )

            5 ->
                reconcileCoverPanelGen4(
                    serviceEpoch = serviceEpoch,
                    intentSequence = intentSequence,
                    reason = reason,
                )

            else ->
                gen4PanelBundle(
                    operation = "unknown:$operation",
                    ok = false,
                    decision = "unsupported-operation",
                    error = "unknown Gen4 panel operation $operation",
                )
        }
    }

    private fun admitPanelSessionGen4(
        serviceEpoch: Long,
        intentSequence: Long,
        reason: String,
    ): Bundle {
        val before = gen4PanelAuthority.snapshot()

        if (
            before.phase in setOf(
                Fold7PanelAuthorityGen4.Phase.COVER_PREPARING,
                Fold7PanelAuthorityGen4.Phase.COVER_READY_HIDDEN,
                Fold7PanelAuthorityGen4.Phase.RELEASE_PENDING,
            )
        ) {
            gen4PanelAuthority.beginRelease(
                serviceEpoch = serviceEpoch,
                intentSequence = intentSequence,
            )

            val cleanup =
                normalizeGen4SecondaryRoute(
                    "session-admission:$reason"
                )

            gen4PanelAuthority.completeRelease(
                intentSequence = intentSequence,
                success = cleanup.ok,
                nativeCover = cleanup.nativeCover,
            )

            return gen4PanelBundle(
                operation = "session-admission:$reason",
                ok = cleanup.ok,
                decision = if (cleanup.ok) "native-session-admitted" else "release-pending",
                error = cleanup.error,
            )
        }

        return gen4PanelBundle(
            operation = "session-admission:$reason",
            ok = true,
            decision = "native-session-admitted",
        )
    }

    private fun prepareCoverPanelGen4(
        serviceEpoch: Long,
        closeCycleId: Long,
        transitionGeneration: Long,
        intentSequence: Long,
        reason: String,
    ): Bundle {
        if (closeCycleId <= 0L || transitionGeneration < 0L) {
            return gen4PanelBundle(
                operation = "prepare:$reason",
                ok = false,
                stale = true,
                decision = "invalid-owner-identity",
            )
        }

        val owner =
            Fold7PanelAuthorityGen4.Owner(
                serviceEpoch = serviceEpoch,
                closeCycleId = closeCycleId,
                transitionGeneration = transitionGeneration,
            )

        gen4PanelAuthority.beginPrepare(
            owner = owner,
            intentSequence = intentSequence,
        )

        val physicalId = resolveFold7CoverPhysicalDisplayId(-1)
        val (physicalPowered, physicalError) =
            setPhysicalPowerNormal(physicalId)

        val activation =
            if (physicalPowered) {
                activateOwnedCoverRouteAfterPhysicalWake(physicalId)
            } else {
                CoverRouteActivation(
                    logicalId = -1,
                    physicalId = physicalId,
                    routeEnabled = false,
                    logicalPowered = false,
                    stillSafe = false,
                    error = physicalError ?: "physical cover wake failed",
                )
            }

        gen4PanelAuthority.completePrepare(
            intentSequence = intentSequence,
            success = physicalPowered,
            physicalDisplayId = physicalId.takeIf { it >= 0L },
            logicalDisplayId = activation.logicalId.takeIf { activation.stillSafe },
            routeReady = physicalPowered && activation.ok,
        )

        return gen4PanelBundle(
            operation = "prepare:$reason",
            ok = physicalPowered,
            decision =
                if (activation.ok) {
                    "cover-ready-hidden"
                } else {
                    "physical-ready-route-pending"
                },
            error = activation.error ?: physicalError,
        )
    }

    private fun reassertCoverPanelGen4(
        serviceEpoch: Long,
        closeCycleId: Long,
        transitionGeneration: Long,
        intentSequence: Long,
        reason: String,
    ): Bundle {
        val before = gen4PanelAuthority.snapshot()
        val expectedOwner =
            Fold7PanelAuthorityGen4.Owner(
                serviceEpoch = serviceEpoch,
                closeCycleId = closeCycleId,
                transitionGeneration = transitionGeneration,
            )

        if (before.owner != expectedOwner) {
            return gen4PanelBundle(
                operation = "reassert:$reason",
                ok = false,
                stale = true,
                decision = "owner-changed",
            )
        }

        val physicalId =
            before.physicalDisplayId
                ?: resolveFold7CoverPhysicalDisplayId(-1)

        val (physicalPowered, physicalError) =
            setPhysicalPowerNormal(physicalId)

        val activation =
            if (physicalPowered) {
                activateOwnedCoverRouteAfterPhysicalWake(physicalId)
            } else {
                CoverRouteActivation(
                    logicalId = -1,
                    physicalId = physicalId,
                    routeEnabled = false,
                    logicalPowered = false,
                    stillSafe = false,
                    error = physicalError ?: "cover reassert physical wake failed",
                )
            }

        gen4PanelAuthority.completePrepare(
            intentSequence = intentSequence,
            success = physicalPowered,
            physicalDisplayId = physicalId.takeIf { it >= 0L },
            logicalDisplayId = activation.logicalId.takeIf { activation.stillSafe },
            routeReady = physicalPowered && activation.ok,
        )

        return gen4PanelBundle(
            operation = "reassert:$reason",
            ok = physicalPowered,
            decision = if (activation.ok) "cover-ready-hidden" else "route-pending",
            error = activation.error ?: physicalError,
        )
    }

    private fun returnCoverPanelGen4(
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

    private fun reconcileCoverPanelGen4(
        serviceEpoch: Long,
        intentSequence: Long,
        reason: String,
    ): Bundle {
        val before = gen4PanelAuthority.snapshot()

        return when (before.phase) {
            Fold7PanelAuthorityGen4.Phase.RELEASE_PENDING ->
                returnCoverPanelGen4(
                    serviceEpoch = serviceEpoch,
                    intentSequence = intentSequence,
                    reason = "reconcile:$reason",
                )

            Fold7PanelAuthorityGen4.Phase.COVER_PREPARING,
            Fold7PanelAuthorityGen4.Phase.COVER_READY_HIDDEN -> {
                val owner = before.owner
                    ?: return gen4PanelBundle(
                        operation = "reconcile:$reason",
                        ok = false,
                        decision = "prepared-state-without-owner",
                    )

                reassertCoverPanelGen4(
                    serviceEpoch = owner.serviceEpoch,
                    closeCycleId = owner.closeCycleId,
                    transitionGeneration = owner.transitionGeneration,
                    intentSequence = intentSequence,
                    reason = "reconcile:$reason",
                )
            }

            else ->
                gen4PanelBundle(
                    operation = "reconcile:$reason",
                    ok = true,
                    decision = "already-native",
                )
        }
    }

    private fun gen4ShutdownCleanup() {
        // Graceful daemon exit normalizes observable cover routing even if the
        // app never completed Gen4 admission. Crash recovery remains the next
        // daemon lifetime's startup responsibility.
        normalizeGen4SecondaryRoute("shizuku-destroy")
    }

    private fun gen4PanelBundle(
        operation: String,
        ok: Boolean,
        stale: Boolean = false,
        cleanupRequired: Boolean = false,
        decision: String,
        error: String? = null,
    ): Bundle {
        val snapshot = gen4PanelAuthority.snapshot()
        val owner = snapshot.owner

        val leaseState =
            when (snapshot.phase) {
                Fold7PanelAuthorityGen4.Phase.RECOVERING -> "UNKNOWN_RECOVERY"
                Fold7PanelAuthorityGen4.Phase.COVER_PREPARING -> "PREWARM_IN_FLIGHT"
                Fold7PanelAuthorityGen4.Phase.COVER_READY_HIDDEN -> "HELD"
                Fold7PanelAuthorityGen4.Phase.RELEASE_PENDING -> "RELEASE_PENDING"
                Fold7PanelAuthorityGen4.Phase.INNER_NATIVE,
                Fold7PanelAuthorityGen4.Phase.NATIVE_COVER -> "IDLE"
            }

        return Bundle().apply {
            putBoolean("ok", ok)
            putBoolean("stale", stale)
            putBoolean("cleanupRequired", cleanupRequired)
            putString("operation", operation)
            putString("decision", decision)
            putString("error", error)

            putBoolean("gen4", true)
            putString("gen4Phase", snapshot.phase.name)
            putBoolean("gen4RecoveryReady", snapshot.recoveryReady)
            putLong("gen4IntentSequence", snapshot.lastIntentSequence)

            putLong("shellSession", shellSession)
            putLong("shellRevision", coverMutationRevision.incrementAndGet())
            putString("leaseState", leaseState)
            putLong("leaseId", owner?.serviceEpoch ?: 0L)
            // Compatibility receipt identity for the existing app-side readiness gate:
            // stable for one close cycle. intentSequence remains daemon-internal ordering.
            putLong("leaseEpoch", owner?.closeCycleId ?: 0L)
            putLong("ownerGeneration", owner?.transitionGeneration ?: -1L)
            putLong("ownerServiceEpoch", owner?.serviceEpoch ?: 0L)
            putLong("ownerCloseCycleId", owner?.closeCycleId ?: 0L)
            putLong("physicalDisplayId", snapshot.physicalDisplayId ?: -1L)
            putInt("targetDisplayId", snapshot.logicalDisplayId ?: -1)
            putBoolean("physicalLeaseHeld", snapshot.physicalHeld)
            putBoolean("routeReady", snapshot.routeReady)
        }
    }

'''
replace_exact(p, insert_marker, gen4_impl + insert_marker)

# ---------------------------------------------------------------------------
# Coordinator: semantic controller keeps its proven thresholds/renderer, while
# privileged panel authority is admitted and mutated exclusively through Gen4.
# ---------------------------------------------------------------------------
p = ROOT / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"

replace_exact(
    p,
    """    private val currentHingeAngle: () -> Float,\n    private val gen2: Fold7Gen2Kernel<android.graphics.Bitmap>,\n""",
    """    private val currentHingeAngle: () -> Float,\n    private val serviceEpoch: Long,\n    private val gen2: Fold7Gen2Kernel<android.graphics.Bitmap>,\n""",
)

replace_exact(
    p,
    """    private val mirrorSequence = AtomicLong(0L)\n    private val mirrorLeaseCounter = AtomicLong(0L)\n\n    @Volatile private var coverLeaseOwnerGeneration = -1L\n""",
    """    private val mirrorSequence = AtomicLong(0L)\n    private val mirrorLeaseCounter = AtomicLong(0L)\n    private val panelIntentSequence = AtomicLong(0L)\n\n    @Volatile private var coverLeaseOwnerGeneration = -1L\n""",
)

replace_exact(
    p,
    """    @Volatile private var prewarmRetryGeneration = -1L\n    @Volatile private var prewarmRetryCount = 0\n""",
    "",
)

replace_exact(
    p,
    """    @Volatile private var destroyed = false\n    @Volatile private var renderOwnershipArmed = false\n""",
    """    @Volatile private var destroyed = false\n    @Volatile private var renderOwnershipArmed = false\n    @Volatile private var armRequested = true\n    @Volatile private var gen4AdmissionInFlight = false\n    @Volatile private var gen4AdmittedConnectionEpoch = -1L\n    @Volatile private var gen4StartupRetryCount = 0\n    @Volatile private var gen4ReleaseRetryCount = 0\n""",
)

# Arm is now conditional on actual binder + daemon recovery admission.
arm_start = "    fun arm() {\n"
arm_end = "    fun onHinge(\n"
new_arm = r'''    fun arm() {
        armRequested = true
        destroyed = false
        renderOwnershipArmed = false

        if (!ShizukuBridge.ready) {
            onStatus("Fold7 continuity is waiting for the Gen4 panel daemon.")
            return
        }

        // Always perform a native-state admission round trip. This prevents a
        // rapid manual re-arm from racing an earlier asynchronous release.
        requestGen4Admission("manual-arm")
    }

    private fun armRecovered(
        reason: String,
    ) {
        if (
            destroyed ||
            !armRequested ||
            !ShizukuBridge.ready ||
            gen4AdmittedConnectionEpoch != ShizukuBridge.connectionEpoch
        ) {
            return
        }

        gen2.cancelActiveCycle()
        renderOwnershipArmed = true

        val angle =
            currentHingeAngle()
                .takeIf { it.isFinite() }
                ?: inferredRestAngle()

        val result =
            controller.reset(
                angle = angle,
                nowMs = SystemClock.uptimeMillis(),
                topology = topology(),
            )

        onStatus("Fold7 Gen4 continuity armed: ${result.state}.")
        DuoDiagnostics.event(
            "gen4-authority",
            "armed reason=$reason serviceEpoch=$serviceEpoch " +
                "connection=${ShizukuBridge.connectionEpoch} state=${result.state}",
        )

        hideMirror(
            generation = result.generation,
            reason = "gen4-arm:$reason",
            stopShellMirror = true,
        )
    }

    private fun requestGen4Admission(
        reason: String,
    ) {
        if (
            destroyed ||
            !ShizukuBridge.ready ||
            gen4AdmissionInFlight
        ) {
            return
        }

        val requestConnectionEpoch = ShizukuBridge.connectionEpoch
        val intentSequence = panelIntentSequence.incrementAndGet()
        gen4AdmissionInFlight = true
        renderOwnershipArmed = false

        scope.launch(Dispatchers.IO) {
            val result =
                runCatching {
                    ShizukuBridge.coverPanelStatusGen4(
                        serviceEpoch = serviceEpoch,
                        intentSequence = intentSequence,
                        reason = reason,
                    )
                }.getOrNull()

            handler.post {
                gen4AdmissionInFlight = false

                if (
                    destroyed ||
                    requestConnectionEpoch != ShizukuBridge.connectionEpoch ||
                    !ShizukuBridge.ready
                ) {
                    return@post
                }

                val acceptance =
                    acceptCoverLeaseSnapshot(
                        result = result,
                        connectionEpoch = requestConnectionEpoch,
                        reason = "gen4-admission:$reason",
                    )

                val phase = result?.getString("gen4Phase")
                val ready =
                    acceptance.accepted &&
                        result?.getBoolean("ok", false) == true &&
                        result.getBoolean("gen4RecoveryReady", false) &&
                        phase in setOf("INNER_NATIVE", "NATIVE_COVER")

                if (ready) {
                    gen4AdmittedConnectionEpoch = requestConnectionEpoch
                    gen4StartupRetryCount = 0
                    DuoDiagnostics.event(
                        "gen4-authority",
                        "admitted serviceEpoch=$serviceEpoch connection=$requestConnectionEpoch " +
                            "phase=${result.getString("gen4Phase")}",
                    )
                    if (armRequested) {
                        armRecovered("$reason:admitted")
                    }
                    return@post
                }

                gen4AdmittedConnectionEpoch = -1L
                renderOwnershipArmed = false

                if (gen4StartupRetryCount < MAX_GEN4_STARTUP_RETRIES) {
                    gen4StartupRetryCount += 1
                    handler.postDelayed(
                        {
                            requestGen4Admission(
                                "retry-$gen4StartupRetryCount:$reason"
                            )
                        },
                        GEN4_STARTUP_RETRY_MS,
                    )
                } else {
                    onStatus("Fold7 Gen4 panel recovery could not prove a safe route; continuity remains disarmed.")
                }
            }
        }
    }

'''
replace_between(p, arm_start, arm_end, new_arm)

replace_exact(
    p,
    """    fun onHinge(\n        angle: Float,\n        observedUptimeMs: Long = SystemClock.uptimeMillis(),\n    ) {\n        val decision =\n""",
    """    fun onHinge(\n        angle: Float,\n        observedUptimeMs: Long = SystemClock.uptimeMillis(),\n    ) {\n        if (!renderOwnershipArmed) return\n\n        val decision =\n""",
)

replace_exact(
    p,
    """    fun onEarlyOpeningEdge(\n        reason: String,\n    ) {\n        val decision =\n""",
    """    fun onEarlyOpeningEdge(\n        reason: String,\n    ) {\n        if (!renderOwnershipArmed) return\n\n        val decision =\n""",
)

replace_exact(
    p,
    """    fun onTopologyFastLane(reason: String) {\n        val angle =\n""",
    """    fun onTopologyFastLane(reason: String) {\n        if (!renderOwnershipArmed) return\n\n        val angle =\n""",
)

replace_exact(
    p,
    """    fun onTopologyChanged(reason: String) {\n        onTopologyFastLane(reason)\n        reconcileCoverLease(\"topology:$reason\")\n    }\n""",
    """    fun onTopologyChanged(reason: String) {\n        if (!renderOwnershipArmed) {\n            if (ShizukuBridge.ready) {\n                requestGen4Admission(\"topology:$reason\")\n            }\n            return\n        }\n\n        onTopologyFastLane(reason)\n        reconcileCoverLease(\"topology:$reason\")\n    }\n""",
)

replace_exact(
    p,
    """    fun release(reason: String) {\n        renderOwnershipArmed = false\n""",
    """    fun release(reason: String) {\n        armRequested = false\n        renderOwnershipArmed = false\n""",
)

replace_exact(
    p,
    """    fun destroy() {\n        destroyed = true\n        renderOwnershipArmed = false\n""",
    """    fun destroy() {\n        destroyed = true\n        armRequested = false\n        renderOwnershipArmed = false\n""",
)

# Destroy: route cleanup is semantic Gen4 return, never app-owned token release.
old_destroy_cover = r'''        val coverToken = gen2.coverAuthority.acceptedToken
        val coverShellSession =
            gen2.coverAuthority.acceptedSnapshot?.shellSession ?: 0L
        if (ShizukuBridge.ready) {
            Thread(
                {
                    runCatching {
                        if (coverToken != null) {
                            ShizukuBridge.releaseSecondaryDisplayV3(coverToken, "destroy")
                        } else {
                            ShizukuBridge.reconcileSecondaryDisplayLeaseV3(
                                coverShellSession,
                                "destroy",
                            )
                        }
                    }
                },
                "duo-cover-lease-destroy",
            ).apply { isDaemon = true }.start()
        }
'''
new_destroy_cover = r'''        if (ShizukuBridge.ready) {
            val intentSequence = panelIntentSequence.incrementAndGet()
            Thread(
                {
                    runCatching {
                        ShizukuBridge.returnCoverPanelGen4(
                            serviceEpoch = serviceEpoch,
                            intentSequence = intentSequence,
                            reason = "destroy",
                        )
                    }
                },
                "duo-gen4-cover-destroy",
            ).apply { isDaemon = true }.start()
        }
'''
replace_exact(p, old_destroy_cover, new_destroy_cover)

# Privileged ready/unavailable now reset connection admission explicitly.
ready_start = "    fun onPrivilegedReady() {\n"
ready_end = "    private fun apply(\n"
new_ready = r'''    fun onPrivilegedReady() {
        if (destroyed) return

        if (!ShizukuBridge.ready) {
            renderOwnershipArmed = false
            gen4AdmittedConnectionEpoch = -1L
            return
        }

        gen2.coverAuthority.onConnectionEpoch(
            ShizukuBridge.connectionEpoch
        )

        if (gen4AdmittedConnectionEpoch != ShizukuBridge.connectionEpoch) {
            renderOwnershipArmed = false
            requestGen4Admission("shizuku-ready")
            return
        }

        if (armRequested && !renderOwnershipArmed) {
            armRecovered("shizuku-ready")
        }

        reconcileCoverLease("shizuku-ready")
    }

    fun onPrivilegedUnavailable() {
        val previousState =
            controller.state

        renderOwnershipArmed = false
        gen4AdmittedConnectionEpoch = -1L
        gen4AdmissionInFlight = false
        gen4StartupRetryCount = 0

        hideMirror(
            generation = controller.generation,
            reason = "privilege-unavailable",
            stopShellMirror = false,
        )

        gen2.cancelActiveCycle()

        mirrorSession = 0L
        mirrorSessionOpening = false
        mirrorSequence.set(0L)
        coverRouteReassertInFlight = false
        prewarmInFlightGeneration = -1L
        prewarmInFlightConnectionEpoch = -1L

        gen2.coverAuthority.onConnectionEpoch(
            ShizukuBridge.connectionEpoch
        )

        gen2.coverReadiness.invalidate()

        val angle =
            currentHingeAngle()
                .takeIf { it.isFinite() }
                ?: inferredRestAngle()

        val reset =
            controller.reset(
                angle = angle,
                nowMs = SystemClock.uptimeMillis(),
                topology = topology(),
            )

        DuoDiagnostics.event(
            "gen4-authority",
            "privilege lost state=$previousState -> ${reset.state} " +
                "generation=${reset.generation} angle=$angle; " +
                "connection admission/render authority revoked",
        )
    }

'''
replace_between(p, ready_start, ready_end, new_ready)

# Replace prewarm with semantic Gen4 prepare. Existing readiness gate remains a
# receipt consumer only; it no longer grants physical mutation authority.
prewarm_start = "    private fun beginPrewarm(\n"
prewarm_end = "    private fun showMirror(\n"
new_prewarm = r'''    private fun beginPrewarm(
        generation: Long,
    ) {
        if (!controller.isGenerationCurrent(generation)) return

        val cycle = gen2.activeCycle
        if (
            !ShizukuBridge.ready ||
            gen4AdmittedConnectionEpoch != ShizukuBridge.connectionEpoch ||
            cycle == null
        ) {
            val decision =
                controller.onPrewarmResult(
                    requestGeneration = generation,
                    ok = false,
                    nowMs = SystemClock.uptimeMillis(),
                    topology = topology(),
                )
            apply(decision)
            return
        }

        val requestConnectionEpoch = ShizukuBridge.connectionEpoch
        if (
            prewarmInFlightGeneration == generation &&
            prewarmInFlightConnectionEpoch == requestConnectionEpoch
        ) {
            return
        }
        prewarmInFlightGeneration = generation
        prewarmInFlightConnectionEpoch = requestConnectionEpoch

        val intentSequence = panelIntentSequence.incrementAndGet()
        gen4RouteRetryCount = 0
        onStatus("Fold7 Gen4 cover preparing; visual remains hidden.")

        scope.launch(Dispatchers.IO) {
            if (!controller.isGenerationCurrent(generation)) {
                return@launch
            }

            val result =
                runCatching {
                    ShizukuBridge.prepareCoverPanelGen4(
                        serviceEpoch = cycle.serviceEpoch,
                        closeCycleId = cycle.closeCycleId,
                        transitionGeneration = generation,
                        intentSequence = intentSequence,
                        reason = "prewarm",
                    )
                }.getOrNull()

            handler.post {
                if (
                    prewarmInFlightGeneration == generation &&
                    prewarmInFlightConnectionEpoch == requestConnectionEpoch
                ) {
                    prewarmInFlightGeneration = -1L
                    prewarmInFlightConnectionEpoch = -1L
                }

                if (
                    !controller.isGenerationCurrent(generation) ||
                    requestConnectionEpoch != ShizukuBridge.connectionEpoch
                ) {
                    return@post
                }

                val acceptance =
                    acceptCoverLeaseSnapshot(
                        result = result,
                        connectionEpoch = requestConnectionEpoch,
                        reason = "gen4-prewarm",
                    )

                val snapshot = acceptance.snapshot
                val token = acceptance.token
                val currentCycle = gen2.activeCycle
                val ownsRequestedCycle =
                    token != null &&
                        token.ownerServiceEpoch == cycle.serviceEpoch &&
                        token.ownerCloseCycleId == cycle.closeCycleId &&
                        token.ownerGeneration == generation

                if (
                    !acceptance.accepted ||
                    snapshot == null ||
                    token == null ||
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

                val demand =
                    Fold7CoverReadiness.Demand(
                        serviceEpoch = currentCycle.serviceEpoch,
                        closeCycleId = currentCycle.closeCycleId,
                        transitionGeneration = generation,
                        leaseToken = token,
                        expectedLogicalId = snapshot.targetLogicalId,
                    )

                gen2.coverReadiness.begin(
                    demand = demand,
                    shellRouteReady = snapshot.routeReady,
                )

                observeCoverReadiness("gen4-prewarm-result")

                if (
                    controller.state == Fold7ContinuityController.State.COVER_PREWARMING &&
                    gen2.coverReadiness.state != Fold7CoverReadiness.State.READY
                ) {
                    scheduleReadinessWatchdog(currentCycle.closeCycleId)
                }
            }
        }
    }

'''
replace_between(p, prewarm_start, prewarm_end, new_prewarm)

# Replace route reassert/release/reconcile with Gen4 semantic intents.
authority_start = "    private fun ensureCoverRouteHeld(\n"
authority_end = "    private data class DisplaySnapshot(\n"
new_authority = r'''    private fun ensureCoverRouteHeld(
        reason: String,
    ) {
        if (
            destroyed ||
            !ShizukuBridge.ready ||
            gen4AdmittedConnectionEpoch != ShizukuBridge.connectionEpoch ||
            coverRouteReassertInFlight
        ) {
            return
        }

        if (
            controller.state !in setOf(
                Fold7ContinuityController.State.COVER_PREWARMING,
                Fold7ContinuityController.State.COVER_READY_HIDDEN,
                Fold7ContinuityController.State.COVER_VISUAL,
            )
        ) {
            return
        }

        val cycle = gen2.activeCycle ?: return
        val requestGeneration =
            gen2.coverReadiness.currentDemand?.transitionGeneration
                ?: gen2.coverAuthority.acceptedToken?.ownerGeneration
                ?: controller.generation
        val requestConnectionEpoch = ShizukuBridge.connectionEpoch
        val intentSequence = panelIntentSequence.incrementAndGet()
        coverRouteReassertInFlight = true

        scope.launch(Dispatchers.IO) {
            val result =
                runCatching {
                    ShizukuBridge.reassertCoverPanelGen4(
                        serviceEpoch = cycle.serviceEpoch,
                        closeCycleId = cycle.closeCycleId,
                        transitionGeneration = requestGeneration,
                        intentSequence = intentSequence,
                        reason = reason,
                    )
                }.getOrNull()

            handler.post {
                coverRouteReassertInFlight = false

                if (
                    destroyed ||
                    requestConnectionEpoch != ShizukuBridge.connectionEpoch
                ) {
                    return@post
                }

                val acceptance =
                    acceptCoverLeaseSnapshot(
                        result = result,
                        connectionEpoch = requestConnectionEpoch,
                        reason = "gen4-route-reassert:$reason",
                    )

                DuoDiagnostics.event(
                    "gen4-authority",
                    "route reassert reason=$reason generation=$requestGeneration " +
                        "accepted=${acceptance.accepted} decision=${acceptance.reason}",
                )

                if (acceptance.accepted) {
                    observeCoverReadiness("gen4-route-reassert:$reason")

                    if (gen2.coverReadiness.state == Fold7CoverReadiness.State.READY) {
                        gen4RouteRetryCount = 0
                    } else if (
                        gen4RouteRetryCount < MAX_GEN4_ROUTE_RETRIES &&
                        gen2.activeCycle?.closeCycleId == cycle.closeCycleId
                    ) {
                        gen4RouteRetryCount += 1
                        scheduleReadinessWatchdog(cycle.closeCycleId)
                    }
                }
            }
        }
    }

    private fun releaseCoverLease(
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

    private fun reconcileCoverLease(
        reason: String,
    ) {
        if (
            destroyed ||
            !ShizukuBridge.ready ||
            gen4AdmittedConnectionEpoch != ShizukuBridge.connectionEpoch
        ) {
            return
        }

        val requestConnectionEpoch = ShizukuBridge.connectionEpoch
        val intentSequence = panelIntentSequence.incrementAndGet()

        scope.launch(Dispatchers.IO) {
            val result =
                ShizukuBridge.reconcileCoverPanelGen4(
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
                        reason = "gen4-reconcile:$reason",
                    )

                if (acceptance.accepted) {
                    observeCoverReadiness("gen4-reconcile:$reason")
                }

                val pending =
                    acceptance.accepted &&
                        acceptance.snapshot?.leaseState == "RELEASE_PENDING"

                if (pending && gen4ReleaseRetryCount < MAX_GEN4_RELEASE_RETRIES) {
                    gen4ReleaseRetryCount += 1
                    handler.postDelayed(
                        {
                            reconcileCoverLease(
                                "pending-retry-$gen4ReleaseRetryCount:$reason"
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

'''
replace_between(p, authority_start, authority_end, new_authority)

# Gen4-specific constants; old CAS retry constant is no longer used.
replace_exact(
    p,
    """        const val READINESS_WATCHDOG_MS = 80L\n        const val FROZEN_FRAME_MAX_AGE_MS = 10_000L\n        const val MAX_PREWARM_CAS_RETRIES = 2\n""",
    """        const val READINESS_WATCHDOG_MS = 80L\n        const val FROZEN_FRAME_MAX_AGE_MS = 10_000L\n        const val MAX_GEN4_STARTUP_RETRIES = 4\n        const val GEN4_STARTUP_RETRY_MS = 60L\n        const val MAX_GEN4_RELEASE_RETRIES = 3\n        const val GEN4_RELEASE_RETRY_MS = 80L\n""",
)

# ---------------------------------------------------------------------------
# Accessibility service: no immediate arm. A Shizuku State.Ready emission only
# counts when the user-service binder is actually connected.
# ---------------------------------------------------------------------------
p = ROOT / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"

# Remove old one-shot immediate-auto-arm field/comment.
old_autoarm = r'''    /**
     * Automatically arm Fold7 geometry continuity once per accessibility-service
     * lifetime after Shizuku becomes ready.
     *
     * This is equivalent to pressing "Arm geometry continuity (4°)" once after
     * startup. It deliberately does not repeatedly re-arm on later Shizuku state
     * emissions, which could otherwise reset an active fold transition.
     */
    private var continuityAutoArmAttempted =
        false

'''
replace_exact(p, old_autoarm, "")

replace_exact(
    p,
    """            currentHingeAngle = { hinge.lastAngle },\n            gen2 = gen2,\n""",
    """            currentHingeAngle = { hinge.lastAngle },\n            serviceEpoch = serviceEpoch,\n            gen2 = gen2,\n""",
)

replace_exact(
    p,
    """                if (\n                    state is\n                        ShizukuBridge.State.Ready\n                ) {\n                    continuity.onPrivilegedReady()\n\n                    if (!continuityAutoArmAttempted) {\n                        continuityAutoArmAttempted =\n                            true\n\n                        continuity.arm()\n                    }\n                    primeCoverRoute(\n                        \"shizuku-ready\"\n                    )\n                } else {\n""",
    """                if (\n                    state is ShizukuBridge.State.Ready &&\n                    ShizukuBridge.ready\n                ) {\n                    continuity.onPrivilegedReady()\n                    primeCoverRoute(\n                        \"shizuku-ready\"\n                    )\n                } else {\n""",
)

# ---------------------------------------------------------------------------
# Version: Gen4 Alpha1.
# ---------------------------------------------------------------------------
p = ROOT / "app/build.gradle.kts"
replace_exact(p, "        versionCode = 40\n", "        versionCode = 41\n")
replace_exact(
    p,
    '        versionName = "3.0.0-alpha3-zfold7"\n',
    '        versionName = "4.0.0-alpha1-zfold7"\n',
)

# ---------------------------------------------------------------------------
# Fail-closed postconditions.
# ---------------------------------------------------------------------------
protocol = ROOT / "app/src/full/java/com/duoopen/shell/ShellProtocol.kt"
bridge = ROOT / "app/src/full/java/com/duoopen/shell/ShizukuBridge.kt"
shell = ROOT / "app/src/full/java/com/duoopen/shell/DuoShellService.kt"
coord = ROOT / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"
service = ROOT / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"
model = ROOT / "app/src/full/java/com/duoopen/shell/Fold7PanelAuthorityGen4.kt"
test = ROOT / "app/src/test/java/com/duoopen/shell/Fold7PanelAuthorityGen4Test.kt"
gradle = ROOT / "app/build.gradle.kts"

require(protocol, "const val COVER_PANEL_GEN4 = 18", 1)
require(bridge, "prepareCoverPanelGen4(", 1)
require(bridge, "returnCoverPanelGen4(", 1)
require(shell, "Fold7PanelAuthorityGen4()", 1)
require(shell, "legacy cover mutation rejected: Gen4 panel authority is active", 1)
require(shell, "ensureGen4StartupRecovered(", 2)
require(shell, "gen4ShutdownCleanup()", 2)
require(coord, "serviceEpoch: Long,", 1)
require(coord, "coverPanelStatusGen4(", 1)
require(coord, "prepareCoverPanelGen4(", 1)
require(coord, "reassertCoverPanelGen4(", 1)
require(coord, "returnCoverPanelGen4(", 2)
require(coord, "reconcileCoverPanelGen4(", 1)
forbid(coord, "prewarmSecondaryDisplayV4(")
forbid(coord, "ensureSecondaryDisplayHeldV3(")
forbid(coord, "releaseSecondaryDisplayV3(")
forbid(coord, "reconcileSecondaryDisplayLeaseV3(")
forbid(service, "continuityAutoArmAttempted")
require(service, "state is ShizukuBridge.State.Ready &&", 1)
require(service, "serviceEpoch = serviceEpoch,", 2)
require(model, "new-service-requires-route-normalization", 1)
require(test, "replacementServiceMustNormalizePreparedRoute", 1)
require(gradle, "versionCode = 41", 1)
require(gradle, 'versionName = "4.0.0-alpha1-zfold7"', 1)

# Preserve the measured Gen3 geometry policy exactly.
controller = ROOT / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityController.kt"
for needle in [
    "INNER_WAKE_MIN_DEG = 3f",
    "INNER_HANDOFF_MIN_DEG = 8f",
    "COVER_PREWARM_DEG = 174f",
    "COVER_VISUAL_START_DEG = 135f",
    "OPEN_LATCH_DEG = 172f",
    "OPEN_REARM_DEG = 166f",
]:
    require(controller, needle, 1)

# Gen4 may normalize a logical route with the existing power-reset primitive,
# but it must not introduce raw physical OFF or task migration.
for path in [coord, service, model]:
    forbid(path, "moveTaskToDisplay")
    forbid(path, "Display.STATE_OFF")

print("GEN4 ALPHA1 PANEL AUTHORITY PATCH: PASS")
