#!/usr/bin/env python3
"""Apply Gen10.2 protected-content fail-open guard after Gen10.1.

The Gen10 live SurfaceControl mirror is only allowed to publish when the current
close cycle has a fresh, non-black continuity capture. Secure/DRM windows are
not capturable; Duo must therefore stay transparent and let Samsung/Android
render the native application instead of presenting an opaque black mirror.
"""

from __future__ import annotations

import argparse
from pathlib import Path

TARGET_VERSION_CODE = 49
TARGET_VERSION_NAME = "5.4.2-gen10-secure-fail-open-zfold7"
MARKER = "GEN10_2_SECURE_FAIL_OPEN"


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
        "versionCode = 48",
        f"versionCode = {TARGET_VERSION_CODE}",
        "versionCode",
    )
    build_text = replace_once(
        build_text,
        'versionName = "5.4.1-gen10-handoff-guard-zfold7"',
        f'versionName = "{TARGET_VERSION_NAME}"',
        "versionName",
    )
    build.write_text(build_text)

    # The exact-cycle Shizuku prime is authoritative evidence that the content
    # can safely participate in continuity. Secure content can be returned as a
    # black capture by privileged capture paths, so reject that frame before it
    # reaches the continuity frame store. beginCapture() has already cleared the
    # previous lease, ensuring a failed secure capture cannot resurrect stale
    # non-secure content.
    panel = repo / "app/src/full/java/com/duoopen/overlay/PanelEngine.kt"
    text = panel.read_text()
    text = replace_once(
        text,
        '''            if (bitmap == null) {
                continuityPrimeOwner.markFailed(
                    attempt,
                    "capture-null",
                )

                com.duoopen.debug.DuoDiagnostics.event(
                    "snapshot-transition",
                    "Gen3 continuity prime FAILED serviceEpoch=${cycle.serviceEpoch} " +
                        "closeCycle=${cycle.closeCycleId} attempt=${attempt.attemptSequence} " +
                        "latencyMs=${SystemClock.uptimeMillis() - startedUptimeMs}",
                )

                onContinuityFrameChanged(
                    "prime-failed"
                )
                return@launch
            }

            val lease =
''',
        '''            if (bitmap == null) {
                continuityPrimeOwner.markFailed(
                    attempt,
                    "capture-null",
                )

                com.duoopen.debug.DuoDiagnostics.event(
                    "snapshot-transition",
                    "Gen3 continuity prime FAILED serviceEpoch=${cycle.serviceEpoch} " +
                        "closeCycle=${cycle.closeCycleId} attempt=${attempt.attemptSequence} " +
                        "latencyMs=${SystemClock.uptimeMillis() - startedUptimeMs}",
                )

                onContinuityFrameChanged(
                    "prime-failed"
                )
                return@launch
            }

            /*
             * GEN10_2_SECURE_FAIL_OPEN
             *
             * A privileged capture of FLAG_SECURE/DRM content may be rejected
             * outright or may contain only protected black pixels. Never turn
             * such a capture into permission to construct an opaque live
             * mirror. A false positive here only disables the transition for a
             * naturally dark frame; the native application remains visible.
             */
            val continuityPrimeBlack =
                withContext(Dispatchers.Default) {
                    isMostlyBlack(bitmap)
                }

            if (continuityPrimeBlack) {
                runCatching {
                    bitmap.recycle()
                }

                continuityPrimeOwner.markFailed(
                    attempt,
                    "capture-protected-or-black",
                )

                com.duoopen.debug.DuoDiagnostics.event(
                    "gen10-secure-guard",
                    "continuity prime rejected protected/black " +
                        "serviceEpoch=${cycle.serviceEpoch} " +
                        "closeCycle=${cycle.closeCycleId} " +
                        "attempt=${attempt.attemptSequence} " +
                        "capture=${ticket.captureSequence} reason=$reason",
                )

                onContinuityFrameChanged(
                    "prime-protected-or-black"
                )
                return@launch
            }

            val lease =
''',
        "reject black exact-cycle continuity prime",
    )
    panel.write_text(text)

    mirror = repo / "app/src/full/java/com/duoopen/overlay/DisplayMirrorHost.kt"
    text = mirror.read_text()

    text = replace_once(
        text,
        '''    private var appMirror: SurfaceControl? = null
    @Volatile private var shellStopRequested = false
''',
        '''    private var appMirror: SurfaceControl? = null
    @Volatile private var shellStopRequested = false

    /*
     * GEN10_2_SECURE_FAIL_OPEN
     * Retry briefly while the exact-cycle continuity prime is still in flight.
     * During these retries the host remains transparent; protected content is
     * never covered by a speculative mirror.
     */
    private var captureProofRetryCount = 0
''',
        "capture proof retry state",
    )

    text = replace_once(
        text,
        '''        /*
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
''',
        '''        /*
         * GEN10_2_SECURE_FAIL_OPEN
         *
         * A valid SurfaceControl handle does not prove that its protected
         * layers can be rendered into our accessibility overlay. Require a
         * fresh exact-cycle capture lease before live mirroring. The frame
         * store clears its previous lease at beginCapture(), and PanelEngine
         * rejects protected/black Shizuku captures, so null here means we
         * cannot prove that publishing the mirror is safe.
         *
         * Fail OPEN visually: remove any Duo pixels and leave this transparent
         * host in place while Android renders the real application normally.
         */
        val captureProof =
            runCatching {
                frozenFrameProvider(
                    sourceWidth,
                    sourceHeight,
                )
            }.getOrNull()

        val captureProofBitmap =
            captureProof?.payload

        val captureProofValid =
            captureProofBitmap != null &&
                !captureProofBitmap.isRecycled &&
                captureProofBitmap.width == sourceWidth &&
                captureProofBitmap.height == sourceHeight

        if (!captureProofValid) {
            if (appMirror != null) {
                requestShellStop(
                    "uncapturable-content:$reason"
                )
            }
            releaseAppMirror()
            mirrorSourceKey = null
            clearFrozenFrame()

            com.duoopen.debug.DuoDiagnostics.event(
                "gen10-secure-guard",
                "live mirror withheld; native fail-open reason=$reason " +
                    "source=${source.displayId} destination=$displayId " +
                    "retry=$captureProofRetryCount",
            )

            onStatus(
                "Protected/uncapturable content: native display passthrough."
            )

            if (
                isUsable &&
                captureProofRetryCount < MAX_CAPTURE_PROOF_RETRIES
            ) {
                captureProofRetryCount++
                hostView.postDelayed(
                    {
                        if (isUsable) {
                            refresh(
                                "capture-proof-retry:$reason"
                            )
                        }
                    },
                    CAPTURE_PROOF_RETRY_MS,
                )
            }
            return
        }

        captureProofRetryCount = 0

        /*
         * Gen10 invariant: once capturability is proven, live application
         * content remains authoritative during the normal close. The bitmap is
         * retained only as a failure fallback and is not displayed here.
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
            clearFrozenFrame()
        }

        val current = appMirror
''',
        "live mirror capture proof gate",
    )

    text = replace_once(
        text,
        '''        const val INNER_WIDTH = 1968
        const val INNER_HEIGHT = 2184
''',
        '''        const val INNER_WIDTH = 1968
        const val INNER_HEIGHT = 2184
        const val MAX_CAPTURE_PROOF_RETRIES = 8
        const val CAPTURE_PROOF_RETRY_MS = 25L
''',
        "capture proof retry constants",
    )

    mirror.write_text(text)


