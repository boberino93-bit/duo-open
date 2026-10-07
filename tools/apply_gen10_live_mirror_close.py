#!/usr/bin/env python3
"""Apply Gen10 live-mirror-first closing presentation after Gen9.1.

Gen10 removes the normal closing dependency on the bitmap/screenshot shader.
The existing AOSP mirrorDisplay()/setGeometry() path becomes authoritative for
COVER_VISUAL. A frozen frame remains available only as a failure fallback when
the live SurfaceControl mirror cannot be created or attached.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def apply(repo: Path) -> None:
    build = repo / "app/build.gradle.kts"
    text = build.read_text()
    text = replace_once(text, "versionCode = 46", "versionCode = 47", "versionCode")
    text = replace_once(
        text,
        'versionName = "5.3.1-gen9-guarded-zfold7"',
        'versionName = "5.4.0-gen10-live-mirror-zfold7"',
        "versionName",
    )
    build.write_text(text)

    # Re-enable the continuity coordinator's already implemented live mirror
    # host. Gen3 previously interpreted ShowMirror as demand only, leaving the
    # live SurfaceControl host permanently null while a screenshot shader was
    # rendered above the application.
    coordinator = repo / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"
    text = coordinator.read_text()

    old_show = """        if (
            currentTopology.innerActive &&
            !currentTopology.coverActive
        ) {
            ensureCoverRouteHeld(
                \"state-show\"
            )
        }

        DuoDiagnostics.event(
            \"gen3-visual\",
            \"closing visual demand generation=$generation\",
        )
"""

    new_show = """        if (
            currentTopology.innerActive &&
            !currentTopology.coverActive
        ) {
            ensureCoverRouteHeld(
                \"state-show\"
            )
        }

        /*
         * Gen10: ShowMirror once again means an actual live SurfaceControl
         * presentation, not merely a request for the Gen3 bitmap shader.
         * syncMirrorHost() opens the V2 mirror session as needed and binds the
         * right-pane geometry when both physical routes are available.
         */
        syncMirrorHost(
            reason = \"state-show\",
            generation = generation,
        )

        DuoDiagnostics.event(
            \"gen10-live-mirror\",
            \"closing live visual demand generation=$generation\",
        )
