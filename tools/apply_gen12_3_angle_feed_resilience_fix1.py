#!/usr/bin/env python3
from __future__ import annotations

import runpy
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "apply_gen12_3_angle_feed_resilience.py"

text = SOURCE.read_text(encoding="utf-8")

old_ensure = '''    if feed_text.count("ensureAnchor()") != 3:\n        fail(f"expected three ensureAnchor calls, found {feed_text.count('ensureAnchor()')}")\n'''
new_ensure = '''    if feed_text.count("ensureAnchor()") != 4:\n        fail(f"expected three ensureAnchor call sites plus declaration, found {feed_text.count('ensureAnchor()')}")\n'''

old_remove = '''    if feed_text.count("removeAnchor()") != 1:\n        fail(f"expected one removeAnchor call, found {feed_text.count('removeAnchor()')}")\n'''
new_remove = '''    if feed_text.count("removeAnchor()") != 3:\n        fail(f"expected stop call, ensureAnchor refresh call, and declaration; found {feed_text.count('removeAnchor()')}")\n'''

if text.count(old_ensure) != 1:
    raise SystemExit("ERROR: Gen12.3 ensureAnchor matcher patch anchor missing")
if text.count(old_remove) != 1:
    raise SystemExit("ERROR: Gen12.3 removeAnchor matcher patch anchor missing")

text = text.replace(old_ensure, new_ensure, 1)
text = text.replace(old_remove, new_remove, 1)

patched = HERE / ".apply_gen12_3_angle_feed_resilience_fixed.py"
patched.write_text(text, encoding="utf-8")

sys.argv[0] = str(patched)
runpy.run_path(str(patched), run_name="__main__")
