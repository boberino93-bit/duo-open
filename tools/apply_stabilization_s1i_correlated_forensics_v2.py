#!/usr/bin/env python3
"""Escape-safe S1I transformer entry point for S1J replay.

This branch's workflow historically invokes the v2 filename. S1I's validated
build used the escape-safe behavior later named v3: preserve Kotlin's literal
``\\t`` and ``\\n`` source escapes for the manifest replacement, and keep the
corrected source-shape validator. This file intentionally aliases that proven
behavior so S1J reconstructs the exact S1I diagnostic layer that passed CI and
ran on the Fold7.
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
