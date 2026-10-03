#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

BASE_HEAD = "41c6f20c817226b233eb4cbfb402e879c5e3e3ea"
TARGET_VERSION_CODE = 43
TARGET_VERSION_NAME = "5.1.0-beta2-zfold7"
MARKER = "GEN7_RUNTIME_REGRESSION_BETA2"

EXPECTED_BLOBS = {
    "app/build.gradle.kts": "f11b8c5a15a67f2e7cad874db66d943c768fdce8",
    "app/src/full/java/com/duoopen/overlay/Fold7ContinuityController.kt": "23cfa0cc9802c2921d56190bf0abbf4478c1547b",
    "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt": "cfab7a1e6d4dc7cfca6126a8bf8231c77e952895",
    "app/src/full/java/com/duoopen/overlay/PanelEngine.kt": "866d21ed1bd3fecfc25fffdcd3633489db9a80d9",
    "app/src/full/java/com/duoopen/overlay/Fold7CoverVisualHost.kt": "852c07f5b7ed7012e4ddccbbf984ee84db221455",
    "app/src/full/java/com/duoopen/overlay/Fold7Gen3VisualCoordinator.kt": "0b5782eeab938f0f17480d04e68d716d270ec3c9",
    "app/src/full/java/com/duoopen/overlay/Fold7RightPaneComposer.kt": "fdd836b90f5d83fe07dcd0153211671ccc28d893",
    "app/src/full/java/com/duoopen/overlay/FoldOverlayView.kt": "61d6adc47a0177363969aeec04708fdcbca30662",
    "app/src/full/java/com/duoopen/overlay/SnapshotCache.kt": "4b1b6bb9837de4fb77cdc1bdc26f4a39aa72ab26",
    "app/src/full/java/com/duoopen/shell/ShizukuBridge.kt": "d276f950eb279b3af281b9930dda7a8e8c3fd6a1",
    "app/src/full/java/com/duoopen/shell/ShellProtocol.kt": "a1f505fcff77fe4fad7c13a8f9be73e546746352",
    "app/src/full/java/com/duoopen/shell/DuoShellService.kt": "e19469eebaa967cbce10f5bcf85eef795e1d6b7d",
    "app/src/main/java/com/duoopen/fold/Fold7VirtualHingeGen5.kt": "fe44ee237198b467033f5dec33be8c0904a1076b",
    "app/src/test/java/com/duoopen/fold/Fold7VirtualHingeGen5Test.kt": "7728a57e210dce4be876363277c15fbac3385a36",
    "app/src/test/java/com/duoopen/overlay/Fold7ContinuityControllerTest.kt": "287a4e52146307ac2e6c349f99ecbd2711423a92",
}

NEW_FILES = {
    "app/src/full/java/com/duoopen/overlay/Fold7CoverPresentationPolicy.kt": "Fold7CoverPresentationPolicy.kt",
    "app/src/full/java/com/duoopen/overlay/Fold7DisplayTransform.kt": "Fold7DisplayTransform.kt",
    "app/src/test/java/com/duoopen/overlay/Fold7CoverPresentationPolicyTest.kt": "Fold7CoverPresentationPolicyTest.kt",
    "app/src/test/java/com/duoopen/overlay/Fold7DisplayTransformTest.kt": "Fold7DisplayTransformTest.kt",
}


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one literal match, found {count}")
    return text.replace(old, new, 1)


def replace_regex_once(text: str, pattern: str, replacement: str, label: str, flags=re.S) -> str:
    out, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one regex match, found {count}")
    return out


def guard(repo: Path, rel: str) -> None:
    p = repo / rel
    if not p.exists():
        raise RuntimeError(f"missing baseline file: {rel}")
    data = p.read_bytes()
    actual = git_blob_sha(data)
    expected = EXPECTED_BLOBS[rel]
    if actual != expected:
        text = data.decode("utf-8", errors="ignore")
        if MARKER in text or TARGET_VERSION_NAME in text:
            return
        if (
            rel == "app/src/full/java/com/duoopen/shell/ShizukuBridge.kt" and
            all(
                marker in text
                for marker in (
                    "object Binding : State",
                    "class BindFailed",
                    "BIND_TIMEOUT_MS = 8_000L",
                    "fun retryBind()",
                )
            )
        ):
            # The prior Shizuku/onboarding pack is a required predecessor for
            # test APKs. Its own exact-blob patcher already proved the baseline.
            return
        raise RuntimeError(
            f"baseline drift for {rel}: expected git blob {expected}, got {actual}. "
            "Refuse to patch a different source tree."
        )


def transform_build_gradle(text: str) -> str:
    if TARGET_VERSION_NAME in text:
        return text
    text = replace_once(text, "versionCode = 42", f"versionCode = {TARGET_VERSION_CODE}", "versionCode")
    text = replace_once(
        text,
        'versionName = "5.0.0-beta1-zfold7"',
        f'versionName = "{TARGET_VERSION_NAME}"',
        "versionName",
    )
    return text


def transform_controller(text: str) -> str:
    if "device-state-opening-edge-recovered" not in text:
        replacement = r'''fun onEarlyOpeningEdge(
        nowMs: Long,
        topology: Topology,
    ): Decision {
        val angle =
            lastAngle
                .takeIf { it.isFinite() }
                ?: 0f

        /* GEN7_RUNTIME_REGRESSION_BETA2
         *
         * Field evidence showed DeviceState's folded -> unfolded edge arriving
         * while the semantic controller was still COVER_PREWARMING/COVER_VISUAL.
         * The old state==NATIVE_COVER precondition dropped that real opening
         * edge, leaving physical inner wake to wait until a coarse 90-degree
         * public sample.
         *
         * Recovery is still closed-endpoint constrained: we require cover-only
         * topology and <=12-degree precise geometry. DeviceState never becomes
         * visual geometry; it only starts infrastructure wake/release work.
         */
        val closedEndpointEvidence =
            topology.coverActive &&
                !topology.innerActive &&
                (
                    topology.nativeCover ||
                        angle <= NATIVE_COVER_MAX_DEG
                    )

        val recoverableState =
            state in setOf(
                State.NATIVE_COVER,
                State.COVER_PREWARMING,
                State.COVER_READY_HIDDEN,
                State.COVER_VISUAL,
            )

        if (!recoverableState || !closedEndpointEvidence) {
            return decision()
        }

        val wasNativeCover =
            state == State.NATIVE_COVER

        val wasVisual =
            state == State.COVER_VISUAL

        val hadSecondary =
            state in SECONDARY_STATES

        direction =
            Direction.OPENING

        lastSampleMs =
            nowMs

        transition(
            to = State.OPENING_FROM_CLOSED,
            angle = angle,
            reason =
                if (wasNativeCover) {
                    "device-state-opening-edge"
                } else {
                    "device-state-opening-edge-recovered"
                },
            topology = topology,
        )

        activePrewarmGeneration = -1L
        resetIntent()

        val actions =
            mutableListOf<Action>()

        if (wasVisual) {
            actions += Action.HideMirror(generation)
        }

        if (hadSecondary) {
            actions += Action.ReleaseSecondary(generation)
        }

        actions += Action.WakeInner(generation)

        return decision(actions)
    }

    fun onPrewarmResult('''
        text = replace_regex_once(
            text,
            r"fun onEarlyOpeningEdge\(.*?\n    fun onPrewarmResult\(",
            replacement,
            "onEarlyOpeningEdge",
        )
    text = text.replace("const val COVER_PREWARM_DEG = 174f", "const val COVER_PREWARM_DEG = 175f")
    return text


def transform_virtual_hinge(text: str) -> str:
    if "AWAIT_PRECISE" not in text:
        text = replace_once(
            text,
            "        IDLE,\n        BLIND_BOOTSTRAP,",
            "        IDLE,\n        AWAIT_PRECISE,\n        BLIND_BOOTSTRAP,",
            "virtual hinge mode",
        )
        old = r'''        if (latest == null) {
            val elapsedNs = (callbackTimeNs - openingStartedNs).coerceAtLeast(0L)
            val elapsedSec = elapsedNs / 1_000_000_000.0
            val blind =
                (initialAngle + BLIND_VELOCITY_DPS * elapsedSec)
                    .toFloat()
                    .coerceAtMost(BLIND_MAX_ANGLE_DEG)
            val confidence =
                (BLIND_INITIAL_CONFIDENCE -
                    (elapsedNs / 1_000_000_000.0 * BLIND_CONFIDENCE_DECAY_PER_SEC))
                    .toFloat()
                    .coerceIn(BLIND_MIN_CONFIDENCE, BLIND_INITIAL_CONFIDENCE)
            return RawTarget(blind, confidence, Mode.BLIND_BOOTSTRAP, 0L)
        }'''
        new = r'''        if (latest == null) {
            /* GEN7_RUNTIME_REGRESSION_BETA2
             * Never manufacture opening geometry before a measured sample.
             * The field bundle captured physical=90 while the old blind clock
             * independently swept 13 -> 92 degrees, producing the corrupted
             * first-open animation. Hold the closed seed until real geometry
             * arrives; infrastructure wake may still happen independently.
             */
            return RawTarget(
                desired = initialAngle,
                confidence = 0f,
                mode = Mode.AWAIT_PRECISE,
                leadNs = 0L,
            )
        }'''
        text = replace_once(text, old, new, "blind bootstrap")
    return text


