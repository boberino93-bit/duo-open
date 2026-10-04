#!/usr/bin/env python3
"""Escape-safe S1I transformer entry point.

S1I v1's manifest header replacement used a normal Python string, so Kotlin's
literal ``\\t`` and ``\\n`` source escapes were interpreted before matching.
This wrapper preserves the transformation and overrides only that one exact
replacement plus the corrected source-shape validator.
"""
from __future__ import annotations

import apply_stabilization_s1i_correlated_forensics as base

_original_one = base.one


def one(text: str, old: str, new: str, label: str) -> str:
    if label == "manifest timing header":
        old = r'''        file.writeText("sample\ttargetMs\tactualMs\tpanel\tbackend\tlogicalId\tphysicalId\tdisplayState\trawStatus\tclassification\tsecure\tfile\tbytes\tsha256\tmeanLuma\tlumaRange\tdarkFraction\terror\n")
'''
        new = r'''        file.writeText("sample\ttargetMs\tactualMs\tpanel\tbackend\tlogicalId\tphysicalId\tdisplayState\trawStatus\tclassification\tsecure\tfile\tbytes\tsha256\tmeanLuma\tlumaRange\tdarkFraction\tcaptureStartedElapsedMs\tcaptureFinishedElapsedMs\twallCaptureMs\tbackendCaptureMs\tsourceWidth\tsourceHeight\terror\n")
'''
    return _original_one(text, old, new, label)


def validate(p: str, s: str, b: str, v: str) -> None:
    required = (
        (p, ["RENDER_TIMELINE_PROBE = 20"]),
        (s, [base.M, "renderTimelineProbe()", "probeTimings", "displayFramework", "windowDisplays", "surfaceLayers"]),
        (b, ["fun renderTimelineProbe()", "RENDER_TIMELINE_PROBE"]),
        (
            v,
            [
                base.M,
                "captureStartedElapsedMs",
                "captureFinishedElapsedMs",
                "wallCaptureMs",
                "backendCaptureMs",
                "sourceWidth",
                "sourceHeight",
                "correlated-context.txt",
                "visual-forensics-sample",
            ],
        ),
    )
    for text, needles in required:
        for needle in needles:
            if needle not in text:
                raise RuntimeError("missing S1I invariant: " + needle)


base.one = one
base.validate = validate

if __name__ == "__main__":
    raise SystemExit(base.main())
