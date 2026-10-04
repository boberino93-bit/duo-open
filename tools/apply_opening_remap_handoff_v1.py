#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

GRADLE = Path("app/build.gradle.kts")
SERVICE = Path("app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt")
PANEL = Path("app/src/full/java/com/duoopen/overlay/PanelEngine.kt")
EXPORTER = Path("app/src/main/java/com/duoopen/debug/DebugBundleExporter.kt")
MARKER = "OPENING_REMAP_HANDOFF_V1"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_gradle(text: str) -> str:
    if 'versionName = "5.1.0-beta2-zfold7-s1k"' in text:
        return text
    text = one(text, "        versionCode = 44\n", "        versionCode = 45\n", "versionCode")
    return one(
        text,
        '        versionName = "5.1.0-beta2-zfold7-s1j"\n',
        '        versionName = "5.1.0-beta2-zfold7-s1k"\n',
        "versionName",
    )


def transform_service(text: str) -> str:
    if "S1K_AUTOMATIC_VISUAL_BURST_SUPPRESSED" in text:
        return text
    old = '''        VisualForensics.beginOpeningBurst(\n            context = applicationContext,\n            displayManager = displayManager,\n            scope = scope,\n            openingGeneration = continuity.generation,\n            reason = reason,\n            excludedLayers = forensicExclusions,\n        )\n'''
    new = '''        // S1K_AUTOMATIC_VISUAL_BURST_SUPPRESSED: S1J proved the ownership\n        // failure. Physical screencap calls can take hundreds of milliseconds\n        // and must not compete with behavior validation of the actual handoff.\n        DuoDiagnostics.event(\n            "opening-handoff-truth",\n            "automatic-visual-burst-suppressed generation=${continuity.generation} reason=$reason",\n        )\n'''
    return one(text, old, new, "suppress automatic visual burst")


