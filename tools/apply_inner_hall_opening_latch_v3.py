#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

CONTROLLER = Path("app/src/full/java/com/duoopen/overlay/Fold7ContinuityController.kt")
COORDINATOR = Path("app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt")
SERVICE = Path("app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt")
MARKER = "INNER_HALL_OPENING_LATCH_V3"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_controller(text: str) -> str:
    if MARKER in text:
        return text

    text = replace_once(
        text,
        "    private var closingFloorAngle = Float.NaN\n",
        "    private var closingFloorAngle = Float.NaN\n\n"
        "    // INNER_HALL_OPENING_LATCH_V3: accepted binary opening evidence\n"
        "    // survives Samsung's stale native-cover/0deg intermediate posture.\n"
        "    private var earlyOpeningLatched = false\n",
        "opening latch field",
    )

    text = replace_once(
        text,
        "        activePrewarmGeneration = -1L\n        prewarmRetryAfterMs = 0L\n        resetIntent()\n",
        "        activePrewarmGeneration = -1L\n        prewarmRetryAfterMs = 0L\n        earlyOpeningLatched = false\n        resetIntent()\n",
        "reset opening latch",
    )

    text = replace_once(
        text,
        "        direction =\n            Direction.OPENING\n\n        lastSampleMs =\n",
        "        direction =\n            Direction.OPENING\n\n        earlyOpeningLatched = true\n\n        lastSampleMs =\n",
        "latch accepted early opening",
    )

    method = '''    /**
     * Authoritative binary close edge from SW_LID/Hall.
     * Clears the early-opening latch immediately. If Samsung already reports
     * native cover, collapse to NATIVE_COVER now; otherwise normal topology
     * reconciliation will finish the close.
     */
    fun onEarlyClosingEdge(
        nowMs: Long,
        topology: Topology,
    ): Decision {
        earlyOpeningLatched = false
        lastSampleMs = nowMs

        if (
            topology.nativeCover &&
            state in OPENING_STATES
        ) {
            direction = Direction.STEADY
            val angle =
                lastAngle
                    .takeIf { it.isFinite() }
                    ?: 0f

            transition(
                to = State.NATIVE_COVER,
                angle = angle,
                reason = "lid-closed-authoritative",
                topology = topology,
            )
        }

        return decision()
    }

'''
    text = replace_once(
        text,
        "    fun onPrewarmResult(\n",
        method + "    fun onPrewarmResult(\n",
        "early closing edge method",
    )

    # Release the binary latch only on evidence that truly supersedes it:
    # native INNER has appeared, or measured motion has reversed toward closed.
    # This keeps Samsung's stale native-cover/0deg intermediate posture from
    # cancelling the opening while avoiding branch-shape-specific patching.
    text = replace_once(
        text,
        '''        val openingAwayFromNativeCover =
            state in OPENING_STATES &&
                angle >= INNER_WAKE_MIN_DEG &&
                direction != Direction.CLOSING
''',
        '''        if (
            earlyOpeningLatched &&
            (
                topology.nativeInner ||
                    (state in OPENING_STATES && direction == Direction.CLOSING)
            )
        ) {
            earlyOpeningLatched = false
        }

        val openingAwayFromNativeCover =
            state in OPENING_STATES &&
                (earlyOpeningLatched || angle >= INNER_WAKE_MIN_DEG) &&
                direction != Direction.CLOSING
''',
        "native cover opening protection",
    )

    return text


def transform_coordinator(text: str) -> str:
    if MARKER in text:
        return text

    old = '''        apply(decision)
    }

    fun onTopologyFastLane(reason: String) {
'''
    new = '''        apply(decision)
    }

    // INNER_HALL_OPENING_LATCH_V3: SW_LID close is the authoritative
    // cancellation edge for a Hall-latched opening attempt.
    fun onEarlyClosingEdge(
        reason: String,
    ) {
        if (!renderOwnershipArmed) return

        val decision =
            controller.onEarlyClosingEdge(
                nowMs = SystemClock.uptimeMillis(),
                topology = topology(),
            )

        DuoDiagnostics.event(
            "early-wake",
            "closing edge reason=$reason state=${controller.state} " +
                "generation=${decision.generation} precise=${currentHingeAngle()}",
        )

        apply(decision)
    }

    fun onTopologyFastLane(reason: String) {
'''
    return replace_once(text, old, new, "coordinator closing edge")


