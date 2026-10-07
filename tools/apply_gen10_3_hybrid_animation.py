#!/usr/bin/env python3
"""Apply Gen10.3 Fold7 hybrid closing animation after Gen10.2.

Field evidence from the Gen10.2 candidate showed two independent regressions:
1. Gen10 explicitly removed the Gen3 closing shader and delegated all closing
   pixels to the live SurfaceControl mirror, so the cover fold animation was
   absent by construction.
2. DisplayMirrorHost received only a one-time hinge seed at construction. The
   authoritative hinge stream continued, but the live mirror host's telemetry
   and visual state remained frozen at the construction angle.

Gen10.3 restores the exact-cycle closing shader only when Gen10.2 has already
proved the current content capturable, keeps the live mirror beneath that
animated presentation, forwards every authoritative hinge sample to the live
mirror host, and suppresses redundant stable topology geometry refreshes.
Protected/FLAG_SECURE content remains native fail-open; this patch does not
weaken or bypass the Gen10.2 guard.
"""

from __future__ import annotations

import argparse
from pathlib import Path

TARGET_VERSION_CODE = 50
TARGET_VERSION_NAME = "5.4.3-gen10-hybrid-animation-zfold7"
MARKER = "GEN10_3_HYBRID_ANIMATION"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def apply(repo: Path) -> None:
    build = repo / "app/build.gradle.kts"
    text = build.read_text()
    text = replace_once(
        text,
        "versionCode = 49",
        f"versionCode = {TARGET_VERSION_CODE}",
        "versionCode",
    )
    text = replace_once(
        text,
        'versionName = "5.4.2-gen10-secure-fail-open-zfold7"',
        f'versionName = "{TARGET_VERSION_NAME}"',
        "versionName",
    )
    build.write_text(text)

    # Restore the Gen3 exact-cycle Fold7 shader above the live mirror, but only
    # when a fresh frame from this close cycle exists. Gen10.2 clears/rejects
    # secure or mostly-black captures, so frame == null is the secure/native
    # fail-open path and must never attach an opaque Duo renderer.
    gen3 = repo / "app/src/full/java/com/duoopen/overlay/Fold7Gen3VisualCoordinator.kt"
    text = gen3.read_text()

    old_render = '''        if (
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
                "gen10-live-mirror-owned:$reason"
            )

            recordStage(
                type = "gen10-live-mirror-delegated",
                movement = movement,
                hostEpoch = owner.snapshot().host?.hostEpoch,
                reason = reason,
            )
        } else {
            detachRenderer(
                "ready-hidden:$reason"
            )
        }
'''

    new_render = '''        if (
            owner.snapshot()
                .visibleDemand
        ) {
            /*
             * GEN10_3_HYBRID_ANIMATION
             *
             * Restore the Fold7 optical close animation above the Gen10 live
             * mirror, but only with a fresh exact-cycle frame. Gen10.2 rejects
             * protected/mostly-black continuity primes before they enter the
             * frame store, so frame == null deliberately means native fail-open.
             */
            if (frame != null) {
                ensureRenderer(
                    movement,
                    frame,
                    reason,
                )

                recordStage(
                    type = "gen10-3-hybrid-animation",
                    movement = movement,
                    hostEpoch = owner.snapshot().host?.hostEpoch,
                    contentLeaseId = frame.contentLeaseId,
                    reason = reason,
                )
            } else {
                detachRenderer(
                    "gen10-3-native-fail-open:$reason"
                )

                recordStage(
                    type = "gen10-3-native-fail-open",
                    movement = movement,
                    hostEpoch = owner.snapshot().host?.hostEpoch,
                    reason = reason,
                )
            }
        } else {
            detachRenderer(
                "ready-hidden:$reason"
            )
        }
'''
    text = replace_once(text, old_render, new_render, "restore guarded close shader")
    text = replace_once(
        text,
        'Fold7CoverVisualAttemptOwner.Direction.CLOSING ->\n                        "GEN10_LIVE_MIRROR_DELEGATED"',
        'Fold7CoverVisualAttemptOwner.Direction.CLOSING ->\n                        "GEN10_3_HYBRID_ANIMATED_CLOSE"',
        "Gen10.3 closing render telemetry",
    )
    gen3.write_text(text)

    coordinator = repo / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"
    text = coordinator.read_text()

    # The live mirror host was previously seeded only once at construction.
    # Feed it every authoritative sample so hinge direction/velocity and any
    # host-side visual decisions cannot freeze at the attach angle.
    text = replace_once(
        text,
        '''        apply(decision)

    }
''',
        '''        apply(decision)

        /*
         * GEN10_3_HYBRID_ANIMATION
         * Keep the live mirror on the same authoritative hinge timeline as
         * Gen3/PanelEngine. Gen10 seeded this host only once at construction,
         * which field logs showed freezing around 98 degrees while the device
         * continued toward closed.
         */
        if (visualMirrorActive) {
            mirrorHost?.onHinge(angle)
        }

    }
''',
        "authoritative live-mirror hinge forwarding",
    )

    # Samsung emits dense display-changed/sync callbacks during a fold. Once a
    # host is valid on the same cover display, replaying setGeometry for each of
    # those callbacks creates redundant transactions and presentation attempts.
    # Layout changes already refresh from DisplayMirrorHost itself. Keep an
    # explicit refresh for non-routine reasons and always update hinge state.
    text = replace_once(
        text,
        '''        if (
            current != null &&
            current.displayId == activeCover.displayId &&
            current.isUsable
        ) {
            runCatching {
                current.refresh("stable:$reason")
            }
            return
        }
''',
        '''        if (
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
''',
        "suppress redundant stable geometry refresh",
    )
    coordinator.write_text(text)

    # Reduce only the close shader's follower latency. This does not request a
    # display mode switch and therefore cannot introduce a non-seamless 60/120
    # Hz transition. The field trace showed 60 Hz remaining active even after a
    # seamless-only 120 Hz request, so mode forcing is intentionally deferred.
    host = repo / "app/src/full/java/com/duoopen/overlay/Fold7CoverVisualHost.kt"
    text = host.read_text()
    text = replace_once(
        text,
        '''        const val CLOSING_TAU_S =
            0.028f
''',
        '''        // GEN10_3_HYBRID_ANIMATION: lower close-follow latency at 60 Hz.
        const val CLOSING_TAU_S =
            0.020f
''',
        "closing follower latency",
    )
    host.write_text(text)


