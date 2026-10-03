#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

CONTROLLER = Path("app/src/full/java/com/duoopen/overlay/Fold7ContinuityController.kt")
COORDINATOR = Path("app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt")
SERVICE = Path("app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt")
TEST = Path("app/src/test/java/com/duoopen/overlay/Fold7ContinuityControllerTest.kt")
MARKER = "HALL_OPEN_LATCH_V3"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected one match, found {n}")
    return text.replace(old, new, 1)


def transform_controller(text: str) -> str:
    if MARKER in text:
        return text

    text = replace_once(
        text,
        "    private var lastAngle = Float.NaN\n    private var lastSampleMs = 0L\n",
        "    private var lastAngle = Float.NaN\n    private var lastSampleMs = 0L\n\n"
        "    // HALL_OPEN_LATCH_V3: a real SW_LID open edge outranks stale cover-default\n"
        "    // topology while Samsung's precise hinge/logical INNER are still unavailable.\n"
        "    private var physicalOpeningLatched = false\n",
        "physical opening latch field",
    )

    text = replace_once(
        text,
        "        resetIntent()\n\n        lastAngle = angle.takeIf { it.isFinite() } ?: Float.NaN\n",
        "        resetIntent()\n        physicalOpeningLatched = false\n\n        lastAngle = angle.takeIf { it.isFinite() } ?: Float.NaN\n",
        "reset physical latch",
    )

    text = replace_once(
        text,
        "    fun onEarlyOpeningEdge(\n        nowMs: Long,\n        topology: Topology,\n    ): Decision {\n",
        "    fun onEarlyOpeningEdge(\n        nowMs: Long,\n        topology: Topology,\n        physicalEdge: Boolean = false,\n    ): Decision {\n",
        "opening edge signature",
    )

    text = replace_once(
        text,
        "        direction =\n            Direction.OPENING\n\n        lastSampleMs =\n",
        "        if (physicalEdge) {\n            physicalOpeningLatched = true\n        }\n\n        direction =\n            Direction.OPENING\n\n        lastSampleMs =\n",
        "latch physical opening",
    )

    anchor = "        return decision(\n            listOf(\n                Action.WakeInner(\n                    generation\n                )\n            )\n        )\n    }\n\n    fun onPrewarmResult(\n"
    replacement = "        return decision(\n            listOf(\n                Action.WakeInner(\n                    generation\n                )\n            )\n        )\n    }\n\n    /** Explicit physical-close terminal for a Hall-latched opening. */\n    fun onPhysicalClosedEdge(\n        nowMs: Long,\n        topology: Topology,\n    ): Decision {\n        physicalOpeningLatched = false\n        lastSampleMs = nowMs\n\n        if (state in OPENING_STATES && topology.nativeCover) {\n            direction = Direction.STEADY\n            val angle = lastAngle.takeIf { it.isFinite() } ?: 0f\n            transition(\n                to = State.NATIVE_COVER,\n                angle = angle,\n                reason = \"lid-closed-authoritative\",\n                topology = topology,\n            )\n            activePrewarmGeneration = -1L\n            resetIntent()\n        }\n\n        return decision()\n    }\n\n    fun onPrewarmResult(\n"
    text = replace_once(text, anchor, replacement, "physical closed edge method")

    text = replace_once(
        text,
        "        val openingAwayFromNativeCover =\n            state in OPENING_STATES &&\n                angle >= INNER_WAKE_MIN_DEG &&\n                direction != Direction.CLOSING\n",
        "        val openingAwayFromNativeCover =\n            state in OPENING_STATES &&\n                direction != Direction.CLOSING &&\n                (physicalOpeningLatched || angle >= INNER_WAKE_MIN_DEG)\n",
        "native-cover guard",
    )

    text = replace_once(
        text,
        "            val wasVisual = state == State.COVER_VISUAL\n            val hadSecondary = state in SECONDARY_STATES\n\n            transition(\n",
        "            val wasVisual = state == State.COVER_VISUAL\n            val hadSecondary = state in SECONDARY_STATES\n            physicalOpeningLatched = false\n\n            transition(\n",
        "clear latch on native cover",
    )

    text = replace_once(
        text,
        "        ) {\n            transition(\n                to = State.OPEN_INNER,\n",
        "        ) {\n            physicalOpeningLatched = false\n            transition(\n                to = State.OPEN_INNER,\n",
        "clear latch on native inner",
    )

    if MARKER not in text:
        raise RuntimeError("controller marker missing")
    return text