def transform_panel(text: str) -> str:
    if MARKER in text:
        return text

    text = one(
        text,
        '''    /** Explicit CLOSED -> OPEN visual started from the device-state opening edge. */\n    private var continuityOpeningVisual = false\n''',
        '''    /** Explicit CLOSED -> OPEN visual started from the device-state opening edge. */\n    private var continuityOpeningVisual = false\n\n    // OPENING_REMAP_HANDOFF_V1: same logical display id can morph from cover\n    // geometry to inner geometry while the accepted opening is still active.\n    private var openingRemapHandoffSequence = 0L\n    private var openingRemapInnerSurfaceReady = false\n''',
        "opening remap fields",
    )

    old_owner = '''        continuityCoverOwned = owned\n\n        com.duoopen.debug.DuoDiagnostics.event(\n            "cover-render-owner",\n            "display=$displayId owned=$owned reason=$reason " +\n                "phase=$phase openingVisual=$continuityOpeningVisual",\n        )\n\n        if (!owned) {\n            if (continuityOpeningVisual) {\n                endContinuityOpeningVisual(\n                    "owner-released:$reason"\n                )\n            }\n            return\n        }\n'''
    new_owner = '''        val previousCoverOwned = continuityCoverOwned\n        continuityCoverOwned = owned\n\n        com.duoopen.debug.DuoDiagnostics.event(\n            "cover-render-owner",\n            "display=$displayId owned=$owned reason=$reason " +\n                "phase=$phase openingVisual=$continuityOpeningVisual",\n        )\n\n        if (!owned) {\n            if (continuityOpeningVisual) {\n                val transferToInner =\n                    Fold7OpeningRemapHandoffPolicy.shouldTransferToInner(\n                        openingVisualActive = continuityOpeningVisual,\n                        previousCoverOwned = previousCoverOwned,\n                        coverGeometryNow = isFold7CoverGeometryNow(),\n                        innerGeometryNow = isFold7InnerGeometryNow(),\n                        privilegedCaptureReady = ShizukuBridge.ready,\n                    )\n\n                if (transferToInner) {\n                    handoffContinuityOpeningToInner(\n                        "owner-remap:$reason"\n                    )\n                } else {\n                    endContinuityOpeningVisual(\n                        "owner-released:$reason"\n                    )\n                }\n            }\n            return\n        }\n'''
    text = one(text, old_owner, new_owner, "ownership remap transfer gate")

    helper = r'''    // OPENING_REMAP_HANDOFF_V1
    // Samsung remaps the same logical display id from cover -> inner geometry.
    // Keep the accepted opening alive across that remap, then replace the cover
    // visual with an inner-geometry snapshot as soon as a useful frame exists.
    private fun handoffContinuityOpeningToInner(
        reason: String,
    ) {
        val sequence =
            ++openingRemapHandoffSequence
        val startedUptimeMs =
            SystemClock.uptimeMillis()

        captureGen++
        stopGen5OpeningClock()
        continuityOpeningVisual = false
        innerPanel = true
        restArmed = false
        panelSwitched = false
        openingRemapInnerSurfaceReady = false

        val handoffTilt =
            openingRemapHandoffTilt()

        val bounds =
            runCatching {
                windowManager.maximumWindowMetrics.bounds
            }.getOrNull()

        val cachedInner =
            bounds?.let {
                cache.get(
                    innerPanel = true,
                    width = it.width(),
                    height = it.height(),
                )
            }

        if (cachedInner != null) {
            if (surface != null) {
                removeOverlay()
            }
            phase = Phase.CAPTURING
            present(
                bitmap = cachedInner,
                afterSwap = false,
                startTilt = handoffTilt,
                t0 = startedUptimeMs,
            )
            openingRemapInnerSurfaceReady =
                phase == Phase.SHOWING &&
                    surface is SnapshotSurface

            com.duoopen.debug.DuoDiagnostics.event(
                "opening-remap-handoff",
                "BRIDGE sequence=$sequence display=$displayId reason=$reason " +
                    "cachedInner=true tilt=$handoffTilt ready=$openingRemapInnerSurfaceReady",
            )
        }

        com.duoopen.debug.DuoDiagnostics.event(
            "opening-remap-handoff",
            "START sequence=$sequence display=$displayId reason=$reason " +
                "hinge=${hinge.lastAngle} oldSurface=${surface != null} cachedInner=${cachedInner != null}",
        )

        captureOpeningRemapInnerFrame(
            sequence = sequence,
            attempt = 1,
            reason = reason,
            startedUptimeMs = startedUptimeMs,
        )
    }

    private fun openingRemapHandoffTilt(): Float {
        val tilt = currentTilt()
        return if (tilt.isFinite()) {
            tilt.coerceAtLeast(COVER_OPEN_IMMEDIATE_TILT)
        } else {
            COVER_OPEN_IMMEDIATE_TILT
        }
    }

    private fun captureOpeningRemapInnerFrame(
        sequence: Long,
        attempt: Int,
        reason: String,
        startedUptimeMs: Long,
    ) {
        scope.launch {
            val excluded =
                excludedLayers()

            val bitmap =
                withContext(Dispatchers.IO) {
                    ShizukuBridge.capture(
                        displayId,
                        excluded,
                        INITIAL_SHELL_SCALE,
                    )
                }

            val now =
                SystemClock.uptimeMillis()
            val angle =
                hinge.lastAngle
            val stale =
                sequence != openingRemapHandoffSequence ||
                    !isFold7InnerGeometryNow() ||
                    activeCloseCycle() != null ||
                    now - startedUptimeMs > OPENING_REMAP_CAPTURE_MAX_AGE_MS ||
                    (angle.isFinite() && angle >= INNER_OPEN_LATCH_DEG)

            if (stale) {
                bitmap?.let {
                    if (!it.isRecycled) {
                        runCatching { it.recycle() }
                    }
                }
                com.duoopen.debug.DuoDiagnostics.event(
                    "opening-remap-handoff",
                    "STALE sequence=$sequence attempt=$attempt display=$displayId " +
                        "ageMs=${now - startedUptimeMs} hinge=$angle reason=$reason",
                )
                return@launch
            }

            if (bitmap == null) {
                retryOrFallbackOpeningRemap(
                    sequence = sequence,
                    attempt = attempt,
                    reason = reason,
                    startedUptimeMs = startedUptimeMs,
                    failure = "capture-null",
                )
                return@launch
            }

            val black =
                withContext(Dispatchers.Default) {
                    isMostlyBlack(bitmap)
                }

            if (black) {
                if (!bitmap.isRecycled) {
                    runCatching { bitmap.recycle() }
                }
                retryOrFallbackOpeningRemap(
                    sequence = sequence,
                    attempt = attempt,
                    reason = reason,
                    startedUptimeMs = startedUptimeMs,
                    failure = "capture-black",
                )
                return@launch
            }

            cache.put(
                true,
                bitmap,
            )

            val existingInnerSurface =
                if (openingRemapInnerSurfaceReady) {
                    surface as? SnapshotSurface
                } else {
                    null
                }

            if (
                existingInnerSurface != null &&
                phase == Phase.SHOWING
            ) {
                existingInnerSurface.replaceSnapshot(
                    bitmap
                )
                com.duoopen.debug.DuoDiagnostics.event(
                    "opening-remap-handoff",
                    "READY sequence=$sequence attempt=$attempt display=$displayId " +
                        "latencyMs=${now - startedUptimeMs} replace=true hinge=$angle reason=$reason",
                )
                return@launch
            }

            if (surface != null) {
                removeOverlay()
            }

            phase = Phase.CAPTURING
            present(
                bitmap = bitmap,
                afterSwap = false,
                startTilt = openingRemapHandoffTilt(),
                t0 = startedUptimeMs,
            )
            openingRemapInnerSurfaceReady =
                phase == Phase.SHOWING &&
                    surface is SnapshotSurface

            com.duoopen.debug.DuoDiagnostics.event(
                "opening-remap-handoff",
                "READY sequence=$sequence attempt=$attempt display=$displayId " +
                    "latencyMs=${now - startedUptimeMs} replace=false " +
                    "shown=$openingRemapInnerSurfaceReady hinge=$angle reason=$reason",
            )
        }
    }

    private fun retryOrFallbackOpeningRemap(
        sequence: Long,
        attempt: Int,
        reason: String,
        startedUptimeMs: Long,
        failure: String,
    ) {
        if (
            sequence != openingRemapHandoffSequence
        ) {
            return
        }

        if (
            attempt < OPENING_REMAP_MAX_ATTEMPTS &&
            SystemClock.uptimeMillis() - startedUptimeMs <
                OPENING_REMAP_CAPTURE_MAX_AGE_MS
        ) {
            com.duoopen.debug.DuoDiagnostics.event(
                "opening-remap-handoff",
                "RETRY sequence=$sequence attempt=$attempt display=$displayId failure=$failure reason=$reason",
            )
            handler.postDelayed(
                {
                    if (sequence == openingRemapHandoffSequence) {
                        captureOpeningRemapInnerFrame(
                            sequence = sequence,
                            attempt = attempt + 1,
                            reason = reason,
                            startedUptimeMs = startedUptimeMs,
                        )
                    }
                },
                OPENING_REMAP_RETRY_MS,
            )
            return
        }

        com.duoopen.debug.DuoDiagnostics.event(
            "opening-remap-handoff",
            "FALLBACK sequence=$sequence attempt=$attempt display=$displayId " +
                "failure=$failure ageMs=${SystemClock.uptimeMillis() - startedUptimeMs} reason=$reason",
        )

        openingRemapInnerSurfaceReady = false
        if (surface != null) {
            removeOverlay()
        }
        phase = Phase.IDLE
        restArmed = false
        panelSwitched = false
        startEffect(
            afterSwap = false,
            startTilt = openingRemapHandoffTilt(),
        )
    }

'''
    text = one(
        text,
        "    fun beginContinuityOpeningVisual(\n",
        helper + "    fun beginContinuityOpeningVisual(\n",
        "opening remap helpers",
    )

    text = one(
        text,
        '''        continuityOpeningVisual = true\n        captureGen++\n''',
        '''        openingRemapHandoffSequence++\n        openingRemapInnerSurfaceReady = false\n        continuityOpeningVisual = true\n        captureGen++\n''',
        "new opening invalidates old remap handoff",
    )

    text = one(
        text,
        '''    fun destroy() {\n        captureGen++ // orphan any capture in flight\n''',
        '''    fun destroy() {\n        openingRemapHandoffSequence++\n        openingRemapInnerSurfaceReady = false\n        captureGen++ // orphan any capture in flight\n''',
        "destroy invalidates remap handoff",
    )

    text = one(
        text,
        '''        const val COVER_OPEN_IMMEDIATE_TILT = 0.15f\n        const val GEN5_REQUESTED_HZ = 120f\n''',
        '''        const val COVER_OPEN_IMMEDIATE_TILT = 0.15f\n        const val OPENING_REMAP_MAX_ATTEMPTS = 3\n        const val OPENING_REMAP_RETRY_MS = 36L\n        const val OPENING_REMAP_CAPTURE_MAX_AGE_MS = 450L\n        const val GEN5_REQUESTED_HZ = 120f\n''',
        "opening remap constants",
    )

    return text


