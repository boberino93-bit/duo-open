#!/usr/bin/env python3
"""Apply Gen10.5 Fold7 mirror warm-up retention after Gen10.4.

Gen10.4 field evidence showed that its construction fence prevented true
re-entrant construction, but the coordinator could still replace a host in the
few-millisecond gap after WindowManager.addView() succeeded and before
hostView.isAttachedToWindow became true. The coordinator's same-display reuse
condition used isUsable, so that transient warm-up state looked like a failed
host. Samsung display callbacks then detached it, invalidated its shell lease,
and created a replacement. Several close cycles showed 2-4 sequential hosts
and lease-mismatch stops before stabilization.

Gen10.5 gives a newly accepted host a bounded warm-up retention window. A host
that is attached/attaching on the same cover display is retained while Android
finishes attaching its accessibility window. A real detach still clears the
window immediately, and a host that never attaches ages out after 250 ms so it
can be replaced. Secure-content/native fail-open behavior is unchanged.
"""

from __future__ import annotations

import argparse
from pathlib import Path

TARGET_VERSION_CODE = 52
TARGET_VERSION_NAME = "5.4.5-gen10-mirror-warmup-retention-zfold7"
MARKER = "GEN10_5_MIRROR_WARMUP_RETENTION"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def apply(repo: Path) -> None:
    build = repo / "app/build.gradle.kts"
    text = build.read_text()
    text = replace_once(text, "versionCode = 51", f"versionCode = {TARGET_VERSION_CODE}", "versionCode")
    text = replace_once(
        text,
        'versionName = "5.4.4-gen10-io-coalescing-zfold7"',
        f'versionName = "{TARGET_VERSION_NAME}"',
        "versionName",
    )
    build.write_text(text)

    host = repo / "app/src/full/java/com/duoopen/overlay/DisplayMirrorHost.kt"
    text = host.read_text()

    text = replace_once(
        text,
        '''    val isUsable: Boolean
        get() = attached && hostView.isAttachedToWindow
''',
        '''    val isUsable: Boolean
        get() = attached && hostView.isAttachedToWindow

    /*
     * GEN10_5_MIRROR_WARMUP_RETENTION
     * WindowManager.addView() may succeed before View attachment propagates.
     * During that short interval isUsable is false even though this exact host
     * owns the accepted window/lease and should not be replaced.
     */
    val isAttachInProgress: Boolean
        get() =
            attached &&
                !hostView.isAttachedToWindow &&
                attachGraceDeadlineUptimeMs > 0L &&
                SystemClock.uptimeMillis() <= attachGraceDeadlineUptimeMs
''',
        "warm-up retention property",
    )

    text = replace_once(
        text,
        '''    private var attached = false
    private var generation = 0
''',
        '''    private var attached = false
    private var attachGraceDeadlineUptimeMs = 0L
    private var generation = 0
''',
        "warm-up retention state",
    )

    text = replace_once(
        text,
        '''                    override fun onViewAttachedToWindow(v: View) {
                        attached = true
                        v.post { bind("window-attached") }
                    }
''',
        '''                    override fun onViewAttachedToWindow(v: View) {
                        attached = true
                        attachGraceDeadlineUptimeMs = 0L
                        v.post { bind("window-attached") }
                    }
''',
        "clear grace on real attach",
    )

    text = replace_once(
        text,
        '''                    override fun onViewDetachedFromWindow(v: View) {
                        attached = false
                        generation++
''',
        '''                    override fun onViewDetachedFromWindow(v: View) {
                        attached = false
                        attachGraceDeadlineUptimeMs = 0L
                        generation++
''',
        "clear grace on detach",
    )

    text = replace_once(
        text,
        '''        if (attached) {
            return
        }

        val params =
''',
        '''        if (attached) {
            return
        }

        attachGraceDeadlineUptimeMs =
            SystemClock.uptimeMillis() +
                ATTACH_GRACE_MS

        val params =
''',
        "start bounded attach grace",
    )

    text = replace_once(
        text,
        '''    private companion object {
''',
        '''    private companion object {
        const val ATTACH_GRACE_MS = 250L
''',
        "attach grace constant",
    )

    host.write_text(text)

    coordinator = repo / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"
    text = coordinator.read_text()

    old_same_host = '''        if (
            current != null &&
            current.displayId == activeCover.displayId &&
            current.isUsable
        ) {
            val latestHinge = currentHingeAngle()
            if (latestHinge.isFinite()) {
                current.onHinge(latestHinge)
            }

            val routineStableTopology =
                reason.startsWith("topology:display-changed:") ||
                    reason == "topology:sync-displays"

            if (!routineStableTopology) {
                runCatching {
                    current.refresh("stable:$reason")
                }
            } else {
                DuoDiagnostics.event(
                    "gen10-3-hybrid",
                    "stable geometry refresh suppressed reason=$reason " +
                        "display=${current.displayId} hinge=$latestHinge",
                )
            }
            return
        }
'''

    new_same_host = '''        if (
            current != null &&
            current.displayId == activeCover.displayId &&
            (
                current.isUsable ||
                    current.isAttachInProgress
            )
        ) {
            val latestHinge = currentHingeAngle()
            if (latestHinge.isFinite()) {
                current.onHinge(latestHinge)
            }

            if (current.isAttachInProgress) {
                DuoDiagnostics.event(
                    "gen10-5-mirror-warmup",
                    "retaining attaching host reason=$reason generation=$generation " +
                        "display=${current.displayId} hinge=$latestHinge",
                )
                return
            }

            val routineStableTopology =
                reason.startsWith("topology:display-changed:") ||
                    reason == "topology:sync-displays"

            if (!routineStableTopology) {
                runCatching {
                    current.refresh("stable:$reason")
                }
            } else {
                DuoDiagnostics.event(
                    "gen10-3-hybrid",
                    "stable geometry refresh suppressed reason=$reason " +
                        "display=${current.displayId} hinge=$latestHinge",
                )
            }
            return
        }
'''

    text = replace_once(text, old_same_host, new_same_host, "retain same-display host while attaching")
    coordinator.write_text(text)


