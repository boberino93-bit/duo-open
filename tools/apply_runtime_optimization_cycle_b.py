#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

MARKER_A = "RUNTIME_OPTIMIZATION_CYCLE_A_V1"
MARKER_B = "RUNTIME_OPTIMIZATION_CYCLE_B_V1"
HINGE = "app/src/main/java/com/duoopen/fold/HingeAngleSource.kt"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_hinge(text: str) -> str:
    if f"{MARKER_B}:HINGE_INCREMENTAL" in text:
        return text
    if f"{MARKER_A}:HINGE_SELECTOR" not in text:
        raise RuntimeError("Cycle B requires the validated Cycle A hinge selector first")

    old_candidates = '''    private val candidates: List<Stats> = discover().map(::Stats)\n    private val authority = Fold7AngleAuthority()'''
    new_candidates = f'''    private val candidates: List<Stats> = discover().map(::Stats)\n    // {MARKER_B}:SENSOR_INDEX\n    // Sensor objects are stable for this source lifetime; index once instead of\n    // linearly scanning every candidate for every hardware callback.\n    private val statsBySensor = candidates.associateBy {{ it.sensor }}\n    private val authority = Fold7AngleAuthority()'''
    text = replace_once(text, old_candidates, new_candidates, "sensor stats index")

    old_lookup = '''        val stats = candidates.firstOrNull { it.sensor == event.sensor } ?: return'''
    new_lookup = '''        val stats = statsBySensor[event.sensor] ?: return'''
    text = replace_once(text, old_lookup, new_lookup, "per-sample sensor lookup")

    old_call = '''        if (choose() !== stats) return'''
    new_call = '''        if (choose(stats) !== stats) return'''
    text = replace_once(text, old_call, new_call, "incremental selector call")

    old_choose = '''    private fun choose(): Stats? {\n        // RUNTIME_OPTIMIZATION_CYCLE_A_V1:HINGE_SELECTOR\n        // Preserve the exact ordering rule from filter + minWithOrNull while\n        // avoiding a temporary List and Comparator traversal on every sensor sample.\n        var best: Stats? = null\n        for (candidate in candidates) {\n            if (candidate.events <= 0) continue\n            val incumbent = best\n            if (\n                incumbent == null ||\n                candidate.resolution < incumbent.resolution ||\n                (\n                    candidate.resolution == incumbent.resolution &&\n                        candidate.isStandard &&\n                        !incumbent.isStandard\n                    )\n            ) {\n                best = candidate\n            }\n        }\n\n        val selected = best ?: return null\n        val current = active\n        if (current == null || selected.resolution < current.resolution) {\n            if (current !== selected) {\n                Log.i(\n                    TAG,\n                    "public hinge source: ${selected.sensor.name} (res ${selected.resolution})",\n                )\n            }\n            active = selected\n            activeSensor = selected.sensor\n            return selected\n        }\n        return current\n    }'''

    new_choose = f'''    private fun choose(reporting: Stats): Stats? {{\n        // {MARKER_B}:HINGE_INCREMENTAL\n        // The original selector can change ownership only when a newly reporting\n        // sensor has strictly finer resolution than the current owner. Preserve\n        // that exact promotion rule directly instead of rescanning all producers.\n        val current = active\n        if (current == null || reporting.resolution < current.resolution) {{\n            if (current !== reporting) {{\n                Log.i(\n                    TAG,\n                    "public hinge source: ${{reporting.sensor.name}} (res ${{reporting.resolution}})",\n                )\n            }}\n            active = reporting\n            activeSensor = reporting.sensor\n            return reporting\n        }}\n        return current\n    }}'''
    text = replace_once(text, old_choose, new_choose, "incremental hinge selector")
    return text


def apply(repo: Path, check_only: bool) -> None:
    path = repo / HINGE
    if not path.exists():
        raise RuntimeError(f"missing source file: {HINGE}")
    before = path.read_text(encoding="utf-8")
    after = transform_hinge(before)
    if MARKER_B not in after:
        raise RuntimeError("Cycle B marker missing after transform")
    if not check_only and after != before:
        path.write_text(after, encoding="utf-8")


def self_test() -> None:
    # Exact semantic equivalence of the ownership promotion rule:
    # first reporting sensor owns; later ownership changes only for strictly
    # finer resolution. Equal-resolution producers never displace current.
    def old(events, resolutions, standards, active_index, reporting_index):
        reporting = [i for i, count in enumerate(events) if count > 0]
        if not reporting:
            return None
        best = min(reporting, key=lambda i: (resolutions[i], not standards[i]))
        if active_index is None or resolutions[best] < resolutions[active_index]:
            return best
        return active_index

    def incremental(resolutions, active_index, reporting_index):
        if active_index is None or resolutions[reporting_index] < resolutions[active_index]:
            return reporting_index
        return active_index

    scenarios = [
        ([1, 0], [1.0, 0.1], [True, False], None, 0),
        ([1, 1], [1.0, 0.1], [True, False], 0, 1),
        ([1, 1], [0.1, 0.1], [False, True], 0, 1),
        ([3, 4, 1], [0.5, 0.2, 1.0], [True, False, True], 1, 2),
    ]
    for events, resolutions, standards, active_index, reporting_index in scenarios:
        assert old(events, resolutions, standards, active_index, reporting_index) == incremental(
            resolutions,
            active_index,
            reporting_index,
        )
    print("runtime optimization cycle B selector model: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    apply(Path(args.repo).resolve(), check_only=args.check)
    print(
        "runtime optimization cycle B: " +
        ("source shape verified" if args.check else "applied")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
