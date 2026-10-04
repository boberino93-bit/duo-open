#!/usr/bin/env python3
"""S1Q test-corrected entry point.

V1's implementation is retained. The original acceleration test mistakenly
converted the first 25 ms integration step using an 8.33 ms divisor. Warm the
integrator once, then compare equal 120 Hz intervals. V2's write-loop fix is
also retained here.
"""
from __future__ import annotations
from pathlib import Path
import apply_s1q_animation_coherence_v1 as base

_original_transform_hinge_test = base.transform_hinge_test


def transform_hinge_test(text: str) -> str:
    out = _original_transform_hinge_test(text)
    old = '''        val a = v.targetForFrame(25_000_000L, 33_333_333L)
        val b = v.targetForFrame(33_333_333L, 41_666_666L)
        val c = v.targetForFrame(41_666_666L, 49_999_999L)
        val dt = 0.008333333f
'''
    new = '''        // First callback is 25 ms after opening start; use it only to
        // warm the integrator. The acceleration assertion below compares
        // equal consecutive 120 Hz intervals.
        v.targetForFrame(25_000_000L, 33_333_333L)
        val a = v.targetForFrame(33_333_333L, 41_666_666L)
        val b = v.targetForFrame(41_666_666L, 49_999_999L)
        val c = v.targetForFrame(49_999_999L, 58_333_332L)
        val dt = 0.008333333f
'''
    if old not in out:
        raise RuntimeError("S1Q acceleration test shape changed")
    return out.replace(old, new, 1)


base.transform_hinge_test = transform_hinge_test


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
        for rel, output in (
            (base.GRADLE, g),
            (base.HINGE, h),
            (base.HINGE_TEST, ht),
            (base.PANEL, p),
            (base.SHELL, s),
            (base.EXPORTER, e),
        ):
            (repo / rel).write_text(output)


base.apply = apply

if __name__ == "__main__":
    raise SystemExit(base.main())