def verify(repo: Path) -> None:
    build = (repo / "app/build.gradle.kts").read_text()
    host = (repo / "app/src/full/java/com/duoopen/overlay/DisplayMirrorHost.kt").read_text()
    coordinator = (repo / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt").read_text()
    service = (repo / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt").read_text()
    gen3 = (repo / "app/src/full/java/com/duoopen/overlay/Fold7Gen3VisualCoordinator.kt").read_text()
    panel = (repo / "app/src/full/java/com/duoopen/overlay/PanelEngine.kt").read_text()

    required = [
        f"versionCode = {TARGET_VERSION_CODE}",
        f'versionName = "{TARGET_VERSION_NAME}"',
        MARKER,
        "val isAttachInProgress: Boolean",
        "attachGraceDeadlineUptimeMs",
        "ATTACH_GRACE_MS = 250L",
        "current.isAttachInProgress",
        '"retaining attaching host reason=$reason generation=$generation "',
        "mirrorHostConstructing",
        "coverPresentationGate.offer(",
        'type = "gen10-3-hybrid-animation"',
        '"capture-protected-or-black"',
        '"Protected/uncapturable content: native display passthrough."',
    ]
    joined = "\n".join([build, host, coordinator, service, gen3, panel])
    missing = [needle for needle in required if needle not in joined]
    if missing:
        raise RuntimeError(f"Gen10.5 verification failed; missing: {missing}")

    if coordinator.count("current.isAttachInProgress") != 2:
        raise RuntimeError("Gen10.5 verification failed: warm-up host policy is incomplete")

    if host.count("ATTACH_GRACE_MS") != 2:
        raise RuntimeError("Gen10.5 verification failed: attach grace declaration/use mismatch")

    proof_index = host.index("val captureProof =")
    start_index = host.index("ShizukuBridge.startDisplayMirrorV2(")
    if proof_index >= start_index:
        raise RuntimeError("Gen10.5 verification failed: secure proof no longer gates live mirror")

    forbidden = [
        "FLAG_SECURE bypass",
        "clear FLAG_SECURE",
        "disable FLAG_SECURE",
    ]
    for needle in forbidden:
        if needle.lower() in joined.lower():
            raise RuntimeError(f"Gen10.5 verification failed: forbidden secure behavior: {needle}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    apply(repo)
    verify(repo)
    print("Gen10.5 mirror warm-up retention applied and verified")


if __name__ == "__main__":
    main()
