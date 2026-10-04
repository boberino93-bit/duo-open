#!/usr/bin/env python3
"""Compile-safe S1L entry point.

The first S1L transformer coupled the speculative physical prewake callback to
WallpaperAngleFeed.kickPreciseBurst(). The reconstructed Beta2/S1J/S1K source
shape used by this build does not expose that optional helper. It is also not
required for S1L: the field finding is specifically about moving physical inner
panel power earlier while leaving angle acquisition, routing, continuity state,
and renderer authority unchanged.

Keep the S1L transformation otherwise identical and remove only that optional
precise-angle burst call from the generated FoldOverlayService source.
"""
from __future__ import annotations

import apply_speculative_inner_prewake_v1 as base

_original_transform_service = base.transform_service


def transform_service(text: str) -> str:
    out = _original_transform_service(text)
    optional = '''                    angleFeed
                        ?.kickPreciseBurst(
                            reason
                        )

'''
    if optional in out:
        out = out.replace(optional, "", 1)
    if "kickPreciseBurst(" in out and "device-state-preopen:" in out:
        raise RuntimeError("S1L pre-open callback must not depend on optional precise-burst helper")
    return out


base.transform_service = transform_service

if __name__ == "__main__":
    raise SystemExit(base.main())