def transform_exporter(text: str) -> str:
    if "openingRemapHandoff=OPENING_REMAP_HANDOFF_V1" in text:
        return text
    old = '''                        appendLine(\n                            "visualShellProbePolicy=FINAL_SAMPLE_ONLY"\n                        )\n'''
    new = old + '''                        appendLine(\n                            "openingRemapHandoff=OPENING_REMAP_HANDOFF_V1"\n                        )\n                        appendLine(\n                            "automaticVisualForensics=SUPPRESSED_FOR_S1K_BEHAVIOR_VALIDATION"\n                        )\n'''
    return one(text, old, new, "export S1K identity")


def validate(g: str, f: str, p: str, e: str) -> None:
    required = (
        (g, ['versionCode = 45', 'versionName = "5.1.0-beta2-zfold7-s1k"']),
        (f, ["S1K_AUTOMATIC_VISUAL_BURST_SUPPRESSED", "automatic-visual-burst-suppressed"]),
        (p, [MARKER, "handoffContinuityOpeningToInner", "captureOpeningRemapInnerFrame", "Fold7OpeningRemapHandoffPolicy.shouldTransferToInner", "OPENING_REMAP_CAPTURE_MAX_AGE_MS", '"opening-remap-handoff"']),
        (e, ["openingRemapHandoff=OPENING_REMAP_HANDOFF_V1", "automaticVisualForensics=SUPPRESSED_FOR_S1K_BEHAVIOR_VALIDATION"]),
    )
    for text, needles in required:
        for needle in needles:
            if needle not in text:
                raise RuntimeError("missing opening remap handoff invariant: " + needle)

    if "VisualForensics.beginOpeningBurst(" in f:
        raise RuntimeError("S1K behavior validation must suppress automatic heavy visual burst")


def apply(repo: Path, check: bool) -> None:
    for path in (GRADLE, SERVICE, PANEL, EXPORTER):
        if not (repo / path).exists():
            raise RuntimeError("missing " + str(path))

    g = transform_gradle((repo / GRADLE).read_text())
    f = transform_service((repo / SERVICE).read_text())
    p = transform_panel((repo / PANEL).read_text())
    e = transform_exporter((repo / EXPORTER).read_text())
    validate(g, f, p, e)

    if not check:
        for path, text in ((GRADLE, g), (SERVICE, f), (PANEL, p), (EXPORTER, e)):
            (repo / path).write_text(text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        sample = '''        versionCode = 44\n        versionName = "5.1.0-beta2-zfold7-s1j"\n'''
        out = transform_gradle(sample)
        assert "versionCode = 45" in out
        assert "zfold7-s1k" in out
        print("opening remap handoff v1 transformer self-test: PASS")
        if not args.check:
            return 0

    apply(Path(args.repo).resolve(), args.check)
    print("opening remap handoff v1: " + ("source shape verified" if args.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
