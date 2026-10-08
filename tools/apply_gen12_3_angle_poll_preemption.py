#!/usr/bin/env python3
"""Apply the Gen12.3 Fold7 precise-angle high-priority poll preemption overlay.

This patch is intentionally narrow. It assumes the Gen12.2 route-retention
candidate has already been reconstructed/applied, then:
- adds same-session retirement of one in-flight Samsung precise-angle poll;
- fences a retired command before main-thread dispatch when cancellation wins;
- makes the existing opening-edge kick always schedule a fresh sequence;
- records preemption / reacquisition-target diagnostics;
- adds deterministic ownership tests;
- advances the validation-candidate version to 5.6.3 / code 59.

It does not change hinge thresholds, geometry, wallpaper ownership, the global
96 ms timeout, Shizuku protocol, or Samsung callback acceptance semantics.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def patch_file(path: Path, transform) -> None:
    original = path.read_text(encoding="utf-8")
    updated = transform(original)
    if updated == original:
        raise RuntimeError(f"{path}: transform made no change")
    path.write_text(updated, encoding="utf-8")


def patch_pipeline(text: str) -> str:
    marker = """    fun completePoll(\n        token: PollToken,\n        completionUptimeMs: Long,\n    ): Long? {\n"""
    insertion = """    /**\n     * Retire only the current poll token without invalidating the reader\n     * session. A replacement poll receives a larger sequence, so any late\n     * callback or timeout from the retired token is rejected by the existing\n     * identity checks.\n     */\n    fun preemptInFlightPoll(): PollToken? {\n        val current = inFlight ?: return null\n        inFlight = null\n        return current\n    }\n\n""" + marker
    return replace_once(
        text,
        marker,
        insertion,
        "Fold7AnglePipelineGen2 preemption insertion",
    )


def patch_feed(text: str) -> str:
    field_marker = """    private var scheduledPollSession = -1L\n\n"""
    text = replace_once(
        text,
        field_marker,
        field_marker
        + """    /** Highest same-session poll sequence explicitly retired by a strong reacquisition edge. */\n    @Volatile\n    private var preemptedThroughPollSequence = 0L\n\n""",
        "WallpaperAngleFeed preempt watermark field",
    )

    reset_marker = """        lastWallpaperIdentity = \"\"\n        lastFreshState = null\n\n"""
    text = replace_once(
        text,
        reset_marker,
        reset_marker + "        preemptedThroughPollSequence = 0L\n\n",
        "WallpaperAngleFeed preempt watermark reset",
    )

    old_kick = """    /**\n     * An independent opening edge can pull the next precise sample forward\n     * without inventing any visual angle.\n     */\n    fun kickBurst(\n        reason: String,\n    ) {\n        val session =\n            readerSession\n\n        controlHandler.post {\n            if (!isCurrent(session)) return@post\n\n            TransitionLab.recordIngressStage(\n                type = \"poll-kick\",\n                angleSession = session,\n                reason = reason,\n            )\n\n            if (pipeline.inFlightPoll == null) {\n                schedulePoll(\n                    session = session,\n                    delayMs = 0L,\n                )\n            }\n        }\n    }\n"""
    new_kick = """    /**\n     * A strong independent opening edge can pull the next precise sample\n     * forward without inventing any visual angle. If an older poll is still\n     * waiting on a non-responsive wallpaper target, retire only that token and\n     * immediately issue a higher sequence in the same reader session.\n     */\n    fun kickBurst(\n        reason: String,\n    ) {\n        val session =\n            readerSession\n\n        controlHandler.post {\n            if (!isCurrent(session)) return@post\n\n            TransitionLab.recordIngressStage(\n                type = \"poll-kick\",\n                angleSession = session,\n                reason = reason,\n            )\n\n            val preempted =\n                pipeline.preemptInFlightPoll()\n\n            if (preempted != null) {\n                preemptedThroughPollSequence =\n                    maxOf(\n                        preemptedThroughPollSequence,\n                        preempted.sequence,\n                    )\n\n                TransitionLab.recordIngressStage(\n                    type = \"poll-preempt\",\n                    angleSession = session,\n                    pollSequence = preempted.sequence,\n                    reason = reason,\n                )\n            }\n\n            // One exact target observation per strong reacquisition edge. This\n            // is diagnostic only and deliberately avoids per-poll wallpaper\n            // identity Binder traffic.\n            mainHandler.post {\n                if (isCurrent(session)) {\n                    TransitionLab.recordIngressStage(\n                        type = \"poll-reacquire-target\",\n                        angleSession = session,\n                        reason =\n                            \"$reason wallpaper=${wallpaperIdentity(context)}\",\n                    )\n                }\n            }\n\n            schedulePoll(\n                session = session,\n                delayMs = 0L,\n            )\n        }\n    }\n"""
    text = replace_once(
        text,
        old_kick,
        new_kick,
        "WallpaperAngleFeed kickBurst replacement",
    )

    old_session_guard = """        mainHandler.post {\n            if (!isCurrent(session)) {\n                controlHandler.post {\n                    completePollWithoutSample(\n                        session = session,\n                        poll = poll,\n                        reason = \"session-invalid-before-command\",\n                    )\n                }\n                return@post\n            }\n\n            val commandStartNs =\n"""
    new_session_guard = """        mainHandler.post {\n            if (!isCurrent(session)) {\n                controlHandler.post {\n                    completePollWithoutSample(\n                        session = session,\n                        poll = poll,\n                        reason = \"session-invalid-before-command\",\n                    )\n                }\n                return@post\n            }\n\n            // If the high-priority edge retired this sequence before its\n            // main-thread command began, do not dispatch the obsolete command.\n            // A command that has already entered sendWallpaperCommand cannot be\n            // synchronously cancelled; its later response remains sequence-fenced.\n            if (poll.sequence <= preemptedThroughPollSequence) {\n                TransitionLab.recordIngressStage(\n                    type = \"poll-command-skip-preempted\",\n                    angleSession = session,\n                    pollSequence = poll.sequence,\n                    reason =\n                        \"preemptedThrough=$preemptedThroughPollSequence\",\n                )\n                return@post\n            }\n\n            val commandStartNs =\n"""
    return replace_once(
        text,
        old_session_guard,
        new_session_guard,
        "WallpaperAngleFeed pre-dispatch retirement fence",
    )


def patch_test(text: str) -> str:
    marker = """    @Test\n    fun invalidAnglesAreRejected() {\n"""
    test = """    @Test\n    fun preemptedPollIsFencedWithoutInvalidatingSession() {\n        val pipeline = Fold7AnglePipelineGen2()\n        val session = pipeline.startSession()\n\n        val first = pipeline.tryStartPoll(100L)!!\n        assertEquals(first, pipeline.preemptInFlightPoll())\n        assertNull(pipeline.inFlightPoll)\n\n        val second = pipeline.tryStartPoll(101L)!!\n        assertEquals(session, second.session)\n        assertTrue(second.sequence > first.sequence)\n\n        assertNull(pipeline.nextSample(first, 10f))\n        assertNull(pipeline.completePoll(first, 102L))\n        assertNull(pipeline.timeoutPoll(first, 196L))\n\n        assertNotNull(pipeline.nextSample(second, 11f))\n        assertNull(pipeline.tryStartPoll(103L))\n    }\n\n""" + marker
    return replace_once(
        text,
        marker,
        test,
        "Fold7AnglePipelineGen2Test preemption contract",
    )


def patch_version(text: str) -> str:
    text = replace_once(
        text,
        "versionCode = 58",
        "versionCode = 59",
        "versionCode 58 -> 59",
    )
    return replace_once(
        text,
        'versionName = "5.6.2-gen12-2-route-retention-fence-zfold7"',
        'versionName = "5.6.3-gen12-3-angle-poll-preemption-zfold7"',
        "Gen12.3 versionName",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()

    patch_file(
        repo / "app/src/full/java/com/duoopen/shell/Fold7AnglePipelineGen2.kt",
        patch_pipeline,
    )
    patch_file(
        repo / "app/src/full/java/com/duoopen/shell/WallpaperAngleFeed.kt",
        patch_feed,
    )
    patch_file(
        repo / "app/src/test/java/com/duoopen/shell/Fold7AnglePipelineGen2Test.kt",
        patch_test,
    )
    patch_file(repo / "app/build.gradle.kts", patch_version)

    print("GEN12.3 ANGLE POLL PREEMPTION OVERLAY: APPLIED")


if __name__ == "__main__":
    main()
