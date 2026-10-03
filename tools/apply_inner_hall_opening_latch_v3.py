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
        "    // INNER_HALL_OPENING_LATCH_V3: an accepted binary opening edge is\n"
        "    // authoritative evidence that the handset has left the magnetic fully-closed rest.\n"
        "    // Samsung may continue reporting native-cover/0deg for a while; that stale\n"
        "    // topology must not cancel the opening attempt before precise angle returns.\n"
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

    anchor = '''        return decision(\n            listOf(\n                Action.WakeInner(\n                    generation\n                )\n            )\n        )\n    }\n\n    fun onPrewarmResult(\n'''
    insert = '''        return decision(\n            listOf(\n                Action.WakeInner(\n                    generation\n                )\n            )\n        )\n    }\n\n    /**\n     * Authoritative binary close edge from SW_LID/Hall.\n     *\n     * This is the symmetric cancellation for [onEarlyOpeningEdge]. It clears\n     * the opening latch immediately. If Samsung already reports native cover,\n     * collapse to NATIVE_COVER now; otherwise the next topology/hinge sample\n     * will do so normally.\n     */\n    fun onEarlyClosingEdge(\n        nowMs: Long,\n        topology: Topology,\n    ): Decision {\n        earlyOpeningLatched = false\n        lastSampleMs = nowMs\n\n        if (\n            topology.nativeCover &&\n            state in OPENING_STATES\n        ) {\n            direction = Direction.STEADY\n            val angle =\n                lastAngle\n                    .takeIf { it.isFinite() }\n                    ?: 0f\n\n            transition(\n                to = State.NATIVE_COVER,\n                angle = angle,\n                reason = "lid-closed-authoritative",\n                topology = topology,\n            )\n        }\n\n        return decision()\n    }\n\n    fun onPrewarmResult(\n'''
    text = replace_once(text, anchor, insert, "early closing edge method")

    text = replace_once(
        text,
        '''        val openingAwayFromNativeCover =\n            state in OPENING_STATES &&\n                angle >= INNER_WAKE_MIN_DEG &&\n                direction != Direction.CLOSING\n''',
        '''        val openingAwayFromNativeCover =\n            state in OPENING_STATES &&\n                (earlyOpeningLatched || angle >= INNER_WAKE_MIN_DEG) &&\n                direction != Direction.CLOSING\n''',
        "native cover opening protection",
    )

    text = replace_once(
        text,
        '''            activePrewarmGeneration = -1L\n            resetIntent()\n\n            return decision(actions)\n        }\n\n        // Stable fully-open endpoint.\n''',
        '''            earlyOpeningLatched = false\n            activePrewarmGeneration = -1L\n            resetIntent()\n\n            return decision(actions)\n        }\n\n        // Stable fully-open endpoint.\n''',
        "clear latch on native-cover authority",
    )

    text = replace_once(
        text,
        '''            activePrewarmGeneration = -1L\n            resetIntent()\n\n            return decision(actions)\n        }\n\n        when (state) {\n''',
        '''            earlyOpeningLatched = false\n            activePrewarmGeneration = -1L\n            resetIntent()\n\n            return decision(actions)\n        }\n\n        when (state) {\n''',
        "clear latch at open-inner",
    )

    return text


def transform_coordinator(text: str) -> str:
    if MARKER in text:
        return text

    old = '''        apply(decision)\n    }\n\n    fun onTopologyFastLane(reason: String) {\n'''
    new = '''        apply(decision)\n    }\n\n    // INNER_HALL_OPENING_LATCH_V3: SW_LID close is the authoritative\n    // cancellation edge for a Hall-latched opening attempt.\n    fun onEarlyClosingEdge(\n        reason: String,\n    ) {\n        if (!renderOwnershipArmed) return\n\n        val decision =\n            controller.onEarlyClosingEdge(\n                nowMs = SystemClock.uptimeMillis(),\n                topology = topology(),\n            )\n\n        DuoDiagnostics.event(\n            "early-wake",\n            "closing edge reason=$reason state=${controller.state} " +\n                "generation=${decision.generation} precise=${currentHingeAngle()}",\n        )\n\n        apply(decision)\n    }\n\n    fun onTopologyFastLane(reason: String) {\n'''
    return replace_once(text, old, new, "coordinator closing edge")


