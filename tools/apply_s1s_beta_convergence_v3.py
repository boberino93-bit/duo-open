#!/usr/bin/env python3
"""Compile-safe S1S entry point.

S1S replaces optical-proxy release timing with presentation readiness, but a
separate secondary reconciliation path still uses the historical 80 ms debounce.
Retain that constant for the secondary path only; the opening bridge release
continues to use Fold7InnerPresentationGate.
"""
from __future__ import annotations

import apply_s1s_beta_convergence_v2 as base

_original = base.base.transform_coordinator


def transform_coordinator(text: str) -> str:
    out = _original(text)
    if "const val INNER_BRIDGE_HANDOFF_SETTLE_MS = 80L" not in out:
        anchor = '''        // S1S supersedes the fixed 80 ms topology-only handoff.\n        const val INNER_PRESENTATION_STABLE_MS = 160L\n'''
        replacement = '''        // S1S supersedes the fixed 80 ms topology-only handoff for\n        // optical-proxy release. Retain 80 ms only for the independent\n        // secondary reconciliation debounce that still references it.\n        const val INNER_BRIDGE_HANDOFF_SETTLE_MS = 80L\n        const val INNER_PRESENTATION_STABLE_MS = 160L\n'''
        if anchor not in out:
            raise RuntimeError("S1S presentation constants anchor changed")
        out = out.replace(anchor, replacement, 1)
    return out


base.base.transform_coordinator = transform_coordinator

if __name__ == "__main__":
    raise SystemExit(base.base.main())
