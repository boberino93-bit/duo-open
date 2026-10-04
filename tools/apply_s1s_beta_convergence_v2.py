#!/usr/bin/env python3
"""S1S source-shape wrapper.

V1 implemented the NATIVE_COVER prepare fence but its validator intentionally
looked for a stable textual marker that was only present in the shell-side
rejection path. Add that same marker to the authority boundary without changing
behavior, then reuse the V1 transform/validation in full.
"""
from __future__ import annotations

import apply_s1s_beta_convergence_v1 as base

_original = base.transform_panel_authority


def transform_panel_authority(text: str) -> str:
    out = _original(text)
    if "terminal-native-cover-fence" not in out:
        needle = "        // S1S_BETA_CONVERGENCE_V1: NATIVE_COVER is terminal for a close\n"
        replacement = (
            "        // terminal-native-cover-fence\n"
            "        // S1S_BETA_CONVERGENCE_V1: NATIVE_COVER is terminal for a close\n"
        )
        if needle not in out:
            raise RuntimeError("S1S authority fence comment anchor changed")
        out = out.replace(needle, replacement, 1)
    return out


base.transform_panel_authority = transform_panel_authority

if __name__ == "__main__":
    raise SystemExit(base.main())