def transform_service(text: str) -> str:
    if MARKER in text:
        return text

    old = '''                    if (closed) {\n                        scope.launch(Dispatchers.IO) {\n                            ShizukuBridge\n                                .forceReleaseInnerPhysicalBridge(\n                                    "lid-closed"\n                                )\n                        }\n                    } else {\n                        handleEarlyOpeningEdge(\n                            "lid-switch-open"\n                        )\n                    }\n'''
    new = '''                    if (closed) {\n                        // INNER_HALL_OPENING_LATCH_V3: a real Hall close cancels\n                        // the opening latch immediately; Samsung's intermediate\n                        // DeviceState values are no longer allowed to do that.\n                        continuity.onEarlyClosingEdge(\n                            "lid-switch-closed"\n                        )\n                        setEarlyOpeningVisualLatched(\n                            value = false,\n                            reason = "lid-switch-closed",\n                        )\n                        scope.launch(Dispatchers.IO) {\n                            ShizukuBridge\n                                .forceReleaseInnerPhysicalBridge(\n                                    "lid-closed"\n                                )\n                        }\n                        reconcileContinuityCoverRendering(\n                            "lid-switch-closed"\n                        )\n                    } else {\n                        handleEarlyOpeningEdge(\n                            "lid-switch-open"\n                        )\n                    }\n'''
    return replace_once(text, old, new, "Hall close cancellation")


def apply(repo: Path, check: bool) -> None:
    paths = {
        CONTROLLER: transform_controller,
        COORDINATOR: transform_coordinator,
        SERVICE: transform_service,
    }
    changed = []
    for rel, fn in paths.items():
        path = repo / rel
        if not path.exists():
            raise RuntimeError(f"missing {rel}")
        before = path.read_text(encoding="utf-8")
        after = fn(before)
        if MARKER not in after:
            raise RuntimeError(f"{rel}: V3 marker missing")
        if after != before:
            changed.append(str(rel))
        if not check:
            path.write_text(after, encoding="utf-8")

    required = {
        CONTROLLER: [
            "private var earlyOpeningLatched = false",
            "earlyOpeningLatched || angle >= INNER_WAKE_MIN_DEG",
            "fun onEarlyClosingEdge(",
            'reason = "lid-closed-authoritative"',
        ],
        COORDINATOR: ["fun onEarlyClosingEdge(", "closing edge reason=$reason"],
        SERVICE: ["continuity.onEarlyClosingEdge(", 'reason = "lid-switch-closed"'],
    }
    for rel, needles in required.items():
        rendered = (repo / rel).read_text(encoding="utf-8") if check else (repo / rel).read_text(encoding="utf-8")
        # In --check mode transformations are not written, so validate transformed text directly.
        if check:
            rendered = paths[rel](rendered)
        for needle in needles:
            if needle not in rendered:
                raise RuntimeError(f"{rel}: missing invariant {needle}")

    print("inner Hall opening latch v3: " + ("source shape verified" if check else "applied"))


def self_test() -> None:
    sample = '''    private var closingFloorAngle = Float.NaN\n    fun reset(\n        angle: Float,\n        nowMs: Long,\n        topology: Topology,\n    ): Decision {\n        generation++\n        activePrewarmGeneration = -1L\n        prewarmRetryAfterMs = 0L\n        resetIntent()\n        direction =\n            Direction.OPENING\n\n        lastSampleMs =\n            nowMs\n        return decision(\n            listOf(\n                Action.WakeInner(\n                    generation\n                )\n            )\n        )\n    }\n\n    fun onPrewarmResult(\n        val openingAwayFromNativeCover =\n            state in OPENING_STATES &&\n                angle >= INNER_WAKE_MIN_DEG &&\n                direction != Direction.CLOSING\n            activePrewarmGeneration = -1L\n            resetIntent()\n\n            return decision(actions)\n        }\n\n        // Stable fully-open endpoint.\n            activePrewarmGeneration = -1L\n            resetIntent()\n\n            return decision(actions)\n        }\n\n        when (state) {\n'''
    out = transform_controller(sample)
    assert "earlyOpeningLatched || angle >= INNER_WAKE_MIN_DEG" in out
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