def verify(repo: Path) -> None:
    build_text = (repo / "app/build.gradle.kts").read_text()
    panel_text = (repo / "app/src/full/java/com/duoopen/overlay/PanelEngine.kt").read_text()
    mirror_text = (repo / "app/src/full/java/com/duoopen/overlay/DisplayMirrorHost.kt").read_text()

    required = [
        f"versionCode = {TARGET_VERSION_CODE}",
        f'versionName = "{TARGET_VERSION_NAME}"',
        MARKER,
        '"capture-protected-or-black"',
        '"gen10-secure-guard"',
        "val captureProof =",
        "if (!captureProofValid)",
        '"Protected/uncapturable content: native display passthrough."',
        "MAX_CAPTURE_PROOF_RETRIES = 8",
        "CAPTURE_PROOF_RETRY_MS = 25L",
    ]
    joined = build_text + "\n" + panel_text + "\n" + mirror_text
    missing = [needle for needle in required if needle not in joined]
    if missing:
        raise RuntimeError(f"Gen10.2 verification failed; missing: {missing}")

    if joined.count(MARKER) < 2:
        raise RuntimeError("Gen10.2 verification failed: secure fail-open markers incomplete")

    # The live mirror must not be started before the capture proof gate.
    proof_index = mirror_text.index("val captureProof =")
    start_index = mirror_text.index("ShizukuBridge.startDisplayMirrorV2(")
    if proof_index >= start_index:
        raise RuntimeError("Gen10.2 verification failed: mirror starts before capture proof")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    apply(repo)
    verify(repo)
    print("Gen10.2 secure-content fail-open guard applied and verified")


if __name__ == "__main__":
    main()
