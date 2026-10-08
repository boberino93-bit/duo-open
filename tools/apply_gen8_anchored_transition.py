#!/usr/bin/env python3
"""Apply the Gen8 anchored-transition ownership patch after Gen7 Beta2."""

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
    build_text = build.read_text()
    build_text = replace_once(
        build_text,
        'versionCode = 43',
        'versionCode = 44',
        'versionCode',
    )
    build_text = replace_once(
        build_text,
        'versionName = "5.1.0-beta2-zfold7"',
        'versionName = "5.2.0-gen8-anchored-zfold7"',
        'versionName',
    )
    build.write_text(build_text)

    host = repo / "app/src/full/java/com/duoopen/overlay/Fold7CoverVisualHost.kt"
    text = host.read_text()

    text = replace_once(
        text,
        """    private val displayManager =\n        service.getSystemService(DisplayManager::class.java)\n\n    @Volatile\n    private var liveClosingLoop = false\n\n    private var liveClosingFrames = 0L\n""",
        """    private val displayManager =\n        service.getSystemService(DisplayManager::class.java)\n\n    /*\n     * Gen8 physical anchor invariant: the destination cover geometry belongs\n     * to this host instance. Do not let an asynchronous display-rotation read\n     * move the fold axis underneath an active transition.\n     */\n    private val anchorRotation = display.rotation\n\n    private val liveFrameEpoch =\n        Fold7TransitionEpoch()\n\n    @Volatile\n    private var liveClosingLoop = false\n\n    private var liveClosingFrames = 0L\n""",
        'host state',
    )

    # Every display.rotation use in this host describes cover-side destination
    # geometry. Source captures use a separately frozen inner rotation below.
    display_rotation_count = text.count('rotation = display.rotation')
    if display_rotation_count != 4:
        raise RuntimeError(
            f"anchor rotation: expected 4 destination matches, found {display_rotation_count}"
        )
    text = text.replace('rotation = display.rotation', 'rotation = anchorRotation')

    text = replace_once(
        text,
        """    fun detach() {\n        liveClosingLoop = false\n        follower?.cancel()\n""",
        """    fun detach() {\n        liveClosingLoop = false\n        liveFrameEpoch.invalidate()\n        follower?.cancel()\n""",
        'detach invalidation',
    )

    text = replace_once(
        text,
        """        liveClosingLoop = true\n\n        val runner =\n""",
        """        liveClosingLoop = true\n        val loopEpoch =\n            liveFrameEpoch.begin()\n\n        DuoDiagnostics.event(\n            "gen8-frame-epoch",\n            "begin epoch=$loopEpoch anchorRotation=$anchorRotation",\n        )\n\n        val runner =\n""",
        'loop epoch begin',
    )

    text = replace_once(
        text,
        """                override fun run() {\n                    if (!liveClosingLoop) return\n\n                    val inner =\n""",
        """                override fun run() {\n                    if (\n                        !liveClosingLoop ||\n                        !liveFrameEpoch.owns(loopEpoch)\n                    ) {\n                        return\n                    }\n\n                    val inner =\n""",
        'runner epoch gate',
    )

    text = replace_once(
        text,
        """                    val frameStarted =\n                        android.os.SystemClock.uptimeMillis()\n\n                    val nextRun = this\n""",
        """                    val frameStarted =\n                        android.os.SystemClock.uptimeMillis()\n\n                    /*\n                     * Freeze source identity/orientation before the asynchronous\n                     * shell capture. The completed bitmap belongs to this exact\n                     * capture request, not to whatever Display state exists when\n                     * the coroutine returns.\n                     */\n                    val captureDisplayId =\n                        inner.displayId\n                    val captureRotation =\n                        inner.rotation\n\n                    val nextRun = this\n""",
        'capture identity freeze',
    )

    text = replace_once(
        text,
        'displayId = inner.displayId,',
        'displayId = captureDisplayId,',
        'capture display id',
    )
    text = replace_once(
        text,
        'rotation = inner.rotation,',
        'rotation = captureRotation,',
        'capture source rotation',
    )

    text = replace_once(
        text,
        """                            if (\n                                liveClosingLoop &&\n                                composed != null\n                            ) {\n""",
        """                            if (\n                                liveClosingLoop &&\n                                liveFrameEpoch.owns(loopEpoch) &&\n                                composed != null\n                            ) {\n""",
        'publish epoch gate',
    )

    text = replace_once(
        text,
        '"rotation=${inner.rotation} " +',
        '"rotation=$captureRotation epoch=$loopEpoch " +',
        'diagnostic capture rotation',
    )

    text = replace_once(
        text,
        """                            if (liveClosingLoop) {\n                                val elapsed =\n""",
        """                            if (\n                                liveClosingLoop &&\n                                liveFrameEpoch.owns(loopEpoch)\n                            ) {\n                                val elapsed =\n""",
        'reschedule epoch gate',
    )

    host.write_text(text)


def verify(repo: Path) -> None:
    build_text = (repo / "app/build.gradle.kts").read_text()
    host_text = (
        repo / "app/src/full/java/com/duoopen/overlay/Fold7CoverVisualHost.kt"
    ).read_text()

    required = [
        'versionCode = 44',
        'versionName = "5.2.0-gen8-anchored-zfold7"',
        'private val anchorRotation = display.rotation',
        'private val liveFrameEpoch =',
        'liveFrameEpoch.invalidate()',
        'val loopEpoch =',
        '!liveFrameEpoch.owns(loopEpoch)',
        'liveFrameEpoch.owns(loopEpoch) &&',
        'val captureDisplayId =',
        'val captureRotation =',
        'rotation = captureRotation,',
        '"gen8-frame-epoch"',
    ]
    joined = build_text + "\n" + host_text
    missing = [needle for needle in required if needle not in joined]
    if missing:
        raise RuntimeError(f"Gen8 verification failed; missing: {missing}")

    if 'rotation = display.rotation' in host_text:
        raise RuntimeError('Gen8 verification failed: mutable cover rotation remains')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', default='.')
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    apply(repo)
    verify(repo)
    print('Gen8 anchored-transition patch applied and verified')


if __name__ == '__main__':
    main()