def verify(repo: Path) -> None:
    build = (repo / "app/build.gradle.kts").read_text()
    gen3 = (repo / "app/src/full/java/com/duoopen/overlay/Fold7Gen3VisualCoordinator.kt").read_text()
    coordinator = (repo / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt").read_text()
    host = (repo / "app/src/full/java/com/duoopen/overlay/Fold7CoverVisualHost.kt").read_text()
    panel = (repo / "app/src/full/java/com/duoopen/overlay/PanelEngine.kt").read_text()
    mirror = (repo / "app/src/full/java/com/duoopen/overlay/DisplayMirrorHost.kt").read_text()

    required = [
        f"versionCode = {TARGET_VERSION_CODE}",
        f'versionName = "{TARGET_VERSION_NAME}"',
        MARKER,
        'type = "gen10-3-hybrid-animation"',
        'type = "gen10-3-native-fail-open"',
        '"GEN10_3_HYBRID_ANIMATED_CLOSE"',
        "mirrorHost?.onHinge(angle)",
        'reason.startsWith("topology:display-changed:")',
        '"stable geometry refresh suppressed reason=$reason "',
        "const val CLOSING_TAU_S =\n            0.020f",
        '"capture-protected-or-black"',
        '"gen10-secure-guard"',
        '"Protected/uncapturable content: native display passthrough."',
        "GEN10_1_HANDOFF_GUARD",
    ]
    joined = "\n".join([build, gen3, coordinator, host, panel, mirror])
    missing = [needle for needle in required if needle not in joined]
    if missing:
        raise RuntimeError(f"Gen10.3 verification failed; missing: {missing}")

    # Renderer should be reachable exactly once from the close path plus its
    # function declaration. Gen10 intentionally reduced this to declaration-only.
    if gen3.count("ensureRenderer(") != 2:
        raise RuntimeError(
            "Gen10.3 verification failed: closing shader reachability is not exactly one call"
        )

    if "gen10-live-mirror-owned:$reason" in gen3:
        raise RuntimeError(
            "Gen10.3 verification failed: Gen10 close-animation suppression remains"
        )

    # Secure proof remains strictly before privileged live-mirror construction.
    proof_index = mirror.index("val captureProof =")
    start_index = mirror.index("ShizukuBridge.startDisplayMirrorV2(")
    if proof_index >= start_index:
        raise RuntimeError(
            "Gen10.3 verification failed: secure capture proof no longer gates live mirror"
        )

    # No secure bypass may be introduced by this candidate.
    forbidden = [
        "FLAG_SECURE bypass",
        "clear FLAG_SECURE",
        "disable FLAG_SECURE",
    ]
    for needle in forbidden:
        if needle.lower() in joined.lower():
            raise RuntimeError(f"Gen10.3 verification failed: forbidden secure behavior: {needle}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    apply(repo)
    verify(repo)
    print("Gen10.3 hybrid close animation + hinge tracking applied and verified")


if __name__ == "__main__":
    main()