def transform_virtual_hinge_test(text: str) -> str:
    if "awaitPreciseDoesNotInventGeometry" not in text:
        text = replace_regex_once(
            text,
            r'''    @Test\n    fun blindBootstrapMovesButCannotRunPastGlassPeak\(\) \{.*?\n    \}\n''',
            '''    @Test\n    fun awaitPreciseDoesNotInventGeometry() {\n        val v = Fold7VirtualHingeGen5()\n        v.startOpening(0L)\n        val early = v.targetForFrame(100_000_000L, 116_666_667L)\n        val late = v.targetForFrame(700_000_000L, 716_666_667L)\n        assertEquals(Fold7VirtualHingeGen5.Mode.AWAIT_PRECISE, early.mode)\n        assertEquals(Fold7VirtualHingeGen5.CLOSED_SEED_DEG, early.angleDegrees)\n        assertEquals(Fold7VirtualHingeGen5.CLOSED_SEED_DEG, late.angleDegrees)\n    }\n''',
            "virtual hinge test",
        )
    return text



def transform_continuity_controller_test(text: str) -> str:
    if "GEN7_RUNTIME_REGRESSION_BETA2_175_PREWARM_TEST" in text:
        return text

    old = r'''    @Test
    fun deliberateClosePrewarmsEarlyButStaysHiddenUntil135() {
        val c = Fold7ContinuityController()
        c.reset(179f, 0L, openTopology)

        c.onHinge(177.8f, 100L, openTopology)
        c.onHinge(176.3f, 150L, openTopology)
        c.onHinge(174.8f, 200L, openTopology)

        assertEquals(
            Fold7ContinuityController.State.CLOSING_INTENT,
            c.state,
        )

        val prewarm =
            c.onHinge(
                173.8f,
                220L,
                openTopology,
            )

        val request =
            prewarm.actions.single()
                as Fold7ContinuityController.Action.BeginPrewarm
'''
    new = r'''    @Test
    fun deliberateClosePrewarmsAt175ButStaysHiddenUntil135() {
        val c = Fold7ContinuityController()
        c.reset(179f, 0L, openTopology)

        c.onHinge(177.8f, 100L, openTopology)
        c.onHinge(176.3f, 150L, openTopology)

        // GEN7_RUNTIME_REGRESSION_BETA2_175_PREWARM_TEST
        // The cover presentation policy now wakes/prewarms at 175 degrees.
        // The third deliberate-close sample crosses both the intent and
        // prewarm thresholds, so the controller intentionally takes the
        // fast-close path directly into COVER_PREWARMING.
        val prewarm =
            c.onHinge(
                174.8f,
                200L,
                openTopology,
            )

        assertEquals(
            Fold7ContinuityController.State.COVER_PREWARMING,
            c.state,
        )

        val request =
            prewarm.actions.single()
                as Fold7ContinuityController.Action.BeginPrewarm
'''
    return replace_once(
        text,
        old,
        new,
        "175-degree prewarm unit test alignment",
    )


def transform_right_pane_composer(text: str) -> str:
    if "Fold7DisplayTransform.canonicalRightPaneCrop" in text:
        return text
    return '''package com.duoopen.overlay

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Rect

/**
 * Rotation-aware canonical physical-right-pane composer for Fold7.
 * Supports both native and scaled live captures.
 */
internal object Fold7RightPaneComposer {
    const val RIGHT_PANE_LEFT = Fold7DisplayTransform.RIGHT_PANE_LEFT
    const val RIGHT_PANE_RIGHT = Fold7DisplayTransform.RIGHT_PANE_RIGHT
    const val INNER_WIDTH = Fold7DisplayTransform.INNER_WIDTH
    const val INNER_HEIGHT = Fold7DisplayTransform.INNER_HEIGHT
    const val COVER_WIDTH = Fold7DisplayTransform.COVER_WIDTH
    const val COVER_HEIGHT = Fold7DisplayTransform.COVER_HEIGHT

    fun fromInner(
        source: Bitmap,
        rotation: Int = Fold7DisplayTransform.ROTATION_0,
    ): Bitmap? {
        val crop =
            Fold7DisplayTransform.canonicalRightPaneCrop(
                rotation = rotation,
                sourceWidth = source.width,
                sourceHeight = source.height,
            ) ?: return null

        val output =
            Fold7DisplayTransform.coverOutputSize(rotation)

        val result = Bitmap.createBitmap(
            output.width,
            output.height,
            Bitmap.Config.ARGB_8888,
        )

        val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)

        Canvas(result).drawBitmap(
            source,
            Rect(crop.left, crop.top, crop.right, crop.bottom),
            Rect(0, 0, output.width, output.height),
            paint,
        )

        return result
    }
}
'''


def transform_snapshot_cache(text: str) -> str:
    if "data class Key" in text:
        return text
    return '''package com.duoopen.overlay

import android.graphics.Bitmap
import android.os.SystemClock

/**
 * Recent snapshots keyed by panel kind and orientation-sized geometry.
 * Portrait and landscape frames may coexist; one can never stretch into the
 * other merely because the phone rotated mid-transition.
 */
class SnapshotCache(private val maxAgeMs: Long) {
    private data class Key(
        val innerPanel: Boolean,
        val width: Int,
        val height: Int,
    )

    private class Entry(
        val bitmap: Bitmap,
        val at: Long,
    )

    private val entries = HashMap<Key, Entry>()

    fun put(innerPanel: Boolean, bitmap: Bitmap) {
        entries[
            Key(
                innerPanel = innerPanel,
                width = bitmap.width,
                height = bitmap.height,
            )
        ] = Entry(bitmap, SystemClock.uptimeMillis())
    }

    fun get(innerPanel: Boolean, width: Int, height: Int): Bitmap? {
        val e = entries[Key(innerPanel, width, height)] ?: return null
        val b = e.bitmap
        if (b.isRecycled) return null
        if (SystemClock.uptimeMillis() - e.at > maxAgeMs) return null
        return b
    }

    fun ageMs(innerPanel: Boolean): Long? =
        entries
            .filterKeys { it.innerPanel == innerPanel }
            .values
            .maxByOrNull { it.at }
            ?.let { SystemClock.uptimeMillis() - it.at }
}
'''


def transform_overlay_view(text: str) -> str:
    if "centerCropMatrix" in text:
        return text
    text = replace_once(
        text,
        "import kotlin.math.ceil",
        "import kotlin.math.ceil\nimport kotlin.math.max",
        "overlay max import",
    )
    text = replace_once(
        text,
        '''        override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
            matrix.setScale(w / snapshot.width.toFloat(), h / snapshot.height.toFloat())
            shader.setLocalMatrix(matrix)
            paint.shader = shader
        }''',
        '''        override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
            centerCropMatrix(
                matrix = matrix,
                sourceWidth = snapshot.width,
                sourceHeight = snapshot.height,
                destinationWidth = w,
                destinationHeight = h,
            )
            shader.setLocalMatrix(matrix)
            paint.shader = shader
        }''',
        "flat center crop",
    )
    text = replace_once(
        text,
        '''        override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
            matrix.setScale(w / snapshot.width.toFloat(), h / snapshot.height.toFloat())
            image.setLocalMatrix(matrix)
        }''',
        '''        override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
            centerCropMatrix(
                matrix = matrix,
                sourceWidth = snapshot.width,
                sourceHeight = snapshot.height,
                destinationWidth = w,
                destinationHeight = h,
            )
            image.setLocalMatrix(matrix)
        }''',
        "fold center crop",
    )
    insert = '''

    private companion object {
        fun centerCropMatrix(
            matrix: Matrix,
            sourceWidth: Int,
            sourceHeight: Int,
            destinationWidth: Int,
            destinationHeight: Int,
        ) {
            if (
                sourceWidth <= 0 || sourceHeight <= 0 ||
                destinationWidth <= 0 || destinationHeight <= 0
            ) {
                matrix.reset()
                return
            }

            val scale =
                max(
                    destinationWidth / sourceWidth.toFloat(),
                    destinationHeight / sourceHeight.toFloat(),
                )

            val dx =
                (destinationWidth - sourceWidth * scale) * 0.5f

            val dy =
                (destinationHeight - sourceHeight * scale) * 0.5f

            matrix.setScale(scale, scale)
            matrix.postTranslate(dx, dy)
        }
    }
'''
    idx = text.rfind("}\n")
    if idx < 0:
        raise RuntimeError("overlay view: class closing brace not found")
    text = text[:idx] + insert + text[idx:]
    return text


