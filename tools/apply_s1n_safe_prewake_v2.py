#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

GRADLE = Path("app/build.gradle.kts")
OBSERVER = Path("app/src/full/java/com/duoopen/overlay/Fold7DeviceStateObserver.kt")
EXPORTER = Path("app/src/main/java/com/duoopen/debug/DebugBundleExporter.kt")


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_gradle(text: str) -> str:
    if 'versionName = "5.1.0-beta2-zfold7-s1n"' in text:
        return text
    text = one(text, "        versionCode = 46\n", "        versionCode = 48\n", "versionCode")
    return one(
        text,
        '        versionName = "5.1.0-beta2-zfold7-s1l"\n',
        '        versionName = "5.1.0-beta2-zfold7-s1n"\n',
        "versionName",
    )


def transform_observer(text: str) -> str:
    if "Fold7SpeculativePrewakePolicy.shouldPrewake(" in text:
        return text

    old = '''        val speculativePreOpeningEdge =
            previousId != null &&
                previousFolded == true &&
                inferredFolded == true &&
                previousId != id &&
                previousId in learnedFoldedStateIds
'''
    new = '''        // S1N_SAFE_PREWAKE_V2: field regression S1M proved that learned
        // or synthetic DeviceState transitions are unsafe speculative-opening
        // signals. Admit only the native Fold7 CLOSED(0) -> TENT(1) edge that
        // was independently validated in S1L field evidence.
        val speculativePreOpeningEdge =
            Fold7SpeculativePrewakePolicy.shouldPrewake(
                previousStateId = previousId,
                currentStateId = id,
                previousFolded = previousFolded,
                currentFolded = inferredFolded,
            )
'''
    return one(text, old, new, "narrow speculative prewake admission")


def transform_exporter(text: str) -> str:
    if "safeSpeculativePrewake=S1N_SAFE_PREWAKE_V2" in text:
        return text
    old = '''                        appendLine(
                            "speculativeInnerPrewakePolicy=PHYSICAL_ONLY_NO_ROUTE_OR_CONTINUITY_MUTATION"
                        )
'''
    new = old + '''                        appendLine(
                            "safeSpeculativePrewake=S1N_SAFE_PREWAKE_V2"
                        )
                        appendLine(
                            "safeSpeculativePrewakeAdmission=EXACT_NATIVE_CLOSED_0_TO_TENT_1_ONLY"
                        )
                        appendLine(
                            "concurrentDeviceStateRouteProbe=REMOVED_AFTER_S1M_FIELD_REGRESSION"
                        )
'''
    return one(text, old, new, "export S1N identity")


def validate(g: str, o: str, e: str) -> None:
    required = (
        (g, ['versionCode = 48', 'versionName = "5.1.0-beta2-zfold7-s1n"']),
        (o, ["S1N_SAFE_PREWAKE_V2", "Fold7SpeculativePrewakePolicy.shouldPrewake("]),
        (e, ["safeSpeculativePrewake=S1N_SAFE_PREWAKE_V2", "EXACT_NATIVE_CLOSED_0_TO_TENT_1_ONLY", "REMOVED_AFTER_S1M_FIELD_REGRESSION"]),
    )
    for text, needles in required:
        for needle in needles:
            if needle not in text:
                raise RuntimeError("missing S1N invariant: " + needle)

    prohibited = (
        "PROBE_CONCURRENT_OUTER_DEFAULT",
        "cmd device_state state 5",
        "scheduleConcurrentOuterRouteProbe",
        "concurrent-outer-route-probe",
    )
    combined = "\n".join((o, e))
    for needle in prohibited:
        if needle in combined:
            raise RuntimeError("S1N must not retain S1M state-5 route probe: " + needle)


def apply(repo: Path, check: bool) -> None:
    for path in (GRADLE, OBSERVER, EXPORTER):
        if not (repo / path).exists():
            raise RuntimeError("missing " + str(path))

    g = transform_gradle((repo / GRADLE).read_text())
    o = transform_observer((repo / OBSERVER).read_text())
    e = transform_exporter((repo / EXPORTER).read_text())
    validate(g, o, e)

    if not check:
        (repo / GRADLE).write_text(g)
        (repo / OBSERVER).write_text(o)
        (repo / EXPORTER).write_text(e)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        sample = '        versionCode = 46\n        versionName = "5.1.0-beta2-zfold7-s1l"\n'
        out = transform_gradle(sample)
        assert "versionCode = 48" in out
        assert "zfold7-s1n" in out
        print("S1N safe prewake v2 transformer self-test: PASS")
        if not args.check:
            return 0

    apply(Path(args.repo).resolve(), args.check)
    print("S1N safe prewake v2: " + ("source shape verified" if args.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
