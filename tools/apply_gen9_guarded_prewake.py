#!/usr/bin/env python3
"""Apply Gen9.1 one-shot closed-rest prewake guard after Gen9."""

from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def apply(repo: Path) -> None:
    # Version the guarded field candidate separately from Gen9 so the exact
    # binary tested on hardware can be identified from a debug bundle.
    build = repo / "app/build.gradle.kts"
    text = build.read_text()
    text = replace_once(text, "versionCode = 45", "versionCode = 46", "versionCode")
    text = replace_once(
        text,
        'versionName = "5.3.0-gen9-responsive-zfold7"',
        'versionName = "5.3.1-gen9-guarded-zfold7"',
        "versionName",
    )
    build.write_text(text)

    observer = repo / "app/src/full/java/com/duoopen/overlay/Fold7DeviceStateObserver.kt"
    text = observer.read_text()

    text = replace_once(
        text,
        """    private val learnedFoldedStateIds =
        LinkedHashSet<Int>()
""",
        """    private val learnedFoldedStateIds =
        LinkedHashSet<Int>()

    /*
     * Gen9.1: a speculative prewake may fire only once for a corroborated
     * fully-closed rest epoch. A folded->folded state change after that cannot
     * repeatedly power the inner panel until a real opening edge has occurred
     * and the device has subsequently been proven closed again.
     */
    private var corroboratedClosedStateId: Int? = null
    private var preOpeningHintArmed = false
    private var leftFoldedSinceClosedRest = true
""",
        "observer guarded state",
    )

    text = replace_once(
        text,
        """        lastFolded =
            true

        if (learned) {
""",
        """        lastFolded =
            true

        if (
            corroboratedClosedStateId == null ||
            leftFoldedSinceClosedRest
        ) {
            corroboratedClosedStateId = id
            preOpeningHintArmed = true
            leftFoldedSinceClosedRest = false

            DuoDiagnostics.event(
                "inner-prewake",
                "ARM closedRestId=$id precise=$preciseAngle",
            )
        }

        if (learned) {
""",
        "observer arm at corroborated close",
    )

    old_hint = """        if (
            previousId != null &&
            previousId != id &&
            previousFolded == true &&
            inferredFolded == true
        ) {
            onPreOpeningHint(
                previousId,
                id,
            )
        }

        if (
            previousId != null &&
            previousFolded == true &&
            inferredFolded == false
        ) {
            onOpeningEdge(
                previousId,
                id,
            )
        }
"""

    new_hint = """        if (
            previousId != null &&
            previousId != id &&
            previousFolded == true &&
            inferredFolded == true &&
            preOpeningHintArmed &&
            previousId == corroboratedClosedStateId
        ) {
            preOpeningHintArmed = false

            DuoDiagnostics.event(
                "inner-prewake",
                "HINT accepted closedRestId=$corroboratedClosedStateId " +
                    "transition=$previousId->$id source=$source",
            )

            onPreOpeningHint(
                previousId,
                id,
            )
        }

        if (
            previousId != null &&
            previousFolded == true &&
            inferredFolded == false
        ) {
            // A real opening edge ends this closed-rest epoch. A future
            // corroborated closed rest is required before prediction can arm.
            preOpeningHintArmed = false
            corroboratedClosedStateId = null
            leftFoldedSinceClosedRest = true

            onOpeningEdge(
                previousId,
                id,
            )
        }
"""

    text = replace_once(text, old_hint, new_hint, "observer one-shot hint gate")
    observer.write_text(text)

    coordinator = repo / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"
    text = coordinator.read_text()

    text = replace_once(
        text,
        """    @Volatile private var innerPrewakeInFlight = false
    private var lastInnerPrewakeUptimeMs = 0L
""",
        """    @Volatile private var innerPrewakeInFlight = false
    private var lastInnerPrewakeUptimeMs = 0L
    private var lastInnerPrewakeCompletedUptimeMs = 0L
""",
        "coordinator lead telemetry state",
    )

    text = replace_once(
        text,
        """            handler.post {
                innerPrewakeInFlight = false

                val currentTopology =
""",
        """            handler.post {
                innerPrewakeInFlight = false
                lastInnerPrewakeCompletedUptimeMs =
                    SystemClock.uptimeMillis()

                val currentTopology =
""",
        "coordinator prewake completion timestamp",
    )

    text = replace_once(
        text,
        """        val decision =
            controller.onEarlyOpeningEdge(
                nowMs =
                    SystemClock.uptimeMillis(),
                topology =
                    topology(),
            )
""",
        """        val openingEdgeUptimeMs =
            SystemClock.uptimeMillis()

        val prewakeLeadMs =
            if (lastInnerPrewakeCompletedUptimeMs > 0L) {
                (openingEdgeUptimeMs - lastInnerPrewakeCompletedUptimeMs)
                    .coerceAtLeast(0L)
            } else {
                -1L
            }

        val decision =
            controller.onEarlyOpeningEdge(
                nowMs =
                    openingEdgeUptimeMs,
                topology =
                    topology(),
            )
""",
        "coordinator opening edge lead calculation",
    )

    text = replace_once(
        text,
        '"accepted reason=$reason generation=${decision.generation} " +\n                    "precise=${currentHingeAngle()}",',
        '"accepted reason=$reason generation=${decision.generation} " +\n                    "precise=${currentHingeAngle()} prewakeLeadMs=$prewakeLeadMs",',
        "accepted opening telemetry",
    )

    text = replace_once(
        text,
        '"ignored reason=$reason state=${controller.state} " +\n                    "precise=${currentHingeAngle()}",',
        '"ignored reason=$reason state=${controller.state} " +\n                    "precise=${currentHingeAngle()} prewakeLeadMs=$prewakeLeadMs",',
        "ignored opening telemetry",
    )

    coordinator.write_text(text)


def verify(repo: Path) -> None:
    joined = "\n".join(
        (repo / path).read_text()
        for path in [
            "app/build.gradle.kts",
            "app/src/full/java/com/duoopen/overlay/Fold7DeviceStateObserver.kt",
            "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt",
        ]
    )

    required = [
        "versionCode = 46",
        'versionName = "5.3.1-gen9-guarded-zfold7"',
        "corroboratedClosedStateId",
        "preOpeningHintArmed",
        "leftFoldedSinceClosedRest",
        '"ARM closedRestId=',
        '"HINT accepted closedRestId=',
        "previousId == corroboratedClosedStateId",
        "lastInnerPrewakeCompletedUptimeMs",
        "prewakeLeadMs",
    ]
    missing = [needle for needle in required if needle not in joined]
    if missing:
        raise RuntimeError(f"Gen9.1 verification failed; missing: {missing}")

    # Preserve the central Gen8 safety invariant through every later patch.
    if "liveFrameEpoch.owns(loopEpoch)" not in (
        repo / "app/src/full/java/com/duoopen/overlay/Fold7CoverVisualHost.kt"
    ).read_text():
        raise RuntimeError("Gen9.1 verification failed: Gen8 epoch ownership missing")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    apply(repo)
    verify(repo)
    print("Gen9.1 guarded predictive prewake applied and verified")


if __name__ == "__main__":
    main()