"""
    text = replace_once(text, old_show, new_show, "restore live mirror on ShowMirror")

    old_fast_lane = """        apply(decision)
        observeCoverReadiness(\"fast:$reason\")

        if (
            controller.state in setOf(
"""
    new_fast_lane = """        apply(decision)
        observeCoverReadiness(\"fast:$reason\")

        /*
         * Samsung can expose/remap the cover route after ShowMirror. Retry the
         * host bind on topology edges so a mirror request cannot get stranded
         * simply because the cover was not yet active on the first call.
         */
        if (visualMirrorActive) {
            syncMirrorHost(
                reason = \"topology:$reason\",
                generation = mirrorGeneration,
            )
        }

        if (
            controller.state in setOf(
"""
    text = replace_once(text, old_fast_lane, new_fast_lane, "topology mirror retry")
    coordinator.write_text(text)

    # Make live SurfaceControl content authoritative. The previous code bound a
    # frozen frame first and returned before it ever attempted mirrorDisplay().
    mirror = repo / "app/src/full/java/com/duoopen/overlay/DisplayMirrorHost.kt"
    text = mirror.read_text()

    old_policy = """        val existingFrozen =
            frozenFrame

        if (
            mirrorSourceKey ==
                sourceKey &&
            existingFrozen != null &&
            !existingFrozen.isRecycled
        ) {
            frozenPaneView.invalidate()
            return
        }

        if (
            frozenFrame != null &&
            mirrorSourceKey !=
                sourceKey
        ) {
            clearFrozenFrame()
        }

        /*
         * Deterministic Fold7 path. The snapshot was captured by PanelEngine
         * near the start of hinge travel, before Samsung can continue mutating
         * the live inner composition underneath a stationary fold.
         *
         * If no fresh snapshot exists, retain the old live mirror path as a
         * compatibility fallback (secure-content/capture failure).
         */
        if (
            tryBindFrozenFrame(
                sourceKey = sourceKey,
                sourceWidth = sourceWidth,
                sourceHeight = sourceHeight,
                reason = reason,
            )
        ) {
            return
        }

        com.duoopen.debug.DuoDiagnostics.event(
            \"snapshot-transition\",
            \"continuity frozen frame unavailable; \" +
                \"falling back to live mirror reason=$reason\",
        )

        val current = appMirror
"""

    new_policy = """        /*
         * Gen10 invariant: live application content is authoritative during a
         * normal close. A bitmap may be shown only after the real SurfaceControl
         * mirror has failed. This prevents a long-lived screenshot surrogate
         * from diverging from the application/window lifecycle underneath it.
         */
        if (
            frozenFrame != null &&
            mirrorSourceKey != sourceKey
        ) {
            clearFrozenFrame()
        }

        if (
            frozenFrame != null &&
            mirrorSourceKey == sourceKey
        ) {
            // A previous failure fallback is not sticky. A later topology or
            // host refresh is allowed to retry the live mirror.
            clearFrozenFrame()
        }

        val current = appMirror
"""
    text = replace_once(text, old_policy, new_policy, "live-first mirror policy")

    old_failure = """                    val detail =
                        error
                            ?: \"shell returned no valid mirror SurfaceControl\"

                    onStatus(\"Geometry mirror failed: $detail\")

                    com.duoopen.debug.DuoDiagnostics.event(
                        \"live-mirror\",
                        \"geometry bind failed reason=$reason \" +
                            \"session=$mirrorSession lease=$mirrorLeaseId \" +
                            \"source=${source.displayId} \" +
                            \"destination=$displayId error=$detail\",
                    )
                    return@post
"""

    new_failure = """                    val detail =
                        error
                            ?: \"shell returned no valid mirror SurfaceControl\"

                    com.duoopen.debug.DuoDiagnostics.event(
                        \"gen10-live-mirror\",
                        \"live mirror unavailable; falling back to frozen frame \" +
                            \"reason=$reason session=$mirrorSession lease=$mirrorLeaseId \" +
                            \"source=${source.displayId} destination=$displayId error=$detail\",
                    )

                    val fallbackBound =
                        tryBindFrozenFrame(
                            sourceKey = sourceKey,
                            sourceWidth = sourceWidth,
                            sourceHeight = sourceHeight,
                            reason = \"gen10-live-failure:$reason\",
                        )

                    if (!fallbackBound) {
                        onStatus(\"Geometry mirror failed: $detail\")
                    }
                    return@post
"""
    text = replace_once(text, old_failure, new_failure, "failure-only frozen fallback")

    text = replace_once(
        text,
        '"RIGHT PANE GEOMETRY LIVE: inner ${source.displayId} → cover $displayId."',
        '"GEN10 LIVE RIGHT PANE: inner ${source.displayId} → cover $displayId."',
        "live mirror status",
    )
    mirror.write_text(text)

    # Gen3 remains the semantic owner of the exact visual attempt, but it no
    # longer creates Fold7CoverVisualHost for closing. That host is the bitmap
    # screenshot/shader path which caused the field-observed split-brain effect.
    gen3 = repo / "app/src/full/java/com/duoopen/overlay/Fold7Gen3VisualCoordinator.kt"
    text = gen3.read_text()

    old_render = """        if (
            owner.snapshot()
                .visibleDemand
        ) {
            ensureRenderer(
                movement,
                frame,
                reason,
            )
        } else {
            detachRenderer(
                \"ready-hidden:$reason\"
            )
        }
"""

    new_render = """        if (
            owner.snapshot()
                .visibleDemand
        ) {
            /*
             * Gen10: continuity's DisplayMirrorHost owns closing pixels.
             * Never place the screenshot shader above the live app during a
             * normal close. DisplayMirrorHost itself owns the explicit frozen
             * fallback if the privileged mirror fails.
             */
            detachRenderer(
                \"gen10-live-mirror-owned:$reason\"
            )

            recordStage(
                type = \"gen10-live-mirror-delegated\",
                movement = movement,
                hostEpoch = owner.snapshot().host?.hostEpoch,
                reason = reason,
            )
        } else {
            detachRenderer(
                \"ready-hidden:$reason\"
            )
        }
"""
    text = replace_once(text, old_render, new_render, "delegate closing renderer to live mirror")

    text = replace_once(
        text,
        'Fold7CoverVisualAttemptOwner.Direction.CLOSING ->\n                        "GEN3_FROZEN_SHADER"',
        'Fold7CoverVisualAttemptOwner.Direction.CLOSING ->\n                        "GEN10_LIVE_MIRROR_DELEGATED"',
        "Gen10 render path telemetry",
    )
    gen3.write_text(text)


def verify(repo: Path) -> None:
    build = (repo / "app/build.gradle.kts").read_text()
    coordinator = (repo / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt").read_text()
    mirror = (repo / "app/src/full/java/com/duoopen/overlay/DisplayMirrorHost.kt").read_text()
    gen3 = (repo / "app/src/full/java/com/duoopen/overlay/Fold7Gen3VisualCoordinator.kt").read_text()
    cover_host = (repo / "app/src/full/java/com/duoopen/overlay/Fold7CoverVisualHost.kt").read_text()
    observer = (repo / "app/src/full/java/com/duoopen/overlay/Fold7DeviceStateObserver.kt").read_text()

    required = [
        (build, "versionCode = 47"),
        (build, 'versionName = "5.4.0-gen10-live-mirror-zfold7"'),
        (coordinator, 'syncMirrorHost(\n            reason = "state-show"'),
        (coordinator, 'reason = "topology:$reason"'),
        (coordinator, '"gen10-live-mirror"'),
        (mirror, "Gen10 invariant: live application content is authoritative"),
        (mirror, "live mirror unavailable; falling back to frozen frame"),
        (mirror, "GEN10 LIVE RIGHT PANE"),
        (gen3, '"gen10-live-mirror-owned:$reason"'),
        (gen3, '"GEN10_LIVE_MIRROR_DELEGATED"'),
        (cover_host, "liveFrameEpoch.owns(loopEpoch)"),
        (observer, "previousId == corroboratedClosedStateId"),
    ]
    missing = [needle for haystack, needle in required if needle not in haystack]
    if missing:
        raise RuntimeError(f"Gen10 verification failed; missing: {missing}")

    # No closing path should call the screenshot Fold7CoverVisualHost anymore.
    # One occurrence is the ensureRenderer() function declaration itself.
    if gen3.count("ensureRenderer(") != 1:
        raise RuntimeError(
            "Gen10 verification failed: Gen3 closing screenshot renderer is still reachable"
        )

    if "continuity frozen frame unavailable; falling back to live mirror" in mirror:
        raise RuntimeError("Gen10 verification failed: frozen-first policy still present")

    # The fallback helper definition plus exactly one failure-path invocation.
    if mirror.count("tryBindFrozenFrame(") != 2:
        raise RuntimeError(
            "Gen10 verification failed: frozen frame must be failure-only"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    apply(repo)
    verify(repo)
    print("Gen10 live-mirror-first closing presentation applied and verified")


if __name__ == "__main__":
    main()
