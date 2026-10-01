#!/usr/bin/env python3
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"
BASE_PATCHER = ROOT / "tools/apply_gen2_ownership_batch_d.py"

if not BASE_PATCHER.exists():
    raise SystemExit("Missing original Batch D patcher.")

# First apply the exact original Batch D ownership integration.
runpy.run_path(str(BASE_PATCHER), run_name="__main__")

text = SERVICE.read_text()

def cut_before(text: str, start: str, end: str, label: str) -> str:
    s = text.find(start)
    if s < 0:
        raise SystemExit(f"{label}: start anchor missing")
    if text.find(start, s + len(start)) >= 0:
        raise SystemExit(f"{label}: start anchor is not unique")
    e = text.find(end, s)
    if e < 0:
        raise SystemExit(f"{label}: end anchor missing")
    return text[:s] + text[e:]

# Retire service-owned mirror/panel state while keeping the still-used
# cover-route priming flag.
text = cut_before(
    text,
    "    private var mirrorRequested =\n",
    "    private var coverRoutePrimeAttempted =\n",
    "remove legacy ownership fields before cover-route prime state",
)

# The remainder of the obsolete fields sits below coverRoutePrimeAttempted:
# watchdog result, power watchdog, mirror refresh, and 90-second safety reset.
legacy_field_tail_start = """    /**
     * Last watchdog power result, used only to avoid flooding diagnostics with
     * an identical event every 100 ms while the physical cover is held on.
     */
"""
text = cut_before(
    text,
    legacy_field_tail_start,
    "    private var pendingDisplaySyncReason =\n",
    "remove legacy watchdog/mirror/safety-reset fields",
)

# Remove the exact old teardown block. Coordinator.destroy() is now the
# privileged ownership teardown authority.
legacy_destroy_block = """        handler.removeCallbacks(
            displayProbeRunnable
        )

        handler.removeCallbacks(
            mirrorRefreshRunnable
        )

        handler.removeCallbacks(
            openReleaseRunnable
        )

        mirrorRequested =
            false

        mirrorHost?.detach()
        mirrorHost =
            null
        mirrorHostCreatedUptime =
            0L

        runCatching {
            ShizukuBridge.stopDisplayMirror()
        }

        handler.removeCallbacks(
            secondaryDisplaySafetyReset
        )

        handler.removeCallbacks(
            displaySyncRunnable
        )
"""
replacement_destroy_block = """        handler.removeCallbacks(
            displayProbeRunnable
        )

        handler.removeCallbacks(
            displaySyncRunnable
        )
"""
if text.count(legacy_destroy_block) != 1:
    raise SystemExit(
        "remove legacy ownership teardown: expected one complete onDestroy block, "
        f"found {text.count(legacy_destroy_block)}"
    )
text = text.replace(
    legacy_destroy_block,
    replacement_destroy_block,
    1,
)
print("removed legacy ownership teardown")

# Remove helper/state-machine implementations that only served the retired
# service-level continuity controller.
text = cut_before(
    text,
    "    private fun resolveCoverLogicalId(): Int {\n",
    "    private fun primeCoverRoute(\n",
    "remove legacy logical-cover resolver",
)

text = cut_before(
    text,
    "    private fun assertCoverPower(\n",
    "    private fun updateRunning() {\n",
    "remove legacy service continuity state machine",
)

# Remove constants owned solely by the retired service-level controller.
legacy_single = (
    "        private const val SECONDARY_DISPLAY_SAFETY_RESET_MS =\n"
    "            90_000L\n\n"
)
if text.count(legacy_single) != 1:
    raise SystemExit(
        "legacy safety-reset constant: expected exactly one anchor, "
        f"found {text.count(legacy_single)}"
    )
text = text.replace(legacy_single, "", 1)

text = cut_before(
    text,
    "        private const val MIRROR_REBIND_DEBOUNCE_MS =\n"
    "            16L\n",
    "        /** How old a panel's last picture may be and still bridge the next fold. */\n",
    "remove legacy service continuity constants",
)

SERVICE.write_text(text)

final = SERVICE.read_text()

# Single-authority invariant: FoldOverlayService may delegate continuity work,
# but it must not directly own privileged mirror/panel lifecycle anymore.
for forbidden in (
    "DisplayMirrorHost(",
    "ShizukuBridge.stopDisplayMirror()",
    "runSecondaryDisplayExperiment(",
    "private fun syncMirrorHost(",
    "private fun handleContinuityHinge(",
    "private fun armGeometryContinuity(",
    "private fun releaseCoverPowerHold(",
    "mirrorRequested",
    "coverPowerHold",
    "mirrorRefreshRunnable",
    "secondaryDisplaySafetyReset",
    "openReleaseRunnable",
    "coverPowerWatchdog",
):
    if forbidden in final:
        raise SystemExit(
            f"legacy ownership bypass remains in FoldOverlayService: {forbidden}"
        )

for required in (
    "continuity.onHinge(angle)",
    "continuity.onTopologyChanged(",
    "continuity.destroy()",
    "continuity.onPrivilegedReady()",
    "continuity.onPrivilegedUnavailable()",
    "service.continuity.arm()",
    "service.continuity.release(",
    "private var coverRoutePrimeAttempted =",
    "private var pendingDisplaySyncReason =",
):
    if required not in final:
        raise SystemExit(
            f"coordinator/service postcondition missing: {required}"
        )

# Catch accidental duplicate boundaries from text surgery.
for singular in (
    "    private fun primeCoverRoute(\n",
    "    private fun updateRunning() {\n",
    "    private var coverRoutePrimeAttempted =\n",
    "    private var pendingDisplaySyncReason =\n",
):
    count = final.count(singular)
    if count != 1:
        raise SystemExit(
            f"postcondition expected exactly one {singular!r}, found {count}"
        )

print("Batch D Fix 3: FoldOverlayService legacy ownership path removed cleanly.")
