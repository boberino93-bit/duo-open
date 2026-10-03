#!/usr/bin/env python3
"""Corrected entry point for S1I correlated forensics.

The first S1I transformer revision accidentally validated a runtime-expanded
filename prefix ("s0-") that does not exist literally in Kotlin source. Keep
the transformer logic unchanged and replace only that source-shape validator.
"""
from __future__ import annotations

import apply_stabilization_s1i_correlated_forensics as base


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


base.validate = validate

if __name__ == "__main__":
    raise SystemExit(base.main())
