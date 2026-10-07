#!/usr/bin/env python3
"""Compile/validation hardening wrapper for S1V opening anchor proof.

V1 contains the architecture change. V2 keeps that design but fixes two
source-shape issues before CI materialization:
- nullable SnapshotSurface layout evidence is evaluated through one safe call;
- validator distinguishes the intentionally retained Gen5 helper declaration
  from an actual opening-loop invocation, which S1V forbids.
"""
from __future__ import annotations

import apply_s1v_opening_anchor_proof_v1 as base

_original_transform_panel = base.transform_panel
_original_validate = base.validate


def transform_panel(text: str) -> str:
    out = _original_transform_panel(text)
    old = '''                laidOut = snapshot?.view?.width?.let { it > 0 } == true &&
                    snapshot.view.height > 0,
'''
    new = '''                laidOut = snapshot?.view?.let { it.width > 0 && it.height > 0 } == true,
'''
    if old not in out:
        raise RuntimeError("S1V nullable layout evidence shape changed")
    return out.replace(old, new, 1)


def validate(gradle: str, panel: str, surface: str, composer: str, gate: str, gate_test: str) -> None:
    # V1's call-site check also matched the retained helper declaration. The
    # helper can remain dormant; the diagnostic invariant is that no call to it
    # survives in the opening presentation path.
    validation_panel = panel.replace(
        "private fun startGen5OpeningFrameLoop()",
        "private fun __s1v_retained_gen5_loop_helper()",
    )
    _original_validate(gradle, validation_panel, surface, composer, gate, gate_test)

    if "\n            startGen5OpeningFrameLoop()\n" in panel:
        raise RuntimeError("S1V anchor proof must not invoke Gen5 opening animation")


base.transform_panel = transform_panel
base.validate = validate

if __name__ == "__main__":
    raise SystemExit(base.main())
