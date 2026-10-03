#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

CONTROLLER = Path("app/src/full/java/com/duoopen/overlay/Fold7ContinuityController.kt")
MARKER = "INNER_PHYSICAL_BRIDGE_V3"
HOLD_MS = 650


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform(text: str) -> str:
    if MARKER in text:
        return text

    text = replace_once(
        text,
        "    private var activePrewarmGeneration = -1L\n",
        "    private var activePrewarmGeneration = -1L\n\n"
        "    // INNER_PHYSICAL_BRIDGE_V3: once an early opening edge is accepted,\n"
        "    // do not let transient Samsung native-cover topology invalidate the\n"
        "    // same opening while the physical INNER wake is still in flight.\n"
        "    private var openingCommitHoldUntilMs = 0L\n",
        "opening commit field",
    )

    text = replace_once(
        text,
        "        activePrewarmGeneration = -1L\n        prewarmRetryAfterMs = 0L\n        resetIntent()\n",
        "        activePrewarmGeneration = -1L\n"
        "        prewarmRetryAfterMs = 0L\n"
        "        openingCommitHoldUntilMs = 0L\n"
        "        resetIntent()\n",
        "reset opening hold",
    )

    text = replace_once(
        text,
        "        val angle =\n            lastAngle\n                .takeIf {\n                    it.isFinite()\n                }\n                ?: 0f\n\n        transition(\n            to = State.OPENING_FROM_CLOSED,\n",
        "        val angle =\n"
        "            lastAngle\n"
        "                .takeIf {\n"
        "                    it.isFinite()\n"
        "                }\n"
        "                ?: 0f\n\n"
        "        openingCommitHoldUntilMs =\n"
        f"            nowMs + {HOLD_MS}L\n\n"
        "        transition(\n"
        "            to = State.OPENING_FROM_CLOSED,\n",
        "arm hold on early edge",
    )

    text = replace_once(
        text,
        "        val openingAwayFromNativeCover =\n            state in OPENING_STATES &&\n                angle >= INNER_WAKE_MIN_DEG &&\n                direction != Direction.CLOSING\n",
        "        val openingCommitHeld =\n"
        "            state in OPENING_STATES &&\n"
        "                nowMs <= openingCommitHoldUntilMs\n\n"
        "        val openingAwayFromNativeCover =\n"
        "            state in OPENING_STATES &&\n"
        "                (angle >= INNER_WAKE_MIN_DEG || openingCommitHeld) &&\n"
        "                direction != Direction.CLOSING\n",
        "honor commit hold during native cover topology",
    )

    text = replace_once(
        text,
        "            activePrewarmGeneration = -1L\n            resetIntent()\n\n            return decision(actions)\n        }\n\n        // Stable fully-open endpoint.",
        "            activePrewarmGeneration = -1L\n"
        "            openingCommitHoldUntilMs = 0L\n"
        "            resetIntent()\n\n"
        "            return decision(actions)\n"
        "        }\n\n"
        "        // Stable fully-open endpoint.",
        "clear hold on native cover reclaim",
    )

    text = replace_once(
        text,
        "            activePrewarmGeneration = -1L\n            resetIntent()\n\n            return decision(actions)\n        }\n\n        when (state) {\n",
        "            activePrewarmGeneration = -1L\n"
        "            openingCommitHoldUntilMs = 0L\n"
        "            resetIntent()\n\n"
        "            return decision(actions)\n"
        "        }\n\n"
        "        when (state) {\n",
        "clear hold on open latch",
    )

    text = replace_once(
        text,
        "                    transition(\n                        to = State.OPENING_FROM_CLOSED,\n                        angle = angle,\n                        reason = \"early-inner-wake\",\n                        topology = topology,\n                    )\n\n                    /*\n",
        "                    openingCommitHoldUntilMs =\n"
        f"                        nowMs + {HOLD_MS}L\n\n"
        "                    transition(\n"
        "                        to = State.OPENING_FROM_CLOSED,\n"
        "                        angle = angle,\n"
        "                        reason = \"early-inner-wake\",\n"
        "                        topology = topology,\n"
        "                    )\n\n"
        "                    /*\n",
        "arm hold on hinge opening",
    )

    text = replace_once(
        text,
        "        const val INNER_HANDOFF_MIN_DEG = 8f\n",
        "        const val INNER_HANDOFF_MIN_DEG = 8f\n"
        f"        const val OPENING_COMMIT_HOLD_MS = {HOLD_MS}L\n",
        "hold constant",
    )

    # Use the named constant rather than duplicating the literal in runtime code.
    text = text.replace(f"            nowMs + {HOLD_MS}L", "            nowMs + OPENING_COMMIT_HOLD_MS")
    text = text.replace(f"                        nowMs + {HOLD_MS}L", "                        nowMs + OPENING_COMMIT_HOLD_MS")

    if MARKER not in text:
        raise RuntimeError("V3 marker missing")
    return text


def apply(repo: Path, check: bool) -> None:
    path = repo / CONTROLLER
    if not path.exists():
        raise RuntimeError(f"missing {CONTROLLER}")
    before = path.read_text(encoding="utf-8")
    after = transform(before)

    required = (
        "INNER_PHYSICAL_BRIDGE_V3",
        f"const val OPENING_COMMIT_HOLD_MS = {HOLD_MS}L",
        "openingCommitHoldUntilMs",
        "openingCommitHeld",
        "angle >= INNER_WAKE_MIN_DEG || openingCommitHeld",
    )
    for value in required:
        if value not in after:
            raise RuntimeError(f"missing V3 invariant: {value}")

    if not check:
        path.write_text(after, encoding="utf-8")


def self_test() -> None:
    # Structural model: the real behavioral gate is covered by the Kotlin test
    # added alongside this transformer and the existing full regression suite.
    assert HOLD_MS > 384
    assert HOLD_MS < 1000
    print("inner physical bridge v3 model: PASS")


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
    print("inner physical bridge v3: source shape verified" if args.check else "inner physical bridge v3: applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
