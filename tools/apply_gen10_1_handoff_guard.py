#!/usr/bin/env python3
"""Apply Gen10.1 Fold7 terminal-handoff guards after Gen10 live-mirror close."""

from __future__ import annotations

import argparse
from pathlib import Path

TARGET_VERSION_CODE = 48
TARGET_VERSION_NAME = "5.4.1-gen10-handoff-guard-zfold7"
MARKER = "GEN10_1_HANDOFF_GUARD"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def apply(repo: Path) -> None:
    build = repo / "app/build.gradle.kts"
    build_text = build.read_text()
    build_text = replace_once(build_text, "versionCode = 47", f"versionCode = {TARGET_VERSION_CODE}", "versionCode")
    build_text = replace_once(
        build_text,
        'versionName = "5.4.0-gen10-live-mirror-zfold7"',
        f'versionName = "{TARGET_VERSION_NAME}"',
        "versionName",
    )
    build.write_text(build_text)

    coordinator = repo / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"
    text = coordinator.read_text()

    text = replace_once(
        text,
        '''        if (activeInner == null || activeCover == null) {
            DuoDiagnostics.event(
                "fold7-state",
                "mirror wait reason=$reason generation=$generation " +
                    "inner=${snapshot.inner?.displayId}:${snapshot.inner?.state} " +
                    "cover=${snapshot.cover?.displayId}:${snapshot.cover?.state}",
            )
            return
        }

        if (activeInner.displayId == activeCover.displayId) {
''',
        '''        if (activeInner == null || activeCover == null) {
            DuoDiagnostics.event(
                "fold7-state",
                "mirror wait reason=$reason generation=$generation " +
                    "inner=${snapshot.inner?.displayId}:${snapshot.inner?.state} " +
                    "cover=${snapshot.cover?.displayId}:${snapshot.cover?.state}",
            )
            return
        }

        /*
         * GEN10_1_HANDOFF_GUARD
         *
         * Display 0 is Samsung's native/default ownership surface. A COVER_VISUAL
         * decision can briefly outlive the logical 1 -> 0 remap, so never create
         * or refresh a transition host on the native route. The prior Gen10 trace
         * showed exactly this race: a host was constructed on display 0 and torn
         * down a few milliseconds later at NATIVE_COVER.
         */
        if (activeCover.displayId == Display.DEFAULT_DISPLAY) {
            val stale = mirrorHost
            mirrorHost = null
            runCatching { stale?.detach() }
            DuoDiagnostics.event(
                "gen10-handoff-guard",
                "mirror blocked native-default reason=$reason generation=$generation",
            )
            return
        }

        if (activeInner.displayId == activeCover.displayId) {
''',
        "native display mirror fence",
    )

    text = replace_once(
        text,
        '''        if (
            !mirrorRequested ||
            !controller.isGenerationCurrent(generation) ||
            controller.state != Fold7ContinuityController.State.COVER_VISUAL
        ) {
            runCatching { created.detach() }
            return
        }

        val attached =
''',
        '''        if (
            !mirrorRequested ||
            !controller.isGenerationCurrent(generation) ||
            controller.state != Fold7ContinuityController.State.COVER_VISUAL
        ) {
            runCatching { created.detach() }
            return
        }

        /*
         * Re-resolve immediately before attach. Samsung may remap the physical
         * cover after the first topology snapshot but before host construction
         * completes. Fail closed if the destination changed or became default.
         */
        val attachSnapshot = topologySnapshot()
        val attachCover = attachSnapshot.cover?.takeIf(::isActive)
        if (
            attachCover == null ||
            attachCover.displayId == Display.DEFAULT_DISPLAY ||
            attachCover.displayId != activeCover.displayId
        ) {
            runCatching { created.detach() }
            DuoDiagnostics.event(
                "gen10-handoff-guard",
                "mirror attach blocked reason=$reason generation=$generation " +
                    "planned=${activeCover.displayId} current=${attachCover?.displayId}",
            )
            return
        }

        val attached =
''',
        "pre-attach topology fence",
    )

    text = replace_once(
        text,
        '''        if (
            !mirrorRequested ||
            !controller.isGenerationCurrent(generation)
        ) {
            runCatching { created.detach() }
            return
        }

        mirrorHost = created
''',
        '''        if (
            !mirrorRequested ||
            !controller.isGenerationCurrent(generation)
        ) {
            runCatching { created.detach() }
            return
        }

        val publishedSnapshot = topologySnapshot()
        val publishedCover = publishedSnapshot.cover?.takeIf(::isActive)
        if (
            publishedCover == null ||
            publishedCover.displayId == Display.DEFAULT_DISPLAY ||
            publishedCover.displayId != activeCover.displayId
        ) {
            runCatching { created.detach() }
            DuoDiagnostics.event(
                "gen10-handoff-guard",
                "mirror publish blocked reason=$reason generation=$generation " +
                    "planned=${activeCover.displayId} current=${publishedCover?.displayId}",
            )
            return
        }

        mirrorHost = created
''',
        "post-attach topology fence",
    )

    coordinator.write_text(text)

    service = repo / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"
    text = service.read_text()

    text = replace_once(
        text,
        '''    private var innerBrightnessReference =
        Fold7CoverPresentationPolicy.DEFAULT_INNER_REFERENCE
    private var angleFeed: WallpaperAngleFeed? = null
''',
        '''    private var innerBrightnessReference =
        Fold7CoverPresentationPolicy.DEFAULT_INNER_REFERENCE

    /*
     * GEN10_1_HANDOFF_GUARD
     * The physical cover can retain the intended brightness while logical 1
     * is secondary, then Samsung may overwrite it when the same panel becomes
     * logical/default display 0. Reassert once per NATIVE_COVER generation.
     */
    private var nativeCoverBrightnessReassertGeneration = -1L

    private var angleFeed: WallpaperAngleFeed? = null
''',
        "brightness guard state",
    )

    text = replace_once(
        text,
        '''        continuity.onTopologyChanged(
            "sync-displays"
        )

        primeContinuityFrameIfNeeded(
''',
        '''        continuity.onTopologyChanged(
            "sync-displays"
        )

        reconcileNativeCoverBrightnessGuard(
            "sync-displays"
        )

        primeContinuityFrameIfNeeded(
''',
        "sync-displays brightness guard",
    )

    text = replace_once(
        text,
        '''        continuity.onTopologyFastLane(
            reason
        )

        primeContinuityFrameIfNeeded(
''',
        '''        continuity.onTopologyFastLane(
            reason
        )

        reconcileNativeCoverBrightnessGuard(
            "fast:$reason"
        )

        primeContinuityFrameIfNeeded(
''',
        "fast-lane brightness guard",
    )

    guard_function = r'''    private fun reconcileNativeCoverBrightnessGuard(
        reason: String,
    ) {
        if (
            !::continuity.isInitialized ||
            !ShizukuBridge.ready ||
            !continuity.renderOwnershipEnabled
        ) {
            return
        }

        if (
            continuity.state !=
                Fold7ContinuityController.State.NATIVE_COVER
        ) {
            nativeCoverBrightnessReassertGeneration = -1L
            return
        }

        val generation = continuity.generation
        if (
            nativeCoverBrightnessReassertGeneration ==
                generation
        ) {
            return
        }

        nativeCoverBrightnessReassertGeneration =
            generation

        val targetBrightness =
            innerBrightnessReference
                .takeIf { it.isFinite() }
                ?.coerceIn(
                    Fold7CoverPresentationPolicy.MIN_BRIGHTNESS,
                    1f,
                )
                ?: Fold7CoverPresentationPolicy.DEFAULT_INNER_REFERENCE

        val sequence =
            coverPresentationSequence.incrementAndGet()

        /*
         * This uses the existing daemon-side stable physical cover resolver.
         * No logical display id is supplied, so a 1 -> 0 remap cannot retarget
         * the write onto the inner panel.
         */
        scope.launch(Dispatchers.IO) {
            val result =
                ShizukuBridge.setCoverPresentationV1(
                    serviceEpoch = serviceEpoch,
                    transitionGeneration = generation,
                    sequence = sequence,
                    powerOn = true,
                    brightness = targetBrightness,
                    reason =
                        "native-cover-brightness-reassert:$reason",
                )

            DuoDiagnostics.event(
                "gen10-handoff-guard",
                "brightness reassert reason=$reason generation=$generation " +
                    "target=$targetBrightness sequence=$sequence " +
                    "ok=${result?.getBoolean("ok", false) == true} " +
                    "stale=${result?.getBoolean("stale", false) == true} " +
                    "physical=${result?.getLong("physicalDisplayId", -1L) ?: -1L} " +
                    "brightnessError=${result?.getString("brightnessError")}",
            )
        }
    }

'''
    text = replace_once(
        text,
        '''    private fun setEarlyOpeningVisualLatched(
''',
        guard_function + '''    private fun setEarlyOpeningVisualLatched(
''',
        "brightness guard function",
    )

    service.write_text(text)