def transform_panel_engine(text: str) -> str:
    if "live recapture enabled on Fold7" not in text:
        old = '''        if (
            bitmap != null &&
            shellCapture()
        ) {
            if (
                deterministicFrozenFrameMode()
            ) {
                com.duoopen.debug.DuoDiagnostics.event(
                    "snapshot-transition",
                    "frozen frame display=$displayId inner=$innerPanel " +
                        "size=${bitmap.width}x${bitmap.height}; live recapture suppressed",
                )
            } else {
                startLiveLoop()
            }
        }'''
        new = '''        if (
            bitmap != null &&
            shellCapture()
        ) {
            /* GEN7_RUNTIME_REGRESSION_BETA2
             * Freeze transition authority, not application pixels. Field
             * bundles proved the old Fold7 branch emitted "live recapture
             * suppressed" while timers/video/hinge diagnostics visibly froze.
             */
            startLiveLoop()

            if (deterministicFrozenFrameMode()) {
                com.duoopen.debug.DuoDiagnostics.event(
                    "snapshot-transition",
                    "live recapture enabled on Fold7 display=$displayId " +
                        "inner=$innerPanel size=${bitmap.width}x${bitmap.height}",
                )
            }
        }'''
        text = replace_once(text, old, new, "panel live recapture")

    if "Fold7DisplayTransform.innerCaptureSize" not in text:
        old = '''        val cachedInner =
            cache.get(
                innerPanel = true,
                width = Fold7RightPaneComposer.INNER_WIDTH,
                height = Fold7RightPaneComposer.INNER_HEIGHT,
            )
        val canonicalRight =
            cachedInner?.let(Fold7RightPaneComposer::fromInner)'''
        new = '''        val openingRotation =
            display.rotation

        val innerSize =
            Fold7DisplayTransform.innerCaptureSize(
                openingRotation
            )

        val cachedInner =
            cache.get(
                innerPanel = true,
                width = innerSize.width,
                height = innerSize.height,
            )

        val canonicalRight =
            cachedInner?.let {
                Fold7RightPaneComposer.fromInner(
                    source = it,
                    rotation = openingRotation,
                )
            }'''
        text = replace_once(text, old, new, "opening rotation-aware cache")

    if "fun captureExclusionLayers()" not in text:
        marker = """    fun isFold7CoverGeometryNow(): Boolean {"""
        accessor = """    /**
     * Source-layer exclusion for cross-display live continuity capture.
     * Resolve on the service/main thread; the returned SurfaceControl handles
     * are then parcelled to the Shizuku shell capture path.
     */
    fun captureExclusionLayers(): List<SurfaceControl> =
        excludedLayers()

"""
        text = replace_once(
            text,
            marker,
            accessor + marker,
            "panel capture exclusion accessor",
        )

    if "Fold7DisplayTransform.foldFor" not in text:
        old = '''        val foldLine = { w: Float, h: Float, c: com.duoopen.settings.DuoConfig -> DuoShader.foldFor(inner, w, h, c) }'''
        new = '''        val foldLine = { w: Float, h: Float, c: com.duoopen.settings.DuoConfig ->
            if (deterministicFrozenFrameMode()) {
                Fold7DisplayTransform.foldFor(
                    innerPanel = inner,
                    rotation = display.rotation,
                    width = w,
                    height = h,
                    config = c,
                )
            } else {
                DuoShader.foldFor(inner, w, h, c)
            }
        }'''
        text = replace_once(text, old, new, "panel fold transform")
    return text


