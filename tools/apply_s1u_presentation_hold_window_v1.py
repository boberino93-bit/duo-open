#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

GRADLE = Path("app/build.gradle.kts")
GATE = Path("app/src/full/java/com/duoopen/overlay/Fold7InnerPresentationGate.kt")
GATE_TEST = Path("app/src/test/java/com/duoopen/overlay/Fold7InnerPresentationGateTest.kt")
COORDINATOR = Path("app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt")

MARKER = "S1U_PRESENTATION_HOLD_WINDOW_V1"
OLD_MAX_HOLD = "500L"
NEW_MAX_HOLD = "6_500L"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_gradle(text: str) -> str:
    if 'versionName = "5.1.0-beta2-zfold7-s1u"' in text:
        return text
    text = one(text, "        versionCode = 54\n", "        versionCode = 55\n", "versionCode")
    return one(
        text,
        '        versionName = "5.1.0-beta2-zfold7-s1t"\n',
        '        versionName = "5.1.0-beta2-zfold7-s1u"\n',
        "versionName",
    )


def transform_gate(text: str) -> str:
    if MARKER in text:
        return text

    text = one(
        text,
        "    private val maxHoldMs: Long = 500L,\n",
        "    // S1U_PRESENTATION_HOLD_WINDOW_V1: Fold7 field evidence includes a\n"
        "    // legitimate Samsung INNER publication delay near six seconds. Keep\n"
        "    // positive readiness as the normal release path; extend only the\n"
        "    // bounded emergency release so the continuity bridge is not dropped\n"
        "    // underneath a still-unpublished native destination.\n"
        "    private val maxHoldMs: Long = 6_500L,\n",
        "presentation gate max hold",
    )

    timeout_count = text.count('"bounded-timeout"')
    if timeout_count != 2:
        raise RuntimeError(
            f"presentation gate timeout reason: expected two matches, found {timeout_count}"
        )
    text = text.replace('"bounded-timeout"', '"degraded-timeout-release"')
    return text


def transform_gate_test(text: str) -> str:
    if "defaultGateCoversObservedLateSamsungWindow" in text:
        return text

    old = '''    @Test
    fun timeoutIsBounded() {
        val g = Fold7InnerPresentationGate(stableMs = 160L, maxHoldMs = 500L)
        g.begin(1_000L)
        assertEquals(
            Fold7InnerPresentationGate.Action.RELEASE_TIMEOUT,
            g.evaluate(1_501L, false, false).action,
        )
    }
'''
    new = old + '''
    @Test
    fun defaultGateCoversObservedLateSamsungWindow() {
        val g = Fold7InnerPresentationGate()
        g.begin(1_000L)
        assertEquals(
            Fold7InnerPresentationGate.Action.WAIT,
            g.evaluate(6_999L, innerDefault = false, innerPresentationReady = false).action,
        )
        assertEquals(
            Fold7InnerPresentationGate.Action.WAIT,
            g.evaluate(7_499L, innerDefault = false, innerPresentationReady = false).action,
        )
        assertEquals(
            Fold7InnerPresentationGate.Action.RELEASE_TIMEOUT,
            g.evaluate(7_500L, innerDefault = false, innerPresentationReady = false).action,
        )
    }

    @Test
    fun readinessStillReleasesBeforeEmergencyWindow() {
        val g = Fold7InnerPresentationGate()
        g.begin(1_000L)
        assertEquals(
            Fold7InnerPresentationGate.Action.WAIT,
            g.evaluate(6_000L, innerDefault = true, innerPresentationReady = true).action,
        )
        assertEquals(
            Fold7InnerPresentationGate.Action.RELEASE_READY,
            g.evaluate(6_160L, innerDefault = true, innerPresentationReady = true).action,
        )
    }
'''
    return one(text, old, new, "S1U presentation gate regression tests")


def transform_coordinator(text: str) -> str:
    if "S1U_PRESENTATION_MAX_HOLD_MS" in text:
        return text
    return one(
        text,
        "        const val INNER_PRESENTATION_MAX_HOLD_MS = 500L\n",
        "        // S1U_PRESENTATION_MAX_HOLD_MS: field-bounded emergency release.\n"
        "        const val INNER_PRESENTATION_MAX_HOLD_MS = 6_500L\n",
        "coordinator presentation max hold",
    )


def validate(gradle: str, gate: str, gate_test: str, coordinator: str) -> None:
    required = (
        (gradle, ['versionCode = 55', 'versionName = "5.1.0-beta2-zfold7-s1u"']),
        (gate, [MARKER, "private val maxHoldMs: Long = 6_500L", '"degraded-timeout-release"']),
        (gate_test, ["defaultGateCoversObservedLateSamsungWindow", "readinessStillReleasesBeforeEmergencyWindow"]),
        (coordinator, ["S1U_PRESENTATION_MAX_HOLD_MS", "INNER_PRESENTATION_MAX_HOLD_MS = 6_500L"]),
    )
    for text, needles in required:
        for needle in needles:
            if needle not in text:
                raise RuntimeError(f"missing S1U invariant: {needle}")

    if "INNER_PRESENTATION_STABLE_MS = 160L" not in coordinator:
        raise RuntimeError("S1U must not weaken the positive-readiness stable window")


def apply(repo: Path, check: bool) -> None:
    paths = [repo / GRADLE, repo / GATE, repo / GATE_TEST, repo / COORDINATOR]
    if not all(path.exists() for path in paths):
        raise RuntimeError("required S1T materialized sources are missing")

    before = [path.read_text(encoding="utf-8") for path in paths]
    after = [
        transform_gradle(before[0]),
        transform_gate(before[1]),
        transform_gate_test(before[2]),
        transform_coordinator(before[3]),
    ]
    validate(*after)

    if not check:
        for path, content in zip(paths, after):
            path.write_text(content, encoding="utf-8")


def self_test() -> None:
    stable_ms = 160
    max_hold_ms = 6_500

    def evaluate(elapsed: int, ready_since: int | None) -> str:
        if ready_since is not None and elapsed - ready_since >= stable_ms:
            return "RELEASE_READY"
        if elapsed >= max_hold_ms:
            return "RELEASE_TIMEOUT"
        return "WAIT"

    assert evaluate(5_999, None) == "WAIT"
    assert evaluate(6_499, None) == "WAIT"
    assert evaluate(6_500, None) == "RELEASE_TIMEOUT"
    assert evaluate(5_160, 5_000) == "RELEASE_READY"
    print("S1U presentation hold-window model: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        if not args.check:
            return 0

    apply(Path(args.repo).resolve(), args.check)
    print("S1U presentation hold window: " + ("source shape verified" if args.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
