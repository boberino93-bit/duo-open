#!/usr/bin/env python3
"""S1S source-shape/compile-safe wrapper.

V1 implemented the NATIVE_COVER prepare fence but its validator intentionally
looked for a stable textual marker that was only present in the shell-side
rejection path. Add that same marker to the authority boundary.

S1S also replaces optical-proxy release timing with presentation readiness, but
a separate secondary reconciliation path still uses the historical 80 ms
debounce. Retain that constant for that secondary path only; the opening bridge
release continues to use Fold7InnerPresentationGate.
"""
from __future__ import annotations

import apply_s1s_beta_convergence_v1 as base

_original_panel_authority = base.transform_panel_authority
_original_coordinator = base.transform_coordinator


def transform_panel_authority(text: str) -> str:
    out = _original_panel_authority(text)
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


def transform_coordinator(text: str) -> str:
    out = _original_coordinator(text)
    if "const val INNER_BRIDGE_HANDOFF_SETTLE_MS = 80L" not in out:
        anchor = '''        // S1S supersedes the fixed 80 ms topology-only handoff.\n        const val INNER_PRESENTATION_STABLE_MS = 160L\n'''
        replacement = '''        // S1S supersedes the fixed 80 ms topology-only handoff for\n        // optical-proxy release. Retain 80 ms only for the independent\n        // secondary reconciliation debounce that still references it.\n        const val INNER_BRIDGE_HANDOFF_SETTLE_MS = 80L\n        const val INNER_PRESENTATION_STABLE_MS = 160L\n'''
        if anchor not in out:
            raise RuntimeError("S1S presentation constants anchor changed")
        out = out.replace(anchor, replacement, 1)
    return out


base.transform_panel_authority = transform_panel_authority
base.transform_coordinator = transform_coordinator

if __name__ == "__main__":
    raise SystemExit(base.main())
