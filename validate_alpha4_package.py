#!/usr/bin/env python3
from pathlib import Path
import hashlib
import json
import py_compile
import subprocess

ROOT = Path(__file__).resolve().parent


def die(msg: str):
    raise SystemExit(f"ERROR: {msg}")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

required = [
    ROOT / "README_START_HERE_ALPHA4.txt",
    ROOT / "PRIMARY_AGENT_HANDOFF_ALPHA4.txt",
    ROOT / "ALPHA4_RND_VALIDATION.txt",
    ROOT / "UPLOAD_AT_REPOSITORY_ROOT.txt",
    ROOT / "PACKAGE_MANIFEST.json",
    ROOT / "ALPHA4-SUPPORT-SHA256.txt",
    ROOT / "tools/apply_gen3_alpha4_process_recovery.py",
    ROOT / ".github/workflows/apply-gen3-alpha4-process-recovery.yml",
    ROOT / "payload_alpha4/app/src/full/java/com/duoopen/overlay/Fold7ProcessRecoveryGate.kt",
    ROOT / "payload_alpha4/app/src/test/java/com/duoopen/overlay/Fold7ProcessRecoveryGateTest.kt",
]
for path in required:
    if not path.is_file():
        die(f"missing required file: {path.relative_to(ROOT)}")

manifest = json.loads((ROOT / "PACKAGE_MANIFEST.json").read_text())
if manifest["baseline_commit"] != "98a7c1cde9fd36d47562b40fa25ed0b094038e70":
    die("unexpected baseline commit")
if manifest["target_version"] != "3.0.0-alpha4-zfold7":
    die("unexpected target version")

for line in (ROOT / "ALPHA4-SUPPORT-SHA256.txt").read_text().splitlines():
    if not line.strip():
        continue
    digest, rel = line.split(None, 1)
    path = ROOT / rel.strip()
    if not path.is_file():
        die(f"checksum target missing: {rel}")
    actual = sha256(path)
    if actual != digest:
        die(f"checksum mismatch: {rel}: expected {digest}, got {actual}")

py_compile.compile(
    str(ROOT / "tools/apply_gen3_alpha4_process_recovery.py"),
    doraise=True,
)

workflow = (ROOT / ".github/workflows/apply-gen3-alpha4-process-recovery.yml").read_text()
for needle in [
    "98a7c1cde9fd36d47562b40fa25ed0b094038e70",
    "testFullDebugUnitTest --tests '*Fold7ProcessRecoveryGateTest'",
    "testFullDebugUnitTest assembleFullDebug",
    "Reconcile foreign Fold7 cover authority before startup arm",
    "DuoOpen-ZFold7-3.0.0-alpha4",
]:
    if needle not in workflow:
        die(f"workflow missing invariant: {needle}")

patcher = (ROOT / "tools/apply_gen3_alpha4_process_recovery.py").read_text()
for needle in [
    "Fold7ProcessRecoveryGate(serviceEpoch)",
    "releaseForeignProcessLease",
    "continuityAutoArmAttempted",
    "versionCode = 41",
    "3.0.0-alpha4-zfold7",
]:
    if needle not in patcher:
        die(f"patcher missing invariant: {needle}")

print("ALPHA4 PACKAGE VALIDATION: PASS")