def transform_cover_visual_host(text: str) -> str:
    if "startLiveClosingLoop" in text:
        return text

    text = replace_once(
        text,
        "import android.view.Display\nimport android.view.WindowManager",
        "import android.view.Display\nimport android.hardware.display.DisplayManager\nimport android.os.Handler\nimport android.view.SurfaceControl\nimport android.view.WindowManager\nimport com.duoopen.debug.DuoDiagnostics\nimport com.duoopen.shell.ShizukuBridge\nimport kotlinx.coroutines.CoroutineScope\nimport kotlinx.coroutines.Dispatchers\nimport kotlinx.coroutines.launch",
        "cover host imports",
    )

    text = replace_once(
        text,
        '''    private val service: AccessibilityService,
    val display: Display,''',
        '''    private val service: AccessibilityService,
    private val handler: Handler,
    private val scope: CoroutineScope,
    private val innerCaptureExclusions: () -> List<SurfaceControl>,
    val display: Display,''',
        "cover host constructor",
    )

    text = replace_once(
        text,
        '''    private var ownedCoverBitmap:
        Bitmap? =
        null''',
        '''    private var ownedCoverBitmap:
        Bitmap? =
        null

    private val displayManager =
        service.getSystemService(DisplayManager::class.java)

    @Volatile
    private var liveClosingLoop = false

    private var liveClosingFrames = 0L''',
        "cover host live fields",
    )

    text = replace_regex_once(
        text,
        r'''                Fold7CoverVisualAttemptOwner.Direction.CLOSING -> \{.*?\n                \}\n\n                Fold7CoverVisualAttemptOwner.Direction.OPENING ->''',
        '''                Fold7CoverVisualAttemptOwner.Direction.CLOSING -> {
                    val source =
                        frozenFrame?.payload
                            ?: return false

                    val coverBitmap =
                        Fold7RightPaneComposer.fromInner(
                            source = source,
                            rotation = display.rotation,
                        ) ?: return false

                    ownedCoverBitmap =
                        coverBitmap

                    SnapshotSurface(
                        context = windowContext,
                        windowManager = windowManager,
                        bitmap = coverBitmap,
                        config = config,
                        foldLine = { w, h, c ->
                            Fold7DisplayTransform.coverFold(
                                rotation = display.rotation,
                                width = w,
                                height = h,
                                config = c,
                            )
                        },
                    ).takeIf {
                        it.attached
                    }
                }

                Fold7CoverVisualAttemptOwner.Direction.OPENING ->''',
        "cover host closing surface",
    )

    # Make the opening fold line rotation-aware too.
    text = text.replace(
        "foldLine =\n                                DuoShader::coverFold,",
        '''foldLine = { w, h, c ->
                                Fold7DisplayTransform.coverFold(
                                    rotation = display.rotation,
                                    width = w,
                                    height = h,
                                    config = c,
                                )
                            },''',
    )

    text = replace_once(
        text,
        '''        (
            created as?
                SnapshotSurface
            )?.view''',
        '''        if (
            direction ==
                Fold7CoverVisualAttemptOwner.Direction.CLOSING
        ) {
            startLiveClosingLoop()
        }

        (
            created as?
                SnapshotSurface
            )?.view''',
        "start cover live loop",
    )

    text = replace_once(
        text,
        '''    fun detach() {
        follower?.cancel()''',
        '''    fun detach() {
        liveClosingLoop = false
        follower?.cancel()''',
        "stop cover live loop",
    )

    marker = '''    private fun initialTilt(
'''
    live_method = r'''    private fun startLiveClosingLoop() {
        if (
            liveClosingLoop ||
            direction !=
                Fold7CoverVisualAttemptOwner.Direction.CLOSING ||
            !ShizukuBridge.ready
        ) {
            return
        }

        liveClosingLoop = true

        fun scheduleNext(delayMs: Long) {
            if (liveClosingLoop) {
                handler.postDelayed(
                    { tick() },
                    delayMs,
                )
            }
        }

        fun replaceFrame(
            bitmap: Bitmap,
        ) {
            if (!liveClosingLoop) {
                if (!bitmap.isRecycled) bitmap.recycle()
                return
            }

            val snapshot =
                surface as?
                    SnapshotSurface

            if (snapshot == null) {
                if (!bitmap.isRecycled) bitmap.recycle()
                return
            }

            val old =
                ownedCoverBitmap

            ownedCoverBitmap =
                bitmap

            snapshot.replaceSnapshot(
                bitmap
            )

            if (
                old != null &&
                old !== bitmap &&
                !old.isRecycled
            ) {
                runCatching {
                    old.recycle()
                }
            }
        }

        fun tick() {
            if (!liveClosingLoop) return

            val inner =
                displayManager.displays
                    .firstOrNull { candidate ->
                        if (
                            candidate.state ==
                                Display.STATE_OFF
                        ) {
                            return@firstOrNull false
                        }

                        val mode =
                            runCatching {
                                candidate.mode
                            }.getOrNull()
                                ?: return@firstOrNull false

                        mode.physicalWidth ==
                            Fold7DisplayTransform.INNER_WIDTH &&
                            mode.physicalHeight ==
                            Fold7DisplayTransform.INNER_HEIGHT
                    }

            if (
                inner == null ||
                !ShizukuBridge.ready
            ) {
                scheduleNext(LIVE_RETRY_MS)
                return
            }

            val frameStarted =
                android.os.SystemClock.uptimeMillis()

            scope.launch(Dispatchers.IO) {
                val captured =
                    ShizukuBridge.capture(
                        displayId = inner.displayId,
                        excluded = emptyList(),
                        scale = LIVE_CAPTURE_SCALE,
                    )

                val composed =
                    captured?.let {
                        Fold7RightPaneComposer.fromInner(
                            source = it,
                            rotation = inner.rotation,
                        )
                    }

                if (
                    captured != null &&
                    captured !== composed &&
                    !captured.isRecycled
                ) {
                    runCatching {
                        captured.recycle()
                    }
                }

                handler.post {
                    if (
                        liveClosingLoop &&
                        composed != null
                    ) {
                        replaceFrame(composed)
                        liveClosingFrames++

                        if (
                            liveClosingFrames == 1L ||
                            liveClosingFrames % 20L == 0L
                        ) {
                            DuoDiagnostics.event(
                                "gen3-live-content",
                                "closing frame=$liveClosingFrames " +
                                    "rotation=${inner.rotation} " +
                                    "size=${composed.width}x${composed.height}",
                            )
                        }
                    } else if (
                        composed != null &&
                        !composed.isRecycled
                    ) {
                        runCatching {
                            composed.recycle()
                        }
                    }

                    val elapsed =
                        android.os.SystemClock.uptimeMillis() -
                            frameStarted

                    scheduleNext(
                        (LIVE_FRAME_PERIOD_MS - elapsed)
                            .coerceAtLeast(0L)
                    )
                }
            }
        }

        handler.post {
            tick()
        }
    }

'''
    # Kotlin local function forward references are not allowed. Replace with object Runnable implementation instead below.
    # We install a corrected version after this placeholder construction.
    live_method = r'''    private fun startLiveClosingLoop() {
        if (
            liveClosingLoop ||
            direction !=
                Fold7CoverVisualAttemptOwner.Direction.CLOSING ||
            !ShizukuBridge.ready
        ) {
            return
        }

        liveClosingLoop = true

        val runner =
            object : Runnable {
                override fun run() {
                    if (!liveClosingLoop) return

                    val inner =
                        displayManager.displays
                            .firstOrNull { candidate ->
                                if (
                                    candidate.state ==
                                        Display.STATE_OFF
                                ) {
                                    return@firstOrNull false
                                }

                                val mode =
                                    runCatching {
                                        candidate.mode
                                    }.getOrNull()
                                        ?: return@firstOrNull false

                                mode.physicalWidth ==
                                    Fold7DisplayTransform.INNER_WIDTH &&
                                    mode.physicalHeight ==
                                    Fold7DisplayTransform.INNER_HEIGHT
                            }

                    if (
                        inner == null ||
                        !ShizukuBridge.ready
                    ) {
                        handler.postDelayed(
                            this,
                            LIVE_RETRY_MS,
                        )
                        return
                    }

                    val frameStarted =
                        android.os.SystemClock.uptimeMillis()

                    val nextRun = this

                    /*
                     * Resolve the source overlay layer on main before crossing
                     * into shell capture. Without this exclusion the cover can
                     * recursively capture Duo Open's inner fold overlay and
                     * apply the effect twice to changing content.
                     */
                    val exclusions =
                        runCatching {
                            innerCaptureExclusions()
                        }.getOrDefault(
                            emptyList()
                        )

                    scope.launch(Dispatchers.IO) {
                        val captured =
                            ShizukuBridge.capture(
                                displayId = inner.displayId,
                                excluded = exclusions,
                                scale = LIVE_CAPTURE_SCALE,
                            )

                        val composed =
                            captured?.let {
                                Fold7RightPaneComposer.fromInner(
                                    source = it,
                                    rotation = inner.rotation,
                                )
                            }

                        if (
                            captured != null &&
                            captured !== composed &&
                            !captured.isRecycled
                        ) {
                            runCatching {
                                captured.recycle()
                            }
                        }

                        handler.post {
                            if (
                                liveClosingLoop &&
                                composed != null
                            ) {
                                val snapshot =
                                    surface as?
                                        SnapshotSurface

                                if (snapshot != null) {
                                    val old =
                                        ownedCoverBitmap

                                    ownedCoverBitmap =
                                        composed

                                    snapshot.replaceSnapshot(
                                        composed
                                    )

                                    if (
                                        old != null &&
                                        old !== composed &&
                                        !old.isRecycled
                                    ) {
                                        runCatching {
                                            old.recycle()
                                        }
                                    }

                                    liveClosingFrames++

                                    if (
                                        liveClosingFrames == 1L ||
                                        liveClosingFrames % 20L == 0L
                                    ) {
                                        DuoDiagnostics.event(
                                            "gen3-live-content",
                                            "closing frame=$liveClosingFrames " +
                                                "rotation=${inner.rotation} " +
                                                "size=${composed.width}x${composed.height}",
                                        )
                                    }
                                } else if (!composed.isRecycled) {
                                    runCatching {
                                        composed.recycle()
                                    }
                                }
                            } else if (
                                composed != null &&
                                !composed.isRecycled
                            ) {
                                runCatching {
                                    composed.recycle()
                                }
                            }

                            if (liveClosingLoop) {
                                val elapsed =
                                    android.os.SystemClock.uptimeMillis() -
                                        frameStarted

                                handler.postDelayed(
                                    nextRun,
                                    (LIVE_FRAME_PERIOD_MS - elapsed)
                                        .coerceAtLeast(0L),
                                )
                            }
                        }
                    }
                }
            }

        handler.post(
            runner
        )
    }

'''
    text = replace_once(text, marker, live_method + marker, "cover live method")

    # Replace old local composer with a wrapper so call sites stay compile-safe if any remain.
    text = replace_regex_once(
        text,
        r'''    private fun buildCanonicalRightPane\(\n        source: Bitmap,\n    \): Bitmap\? \{.*?\n    \}\n\n    private fun recycleOwnedBitmap''',
        '''    private fun buildCanonicalRightPane(
        source: Bitmap,
    ): Bitmap? =
        Fold7RightPaneComposer.fromInner(
            source = source,
            rotation = display.rotation,
        )

    private fun recycleOwnedBitmap''',
        "cover composer wrapper",
    )

    text = replace_once(
        text,
        '''        const val CLOSING_TAU_S =
            0.028f''',
        '''        const val CLOSING_TAU_S =
            0.028f

        const val LIVE_CAPTURE_SCALE =
            0.55f

        const val LIVE_FRAME_PERIOD_MS =
            48L

        const val LIVE_RETRY_MS =
            80L''',
        "cover live constants",
    )
    return text


def transform_gen3_visual(text: str) -> str:
    # Beta2 live-content capture runs coroutines from the visual host. The
    # coordinator must receive the service-owned CoroutineScope explicitly;
    # creating an independent scope here would outlive accessibility teardown.
    if "private val scope: kotlinx.coroutines.CoroutineScope" not in text:
        text = replace_once(
            text,
            """    private val currentHingeAngle: () -> Float,
""",
            """    private val currentHingeAngle: () -> Float,
    private val scope: kotlinx.coroutines.CoroutineScope,
""",
            "gen3 coroutine scope dependency",
        )

    if "innerCaptureExclusions: () -> List<android.view.SurfaceControl>" not in text:
        text = replace_once(
            text,
            """    private val scope: kotlinx.coroutines.CoroutineScope,
) {""",
            """    private val scope: kotlinx.coroutines.CoroutineScope,
    private val innerCaptureExclusions: () -> List<android.view.SurfaceControl>,
) {""",
            "gen3 exclusion provider",
        )

    if "handler =\n                    handler" not in text:
        text = replace_once(
            text,
            """            Fold7CoverVisualHost(
                service =
                    service,
                display =""",
            """            Fold7CoverVisualHost(
                service =
                    service,
                handler =
                    handler,
                scope =
                    scope,
                innerCaptureExclusions =
                    innerCaptureExclusions,
                display =""",
            "gen3 host args",
        )
    return text

