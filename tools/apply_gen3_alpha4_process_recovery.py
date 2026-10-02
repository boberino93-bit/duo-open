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
        fail(f"{path}: expected {count} occurrences, found {found}: {old[:140]!r}")
    path.write_text(text.replace(old, new, count))


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
    src = ROOT / "payload_alpha4" / src_rel
    dst = ROOT / dst_rel
    if not src.is_file():
        fail(f"missing payload {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


# ---------------------------------------------------------------------------
# Pure process-recovery owner + focused unit tests.
# ---------------------------------------------------------------------------
copy_payload(
    "app/src/full/java/com/duoopen/overlay/Fold7ProcessRecoveryGate.kt",
    "app/src/full/java/com/duoopen/overlay/Fold7ProcessRecoveryGate.kt",
)
copy_payload(
    "app/src/test/java/com/duoopen/overlay/Fold7ProcessRecoveryGateTest.kt",
    "app/src/test/java/com/duoopen/overlay/Fold7ProcessRecoveryGateTest.kt",
)

# ---------------------------------------------------------------------------
# Coordinator: process recovery becomes the startup authority barrier.
# ---------------------------------------------------------------------------
p = ROOT / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"

replace_exact(
    p,
    """    private val currentHingeAngle: () -> Float,\n    private val gen2: Fold7Gen2Kernel<android.graphics.Bitmap>,\n""",
    """    private val currentHingeAngle: () -> Float,\n    private val serviceEpoch: Long,\n    private val gen2: Fold7Gen2Kernel<android.graphics.Bitmap>,\n""",
)

replace_exact(
    p,
    """    @Volatile private var prewarmRetryCount = 0\n    @Volatile private var destroyed = false\n    @Volatile private var renderOwnershipArmed = false\n""",
    """    @Volatile private var prewarmRetryCount = 0\n    @Volatile private var destroyed = false\n    @Volatile private var renderOwnershipArmed = false\n    @Volatile private var armRequested = true\n\n    private val processRecovery =\n        Fold7ProcessRecoveryGate(serviceEpoch)\n""",
)

replace_exact(
    p,
    """    fun arm() {\n        gen2.cancelActiveCycle()\n        destroyed = false\n        renderOwnershipArmed = true\n\n        val angle =\n            currentHingeAngle()\n                .takeIf { it.isFinite() }\n                ?: inferredRestAngle()\n\n        val result =\n            controller.reset(\n                angle = angle,\n                nowMs = SystemClock.uptimeMillis(),\n                topology = topology(),\n            )\n\n        onStatus(\"Fold7 continuity armed: ${result.state}.\")\n\n        // Clear any stale mirror left by a previous service generation. Do not\n        // issue a power command here: CLOSED -> OPEN must remain purely local.\n        hideMirror(\n            generation = result.generation,\n            reason = \"arm\",\n            stopShellMirror = true,\n        )\n    }\n""",
    """    fun arm() {\n        armRequested = true\n        destroyed = false\n\n        if (!processRecovery.ready) {\n            renderOwnershipArmed = false\n            onStatus(\"Fold7 continuity is recovering prior privileged cover authority.\")\n            DuoDiagnostics.event(\n                \"gen3-recovery\",\n                \"arm deferred phase=${processRecovery.phase} serviceEpoch=$serviceEpoch\",\n            )\n            reconcileCoverLease(\"arm-awaiting-process-recovery\")\n            return\n        }\n\n        armRecovered(\"manual-arm\")\n    }\n\n    private fun armRecovered(\n        reason: String,\n    ) {\n        if (destroyed || !processRecovery.ready || !armRequested) return\n\n        gen2.cancelActiveCycle()\n        renderOwnershipArmed = true\n\n        val angle =\n            currentHingeAngle()\n                .takeIf { it.isFinite() }\n                ?: inferredRestAngle()\n\n        val result =\n            controller.reset(\n                angle = angle,\n                nowMs = SystemClock.uptimeMillis(),\n                topology = topology(),\n            )\n\n        onStatus(\"Fold7 continuity armed: ${result.state}.\")\n        DuoDiagnostics.event(\n            \"gen3-recovery\",\n            \"continuity armed reason=$reason serviceEpoch=$serviceEpoch \" +\n                \"state=${result.state} generation=${result.generation}\",\n        )\n\n        // Clear any stale mirror left by a previous service generation. Do not\n        // issue a power command here: CLOSED -> OPEN must remain purely local.\n        hideMirror(\n            generation = result.generation,\n            reason = \"arm:$reason\",\n            stopShellMirror = true,\n        )\n    }\n""",
)

replace_exact(
    p,
    """    fun onHinge(\n        angle: Float,\n        observedUptimeMs: Long = SystemClock.uptimeMillis(),\n    ) {\n        val decision =\n""",
    """    fun onHinge(\n        angle: Float,\n        observedUptimeMs: Long = SystemClock.uptimeMillis(),\n    ) {\n        if (!processRecovery.ready || !renderOwnershipArmed) return\n\n        val decision =\n""",
)

replace_exact(
    p,
    """    fun onEarlyOpeningEdge(\n        reason: String,\n    ) {\n        val decision =\n""",
    """    fun onEarlyOpeningEdge(\n        reason: String,\n    ) {\n        if (!processRecovery.ready || !renderOwnershipArmed) {\n            DuoDiagnostics.event(\n                \"gen3-recovery\",\n                \"early opening ignored while disarmed reason=$reason \" +\n                    \"phase=${processRecovery.phase}\",\n            )\n            return\n        }\n\n        val decision =\n""",
)

replace_exact(
    p,
    """    fun onTopologyFastLane(reason: String) {\n        val angle =\n""",
    """    fun onTopologyFastLane(reason: String) {\n        if (!processRecovery.ready || !renderOwnershipArmed) return\n\n        val angle =\n""",
)

replace_exact(
    p,
    """    fun onTopologyChanged(reason: String) {\n        onTopologyFastLane(reason)\n        reconcileCoverLease(\"topology:$reason\")\n    }\n""",
    """    fun onTopologyChanged(reason: String) {\n        if (!processRecovery.ready || !renderOwnershipArmed) {\n            reconcileCoverLease(\"process-recovery-topology:$reason\")\n            return\n        }\n\n        onTopologyFastLane(reason)\n        reconcileCoverLease(\"topology:$reason\")\n    }\n""",
)

replace_exact(
    p,
    """    fun release(reason: String) {\n        renderOwnershipArmed = false\n        gen2.cancelActiveCycle()\n        val generation = controller.generation\n\n        hideMirror(\n            generation = generation,\n            reason = reason,\n            stopShellMirror = true,\n        )\n\n        releaseCoverLease(reason)\n    }\n""",
    """    fun release(reason: String) {\n        armRequested = false\n        renderOwnershipArmed = false\n        gen2.cancelActiveCycle()\n        val generation = controller.generation\n\n        hideMirror(\n            generation = generation,\n            reason = reason,\n            stopShellMirror = true,\n        )\n\n        if (!processRecovery.ready) {\n            reconcileCoverLease(\"release-during-process-recovery:$reason\")\n            return\n        }\n\n        releaseCoverLease(reason)\n    }\n""",
)

replace_exact(
    p,
    """    fun destroy() {\n        destroyed = true\n        renderOwnershipArmed = false\n""",
    """    fun destroy() {\n        destroyed = true\n        armRequested = false\n        renderOwnershipArmed = false\n""",
)

replace_exact(
    p,
    """    fun onPrivilegedReady() {\n        if (destroyed) return\n        gen2.coverAuthority.onConnectionEpoch(\n            ShizukuBridge.connectionEpoch\n        )\n        reconcileCoverLease(\"shizuku-ready\")\n\n        if (\n            controller.state ==\n                Fold7ContinuityController.State.COVER_PREWARMING &&\n            gen2.activeCycle != null\n        ) {\n            beginPrewarm(controller.generation)\n        }\n    }\n""",
    """    fun onPrivilegedReady() {\n        if (destroyed) return\n        gen2.coverAuthority.onConnectionEpoch(\n            ShizukuBridge.connectionEpoch\n        )\n\n        if (!processRecovery.ready) {\n            renderOwnershipArmed = false\n            reconcileCoverLease(\"process-startup\")\n            return\n        }\n\n        if (armRequested && !renderOwnershipArmed) {\n            armRecovered(\"privileged-ready\")\n        }\n\n        reconcileCoverLease(\"shizuku-ready\")\n\n        if (\n            renderOwnershipArmed &&\n            controller.state ==\n                Fold7ContinuityController.State.COVER_PREWARMING &&\n            gen2.activeCycle != null\n        ) {\n            beginPrewarm(controller.generation)\n        }\n    }\n""",
)

# Insert process-recovery handling after accepted V3 snapshot parsing and before
# normal readiness observation.
old_reconcile_tail = """                if (acceptance.accepted) {\n                    observeCoverReadiness(\"reconcile:$reason\")\n                }\n            }\n        }\n    }\n\n    private data class DisplaySnapshot(\n"""
new_reconcile_tail = """                if (acceptance.accepted) {\n                    handleProcessRecoverySnapshot(\n                        acceptance = acceptance,\n                        reason = \"reconcile:$reason\",\n                    )\n\n                    if (processRecovery.ready) {\n                        observeCoverReadiness(\"reconcile:$reason\")\n                    }\n                }\n            }\n        }\n    }\n\n    private fun handleProcessRecoverySnapshot(\n        acceptance: Fold7CoverLeaseSnapshotGate.Acceptance,\n        reason: String,\n    ) {\n        if (!acceptance.accepted || processRecovery.ready) return\n\n        val snapshot = acceptance.snapshot ?: return\n        val decision =\n            processRecovery.observe(\n                snapshot = snapshot,\n                token = acceptance.token,\n            )\n\n        DuoDiagnostics.event(\n            \"gen3-recovery\",\n            \"process gate reason=$reason decision=${decision.reason} \" +\n                \"phase=${decision.phase} state=${snapshot.leaseState} \" +\n                \"ownerServiceEpoch=${snapshot.ownerServiceEpoch} \" +\n                \"currentServiceEpoch=$serviceEpoch lease=${snapshot.leaseId} \" +\n                \"leaseEpoch=${snapshot.leaseEpoch}\",\n        )\n\n        when (val action = decision.action) {\n            Fold7ProcessRecoveryGate.Action.None -> Unit\n\n            Fold7ProcessRecoveryGate.Action.Arm ->\n                armRecovered(\"process-recovery:${decision.reason}\")\n\n            is Fold7ProcessRecoveryGate.Action.ReleaseForeign ->\n                releaseForeignProcessLease(\n                    token = action.token,\n                    reason = decision.reason,\n                )\n        }\n    }\n\n    private fun releaseForeignProcessLease(\n        token: Fold7CoverLeaseSnapshotGate.LeaseToken,\n        reason: String,\n    ) {\n        if (destroyed || !ShizukuBridge.ready || processRecovery.ready) return\n\n        val requestConnectionEpoch = ShizukuBridge.connectionEpoch\n\n        DuoDiagnostics.event(\n            \"gen3-recovery\",\n            \"exact foreign release requested reason=$reason \" +\n                \"shell=${token.shellSession} lease=${token.leaseId} \" +\n                \"leaseEpoch=${token.leaseEpoch} ownerServiceEpoch=${token.ownerServiceEpoch} \" +\n                \"currentServiceEpoch=$serviceEpoch\",\n        )\n\n        scope.launch(Dispatchers.IO) {\n            val result =\n                runCatching {\n                    ShizukuBridge.releaseSecondaryDisplayV3(\n                        token = token,\n                        reason = \"process-recovery:$reason\",\n                    )\n                }.getOrNull()\n                    ?: ShizukuBridge.secondaryDisplayLeaseStatusV3(\n                        token.shellSession\n                    )\n\n            handler.post {\n                if (\n                    destroyed ||\n                    requestConnectionEpoch != ShizukuBridge.connectionEpoch\n                ) {\n                    return@post\n                }\n\n                val acceptance =\n                    acceptCoverLeaseSnapshot(\n                        result = result,\n                        connectionEpoch = requestConnectionEpoch,\n                        reason = \"process-recovery-release:$reason\",\n                    )\n\n                if (acceptance.accepted) {\n                    handleProcessRecoverySnapshot(\n                        acceptance = acceptance,\n                        reason = \"release-result:$reason\",\n                    )\n                }\n            }\n        }\n    }\n\n    private data class DisplaySnapshot(\n"""
replace_exact(p, old_reconcile_tail, new_reconcile_tail)

# Make recovery ownership visible in diagnostics.
replace_exact(
    p,
    """                \"epoch=${snapshot.leaseEpoch} owner=${snapshot.ownerGeneration} \" +\n                \"physical=${snapshot.physicalDisplayId} logical=${snapshot.targetLogicalId} \" +\n""",
    """                \"epoch=${snapshot.leaseEpoch} owner=${snapshot.ownerGeneration} \" +\n                \"ownerServiceEpoch=${snapshot.ownerServiceEpoch} \" +\n                \"ownerCloseCycle=${snapshot.ownerCloseCycleId} \" +\n                \"physical=${snapshot.physicalDisplayId} logical=${snapshot.targetLogicalId} \" +\n""",
)

# ---------------------------------------------------------------------------
# Service: recovery coordinator owns automatic startup arm; remove the previous
# immediate arm race from the Shizuku Ready collector.
# ---------------------------------------------------------------------------
p = ROOT / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"

replace_exact(
    p,
    """            currentHingeAngle = { hinge.lastAngle },\n            gen2 = gen2,\n""",
    """            currentHingeAngle = { hinge.lastAngle },\n            serviceEpoch = serviceEpoch,\n            gen2 = gen2,\n""",
)

replace_exact(
    p,
    """    /**\n     * Automatically arm Fold7 geometry continuity once per accessibility-service\n     * lifetime after Shizuku becomes ready.\n     *\n     * This is equivalent to pressing \"Arm geometry continuity (4°)\" once after\n     * startup. It deliberately does not repeatedly re-arm on later Shizuku state\n     * emissions, which could otherwise reset an active fold transition.\n     */\n    private var continuityAutoArmAttempted =\n        false\n\n""",
    """    /*\n     * Startup arm is owned by Fold7ProcessRecoveryGate inside the continuity\n     * coordinator. A fresh app process stays disarmed until daemon-side cover\n     * authority is proven clean or belongs to this exact serviceEpoch.\n     */\n\n""",
)

replace_exact(
    p,
    """                    continuity.onPrivilegedReady()\n\n                    if (!continuityAutoArmAttempted) {\n                        continuityAutoArmAttempted =\n                            true\n\n                        continuity.arm()\n                    }\n                    primeCoverRoute(\n""",
    """                    continuity.onPrivilegedReady()\n\n                    primeCoverRoute(\n""",
)

# ---------------------------------------------------------------------------
# Version bump.
# ---------------------------------------------------------------------------
p = ROOT / "app/build.gradle.kts"
replace_exact(p, "        versionCode = 40\n", "        versionCode = 41\n")
replace_exact(
    p,
    '        versionName = "3.0.0-alpha3-zfold7"\n',
    '        versionName = "3.0.0-alpha4-zfold7"\n',
)

# ---------------------------------------------------------------------------
# Fail-closed postconditions.
# ---------------------------------------------------------------------------
coord = ROOT / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"
service = ROOT / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"
gate = ROOT / "app/src/full/java/com/duoopen/overlay/Fold7ProcessRecoveryGate.kt"
test = ROOT / "app/src/test/java/com/duoopen/overlay/Fold7ProcessRecoveryGateTest.kt"
gradle = ROOT / "app/build.gradle.kts"

require(coord, "Fold7ProcessRecoveryGate(serviceEpoch)", 1)
require(coord, "releaseForeignProcessLease(", 2)
require(coord, "ownerServiceEpoch=${snapshot.ownerServiceEpoch}", 2)
require(coord, "serviceEpoch: Long,")
require(service, "serviceEpoch = serviceEpoch,", 1)
forbid(service, "continuityAutoArmAttempted")
require(service, "continuity.onPrivilegedReady()", 1)
require(gate, "foreign-release-already-requested", 1)
require(test, "foreignHeldLeaseRequiresExactCleanupBeforeArm", 1)
require(gradle, "versionCode = 41", 1)
require(gradle, 'versionName = "3.0.0-alpha4-zfold7"', 1)

# P0 recovery must not add forbidden physical-off/task-migration behavior.
for path in [coord, service, gate]:
    forbid(path, "setDisplayPower")
    forbid(path, "moveTaskToDisplay")

print("GEN3 ALPHA4 PROCESS RECOVERY PATCH: PASS")
