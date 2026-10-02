#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).resolve().parent
PAYLOAD = BASE / "payload"

required = [
    PAYLOAD / "app/src/full/java/com/duoopen/overlay/Fold7Gen6OpeningAttemptOwner.kt",
    PAYLOAD / "app/src/full/java/com/duoopen/overlay/Fold7GlassPrivacyPolicy.kt",
    PAYLOAD / "app/src/full/java/com/duoopen/overlay/Fold7PrivacyRuntime.kt",
    PAYLOAD / "app/src/full/java/com/duoopen/overlay/Fold7WorkProfileDetector.kt",
    BASE / "GEN6_VISUAL_SECURITY_CONTRACT_V1.md",
    BASE / "tools/apply_gen6_alpha1.py",
]
for path in required:
    if not path.exists():
        raise SystemExit(f"missing {path}")

policy = (PAYLOAD / "app/src/full/java/com/duoopen/overlay/Fold7GlassPrivacyPolicy.kt").read_text()
for marker in [
    "PUBLIC_GLASS",
    "PRIVATE_FROST",
    "captureAllowed = false",
    "cacheAllowed = false",
    "proceduralOnly = true",
    "coast capital",
]:
    assert marker.lower() in policy.lower(), marker

patcher = (BASE / "tools/apply_gen6_alpha1.py").read_text()
for marker in [
    "class PublicGlassSurface",
    "class PrivateFrostSurface",
    "PixelFormat.TRANSLUCENT",
    "PixelFormat.OPAQUE",
    "setEarlyOpeningVisualLatched(\\n                            value = true",
    "ShizukuBridge.wakeInnerDisplay()",
    "gen6-wake-hint",
    "captureResult",
    "shell-secure-layer",
    "containsSecureLayers",
    "secure metadata",
    "snapshots.clear()",
    "gen2.frames.clearLatest()",
    "privilegedPixelRendererReady",
    "setGen6PrivateTransitionVisual",
    "cached pixels not reused",
    'versionName = "6.0.0-alpha1-zfold7"',
]:
    assert marker in patcher, marker

# Security/authority constraints.
assert "bitmap = null" in patcher  # PUBLIC_GLASS bootstrap is live/procedural.
assert "never materialize protected pixels" in patcher
assert "if (secure) null else b.getParcelable" in patcher
assert "ERROR_TAKE_SCREENSHOT_SECURE_WINDOW" in patcher
assert "gen6ForcePrivateFrost" in patcher
assert 'accessibilityEventTypes="typeWindowStateChanged"' in patcher


# Gen6 Fix3 proactive compile/security invariants.
for marker in [
    "val refreshView: View",
    "created.refreshView",
    "shell-secure-layer-prime",
    "shell-secure-layer-live",
    "packageChanged",
    "Never allow an old app's pixels to bootstrap a new app context",
    "secure-layer provenance cannot be",
]:
    assert marker in patcher, marker

# All Gen6 Shizuku capture lanes that may feed presentation state must preserve
# secure-layer metadata instead of collapsing it to a generic null bitmap.
assert patcher.count("ShizukuBridge.captureResult") >= 3

# WakeHint may wake infrastructure and visual material, but must not call the
# semantic opening ingress from its callback block.
wake_block_start = patcher.index('onWakeHint = { previousStateId, currentStateId ->')
wake_block_end = patcher.index('WakeHint early wake callback', wake_block_start)
wake_block = patcher[wake_block_start:wake_block_end]
assert "wakeInnerDisplay" in wake_block
assert "setEarlyOpeningVisualLatched" in wake_block
assert "continuity.onEarlyOpeningEdge" not in wake_block

subprocess.run(
    [sys.executable, str(BASE / "tools/apply_gen6_alpha1.py"), "--self-test"],
    check=True,
)

print("GEN6 ALPHA1 V2 PACKAGE STATIC GATE: PASS")