def transform_coordinator(text: str) -> str:
    if "val direction: Fold7ContinuityController.Direction" not in text:
        text = replace_once(
            text,
            '''    val generation: Long
        get() = controller.generation''',
            '''    val generation: Long
        get() = controller.generation

    val direction: Fold7ContinuityController.Direction
        get() = controller.direction''',
            "coordinator direction exposure",
        )

    if "attempt: Int = 1" not in text:
        text = replace_regex_once(
            text,
            r'''    private fun wakeInner\(\n        generation: Long,\n    \) \{.*?\n    \}\n\n    private fun beginPrewarm''',
            r'''    private fun wakeInner(
        generation: Long,
        attempt: Int = 1,
    ) {
        if (!ShizukuBridge.ready) {
            return
        }

        val openingState =
            controller.state in setOf(
                Fold7ContinuityController.State.OPENING_FROM_CLOSED,
                Fold7ContinuityController.State.INNER_HANDOFF,
            )

        if (
            !controller.isGenerationCurrent(generation) &&
            !openingState
        ) {
            return
        }

        val queuedAtNs =
            SystemClock.elapsedRealtimeNanos()

        scope.launch(Dispatchers.IO) {
            val startedAtNs =
                SystemClock.elapsedRealtimeNanos()

            val result =
                runCatching {
                    ShizukuBridge.wakeInnerDisplay()
                }.getOrNull()

            val completedAtNs =
                SystemClock.elapsedRealtimeNanos()

            val queueMs =
                (startedAtNs - queuedAtNs) /
                    1_000_000.0

            val totalMs =
                (completedAtNs - queuedAtNs) /
                    1_000_000.0

            handler.post {
                val topologyNow =
                    topology()

                val proved =
                    topologyNow.innerActive

                DuoDiagnostics.event(
                    "fold7-state",
                    "inner-wake generation=$generation attempt=$attempt " +
                        "ok=${result?.getBoolean("ok", false) == true} " +
                        "physical=${result?.getLong("physicalDisplayId", -1L) ?: -1L} " +
                        "queueMs=${"%.3f".format(queueMs)} " +
                        "shellLatencyMs=${result?.getLong("latencyMs", -1L) ?: -1L} " +
                        "totalMs=${"%.3f".format(totalMs)} " +
                        "innerActive=${topologyNow.innerActive} " +
                        "innerDefault=${topologyNow.innerIsDefault} " +
                        "shellLogical=${result?.getInt("innerLogicalId", -1) ?: -1} " +
                        "shellLogicalPowered=${result?.getBoolean("innerLogicalPowered", false) == true} " +
                        "shellUseful=${result?.getBoolean("usefulReady", false) == true} " +
                        "error=${result?.getString("error")} " +
                        "logicalError=${result?.getString("logicalError")}",
                )

                if (proved) {
                    DuoDiagnostics.event(
                        "inner-wake-proof",
                        "READY attempt=$attempt generation=${controller.generation}",
                    )
                    return@post
                }

                val stillOpening =
                    controller.state in setOf(
                        Fold7ContinuityController.State.OPENING_FROM_CLOSED,
                        Fold7ContinuityController.State.INNER_HANDOFF,
                    )

                if (
                    stillOpening &&
                    ShizukuBridge.ready &&
                    attempt < MAX_INNER_WAKE_ATTEMPTS
                ) {
                    handler.postDelayed(
                        {
                            wakeInner(
                                generation = controller.generation,
                                attempt = attempt + 1,
                            )
                        },
                        INNER_WAKE_RETRY_MS,
                    )
                } else {
                    DuoDiagnostics.event(
                        "inner-wake-proof",
                        "NOT_READY attempt=$attempt state=${controller.state}",
                    )
                }
            }
        }
    }

    private fun beginPrewarm''',
            "wake inner retries",
        )
        # Insert constants before companion close by extending existing startup constants area.
        text = text.replace(
            "const val GEN4_STARTUP_RETRY_MS =",
            "const val MAX_INNER_WAKE_ATTEMPTS = 5\n        const val INNER_WAKE_RETRY_MS = 55L\n        const val GEN4_STARTUP_RETRY_MS =",
            1,
        )
    return text


def transform_shell_protocol(text: str) -> str:
    if "COVER_PRESENTATION_V1" not in text:
        text = replace_once(
            text,
            "    const val COVER_PANEL_GEN4 = 18\n",
            "    const val COVER_PANEL_GEN4 = 18\n\n    // Beta2: serialized physical cover power + brightness presentation.\n    const val COVER_PRESENTATION_V1 = 19\n",
            "shell protocol cover presentation",
        )
    return text


def transform_shizuku_bridge(text: str) -> str:
    if "setCoverPresentationV1" not in text:
        insert = '''

    /**
     * Serialized Fold7 physical cover power/brightness command. Blocking; call
     * off main. The shell daemon rejects stale service/sequence mutations.
     */
    internal fun setCoverPresentationV1(
        serviceEpoch: Long,
        transitionGeneration: Long,
        sequence: Long,
        powerOn: Boolean,
        brightness: Float?,
        reason: String,
    ): Bundle? =
        call(ShellProtocol.COVER_PRESENTATION_V1) { parcel ->
            parcel.writeLong(serviceEpoch)
            parcel.writeLong(transitionGeneration)
            parcel.writeLong(sequence)
            parcel.writeInt(if (powerOn) 1 else 0)
            parcel.writeFloat(brightness ?: Float.NaN)
            parcel.writeString(reason)
        }
'''
        idx = text.rfind("}\n")
        if idx < 0:
            raise RuntimeError("ShizukuBridge closing brace not found")
        text = text[:idx] + insert + text[idx:]
    return text


