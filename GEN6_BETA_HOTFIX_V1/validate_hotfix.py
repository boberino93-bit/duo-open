#!/usr/bin/env python3
from pathlib import Path
import py_compile

root = Path(__file__).resolve().parent
patcher = root / "tools" / "apply_gen6_beta_hotfix.py"
text = patcher.read_text(encoding="utf-8")

required = [
    "coarse-public-shadow-only",
    "physical+logical inner early wake",
    "native-cover-terminal-fence",
    "route reassert fenced before shell mutation",
    "RIGHT_PANE_LEFT = 984f",
    "6.0.0-alpha2-zfold7",
]
for marker in required:
    assert marker in text, marker

wallpaper = text.split("PASSIVE_WALLPAPER = r'''", 1)[1].split("'''", 1)[0]
assert "HingeAngleSource" not in wallpaper
assert "DuoShader" not in wallpaper

py_compile.compile(str(patcher), doraise=True)
print("GEN6 BETA HOTFIX V1 VALIDATION: PASS")
