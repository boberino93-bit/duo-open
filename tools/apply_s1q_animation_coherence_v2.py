#!/usr/bin/env python3
"""Compile-safe S1Q entry point.

V1's transform/validation logic is correct, but its write loop contains a
single local-variable typo (PANEL,q instead of PANEL,p). Reuse every V1
transform exactly and replace only the file-application function.
"""
from __future__ import annotations
from pathlib import Path
import apply_s1q_animation_coherence_v1 as base


def apply(repo: Path, check: bool) -> None:
    for rel in (base.GRADLE, base.HINGE, base.HINGE_TEST, base.PANEL, base.SHELL, base.EXPORTER):
        if not (repo / rel).exists():
            raise RuntimeError("missing " + str(rel))

    g = base.transform_gradle((repo / base.GRADLE).read_text())
    h = base.transform_hinge((repo / base.HINGE).read_text())
    ht = base.transform_hinge_test((repo / base.HINGE_TEST).read_text())
    p = base.transform_panel((repo / base.PANEL).read_text())
    s = base.transform_shell((repo / base.SHELL).read_text())
    e = base.transform_exporter((repo / base.EXPORTER).read_text())
    base.validate(g, h, ht, p, s, e)

    if not check:
        for rel, text in (
            (base.GRADLE, g),
            (base.HINGE, h),
            (base.HINGE_TEST, ht),
            (base.PANEL, p),
            (base.SHELL, s),
            (base.EXPORTER, e),
        ):
            (repo / rel).write_text(text)


base.apply = apply

if __name__ == "__main__":
    raise SystemExit(base.main())
