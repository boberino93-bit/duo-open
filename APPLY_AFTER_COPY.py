#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent

predecessor = root / "service_packs" / "gen7_shizuku_onboarding_v1" / "apply_service_pack_v1.py"
if predecessor.exists():
    subprocess.run([sys.executable, str(predecessor), str(root)], check=True)
else:
    print("NOTE: predecessor Shizuku/onboarding pack is not in this drop; expected it to already exist in the repository.")

subprocess.run(
    [
        sys.executable,
        str(root / "tools" / "apply_gen7_runtime_regression_beta2.py"),
        "--repo",
        str(root),
    ],
    check=True,
)
print("GEN7_RUNTIME_REGRESSION_BETA2_APPLY_PASS")
