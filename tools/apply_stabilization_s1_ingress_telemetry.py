#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

MARKER = "STABILIZATION_S1_INGRESS_TELEMETRY_V1"
COORD = Path("app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt")
SERVICE = Path("app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_coordinator(text: str) -> str:
    if MARKER in text:
        return text

    # Measurement-only S1 change. Do not alter controller state, wake gating,
    # topology handling, hinge math, bridge ownership, or presentation logic.
    text = replace_once(
        text,
        '''            DuoDiagnostics.event(
                "inner-wake-stage",
                "WAKE_COMMITTED serviceEpoch=${openingKey.serviceEpoch} " +
                    "openingAttempt=${openingKey.openingAttemptSequence} retry=$attempt " +
                    "acceptedGeneration=${openingKey.acceptedGeneration} currentGeneration=${controller.generation}",
            )''',
        f'''            // {MARKER}: monotonic timestamps only; behavior is unchanged.
            DuoDiagnostics.event(
                "inner-wake-stage",
                "WAKE_COMMITTED serviceEpoch=${{openingKey.serviceEpoch}} " +
                    "openingAttempt=${{openingKey.openingAttemptSequence}} retry=$attempt " +
                    "acceptedGeneration=${{openingKey.acceptedGeneration}} currentGeneration=${{controller.generation}} " +
                    "queuedNs=$queuedAtNs commitNs=$startedAtNs",
            )''',
        "wake commit timing",
    )

    text = replace_once(
        text,
        '''                    "WAKE_RESULT serviceEpoch=${openingKey.serviceEpoch} " +
                        "openingAttempt=${openingKey.openingAttemptSequence} retry=$attempt " +
                        "keyCurrent=$keyStillCurrent ok=${result?.getBoolean("ok", false) == true} " +''',
        '''                    "WAKE_RESULT serviceEpoch=${openingKey.serviceEpoch} " +
                        "openingAttempt=${openingKey.openingAttemptSequence} retry=$attempt " +
                        "completedNs=$completedAtNs " +
                        "keyCurrent=$keyStillCurrent ok=${result?.getBoolean("ok", false) == true} " +''',
        "wake result completion timing",
    )

    text = replace_once(
        text,
        '''                "OPENING_ACCEPTED serviceEpoch=${wakeKey.serviceEpoch} " +
                    "openingAttempt=${wakeKey.openingAttemptSequence} " +
                    "generation=${wakeKey.acceptedGeneration} reason=${transition.reason}",''',
        '''                "OPENING_ACCEPTED serviceEpoch=${wakeKey.serviceEpoch} " +
                    "openingAttempt=${wakeKey.openingAttemptSequence} " +
                    "acceptedNs=${SystemClock.elapsedRealtimeNanos()} " +
                    "generation=${wakeKey.acceptedGeneration} reason=${transition.reason}",''',
        "opening accepted timing",
    )

    return text


def validate_prerequisites(service: str, coord: str) -> None:
    required_service = (
        '"lid-edge"',
        '"closed=$closed sourceNs=$sourceElapsedNs " +',
        '"arrivalNs=$arrivalNs lagMs=" +',
        'handleEarlyOpeningEdge(\n                            "lid-switch-open"',
    )
    for needle in required_service:
        if needle not in service:
            raise RuntimeError(f"missing S1 Hall-ingress prerequisite: {needle}")

    required_coord = (
        'physicalEdge = reason == "lid-switch-open"',
        '"OPENING_ACCEPTED serviceEpoch=${wakeKey.serviceEpoch} " +',
        '"WAKE_COMMITTED serviceEpoch=${openingKey.serviceEpoch} " +',
        '"WAKE_RESULT serviceEpoch=${openingKey.serviceEpoch} " +',
    )
    for needle in required_coord:
        if needle not in coord:
            raise RuntimeError(f"missing S1 wake-path prerequisite: {needle}")


def validate_output(service: str, coord: str) -> None:
    validate_prerequisites(service, coord)
    required = (
        MARKER,
        'acceptedNs=${SystemClock.elapsedRealtimeNanos()}',
        'queuedNs=$queuedAtNs commitNs=$startedAtNs',
        'completedNs=$completedAtNs',
    )
    for needle in required:
        if needle not in coord:
            raise RuntimeError(f"missing S1 telemetry invariant: {needle}")

    # Guard the phase boundary: S1 is instrumentation only.
    forbidden = (
        "FIRST_USEFUL_PIXEL",
        "COVER_PREWARM_DEG =",
        "INNER_WAKE_MIN_DEG =",
    )
    marker_window = coord[coord.index(MARKER) :]
    for needle in forbidden:
        if needle in marker_window[:1500]:
            raise RuntimeError(f"S1 telemetry unexpectedly touches later-phase behavior: {needle}")


def apply(repo: Path, check_only: bool) -> None:
    coord_path = repo / COORD
    service_path = repo / SERVICE
    if not coord_path.exists() or not service_path.exists():
        raise RuntimeError("required generated runtime sources missing")

    before = coord_path.read_text(encoding="utf-8")
    service = service_path.read_text(encoding="utf-8")
    validate_prerequisites(service, before)
    after = transform_coordinator(before)
    validate_output(service, after)

    if not check_only and after != before:
        coord_path.write_text(after, encoding="utf-8")


def self_test() -> None:
    coord = '''
            DuoDiagnostics.event(
                "inner-wake-stage",
                "WAKE_COMMITTED serviceEpoch=${openingKey.serviceEpoch} " +
                    "openingAttempt=${openingKey.openingAttemptSequence} retry=$attempt " +
                    "acceptedGeneration=${openingKey.acceptedGeneration} currentGeneration=${controller.generation}",
            )
                    "WAKE_RESULT serviceEpoch=${openingKey.serviceEpoch} " +
                        "openingAttempt=${openingKey.openingAttemptSequence} retry=$attempt " +
                        "keyCurrent=$keyStillCurrent ok=${result?.getBoolean("ok", false) == true} " +
                "OPENING_ACCEPTED serviceEpoch=${wakeKey.serviceEpoch} " +
                    "openingAttempt=${wakeKey.openingAttemptSequence} " +
                    "generation=${wakeKey.acceptedGeneration} reason=${transition.reason}",
'''
    out = transform_coordinator(coord)
    assert MARKER in out
    assert 'acceptedNs=${SystemClock.elapsedRealtimeNanos()}' in out
    assert 'queuedNs=$queuedAtNs commitNs=$startedAtNs' in out
    assert 'completedNs=$completedAtNs' in out
    # The transformer must be idempotent.
    assert transform_coordinator(out) == out
    print("stabilization S1 ingress telemetry self-test: PASS")


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

    apply(Path(args.repo).resolve(), check_only=args.check)
    print(
        "stabilization S1 ingress telemetry: " +
        ("source shape verified" if args.check else "applied")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