def transform_service(text: str) -> str:
    if MARKER in text:
        return text

    old = '''                    if (closed) {
                        scope.launch(Dispatchers.IO) {
                            ShizukuBridge
                                .forceReleaseInnerPhysicalBridge(
                                    "lid-closed"
                                )
                        }
                    } else {
                        handleEarlyOpeningEdge(
                            "lid-switch-open"
                        )
                    }
'''
    new = '''                    if (closed) {
                        // INNER_HALL_OPENING_LATCH_V3: only a real Hall close,
                        // actual reversal, or native INNER takeover may cancel
                        // the accepted Hall opening.
                        continuity.onEarlyClosingEdge(
                            "lid-switch-closed"
                        )
                        setEarlyOpeningVisualLatched(
                            value = false,
                            reason = "lid-switch-closed",
                        )
                        scope.launch(Dispatchers.IO) {
                            ShizukuBridge
                                .forceReleaseInnerPhysicalBridge(
                                    "lid-closed"
                                )
                        }
                        reconcileContinuityCoverRendering(
                            "lid-switch-closed"
                        )
                    } else {
                        handleEarlyOpeningEdge(
                            "lid-switch-open"
                        )
                    }
'''
    return replace_once(text, old, new, "Hall close cancellation")


def apply(repo: Path, check: bool) -> None:
    paths = {
        CONTROLLER: transform_controller,
        COORDINATOR: transform_coordinator,
        SERVICE: transform_service,
    }

    transformed = {}
    for rel, fn in paths.items():
        path = repo / rel
        if not path.exists():
            raise RuntimeError(f"missing {rel}")
        before = path.read_text(encoding="utf-8")
        after = fn(before)
        transformed[rel] = after
        if MARKER not in after:
            raise RuntimeError(f"{rel}: V3 marker missing")
        if not check:
            path.write_text(after, encoding="utf-8")

    required = {
        CONTROLLER: [
            "private var earlyOpeningLatched = false",
            "earlyOpeningLatched || angle >= INNER_WAKE_MIN_DEG",
            "topology.nativeInner ||",
            "fun onEarlyClosingEdge(",
            'reason = "lid-closed-authoritative"',
        ],
        COORDINATOR: ["fun onEarlyClosingEdge(", "closing edge reason=$reason"],
        SERVICE: ["continuity.onEarlyClosingEdge(", 'reason = "lid-switch-closed"'],
    }
    for rel, needles in required.items():
        rendered = transformed[rel]
        for needle in needles:
            if needle not in rendered:
                raise RuntimeError(f"{rel}: missing invariant {needle}")

    print("inner Hall opening latch v3: " + ("source shape verified" if check else "applied"))


def self_test() -> None:
    source = """    private var closingFloorAngle = Float.NaN
        activePrewarmGeneration = -1L
        prewarmRetryAfterMs = 0L
        resetIntent()
        direction =
            Direction.OPENING

        lastSampleMs =
            nowMs
    fun onPrewarmResult(
        val openingAwayFromNativeCover =
            state in OPENING_STATES &&
                angle >= INNER_WAKE_MIN_DEG &&
                direction != Direction.CLOSING
"""
    out = transform_controller(source)
    assert "earlyOpeningLatched || angle >= INNER_WAKE_MIN_DEG" in out
    assert "topology.nativeInner ||" in out
    assert "fun onEarlyClosingEdge(" in out
    print("inner Hall opening latch v3 model: PASS")


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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
