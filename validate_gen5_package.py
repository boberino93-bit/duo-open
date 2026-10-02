#!/usr/bin/env python3
from pathlib import Path
import hashlib
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

required = [
    ".github/workflows/apply-gen5-beta1-virtual-hinge.yml",
    "APPLY_GEN5_BETA1_NOW.txt",
    "GEN5_BETA1_IMPLEMENTATION_PLAN.md",
    "GEN5_BETA1_FIELD_TEST_CHECKLIST.md",
    "GEN5_RND_VALIDATION.txt",
    "README_START_HERE_GEN5_BETA1.txt",
    "PRIMARY_AGENT_HANDOFF_GEN5_BETA1.txt",
    "tools/apply_gen5_beta1.py",
    "payload_gen5/main/com/duoopen/fold/Fold7VirtualHingeGen5.kt",
    "payload_gen5/main/com/duoopen/fold/Fold7VisualStateLut.kt",
    "payload_gen5/full/com/duoopen/overlay/Fold7RightPaneComposer.kt",
    "payload_gen5/test/com/duoopen/fold/Fold7VirtualHingeGen5Test.kt",
    "GEN5-SUPPORT-SHA256.txt",
]
for rel in required:
    if not (ROOT / rel).is_file():
        raise SystemExit(f"missing required file: {rel}")

workflow = (ROOT / ".github/workflows/apply-gen5-beta1-virtual-hinge.yml").read_text()
for needle in [
    "Verify exact Gen4 Alpha1 runtime baseline",
    "Run focused Gen5 and regression tests",
    "Run full Gen5 Beta1 gate",
    "Commit and push validated Gen5 Beta1 runtime",
    "Upload Gen5 Beta1 APK",
    "Fold7VirtualHingeGen5Test",
    "CHANGE_FRAME_RATE_ONLY_IF_SEAMLESS",
]:
    if needle not in workflow:
        raise SystemExit(f"workflow missing invariant: {needle}")

patcher = (ROOT / "tools/apply_gen5_beta1.py").read_text()
for needle in [
    'versionName = "5.0.0-beta1-zfold7"',
    "gen5VirtualHinge.startOpening",
    "Fold7RightPaneComposer",
    "GEN5_REQUESTED_HZ",
    "Share diagnostic data",
    "workflow_dispatch",
]:
    if needle not in patcher:
        raise SystemExit(f"patcher missing invariant: {needle}")

subprocess.run([sys.executable, "-m", "py_compile", str(ROOT / "tools/apply_gen5_beta1.py")], check=True)

for raw in (ROOT / "GEN5-SUPPORT-SHA256.txt").read_text().splitlines():
    raw = raw.strip()
    if not raw:
        continue
    expected, rel = raw.split(None, 1)
    rel = rel.strip().lstrip("*")
    data = (ROOT / rel).read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise SystemExit(f"checksum mismatch {rel}: expected={expected} actual={actual}")

# Optional local pure-Kotlin validation when kotlinc/java exist.
import shutil
if shutil.which("kotlinc") and shutil.which("java"):
    work = ROOT / ".validate_tmp"
    work.mkdir(exist_ok=True)
    test_main = work / "Gen5Smoke.kt"
    test_main.write_text('''
package com.duoopen.fold
import kotlin.math.abs
fun main() {
    val v = Fold7VirtualHingeGen5()
    v.startOpening(0L)
    val t = v.targetForFrame(500_000_000L, 516_666_667L)
    check(t.angleDegrees in 0f..Fold7VirtualHingeGen5.BLIND_MAX_ANGLE_DEG)
    val lut = Fold7VisualStateLut()
    check(abs(lut.stateFor(90f).glassAmount - 1f) < 0.001f)
    check(lut.stateFor(0f).glassAmount < 0.001f)
    check(lut.stateFor(180f).glassAmount < 0.001f)
    println("GEN5 PURE KOTLIN SMOKE: PASS")
}
''')
    jar = work / "smoke.jar"
    subprocess.run([
        "kotlinc",
        str(ROOT / "payload_gen5/main/com/duoopen/fold/Fold7VirtualHingeGen5.kt"),
        str(ROOT / "payload_gen5/main/com/duoopen/fold/Fold7VisualStateLut.kt"),
        str(test_main),
        "-include-runtime", "-d", str(jar),
    ], check=True)
    subprocess.run(["java", "-jar", str(jar)], check=True)
    shutil.rmtree(work)

print("GEN5 PACKAGE VALIDATION: PASS")