def transform_shell_service(text: str) -> str:
    if "coverPresentationSequence" not in text:
        text = replace_once(
            text,
            '''    private val coverMutationRevision =
        java.util.concurrent.atomic.AtomicLong(0L)''',
            '''    private val coverMutationRevision =
        java.util.concurrent.atomic.AtomicLong(0L)

    private var coverPresentationServiceEpoch = 0L
    private var coverPresentationSequence = 0L''',
            "shell presentation sequence fields",
        )

    if "ShellProtocol.COVER_PRESENTATION_V1" not in text:
        anchor = '''            ShellProtocol.OPEN_MIRROR_SESSION -> {'''
        block = '''            ShellProtocol.COVER_PRESENTATION_V1 -> {
                val requestServiceEpoch = data.readLong()
                val transitionGeneration = data.readLong()
                val sequence = data.readLong()
                val powerOn = data.readInt() != 0
                val brightness = data.readFloat()
                val reason = data.readString() ?: "unspecified"

                val identity = clearCallingIdentity()
                val result =
                    try {
                        runCoverMutation {
                            setCoverPresentationV1(
                                serviceEpoch = requestServiceEpoch,
                                transitionGeneration = transitionGeneration,
                                sequence = sequence,
                                powerOn = powerOn,
                                brightness = brightness,
                                reason = reason,
                            )
                        }
                    } catch (t: Throwable) {
                        failureBundle("cover-presentation-v1", t)
                    } finally {
                        restoreCallingIdentity(identity)
                    }

                out.writeNoException()
                out.writeBundle(result)
            }

'''
        text = replace_once(text, anchor, block + anchor, "shell presentation transact")

    if "private fun setPhysicalPowerMode(" not in text:
        old = '''    private fun setPhysicalPowerNormal(
        physicalId: Long,
    ): Pair<Boolean, String?> {
        if (physicalId < 0L) {
            return false to "physical display id unavailable"
        }

        return runCatching {
            org.lsposed.hiddenapibypass.HiddenApiBypass
                .addHiddenApiExemptions(
                    "Landroid/view/SurfaceControl;"
                )

            val token =
                SurfaceControl::class.java
                    .getDeclaredMethod(
                        "getPhysicalDisplayToken",
                        java.lang.Long.TYPE,
                    )
                    .invoke(null, physicalId) as? IBinder
                    ?: throw IllegalStateException(
                        "no SurfaceControl token for physical display $physicalId"
                    )

            SurfaceControl::class.java
                .getDeclaredMethod(
                    "setDisplayPowerMode",
                    IBinder::class.java,
                    Integer.TYPE,
                )
                .invoke(null, token, 2)

            true to null
        }.getOrElse { error ->
            false to
                "${error.javaClass.simpleName}: ${error.message}"
        }
    }'''
        new = '''    private fun physicalDisplayToken(
        physicalId: Long,
    ): IBinder {
        if (physicalId < 0L) {
            throw IllegalArgumentException("physical display id unavailable")
        }

        org.lsposed.hiddenapibypass.HiddenApiBypass
            .addHiddenApiExemptions(
                "Landroid/view/SurfaceControl;"
            )

        return SurfaceControl::class.java
            .getDeclaredMethod(
                "getPhysicalDisplayToken",
                java.lang.Long.TYPE,
            )
            .invoke(null, physicalId) as? IBinder
            ?: throw IllegalStateException(
                "no SurfaceControl token for physical display $physicalId"
            )
    }

    private fun setPhysicalPowerMode(
        physicalId: Long,
        powerMode: Int,
    ): Pair<Boolean, String?> =
        runCatching {
            val token =
                physicalDisplayToken(
                    physicalId
                )

            SurfaceControl::class.java
                .getDeclaredMethod(
                    "setDisplayPowerMode",
                    IBinder::class.java,
                    Integer.TYPE,
                )
                .invoke(null, token, powerMode)

            true to null
        }.getOrElse { error ->
            false to
                "${error.javaClass.simpleName}: ${error.message}"
        }

    private fun setPhysicalPowerNormal(
        physicalId: Long,
    ): Pair<Boolean, String?> =
        setPhysicalPowerMode(
            physicalId = physicalId,
            powerMode = 2,
        )

    private fun setPhysicalBrightness(
        physicalId: Long,
        brightness: Float,
    ): Pair<Boolean, String?> =
        runCatching {
            val token =
                physicalDisplayToken(
                    physicalId
                )

            val bounded =
                brightness
                    .coerceIn(0f, 1f)

            val result =
                SurfaceControl::class.java
                    .getDeclaredMethod(
                        "setDisplayBrightness",
                        IBinder::class.java,
                        java.lang.Float.TYPE,
                    )
                    .invoke(null, token, bounded)

            val accepted =
                (result as? Boolean) ?: true

            accepted to
                if (accepted) null else "SurfaceControl rejected brightness"
        }.getOrElse { error ->
            false to
                "${error.javaClass.simpleName}: ${error.message}"
        }'''
        text = replace_once(text, old, new, "physical power/brightness helpers")

    if "innerLogicalPowered" not in text:
        text = replace_regex_once(
            text,
            r'''    private fun wakeInnerPhysicalDisplay\(\): Bundle \{.*?\n    \}\n\n    private fun logicalDisplayIdsDirect''',
            r'''    private fun wakeInnerPhysicalDisplay(): Bundle {
        val t0 =
            SystemClock.elapsedRealtime()

        val physicalId =
            resolveFold7InnerPhysicalDisplayId()

        val (powered, error) =
            setPhysicalPowerNormal(
                physicalId
            )

        var logicalId =
            -1

        var logicalEnabled =
            false

        var logicalPowered =
            false

        var logicalError:
            String? =
            null

        if (powered && physicalId >= 0L) {
            /*
             * GEN7_RUNTIME_REGRESSION_BETA2
             *
             * Physical NORMAL alone did not produce visible inner pixels in the
             * field bundles. Symmetrically with cover prewarm, give Samsung a
             * bounded window to publish the disabled 1968x2184 logical route,
             * enable that exact route, re-resolve it after mutation, and ask
             * DisplayManager for STATE_ON. The physical id is revalidated every
             * time; no logical id is cached as panel identity.
             */
            for (attempt in 0 until 6) {
                val candidate =
                    runCatching {
                        logicalDisplayIdsDirect()
                            .asSequence()
                            .firstOrNull { id ->
                                directGeometry(id) ==
                                    (1968 to 2184) &&
                                    physicalDisplayIdFromLogical(id) ==
                                    physicalId
                            }
                    }.getOrNull()

                if (candidate != null) {
                    logicalId =
                        candidate
                    break
                }

                if (attempt < 5) {
                    Thread.sleep(8L)
                }
            }

            if (logicalId >= 0) {
                runCatching {
                    if (
                        logicalId !=
                            Display.DEFAULT_DISPLAY
                    ) {
                        enableConnectedDisplayInternal(
                            logicalId
                        )
                    }

                    logicalEnabled =
                        true
                }.onFailure { routeError ->
                    logicalError =
                        "${routeError.javaClass.simpleName}: ${routeError.message}"
                }

                val freshLogical =
                    runCatching {
                        logicalDisplayIdsDirect()
                            .asSequence()
                            .firstOrNull { id ->
                                directGeometry(id) ==
                                    (1968 to 2184) &&
                                    physicalDisplayIdFromLogical(id) ==
                                    physicalId
                            }
                    }.getOrNull()

                if (freshLogical != null) {
                    logicalId =
                        freshLogical

                    logicalPowered =
                        runCatching {
                            requestDisplayPowerInternal(
                                freshLogical,
                                Display.STATE_ON,
                            )
                        }.getOrElse { routeError ->
                            logicalError =
                                listOfNotNull(
                                    logicalError,
                                    "${routeError.javaClass.simpleName}: ${routeError.message}",
                                ).joinToString(" | ")
                            false
                        }
                }
            }
        }

        return Bundle().apply {
            putBoolean("ok", powered)
            putLong(
                "physicalDisplayId",
                physicalId,
            )
            putInt("targetWidth", 1968)
            putInt("targetHeight", 2184)
            putBoolean(
                "physicalPowered",
                powered,
            )
            putInt(
                "innerLogicalId",
                logicalId,
            )
            putBoolean(
                "innerLogicalEnabled",
                logicalEnabled,
            )
            putBoolean(
                "innerLogicalPowered",
                logicalPowered,
            )
            putBoolean(
                "usefulReady",
                powered &&
                    logicalPowered,
            )
            putString(
                "command",
                "Fold7 physical + logical inner early wake",
            )
            if (error != null) {
                putString(
                    "error",
                    error,
                )
            }
            if (logicalError != null) {
                putString(
                    "logicalError",
                    logicalError,
                )
            }
            putLong(
                "latencyMs",
                SystemClock.elapsedRealtime() -
                    t0,
            )
        }
    }

    private fun logicalDisplayIdsDirect''',
            "inner logical wake activation",
        )

    if "private fun setCoverPresentationV1(" not in text:
        marker = '''    private fun setCoverPhysicalPowerNormal():'''
        method = '''    private fun setCoverPresentationV1(
        serviceEpoch: Long,
        transitionGeneration: Long,
        sequence: Long,
        powerOn: Boolean,
        brightness: Float,
        reason: String,
    ): Bundle {
        val stale =
            when {
                serviceEpoch < coverPresentationServiceEpoch ->
                    true

                serviceEpoch == coverPresentationServiceEpoch &&
                    sequence <= coverPresentationSequence ->
                    true

                else ->
                    false
            }

        if (stale) {
            return Bundle().apply {
                putBoolean("ok", false)
                putBoolean("stale", true)
                putLong("serviceEpoch", serviceEpoch)
                putLong("sequence", sequence)
                putString("reason", "stale-cover-presentation:$reason")
            }
        }

        if (serviceEpoch > coverPresentationServiceEpoch) {
            coverPresentationServiceEpoch = serviceEpoch
            coverPresentationSequence = 0L
        }

        coverPresentationSequence = sequence

        val physicalId =
            resolveFold7CoverPhysicalDisplayId(-1)

        val powerMode =
            if (powerOn) 2 else 0

        val (powerOk, powerError) =
            setPhysicalPowerMode(
                physicalId = physicalId,
                powerMode = powerMode,
            )

        val brightnessRequested =
            powerOn &&
                brightness.isFinite()

        val (brightnessOk, brightnessError) =
            if (powerOk && brightnessRequested) {
                setPhysicalBrightness(
                    physicalId = physicalId,
                    brightness = brightness,
                )
            } else {
                true to null
            }

        return Bundle().apply {
            putBoolean("ok", powerOk && brightnessOk)
            putBoolean("stale", false)
            putLong("serviceEpoch", serviceEpoch)
            putLong("transitionGeneration", transitionGeneration)
            putLong("sequence", sequence)
            putLong("physicalDisplayId", physicalId)
            putBoolean("powerOn", powerOn)
            if (brightnessRequested) {
                putFloat("brightness", brightness.coerceIn(0f, 1f))
            }
            putString("reason", reason)
            if (powerError != null) putString("powerError", powerError)
            if (brightnessError != null) putString("brightnessError", brightnessError)
        }
    }

'''
        text = replace_once(text, marker, method + marker, "cover presentation shell method")
    return text