def verify(repo: Path) -> None:
    build_text = (repo / "app/build.gradle.kts").read_text()
    coordinator_text = (repo / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt").read_text()
    service_text = (repo / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt").read_text()

    required = [
        f"versionCode = {TARGET_VERSION_CODE}",
        f'versionName = "{TARGET_VERSION_NAME}"',
        MARKER,
        'activeCover.displayId == Display.DEFAULT_DISPLAY',
        'attachCover.displayId == Display.DEFAULT_DISPLAY',
        'publishedCover.displayId == Display.DEFAULT_DISPLAY',
        '"gen10-handoff-guard"',
        'nativeCoverBrightnessReassertGeneration',
        '"native-cover-brightness-reassert:$reason"',
        'reconcileNativeCoverBrightnessGuard(',
    ]
    joined = build_text + "\n" + coordinator_text + "\n" + service_text
    missing = [needle for needle in required if needle not in joined]
    if missing:
        raise RuntimeError(f"Gen10.1 verification failed; missing: {missing}")

    if joined.count(MARKER) < 2:
        raise RuntimeError("Gen10.1 verification failed: guard markers incomplete")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    apply(repo)
    verify(repo)
    print("Gen10.1 terminal-handoff guard applied and verified")


if __name__ == "__main__":
    main()
