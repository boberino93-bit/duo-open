#!/usr/bin/env python3
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"
BASE_PATCHER = ROOT / "tools/apply_gen2_ownership_batch_d.py"

if not BASE_PATCHER.exists():
    raise SystemExit("Missing original Batch D patcher.")

runpy.run_path(str(BASE_PATCHER), run_name="__main__")

text = SERVICE.read_text()

def cut_region(text: str, start: str, end: str, replacement: str, label: str) -> str:
    s = text.find(start)
    if s < 0:
        raise SystemExit(f"{label}: start anchor missing")
    if text.find(start, s + len(start)) >= 0:
        raise SystemExit(f"{label}: start anchor is not unique")
    e = text.find(end, s)
    if e < 0:
        raise SystemExit(f"{label}: end anchor missing")
    return text[:s] + replacement + text[e:]

text = cut_region(
    text,
    "    private var mirrorRequested =\n",
    "    private var coverRoutePrimeAttempted =\n",
    "    private var coverRoutePrimeAttempted =\n",
    "remove legacy ownership fields",
)

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

text = cut_region(
    text,
    "    private fun resolveCoverLogicalId(): Int {\n",
    "    private fun primeCoverRoute(\n",
    "    private fun primeCoverRoute(\n",
    "remove legacy logical-cover resolver",
)

text = cut_region(
    text,
    "    private fun assertCoverPower(\n",
    "    private fun updateRunning() {\n",
    "    private fun updateRunning() {\n",
    "remove legacy service continuity state machine",
)

legacy_single = (
    "        private const val SECONDARY_DISPLAY_SAFETY_RESET_MS =\n"
    "            90_000L\n\n"
)
if legacy_single not in text:
    raise SystemExit("legacy safety-reset constant anchor missing")
text = text.replace(legacy_single, "", 1)

text = cut_region(
    text,
    "        private const val MIRROR_REBIND_DEBOUNCE_MS =\n"
    "            16L\n",
    "        /** How old a panel's last picture may be and still bridge the next fold. */\n",
    "        /** How old a panel's last picture may be and still bridge the next fold. */\n",
    "remove legacy service continuity constants",
)

SERVICE.write_text(text)

final = SERVICE.read_text()

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
):
    if required not in final:
        raise SystemExit(
            f"coordinator authority postcondition missing: {required}"
        )

print("Batch D Fix 2: FoldOverlayService legacy ownership path removed.")