def transform_overlay_service(text: str) -> str:
    if "beforeOpeningState !=" not in text:
        text = replace_once(
            text,
            """                if (
                    beforeOpeningState ==
                        Fold7ContinuityController.State.NATIVE_COVER &&
                    continuity.state ==
                        Fold7ContinuityController.State.OPENING_FROM_CLOSED
                ) {""",
            """                if (
                    beforeOpeningState !=
                        Fold7ContinuityController.State.OPENING_FROM_CLOSED &&
                    continuity.state ==
                        Fold7ContinuityController.State.OPENING_FROM_CLOSED
                ) {""",
            "device-state recovered opening visual",
        )

    if "beforeState !=" not in text:
        text = replace_once(
            text,
            """            if (
                beforeState ==
                    Fold7ContinuityController.State.NATIVE_COVER &&
                continuity.state ==
                    Fold7ContinuityController.State.OPENING_FROM_CLOSED
            ) {""",
            """            if (
                beforeState !=
                    Fold7ContinuityController.State.OPENING_FROM_CLOSED &&
                continuity.state ==
                    Fold7ContinuityController.State.OPENING_FROM_CLOSED
            ) {""",
            "hinge opening visual edge",
        )

    if "innerCaptureExclusions = {" not in text:
        text = replace_once(
            text,
            """                currentHingeAngle = {
                    hinge.lastAngle
                },
            )""",
            """                currentHingeAngle = {
                    hinge.lastAngle
                },
                scope = scope,
                innerCaptureExclusions = {
                    engines.values
                        .firstOrNull {
                            it.isFold7InnerGeometryNow()
                        }
                        ?.captureExclusionLayers()
                        ?: emptyList()
                },
            )""",
            "service Gen3 exclusion provider",
        )

    if "coverPresentationPolicy" not in text:
        text = replace_once(
            text,
            '''    private val gen2 =
        Fold7Gen2Kernel<Bitmap>(serviceEpoch)''',
            '''    private val gen2 =
        Fold7Gen2Kernel<Bitmap>(serviceEpoch)

    private val coverPresentationPolicy =
        Fold7CoverPresentationPolicy()

    private val coverPresentationSequence =
        java.util.concurrent.atomic.AtomicLong(0L)

    private var innerBrightnessReference =
        Fold7CoverPresentationPolicy.DEFAULT_INNER_REFERENCE''',
            "service cover presentation fields",
        )

    if "updateCoverPresentation(angle)" not in text:
        # Add after engine hinge fan-out in normal drain path.
        old = '''        for (engine in engines.values.toList()) {
            engine.onHinge(
                angle = angle,
                observedUptimeMs = last.observedUptimeMs,
            )
        }
    }'''
        new = '''        for (engine in engines.values.toList()) {
            engine.onHinge(
                angle = angle,
                observedUptimeMs = last.observedUptimeMs,
            )
        }

        updateCoverPresentation(
            angle
        )
    }'''
        text = replace_once(text, old, new, "service presentation update call")

    if "private fun updateCoverPresentation(" not in text:
        marker = '''    /** Starts engines for panels that lit up, stops those that went dark, then lets each re-evaluate. */'''
        method = '''    private fun updateCoverPresentation(
        angle: Float,
    ) {
        if (
            !angle.isFinite() ||
            !::continuity.isInitialized
        ) {
            return
        }

        // Capture the brightness the user actually had on the unfolded inner
        // display. This becomes the target of the 175 -> 90 degree front-panel
        // ramp instead of imposing an arbitrary absolute level.
        if (angle >= Fold7CoverPresentationPolicy.POWER_ON_CLOSING_DEG) {
            displayManager.displays
                .firstOrNull { display ->
                    val mode =
                        runCatching {
                            display.mode
                        }.getOrNull()
                            ?: return@firstOrNull false

                    mode.physicalWidth ==
                        Fold7DisplayTransform.INNER_WIDTH &&
                        mode.physicalHeight ==
                        Fold7DisplayTransform.INNER_HEIGHT &&
                        display.state != Display.STATE_OFF
                }
                ?.let { inner ->
                    val brightness =
                        runCatching {
                            val info =
                                Display::class.java
                                    .getMethod("getBrightnessInfo")
                                    .invoke(inner)

                            info
                                ?.javaClass
                                ?.getMethod("getBrightness")
                                ?.invoke(info)
                                ?.let { value -> (value as Number).toFloat() }
                        }.getOrNull()

                    if (
                        brightness != null &&
                        brightness.isFinite() &&
                        brightness > 0f
                    ) {
                        innerBrightnessReference =
                            brightness.coerceIn(
                                Fold7CoverPresentationPolicy.MIN_BRIGHTNESS,
                                1f,
                            )
                    }
                }
        }

        if (
            !ShizukuBridge.ready ||
            !continuity.renderOwnershipEnabled
        ) {
            return
        }

        val direction =
            when (continuity.direction) {
                Fold7ContinuityController.Direction.OPENING ->
                    Fold7CoverPresentationPolicy.Direction.OPENING

                Fold7ContinuityController.Direction.CLOSING ->
                    Fold7CoverPresentationPolicy.Direction.CLOSING

                else ->
                    Fold7CoverPresentationPolicy.Direction.STEADY
            }

        val command =
            coverPresentationPolicy.evaluate(
                angle = angle,
                direction = direction,
                innerReferenceBrightness = innerBrightnessReference,
                nowMs = SystemClock.uptimeMillis(),
            ) ?: return

        val sequence =
            coverPresentationSequence.incrementAndGet()

        val generation =
            continuity.generation

        scope.launch(Dispatchers.IO) {
            val result =
                ShizukuBridge.setCoverPresentationV1(
                    serviceEpoch = serviceEpoch,
                    transitionGeneration = generation,
                    sequence = sequence,
                    powerOn = command.powerOn,
                    brightness = command.brightness,
                    reason = command.reason,
                )

            DuoDiagnostics.event(
                "cover-presentation",
                "angle=$angle direction=$direction " +
                    "power=${command.powerOn} " +
                    "target=${command.brightness} " +
                    "innerReference=$innerBrightnessReference " +
                    "sequence=$sequence generation=$generation " +
                    "ok=${result?.getBoolean("ok", false) == true} " +
                    "stale=${result?.getBoolean("stale", false) == true} " +
                    "physical=${result?.getLong("physicalDisplayId", -1L) ?: -1L} " +
                    "powerError=${result?.getString("powerError")} " +
                    "brightnessError=${result?.getString("brightnessError")}",
            )
        }
    }

'''
        text = replace_once(text, marker, method + marker, "service presentation method")

    if "coverPresentationPolicy.reset()" not in text:
        text = replace_once(
            text,
            '''                } else {
                    setEarlyOpeningVisualLatched(''',
            '''                } else {
                    coverPresentationPolicy.reset()

                    setEarlyOpeningVisualLatched(''',
            "service presentation reset",
        )
    return text


TRANSFORMS = {
    "app/build.gradle.kts": transform_build_gradle,
    "app/src/full/java/com/duoopen/overlay/Fold7ContinuityController.kt": transform_controller,
    "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt": transform_coordinator,
    "app/src/full/java/com/duoopen/overlay/PanelEngine.kt": transform_panel_engine,
    "app/src/full/java/com/duoopen/overlay/Fold7CoverVisualHost.kt": transform_cover_visual_host,
    "app/src/full/java/com/duoopen/overlay/Fold7Gen3VisualCoordinator.kt": transform_gen3_visual,
    "app/src/full/java/com/duoopen/overlay/Fold7RightPaneComposer.kt": transform_right_pane_composer,
    "app/src/full/java/com/duoopen/overlay/FoldOverlayView.kt": transform_overlay_view,
    "app/src/full/java/com/duoopen/overlay/SnapshotCache.kt": transform_snapshot_cache,
    "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt": transform_overlay_service,
    "app/src/full/java/com/duoopen/shell/ShizukuBridge.kt": transform_shizuku_bridge,
    "app/src/full/java/com/duoopen/shell/ShellProtocol.kt": transform_shell_protocol,
    "app/src/full/java/com/duoopen/shell/DuoShellService.kt": transform_shell_service,
    "app/src/main/java/com/duoopen/fold/Fold7VirtualHingeGen5.kt": transform_virtual_hinge,
    "app/src/test/java/com/duoopen/fold/Fold7VirtualHingeGen5Test.kt": transform_virtual_hinge_test,
    "app/src/test/java/com/duoopen/overlay/Fold7ContinuityControllerTest.kt": transform_continuity_controller_test,
}

# FoldOverlayService was not in the initial guard map above in early draft.
EXPECTED_BLOBS["app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"] = "cfc4706458e1da197e0e86ce74dc80c83489a2e6"


def copy_new_files(repo: Path, pack_dir: Path) -> list[str]:
    changed = []
    for rel, src_name in NEW_FILES.items():
        src = pack_dir / src_name
        dst = repo / rel
        payload = src.read_text(encoding="utf-8")
        if dst.exists():
            if read(dst) != payload:
                raise RuntimeError(f"new-file collision with different content: {rel}")
            continue
        write(dst, payload)
        changed.append(rel)
    return changed


