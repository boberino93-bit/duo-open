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
    "coast capital",
]:
    assert marker.lower() in policy.lower(), marker

patcher = (BASE / "tools/apply_gen6_alpha1.py").read_text()
for marker in [
    "showPrivateFrostImmediately",
    "shell-black-terminal",
    "privacy-before-publish",
    "GEN6_PUBLIC_GLASS_MAX_BLUR_SPREAD",
    "snapshots.clear()",
    "gen2.frames.clearLatest()",
    "gen6-wake-hint",
    'versionName = "6.0.0-alpha1-zfold7"',
]:
    assert marker in patcher, marker


# Security/authority shape checks.
source_patch = patcher
assert "class PrivateFrostSurface" in source_patch
assert "PixelFormat.OPAQUE" in source_patch
assert "PrivateFrostSurface(service, windowManager)" in source_patch
assert "bitmap.recycle()" in source_patch
assert "shell-black-terminal" in source_patch
assert "ERROR_TAKE_SCREENSHOT_SECURE_WINDOW" in source_patch
assert "gen6ForcePrivateFrost" in source_patch
assert "accessibilityEventTypes=\"typeWindowStateChanged\"" in source_patch
assert "continuity.onEarlyOpeningEdge" not in source_patch

subprocess.run(
    [sys.executable, str(BASE / "tools/apply_gen6_alpha1.py"), "--self-test"],
    check=True,
)

print("GEN6 ALPHA1 PACKAGE STATIC GATE: PASS")