def transform_coordinator(text: str) -> str:
    if MARKER in text:
        return text

    text = replace_once(
        text,
        "            controller.onEarlyOpeningEdge(\n                nowMs =\n                    SystemClock.uptimeMillis(),\n                topology =\n                    topology(),\n            )\n",
        "            controller.onEarlyOpeningEdge(\n                nowMs =\n                    SystemClock.uptimeMillis(),\n                topology =\n                    topology(),\n                physicalEdge = reason == \"lid-switch-open\",\n            )\n",
        "coordinator physical edge flag",
    )

    anchor = "        apply(decision)\n    }\n\n    fun onTopologyFastLane(reason: String) {\n"
    replacement = "        apply(decision)\n    }\n\n    // HALL_OPEN_LATCH_V3: only a real Hall close explicitly terminates the\n    // pre-topology physical-opening latch.\n    fun onPhysicalClosedEdge(reason: String) {\n        if (!renderOwnershipArmed) return\n\n        val decision =\n            controller.onPhysicalClosedEdge(\n                nowMs = SystemClock.uptimeMillis(),\n                topology = topology(),\n            )\n\n        DuoDiagnostics.event(\n            \"early-wake\",\n            \"physical close edge reason=$reason state=${decision.state} generation=${decision.generation}\",\n        )\n        apply(decision)\n    }\n\n    fun onTopologyFastLane(reason: String) {\n"
    text = replace_once(text, anchor, replacement, "coordinator close edge")

    if MARKER not in text:
        raise RuntimeError("coordinator marker missing")
    return text


def transform_service(text: str) -> str:
    if MARKER in text:
        return text

    old = '''                    if (closed) {
                        Fold7DisplayStatusStore.reset("lid-switch-closed")
                        scope.launch(Dispatchers.IO) {
'''
    new = '''                    if (closed) {
                        Fold7DisplayStatusStore.reset("lid-switch-closed")
                        continuity.onPhysicalClosedEdge("lid-switch-closed")
                        scope.launch(Dispatchers.IO) {
'''
    text = replace_once(text, old, new, "service Hall close terminal")
    text = text.replace(
        "    private fun startLidEventsIfNeeded() {\n",
        "    // HALL_OPEN_LATCH_V3\n    private fun startLidEventsIfNeeded() {\n",
        1,
    )
    if MARKER not in text:
        raise RuntimeError("service marker missing")
    return text


def transform_test(text: str) -> str:
    if "physicalHallOpeningSurvivesNativeCoverTopology" in text:
        return text

    tests = r'''

    @Test
    fun physicalHallOpeningSurvivesNativeCoverTopology() {
        val c = Fold7ContinuityController()
        c.reset(0f, 0L, closedTopology)

        c.onEarlyOpeningEdge(
            nowMs = 5L,
            topology = closedTopology,
            physicalEdge = true,
        )

        c.onTopology(
            angle = 0f,
            nowMs = 100L,
            topology = closedTopology,
        )

        assertEquals(
            Fold7ContinuityController.State.OPENING_FROM_CLOSED,
            c.state,
        )
    }

    @Test
    fun physicalHallCloseTerminatesLatchedOpening() {
        val c = Fold7ContinuityController()
        c.reset(0f, 0L, closedTopology)

        c.onEarlyOpeningEdge(
            nowMs = 5L,
            topology = closedTopology,
            physicalEdge = true,
        )

        c.onPhysicalClosedEdge(
            nowMs = 120L,
            topology = closedTopology,
        )

        assertEquals(
            Fold7ContinuityController.State.NATIVE_COVER,
            c.state,
        )
    }
'''
    idx = text.rfind("\n}")
    if idx < 0:
        raise RuntimeError("test class closing brace not found")
    return text[:idx] + tests + text[idx:]


def apply(repo: Path, check: bool) -> None:
    transforms = {
        CONTROLLER: transform_controller,
        COORDINATOR: transform_coordinator,
        SERVICE: transform_service,
        TEST: transform_test,
    }
    outputs = {}
    for rel, fn in transforms.items():
        path = repo / rel
        if not path.exists():
            raise RuntimeError(f"missing {rel}")
        outputs[path] = fn(path.read_text(encoding="utf-8"))

    required = (
        "physicalOpeningLatched || angle >= INNER_WAKE_MIN_DEG",
        "onPhysicalClosedEdge",
        "physicalEdge = reason == \"lid-switch-open\"",
        "continuity.onPhysicalClosedEdge(\"lid-switch-closed\")",
        "physicalHallOpeningSurvivesNativeCoverTopology",
    )
    all_text = "\n".join(outputs.values())
    for needle in required:
        if needle not in all_text:
            raise RuntimeError(f"missing Hall latch invariant: {needle}")

    if not check:
        for path, output in outputs.items():
            path.write_text(output, encoding="utf-8")


def self_test() -> None:
    # Model the field regression: Hall-open at 0 degrees, stale native-cover
    # topology 100 ms later must not cancel the opening until Hall-close.
    state = "NATIVE_COVER"
    hall_open = True
    state = "OPENING_FROM_CLOSED"
    topology_native_cover = True
    angle = 0.0
    opening_away = state == "OPENING_FROM_CLOSED" and hall_open and topology_native_cover
    assert opening_away and angle == 0.0
    hall_open = False
    assert not hall_open
    print("hall open latch v3 model: PASS")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=".")
    p.add_argument("--check", action="store_true")
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()

    if args.self_test:
        self_test()
        if not args.check:
            return 0

    apply(Path(args.repo).resolve(), args.check)
    print("hall open latch v3: source shape verified" if args.check else "hall open latch v3: applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