def validate_postconditions(repo: Path) -> None:
    checks = {
        "app/build.gradle.kts": [TARGET_VERSION_NAME, f"versionCode = {TARGET_VERSION_CODE}"],
        "app/src/full/java/com/duoopen/overlay/Fold7ContinuityController.kt": [
            "device-state-opening-edge-recovered",
            "const val COVER_PREWARM_DEG = 175f",
        ],
        "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt": [
            "MAX_INNER_WAKE_ATTEMPTS",
            "inner-wake-proof",
            "shellLogicalPowered",
        ],
        "app/src/full/java/com/duoopen/overlay/PanelEngine.kt": [
            "live recapture enabled on Fold7",
            "Fold7DisplayTransform.foldFor",
            "Fold7DisplayTransform.innerCaptureSize",
            "fun captureExclusionLayers()",
        ],
        "app/src/full/java/com/duoopen/overlay/Fold7CoverVisualHost.kt": [
            "startLiveClosingLoop",
            "gen3-live-content",
            "innerCaptureExclusions",
        ],
        "app/src/full/java/com/duoopen/overlay/Fold7Gen3VisualCoordinator.kt": [
            "private val scope: kotlinx.coroutines.CoroutineScope",
            "scope =\n                    scope",
            "innerCaptureExclusions",
        ],
        "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt": [
            "coverPresentationPolicy",
            "setCoverPresentationV1",
            "beforeOpeningState !=",
        ],
        "app/src/full/java/com/duoopen/shell/DuoShellService.kt": [
            "COVER_PRESENTATION_V1",
            "setPhysicalBrightness",
            "setCoverPresentationV1",
            "innerLogicalPowered",
        ],
        "app/src/main/java/com/duoopen/fold/Fold7VirtualHingeGen5.kt": [
            "AWAIT_PRECISE",
            "Never manufacture opening geometry",
        ],
        "app/src/test/java/com/duoopen/overlay/Fold7ContinuityControllerTest.kt": [
            "GEN7_RUNTIME_REGRESSION_BETA2_175_PREWARM_TEST",
            "State.COVER_PREWARMING",
            "deliberateClosePrewarmsAt175ButStaysHiddenUntil135",
        ],
    }
    for rel, needles in checks.items():
        text = read(repo / rel)
        for needle in needles:
            if needle not in text:
                raise RuntimeError(f"postcondition failed: {needle!r} missing from {rel}")

    for rel in NEW_FILES:
        if not (repo / rel).exists():
            raise RuntimeError(f"postcondition failed: new file missing {rel}")


def apply(repo: Path, pack_dir: Path, check_only: bool = False) -> dict:
    repo = repo.resolve()
    changed = []

    # Guard all pre-existing files before any write, so the patch fails closed.
    for rel in TRANSFORMS:
        if rel not in EXPECTED_BLOBS:
            raise RuntimeError(f"internal error: no blob guard for {rel}")
        guard(repo, rel)

    staged = {}
    for rel, transform in TRANSFORMS.items():
        p = repo / rel
        before = read(p)
        after = transform(before)
        staged[rel] = after
        if after != before:
            changed.append(rel)

    for rel, src_name in NEW_FILES.items():
        dst = repo / rel
        payload = read(pack_dir / src_name)
        if not dst.exists():
            changed.append(rel)
        elif read(dst) != payload:
            raise RuntimeError(f"new-file collision with different content: {rel}")

    if check_only:
        return {
            "baseHead": BASE_HEAD,
            "targetVersion": TARGET_VERSION_NAME,
            "wouldChange": changed,
            "status": "CHECK_PASS",
        }

    for rel, after in staged.items():
        write(repo / rel, after)
    copy_new_files(repo, pack_dir)
    validate_postconditions(repo)

    return {
        "baseHead": BASE_HEAD,
        "targetVersion": TARGET_VERSION_NAME,
        "changed": changed,
        "status": "APPLY_PASS",
    }


def self_test() -> None:
    # Exercise the pure patch helpers against representative baseline fragments.
    assert "versionCode = 43" in transform_build_gradle(
        'versionCode = 42\nversionName = "5.0.0-beta1-zfold7"\n'
    )

    vh = '''enum class Mode {\n        IDLE,\n        BLIND_BOOTSTRAP,\n    }\n        if (latest == null) {\n            val elapsedNs = (callbackTimeNs - openingStartedNs).coerceAtLeast(0L)\n            val elapsedSec = elapsedNs / 1_000_000_000.0\n            val blind =\n                (initialAngle + BLIND_VELOCITY_DPS * elapsedSec)\n                    .toFloat()\n                    .coerceAtMost(BLIND_MAX_ANGLE_DEG)\n            val confidence =\n                (BLIND_INITIAL_CONFIDENCE -\n                    (elapsedNs / 1_000_000_000.0 * BLIND_CONFIDENCE_DECAY_PER_SEC))\n                    .toFloat()\n                    .coerceIn(BLIND_MIN_CONFIDENCE, BLIND_INITIAL_CONFIDENCE)\n            return RawTarget(blind, confidence, Mode.BLIND_BOOTSTRAP, 0L)\n        }'''
    out = transform_virtual_hinge(vh)
    assert "AWAIT_PRECISE" in out
    assert "Mode.AWAIT_PRECISE" in out

    gen3 = """internal class Fold7Gen3VisualCoordinator(
    private val currentHingeAngle: () -> Float,
) {
    private fun ensureRenderer() {
        val created =
            Fold7CoverVisualHost(
                service =
                    service,
                display =
                    display,
            )
    }
}
"""
    gen3_out = transform_gen3_visual(gen3)
    assert "private val scope: kotlinx.coroutines.CoroutineScope" in gen3_out
    assert "private val innerCaptureExclusions: () -> List<android.view.SurfaceControl>" in gen3_out
    assert "scope =\n                    scope" in gen3_out

    controller_test = """    @Test
    fun deliberateClosePrewarmsEarlyButStaysHiddenUntil135() {
        val c = Fold7ContinuityController()
        c.reset(179f, 0L, openTopology)

        c.onHinge(177.8f, 100L, openTopology)
        c.onHinge(176.3f, 150L, openTopology)
        c.onHinge(174.8f, 200L, openTopology)

        assertEquals(
            Fold7ContinuityController.State.CLOSING_INTENT,
            c.state,
        )

        val prewarm =
            c.onHinge(
                173.8f,
                220L,
                openTopology,
            )

        val request =
            prewarm.actions.single()
                as Fold7ContinuityController.Action.BeginPrewarm
"""
    controller_test_out = transform_continuity_controller_test(controller_test)
    assert "GEN7_RUNTIME_REGRESSION_BETA2_175_PREWARM_TEST" in controller_test_out
    assert "State.COVER_PREWARMING" in controller_test_out
    assert "174.8f" in controller_test_out
    assert "173.8f" not in controller_test_out

    sc = '''    private fun setPhysicalPowerNormal(\n        physicalId: Long,\n    ): Pair<Boolean, String?> {\n        if (physicalId < 0L) {\n            return false to "physical display id unavailable"\n        }\n\n        return runCatching {\n            org.lsposed.hiddenapibypass.HiddenApiBypass\n                .addHiddenApiExemptions(\n                    "Landroid/view/SurfaceControl;"\n                )\n\n            val token =\n                SurfaceControl::class.java\n                    .getDeclaredMethod(\n                        "getPhysicalDisplayToken",\n                        java.lang.Long.TYPE,\n                    )\n                    .invoke(null, physicalId) as? IBinder\n                    ?: throw IllegalStateException(\n                        "no SurfaceControl token for physical display $physicalId"\n                    )\n\n            SurfaceControl::class.java\n                .getDeclaredMethod(\n                    "setDisplayPowerMode",\n                    IBinder::class.java,\n                    Integer.TYPE,\n                )\n                .invoke(null, token, 2)\n\n            true to null\n        }.getOrElse { error ->\n            false to\n                "${error.javaClass.simpleName}: ${error.message}"\n        }\n    }'''
    assert "setPhysicalBrightness" in transform_shell_service(
        '''    private val coverMutationRevision =\n        java.util.concurrent.atomic.AtomicLong(0L)\n\n''' +
        '''            ShellProtocol.OPEN_MIRROR_SESSION -> {\n''' + sc +
        '''\n    private fun wakeInnerPhysicalDisplay(): Bundle {\n        val physicalId = resolveFold7InnerPhysicalDisplayId()\n        val (powered, error) = setPhysicalPowerNormal(physicalId)\n        return Bundle().apply { putBoolean("ok", powered) }\n    }\n\n    private fun logicalDisplayIdsDirect(): IntArray = intArrayOf()\n\n    private fun setCoverPhysicalPowerNormal():\n        Pair<Boolean, String?> = true to null\n'''
    )

    print("SELF_TEST_PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--pack-dir", type=Path, default=Path(__file__).resolve().parent.parent / "service_packs" / "gen7_runtime_regression_beta2")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    result = apply(args.repo, args.pack_dir, check_only=args.check)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
