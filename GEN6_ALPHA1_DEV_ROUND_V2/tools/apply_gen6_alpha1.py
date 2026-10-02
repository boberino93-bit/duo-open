#!/usr/bin/env python3
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path.cwd()
PKG = Path(__file__).resolve().parents[1]
PAYLOAD = PKG / "payload"

EXPECTED = {
    "app/build.gradle.kts": "f11b8c5a15a67f2e7cad874db66d943c768fdce8",
    "app/src/full/java/com/duoopen/overlay/Fold7DeviceStateObserver.kt": "760d075332740e5ee0d73766766175b17e6f9122",
    "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt": "cfc4706458e1da197e0e86ce74dc80c83489a2e6",
    "app/src/full/java/com/duoopen/overlay/PanelEngine.kt": "866d21ed1bd3fecfc25fffdcd3633489db9a80d9",
    "app/src/full/java/com/duoopen/overlay/FoldSurface.kt": "79cd40dfacc81a87f7af988bca1880cd1ea83625",
    "app/src/full/java/com/duoopen/overlay/SnapshotCache.kt": "4b1b6bb9837de4fb77cdc1bdc26f4a39aa72ab26",
    "app/src/full/java/com/duoopen/overlay/Fold7ContinuityFrameStore.kt": "953200266e6b9117b97f1cdb980cf0ef48190482",
    "app/src/full/res/xml/duo_accessibility.xml": "58c06748df97fdc1207bc873b6f0df8bb3573a08",
    "app/src/full/java/com/duoopen/shell/ShizukuBridge.kt": "d276f950eb279b3af281b9930dda7a8e8c3fd6a1",
    "app/src/full/java/com/duoopen/shell/DuoShellService.kt": "e19469eebaa967cbce10f5bcf85eef795e1d6b7d",
}


def require(condition, message):
    if not condition:
        raise SystemExit("ERROR: " + message)


def blob(path: Path) -> str:
    return subprocess.check_output(["git", "hash-object", str(path)], text=True).strip()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    require(old in text, f"missing patch marker: {label}")
    return text.replace(old, new, 1)


def patch_build(text: str) -> str:
    text = replace_once(text, "versionCode = 42", "versionCode = 43", "version code")
    text = replace_once(
        text,
        'versionName = "5.0.0-beta1-zfold7"',
        'versionName = "6.0.0-alpha1-zfold7"',
        "version name",
    )
    return text


def patch_observer(text: str) -> str:
    text = replace_once(
        text,
        '''    private val onOpeningEdge: (\n        previousStateId: Int,\n        currentStateId: Int,\n    ) -> Unit,\n) {''',
        '''    private val onWakeHint: (\n        previousStateId: Int,\n        currentStateId: Int,\n    ) -> Unit = { _, _ -> },\n    private val onOpeningEdge: (\n        previousStateId: Int,\n        currentStateId: Int,\n    ) -> Unit,\n) {''',
        "observer constructor",
    )
    text = replace_once(
        text,
        '''        DuoDiagnostics.event(\n            "early-wake",\n            "device-state previous=$previousId current=$id " +\n                "folded=$inferredFolded source=$source",\n        )\n\n        if (\n            previousId != null &&\n            previousFolded == true &&\n            inferredFolded == false\n        ) {''',
        '''        DuoDiagnostics.event(\n            "early-wake",\n            "device-state previous=$previousId current=$id " +\n                "folded=$inferredFolded source=$source",\n        )\n\n        // Gen6: leaving an independently learned closed-rest state is a\n        // WakeHint even if Samsung's next posture still reports folded.\n        // It is attempt identity only; semantic opening remains below.\n        if (\n            previousId != null &&\n            previousId in learnedFoldedStateIds &&\n            id != previousId\n        ) {\n            onWakeHint(previousId, id)\n        }\n\n        if (\n            previousId != null &&\n            previousFolded == true &&\n            inferredFolded == false\n        ) {''',
        "observer WakeHint",
    )
    return text


def patch_snapshot_cache(text: str) -> str:
    return replace_once(
        text,
        '''    fun ageMs(innerPanel: Boolean): Long? = entries[innerPanel]?.let { SystemClock.uptimeMillis() - it.at }\n}''',
        '''    fun ageMs(innerPanel: Boolean): Long? = entries[innerPanel]?.let { SystemClock.uptimeMillis() - it.at }\n\n    /** Drop reusable pixel references without recycling live-surface bitmaps. */\n    fun clear() {\n        entries.clear()\n    }\n}''',
        "snapshot clear",
    )


def patch_frame_store(text: str) -> str:
    return replace_once(
        text,
        '''    fun current(\n        cycle: Fold7CycleEnvelope.CloseCycle,''',
        '''    /** Privacy transition: no previous content lease may be reused. */\n    fun clearLatest() {\n        latest = null\n        newestStartedCaptureSequence = 0L\n    }\n\n    fun current(\n        cycle: Fold7CycleEnvelope.CloseCycle,''',
        "frame-store clearLatest",
    )


def patch_surface(text: str) -> str:
    marker = '''/**
 * The system's cross-window blur over the live screen: no screenshot, no
 * capture delay, content keeps moving underneath. SurfaceFlinger blurs a
'''
    require(marker in text, "Gen6 glass insertion")
    gen6_surfaces = r'''
/**
 * Gen6 PUBLIC_GLASS.
 *
 * Transparent procedural glass: the live app remains visible underneath, so
 * the opening animation can start on the first presentation opportunity
 * without waiting for a screenshot or reusing stale pixels from another app.
 */
class PublicGlassSurface(
    context: Context,
    private val windowManager: WindowManager,
) : FoldSurface {
    private val view = PublicGlassView(context)
    val refreshView: View
        get() = view
    val attached: Boolean
    private var materialAnimator: ValueAnimator? = null

    init {
        attached =
            runCatching {
                windowManager.addView(
                    view,
                    overlayParams(
                        WindowManager.LayoutParams.MATCH_PARENT,
                        WindowManager.LayoutParams.MATCH_PARENT,
                        PixelFormat.TRANSLUCENT,
                    ),
                )
            }.onFailure {
                Log.e(TAG, "public glass addView failed", it)
            }.isSuccess
    }

    override var tilt: Float
        get() = view.tilt
        set(value) { view.tilt = value }

    override fun fadeIn(durationMs: Long) {
        materialAnimator?.cancel()
        materialAnimator = ValueAnimator.ofFloat(0f, 1f).apply {
            duration = durationMs
            interpolator = DecelerateInterpolator()
            addUpdateListener { view.materialScale = it.animatedValue as Float }
            start()
        }
    }

    override fun fadeOut(durationMs: Long, onEnd: () -> Unit) {
        view.animate()
            .alpha(0f)
            .setDuration(durationMs)
            .setInterpolator(DecelerateInterpolator())
            .withEndAction(onEnd)
            .start()
    }

    override fun detach() {
        materialAnimator?.cancel()
        runCatching { windowManager.removeViewImmediate(view) }
    }

    private class PublicGlassView(context: Context) : View(context) {
        private val tintPaint = Paint(Paint.ANTI_ALIAS_FLAG)
        private val sheenPaint = Paint(Paint.ANTI_ALIAS_FLAG)

        var materialScale = 1f
            set(value) {
                field = value.coerceIn(0f, 1f)
                rebuild()
                invalidate()
            }

        var tilt = 0f
            set(value) {
                field = value.coerceIn(0f, DuoShader.MAX_TILT)
                rebuild()
                invalidate()
            }

        override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) = rebuild()

        private fun rebuild() {
            if (width <= 0 || height <= 0) return
            val foldEnergy = sin(Math.toRadians((tilt / DuoShader.MAX_TILT * 90f).toDouble())).toFloat()
            val tintAlpha = (10f + 16f * foldEnergy * materialScale).roundToInt().coerceIn(0, 32)
            tintPaint.shader = LinearGradient(
                0f,
                0f,
                width.toFloat(),
                height.toFloat(),
                intArrayOf(
                    Color.argb(tintAlpha / 2, 215, 225, 255),
                    Color.argb(tintAlpha, 255, 255, 255),
                    Color.argb(tintAlpha / 2, 225, 215, 255),
                ),
                floatArrayOf(0f, 0.52f, 1f),
                Shader.TileMode.CLAMP,
            )
            val sheenAlpha = (18f + 44f * foldEnergy * materialScale).roundToInt().coerceIn(0, 72)
            sheenPaint.shader = LinearGradient(
                -width * 0.20f,
                0f,
                width * 1.10f,
                height.toFloat(),
                intArrayOf(
                    Color.argb(0, 255, 255, 255),
                    Color.argb(sheenAlpha, 255, 255, 255),
                    Color.argb(0, 255, 255, 255),
                ),
                floatArrayOf(0.18f, 0.50f, 0.82f),
                Shader.TileMode.CLAMP,
            )
        }

        override fun onDraw(canvas: Canvas) {
            // Deliberately no opaque base: PUBLIC_GLASS shows the live app.
            canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), tintPaint)
            canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), sheenPaint)
        }
    }

    private companion object { const val TAG = "DuoOverlay" }
}

/**
 * Gen6 PRIVATE_FROST.
 *
 * Procedural and fully opaque: no protected pixels are sampled, mirrored,
 * cached, or blurred underneath this material.
 */
class PrivateFrostSurface(
    context: Context,
    private val windowManager: WindowManager,
) : FoldSurface {
    private val view = PrivateFrostView(context)
    val attached: Boolean
    private var materialAnimator: ValueAnimator? = null

    init {
        attached = runCatching {
            windowManager.addView(
                view,
                overlayParams(
                    WindowManager.LayoutParams.MATCH_PARENT,
                    WindowManager.LayoutParams.MATCH_PARENT,
                    PixelFormat.OPAQUE,
                ),
            )
        }.onFailure { Log.e(TAG, "private frost addView failed", it) }.isSuccess
    }

    override var tilt: Float
        get() = view.tilt
        set(value) { view.tilt = value }

    override fun fadeIn(durationMs: Long) {
        materialAnimator?.cancel()
        materialAnimator = ValueAnimator.ofFloat(0f, 1f).apply {
            duration = durationMs
            interpolator = DecelerateInterpolator()
            addUpdateListener { view.materialScale = it.animatedValue as Float }
            start()
        }
    }

    override fun fadeOut(durationMs: Long, onEnd: () -> Unit) {
        view.animate()
            .alpha(0f)
            .setDuration(durationMs)
            .setInterpolator(DecelerateInterpolator())
            .withEndAction(onEnd)
            .start()
    }

    override fun detach() {
        materialAnimator?.cancel()
        runCatching { windowManager.removeViewImmediate(view) }
    }

    private class PrivateFrostView(context: Context) : View(context) {
        private val basePaint = Paint(Paint.ANTI_ALIAS_FLAG)
        private val sheenPaint = Paint(Paint.ANTI_ALIAS_FLAG)

        var materialScale = 1f
            set(value) {
                field = value.coerceIn(0f, 1f)
                rebuild()
                invalidate()
            }

        var tilt = 0f
            set(value) {
                field = value.coerceIn(0f, DuoShader.MAX_TILT)
                rebuild()
                invalidate()
            }

        override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) = rebuild()

        private fun rebuild() {
            if (width <= 0 || height <= 0) return
            val foldEnergy = sin(Math.toRadians((tilt / DuoShader.MAX_TILT * 90f).toDouble())).toFloat()
            basePaint.shader = LinearGradient(
                0f,
                0f,
                width.toFloat(),
                height.toFloat(),
                intArrayOf(
                    Color.rgb(194, 199, 213),
                    Color.rgb(229, 226, 236),
                    Color.rgb(183, 189, 205),
                ),
                floatArrayOf(0f, 0.52f, 1f),
                Shader.TileMode.CLAMP,
            )
            val sheenAlpha = (40f + 82f * foldEnergy * materialScale).roundToInt().coerceIn(0, 150)
            sheenPaint.shader = LinearGradient(
                -width * 0.15f,
                0f,
                width * 0.95f,
                height.toFloat(),
                intArrayOf(
                    Color.argb(0, 255, 255, 255),
                    Color.argb(sheenAlpha, 255, 255, 255),
                    Color.argb(0, 255, 255, 255),
                ),
                floatArrayOf(0.12f, 0.50f, 0.86f),
                Shader.TileMode.CLAMP,
            )
        }

        override fun onDraw(canvas: Canvas) {
            // Security boundary: fully opaque base first.
            canvas.drawColor(Color.rgb(202, 205, 218))
            canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), basePaint)
            canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), sheenPaint)
        }
    }

    private companion object { const val TAG = "DuoOverlay" }
}

'''
    return text.replace(marker, gen6_surfaces + marker, 1)

def patch_panel(text: str) -> str:
    text = replace_once(
        text,
        '''    private val activeCloseCycle: () -> Fold7CycleEnvelope.CloseCycle?,\n    private val onContinuityFrameChanged: (String) -> Unit,\n) {''',
        '''    private val activeCloseCycle: () -> Fold7CycleEnvelope.CloseCycle?,\n    private val onContinuityFrameChanged: (String) -> Unit,\n    private val privacyDecision: () -> Fold7GlassDecision,\n    private val onCaptureBlocked: (String) -> Unit,\n) {''',
        "PanelEngine privacy constructor",
    )

    text = replace_once(
        text,
        '''    /** Explicit CLOSED -> OPEN visual started from the device-state opening edge. */\n    private var continuityOpeningVisual = false''',
        '''    /** Explicit CLOSED -> OPEN visual started from the device-state opening edge. */\n    private var continuityOpeningVisual = false\n\n    /** Gen6 material selection for the current visual attempt only. */\n    private var gen6ForcePrivateFrost = false\n    private var gen6ForcePublicGlass = false\n    private var gen6PrivateTransitionVisual = false''',
        "PanelEngine Gen6 material fields",
    )

    helper_marker = '''    private fun startEffect(afterSwap: Boolean, startTilt: Float? = null) {'''
    require(helper_marker in text, "PanelEngine startEffect marker")
    helper = r'''    /**
     * Service-owned private transition visual. This path may start from IDLE so
     * a Gen3 frozen-frame host can be revoked and replaced with procedural
     * frost in the same control turn.
     */
    fun setGen6PrivateTransitionVisual(
        active: Boolean,
        opening: Boolean,
        reason: String,
    ) {
        if (!isFold7CoverGeometryNow()) return

        if (!active) {
            if (!gen6PrivateTransitionVisual) return
            gen6PrivateTransitionVisual = false
            gen6ForcePrivateFrost = false
            if (surface is PrivateFrostSurface) {
                captureGen++
                removeOverlay()
            }
            return
        }

        if (privacyDecision().mode != Fold7GlassMode.PRIVATE_FROST) return

        gen6PrivateTransitionVisual = true
        gen6ForcePrivateFrost = true
        gen6ForcePublicGlass = false

        val requestedTilt =
            if (opening) COVER_OPEN_IMMEDIATE_TILT else surface?.tilt ?: currentTilt()

        if (surface !is PrivateFrostSurface) {
            showPrivateFrostImmediately(
                afterSwap = false,
                requestedTilt = requestedTilt,
                reason = "private-transition:$reason",
            )
        }
    }

    /** Fail closed when private mode becomes known mid-animation/capture. */
    fun onPrivacyDecisionChanged() {
        if (privacyDecision().mode != Fold7GlassMode.PRIVATE_FROST) return

        if (phase != Phase.IDLE && surface !is PrivateFrostSurface) {
            showPrivateFrostImmediately(
                afterSwap = false,
                requestedTilt = surface?.tilt ?: currentTilt(),
                reason = "privacy-transition",
            )
        }
    }

    private fun showPrivateFrostImmediately(
        afterSwap: Boolean,
        requestedTilt: Float?,
        reason: String,
    ) {
        gen6ForcePrivateFrost = true
        gen6ForcePublicGlass = false
        captureGen++
        captureAttempt = 0
        bridging = false
        liveLoop = false
        follower?.cancel()
        follower = null

        surface?.detach()
        surface = null

        val tilt = requestedTilt ?: currentTilt()
        phase = Phase.CAPTURING

        com.duoopen.debug.DuoDiagnostics.event(
            "gen6-private-frost",
            "present reason=$reason display=$displayId hinge=${hinge.lastAngle} tilt=$tilt",
        )

        present(
            bitmap = null,
            afterSwap = afterSwap,
            startTilt = tilt,
            t0 = SystemClock.uptimeMillis(),
        )
    }

'''
    text = text.replace(helper_marker, helper + helper_marker, 1)

    text = replace_once(
        text,
        '''    private fun startEffect(afterSwap: Boolean, startTilt: Float? = null) {\n        if (liveMode()) {''',
        '''    private fun startEffect(afterSwap: Boolean, startTilt: Float? = null) {\n        if (privacyDecision().mode == Fold7GlassMode.PRIVATE_FROST) {\n            showPrivateFrostImmediately(\n                afterSwap = afterSwap,\n                requestedTilt = startTilt,\n                reason = "private-at-effect-start",\n            )\n            return\n        }\n\n        gen6ForcePrivateFrost = false\n        gen6ForcePublicGlass = false\n\n        if (liveMode()) {''',
        "startEffect privacy gate",
    )

    text = replace_once(
        text,
        '''    private fun capture(gen: Int, attempt: Int, afterSwap: Boolean, startTilt: Float?) {\n        val t0 = SystemClock.uptimeMillis()\n        captureAttempt = attempt''',
        '''    private fun capture(gen: Int, attempt: Int, afterSwap: Boolean, startTilt: Float?) {\n        val t0 = SystemClock.uptimeMillis()\n\n        if (privacyDecision().mode == Fold7GlassMode.PRIVATE_FROST) {\n            showPrivateFrostImmediately(\n                afterSwap = afterSwap,\n                requestedTilt = startTilt,\n                reason = "private-before-capture",\n            )\n            return\n        }\n\n        captureAttempt = attempt''',
        "capture privacy gate",
    )

    shell_old = '''            scope.launch {\n                val bitmap = withContext(Dispatchers.IO) {\n                    ShizukuBridge.capture(displayId, excludedLayers(), INITIAL_SHELL_SCALE)\n                }\n                if (stale()) return@launch\n                if (bitmap == null) {\n                    Log.i(TAG, "display $displayId: shell capture unavailable; using accessibility screenshot")\n                    accessibilityCapture(gen, attempt, afterSwap, startTilt, t0, ::retry, ::stale)\n                    return@launch\n                }'''
    shell_new = '''            scope.launch {\n                val shellResult = withContext(Dispatchers.IO) {\n                    ShizukuBridge.captureResult(displayId, excludedLayers(), INITIAL_SHELL_SCALE)\n                }\n                if (stale()) {\n                    shellResult?.bitmap?.let { bitmap ->\n                        if (!bitmap.isRecycled) bitmap.recycle()\n                    }\n                    return@launch\n                }\n\n                if (shellResult?.secure == true) {\n                    onCaptureBlocked("shell-secure-layer")\n                    showPrivateFrostImmediately(\n                        afterSwap = afterSwap,\n                        requestedTilt = startTilt,\n                        reason = "shell-secure-layer",\n                    )\n                    return@launch\n                }\n\n                val bitmap = shellResult?.bitmap\n                if (bitmap == null) {\n                    Log.i(TAG, "display $displayId: shell capture unavailable; using accessibility screenshot")\n                    accessibilityCapture(gen, attempt, afterSwap, startTilt, t0, ::retry, ::stale)\n                    return@launch\n                }'''
    text = replace_once(text, shell_old, shell_new, "secure-aware shell capture")

    text = replace_once(
        text,
        '''                if (afterSwap && attempt < MAX_CAPTURE_ATTEMPTS) {\n                    val black = withContext(Dispatchers.Default) { isMostlyBlack(bitmap) }\n                    if (stale()) return@launch\n                    if (black && !demoRunning) {\n                        Log.i(TAG, "display $displayId: shell capture $attempt is black after ${SystemClock.uptimeMillis() - t0}ms; retrying")\n                        handler.postDelayed({ if (!stale()) capture(gen, attempt + 1, afterSwap, startTilt) }, SHELL_RETRY_MS)\n                        return@launch\n                    }\n                }\n                onCaptured(''',
        '''                if (afterSwap && !demoRunning) {\n                    val black = withContext(Dispatchers.Default) { isMostlyBlack(bitmap) }\n                    if (stale()) return@launch\n                    if (black) {\n                        if (attempt < MAX_CAPTURE_ATTEMPTS) {\n                            Log.i(TAG, "display $displayId: shell capture $attempt is black after ${SystemClock.uptimeMillis() - t0}ms; retrying")\n                            bitmap.recycle()\n                            handler.postDelayed({ if (!stale()) capture(gen, attempt + 1, afterSwap, startTilt) }, SHELL_RETRY_MS)\n                            return@launch\n                        }\n\n                        bitmap.recycle()\n                        showPrivateFrostImmediately(\n                            afterSwap = afterSwap,\n                            requestedTilt = startTilt,\n                            reason = "shell-black-terminal",\n                        )\n                        return@launch\n                    }\n                }\n                onCaptured(''',
        "shell black fail closed",
    )

    text = replace_once(
        text,
        '''                } else if (bridging) {\n                    bridging = false // secure content etc.: keep playing on the stale picture\n                } else {\n                    phase = Phase.IDLE\n                    demoRunning = false\n                }''',
        '''                } else {\n                    if (\n                        errorCode ==\n                            AccessibilityService.ERROR_TAKE_SCREENSHOT_SECURE_WINDOW\n                    ) {\n                        onCaptureBlocked("accessibility-secure-window")\n                    }\n                    showPrivateFrostImmediately(\n                        afterSwap = afterSwap,\n                        requestedTilt = startTilt,\n                        reason = "accessibility-screenshot-error:$errorCode",\n                    )\n                }''',
        "accessibility fail closed",
    )

    text = replace_once(
        text,
        '''    ) {\n        cache.put(innerPanel, bitmap)\n\n        if (continuityTicket != null) {''',
        '''    ) {\n        if (\n            gen6ForcePrivateFrost ||\n            privacyDecision().mode == Fold7GlassMode.PRIVATE_FROST\n        ) {\n            bitmap.recycle()\n            showPrivateFrostImmediately(\n                afterSwap = afterSwap,\n                requestedTilt = startTilt,\n                reason = "privacy-before-publish",\n            )\n            return\n        }\n\n        cache.put(innerPanel, bitmap)\n\n        if (continuityTicket != null) {''',
        "publish privacy gate",
    )

    begin_old = '''        recycleGen5OpeningBitmap()\n        val cachedInner =\n            cache.get(\n                innerPanel = true,\n                width = Fold7RightPaneComposer.INNER_WIDTH,\n                height = Fold7RightPaneComposer.INNER_HEIGHT,\n            )\n        val canonicalRight =\n            cachedInner?.let(Fold7RightPaneComposer::fromInner)\n\n        if (canonicalRight != null) {\n            gen5OwnedOpeningBitmap = canonicalRight\n            phase = Phase.CAPTURING\n            present(\n                bitmap = canonicalRight,\n                afterSwap = false,\n                startTilt = COVER_OPEN_IMMEDIATE_TILT,\n                t0 = SystemClock.uptimeMillis(),\n            )\n            com.duoopen.debug.DuoDiagnostics.event(\n                "gen5-split-pane",\n                "opening bootstrap uses cached canonical right pane " +\n                    "crop=${Fold7RightPaneComposer.RIGHT_PANE_LEFT}..${Fold7RightPaneComposer.RIGHT_PANE_RIGHT}",\n            )\n        } else {\n            startEffect(\n                afterSwap = false,\n                startTilt = COVER_OPEN_IMMEDIATE_TILT,\n            )\n            com.duoopen.debug.DuoDiagnostics.event(\n                "gen5-split-pane",\n                "canonical right pane unavailable; falling back to current cover capture",\n            )\n        }'''
    begin_new = '''        // Gen6 PUBLIC_GLASS starts from live cover content. Do not bootstrap\n        // opening with a cached inner snapshot: that can be stale across apps.\n        recycleGen5OpeningBitmap()\n        gen6ForcePrivateFrost = false\n        gen6ForcePublicGlass = true\n        phase = Phase.CAPTURING\n        present(\n            bitmap = null,\n            afterSwap = false,\n            startTilt = COVER_OPEN_IMMEDIATE_TILT,\n            t0 = SystemClock.uptimeMillis(),\n        )\n        com.duoopen.debug.DuoDiagnostics.event(\n            "gen6-public-glass",\n            "opening bootstrap uses live transparent material; cached pixels not reused",\n        )'''
    text = replace_once(text, begin_old, begin_new, "public glass opening bootstrap")

    text = replace_once(
        text,
        '''        continuityOpeningVisual = false\n        captureGen++\n        stopGen5OpeningClock()''',
        '''        continuityOpeningVisual = false\n        gen6ForcePublicGlass = false\n        gen6ForcePrivateFrost = false\n        captureGen++\n        stopGen5OpeningClock()''',
        "opening material cleanup",
    )

    old_show = '''        val inner = innerPanel\n        val config = DuoSettings.config.value\n        val foldLine = { w: Float, h: Float, c: com.duoopen.settings.DuoConfig -> DuoShader.foldFor(inner, w, h, c) }\n        val created: FoldSurface? = if (bitmap != null) {\n            SnapshotSurface(service, windowManager, bitmap, config, foldLine).takeIf { it.attached }\n        } else {\n            LiveBlurSurface(service, windowManager, config, DuoShader.pxPerMm(service.createDisplayContext(display)), foldLine)\n                .takeIf { it.attached }\n        }'''
    new_show = '''        val inner = innerPanel\n        val config = DuoSettings.config.value\n        val foldLine = { w: Float, h: Float, c: com.duoopen.settings.DuoConfig -> DuoShader.foldFor(inner, w, h, c) }\n        val created: FoldSurface? =\n            when {\n                gen6ForcePrivateFrost ||\n                    privacyDecision().mode == Fold7GlassMode.PRIVATE_FROST ->\n                    PrivateFrostSurface(service, windowManager).takeIf { it.attached }\n\n                gen6ForcePublicGlass ->\n                    PublicGlassSurface(service, windowManager).takeIf { it.attached }\n\n                bitmap != null ->\n                    SnapshotSurface(service, windowManager, bitmap, config, foldLine).takeIf { it.attached }\n\n                else ->\n                    LiveBlurSurface(\n                        service,\n                        windowManager,\n                        config,\n                        DuoShader.pxPerMm(service.createDisplayContext(display)),\n                        foldLine,\n                    ).takeIf { it.attached }\n            }'''
    text = replace_once(text, old_show, new_show, "Gen6 surface selector")

    text = replace_once(
        text,
        '''            startGen5OpeningFrameLoop()\n            (created as? SnapshotSurface)?.let(::requestGen5RefreshRate)''',
        '''            startGen5OpeningFrameLoop()\n            when (created) {\n                is SnapshotSurface -> requestGen5RefreshRate(created.view)\n                is PublicGlassSurface -> requestGen5RefreshRate(created.refreshView)\n                else -> Unit\n            }''',
        "Gen6 opening refresh target",
    )

    text = replace_once(
        text,
        '''    private fun requestGen5RefreshRate(snapshot: SnapshotSurface) {\n        snapshot.view.post {\n            if (!continuityOpeningVisual) return@post\n            val root = rootSurfaceControl(snapshot.view)''',
        '''    private fun requestGen5RefreshRate(view: View) {\n        view.post {\n            if (!continuityOpeningVisual) return@post\n            val root = rootSurfaceControl(view)''',
        "generic opening refresh view",
    )

    # Gen6 Fix3: preserve secure-layer provenance in the continuity-prime path.
    prime_old = '''        scope.launch {
            val bitmap =
                withContext(Dispatchers.IO) {
                    ShizukuBridge.capture(
                        displayId,
                        excludedLayers(),
                        INITIAL_SHELL_SCALE,
                    )
                }

            if (
                activeCloseCycle() != cycle ||
                !continuityPrimeOwner.isCurrent(attempt)
            ) {
                bitmap?.let {
                    runCatching {
                        it.recycle()
                    }
                }
                return@launch
            }

            if (bitmap == null) {'''
    prime_new = '''        scope.launch {
            val shellResult =
                withContext(Dispatchers.IO) {
                    ShizukuBridge.captureResult(
                        displayId,
                        excludedLayers(),
                        INITIAL_SHELL_SCALE,
                    )
                }

            if (
                activeCloseCycle() != cycle ||
                !continuityPrimeOwner.isCurrent(attempt)
            ) {
                shellResult?.bitmap?.let {
                    runCatching {
                        it.recycle()
                    }
                }
                return@launch
            }

            if (shellResult?.secure == true) {
                continuityPrimeOwner.markFailed(
                    attempt,
                    "secure-layer",
                )
                onCaptureBlocked("shell-secure-layer-prime")
                onContinuityFrameChanged(
                    "prime-secure-layer"
                )
                return@launch
            }

            val bitmap = shellResult?.bitmap
            if (bitmap == null) {'''
    text = replace_once(
        text,
        prime_old,
        prime_new,
        "secure-aware continuity prime",
    )

    # Gen6 Fix3: live re-capture must preserve the secure-layer signal.
    live_old = '''            scope.launch {
                val frame =
                    withContext(
                        Dispatchers.IO,
                    ) {
                        ShizukuBridge.capture(
                            displayId,
                            excluded,
                            LIVE_SHELL_SCALE,
                        )
                    }

                if (
                    liveLoop &&'''
    live_new = '''            scope.launch {
                val shellResult =
                    withContext(
                        Dispatchers.IO,
                    ) {
                        ShizukuBridge.captureResult(
                            displayId,
                            excluded,
                            LIVE_SHELL_SCALE,
                        )
                    }

                if (shellResult?.secure == true) {
                    onCaptureBlocked("shell-secure-layer-live")
                    if (
                        liveLoop &&
                        phase == Phase.SHOWING &&
                        myGen == captureGen
                    ) {
                        showPrivateFrostImmediately(
                            afterSwap = false,
                            requestedTilt = surface?.tilt ?: currentTilt(),
                            reason = "shell-secure-layer-live",
                        )
                    }
                    return@launch
                }

                val frame = shellResult?.bitmap

                if (
                    liveLoop &&'''
    text = replace_once(
        text,
        live_old,
        live_new,
        "secure-aware live recapture",
    )

    return text

def patch_service(text: str) -> str:
    text = replace_once(
        text,
        '''    private val snapshots = SnapshotCache(maxAgeMs = SNAPSHOT_MAX_AGE_MS)\n    private val serviceEpoch =''',
        '''    private val snapshots = SnapshotCache(maxAgeMs = SNAPSHOT_MAX_AGE_MS)\n    private val privacyRuntime = Fold7PrivacyRuntime()\n    private val serviceEpoch =''',
        "privacy runtime field",
    )
    text = replace_once(
        text,
        '''    private val gen2 =\n        Fold7Gen2Kernel<Bitmap>(serviceEpoch)\n    private var angleFeed: WallpaperAngleFeed? = null''',
        '''    private val gen2 =\n        Fold7Gen2Kernel<Bitmap>(serviceEpoch)\n    private val gen6OpeningAttempts =\n        Fold7Gen6OpeningAttemptOwner(serviceEpoch)\n    private var angleFeed: WallpaperAngleFeed? = null''',
        "opening attempt field",
    )

    text = replace_once(
        text,
        '''        deviceStateObserver =\n            Fold7DeviceStateObserver(\n                context = this,\n                handler = handler,\n            ) {\n                    previousStateId,\n                    currentStateId,\n                ->''',
        '''        deviceStateObserver =\n            Fold7DeviceStateObserver(\n                context = this,\n                handler = handler,\n                onWakeHint = { previousStateId, currentStateId ->\n                    val attempt =\n                        gen6OpeningAttempts.onWakeHint(\n                            previousStateId = previousStateId,\n                            currentStateId = currentStateId,\n                            nowUptimeMs = SystemClock.uptimeMillis(),\n                        )\n\n                    if (attempt != null) {\n                        val reason = "device-state:$previousStateId->$currentStateId"\n\n                        DuoDiagnostics.event(\n                            "gen6-opening-attempt",\n                            "WAKE_HINT attempt=${attempt.id} serviceEpoch=${attempt.serviceEpoch} " +\n                                "reason=$reason semantic=false precise=${hinge.lastAngle}",\n                        )\n\n                        com.duoopen.lab.TransitionLab.recordIngressStage(\n                            type = "gen6-wake-hint",\n                            serviceEpoch = serviceEpoch,\n                            presentationAttemptSequence = attempt.id,\n                            reason = reason,\n                        )\n\n                        // WakeHint may prepare infrastructure and visual material,\n                        // but it does not mutate semantic continuity state or hinge geometry.\n                        angleFeed?.kickBurst("gen6-wake-hint:$reason")\n                        setEarlyOpeningVisualLatched(\n                            value = true,\n                            reason = "gen6-wake-hint:$reason",\n                        )\n                        reconcileContinuityCoverRendering(\n                            "gen6-wake-hint:$reason"\n                        )\n\n                        if (ShizukuBridge.ready) {\n                            val queuedAtNs = SystemClock.elapsedRealtimeNanos()\n                            scope.launch(Dispatchers.IO) {\n                                val startedAtNs = SystemClock.elapsedRealtimeNanos()\n                                val result =\n                                    runCatching {\n                                        ShizukuBridge.wakeInnerDisplay()\n                                    }.getOrNull()\n                                val completedAtNs = SystemClock.elapsedRealtimeNanos()\n\n                                DuoDiagnostics.event(\n                                    "gen6-early-wake",\n                                    "attempt=${attempt.id} ok=${result?.getBoolean("ok", false) == true} " +\n                                        "physical=${result?.getLong("physicalDisplayId", -1L) ?: -1L} " +\n                                        "queueMs=${"%.3f".format((startedAtNs - queuedAtNs) / 1_000_000.0)} " +\n                                        "shellLatencyMs=${result?.getLong("latencyMs", -1L) ?: -1L} " +\n                                        "totalMs=${"%.3f".format((completedAtNs - queuedAtNs) / 1_000_000.0)} " +\n                                        "error=${result?.getString("error")}",\n                                )\n                            }\n                        }\n                    }\n                },\n            ) {\n                    previousStateId,\n                    currentStateId,\n                ->''',
        "WakeHint early wake callback",
    )

    semantic_opening_old = '''                if (\n                    beforeOpeningState ==\n                        Fold7ContinuityController.State.NATIVE_COVER &&\n                    continuity.state ==\n                        Fold7ContinuityController.State.OPENING_FROM_CLOSED\n                ) {\n                    gen3Visual.beginOpening('''
    semantic_opening_new = '''                if (\n                    beforeOpeningState ==\n                        Fold7ContinuityController.State.NATIVE_COVER &&\n                    continuity.state ==\n                        Fold7ContinuityController.State.OPENING_FROM_CLOSED\n                ) {\n                    gen6OpeningAttempts\n                        .markSemanticAccepted(continuity.generation)\n                        ?.let { attempt ->\n                            DuoDiagnostics.event(\n                                "gen6-opening-attempt",\n                                "SEMANTIC_ACCEPT attempt=${attempt.id} generation=${continuity.generation}",\n                            )\n                        }\n                    gen3Visual.beginOpening('''
    text = replace_once(
        text,
        semantic_opening_old,
        semantic_opening_new,
        "device-state semantic opening marker",
    )

    semantic_hinge_old = '''            if (\n                beforeState ==\n                    Fold7ContinuityController.State.NATIVE_COVER &&\n                continuity.state ==\n                    Fold7ContinuityController.State.OPENING_FROM_CLOSED\n            ) {\n                gen3Visual.beginOpening('''
    semantic_hinge_new = '''            if (\n                beforeState ==\n                    Fold7ContinuityController.State.NATIVE_COVER &&\n                continuity.state ==\n                    Fold7ContinuityController.State.OPENING_FROM_CLOSED\n            ) {\n                gen6OpeningAttempts\n                    .markSemanticAccepted(continuity.generation)\n                    ?.let { attempt ->\n                        DuoDiagnostics.event(\n                            "gen6-opening-attempt",\n                            "SEMANTIC_ACCEPT attempt=${attempt.id} generation=${continuity.generation}",\n                        )\n                    }\n                gen3Visual.beginOpening('''
    text = replace_once(
        text,
        semantic_hinge_old,
        semantic_hinge_new,
        "authoritative-hinge semantic opening marker",
    )

    text = replace_once(
        text,
        '''        deviceStateObserver\n            ?.corroborateFoldedRest(\n                nativeCover =\n                    continuity.state ==\n                        Fold7ContinuityController.State.NATIVE_COVER,\n                preciseAngle =\n                    angle,\n            )\n\n        for (engine in engines.values.toList()) {''',
        '''        deviceStateObserver\n            ?.corroborateFoldedRest(\n                nativeCover =\n                    continuity.state ==\n                        Fold7ContinuityController.State.NATIVE_COVER,\n                preciseAngle =\n                    angle,\n            )\n\n        if (\n            continuity.state == Fold7ContinuityController.State.NATIVE_COVER &&\n            angle.isFinite() &&\n            angle <= GEN6_CLOSED_REST_MAX_DEG\n        ) {\n            setEarlyOpeningVisualLatched(\n                value = false,\n                reason = "corroborated-closed",\n            )\n\n            gen6OpeningAttempts\n                .finish(\n                    reason = "corroborated-closed",\n                    nowUptimeMs = SystemClock.uptimeMillis(),\n                )\n                ?.let { terminal ->\n                    DuoDiagnostics.event(\n                        "gen6-opening-attempt",\n                        "END attempt=${terminal.attempt.id} reason=${terminal.reason}",\n                    )\n                }\n        }\n\n        for (engine in engines.values.toList()) {''',
        "closed attempt finish",
    )

    text = replace_once(
        text,
        '''        instance = null\n\n        deviceStateObserver''',
        '''        instance = null\n\n        gen6OpeningAttempts.finish(\n            reason = "service-destroy",\n            nowUptimeMs = SystemClock.uptimeMillis(),\n        )\n\n        deviceStateObserver''',
        "service destroy attempt finish",
    )

    text = replace_once(
        text,
        '''    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit\n    override fun onInterrupt() = Unit''',
        '''    override fun onAccessibilityEvent(event: AccessibilityEvent?) {\n        val foregroundPackage =\n            event\n                ?.packageName\n                ?.toString()\n                ?.takeIf { it.isNotBlank() && it != packageName }\n                ?: return\n\n        val isWorkProfile =\n            Fold7WorkProfileDetector.packageExistsInManagedProfile(\n                context = this,\n                packageName = foregroundPackage,\n            )\n\n        // Ignore transient system windows (permission panels, SystemUI, IME)\n        // rather than accidentally downgrading a private foreground app.\n        val launchable =\n            runCatching {\n                packageManager.getLaunchIntentForPackage(foregroundPackage) != null\n            }.getOrDefault(false)\n\n        if (!launchable && !isWorkProfile) {\n            return\n        }\n\n        val label =\n            runCatching {\n                val info = packageManager.getApplicationInfo(foregroundPackage, 0)\n                packageManager.getApplicationLabel(info).toString()\n            }.getOrNull()\n\n        applyPrivacyTransition(\n            transition =\n                privacyRuntime.onForegroundApp(\n                    packageName = foregroundPackage,\n                    appLabel = label,\n                    isWorkProfile = isWorkProfile,\n                ),\n            source = "accessibility-event:${event.eventType}",\n        )\n    }\n\n    private fun onCaptureBlocked(reason: String) {\n        applyPrivacyTransition(\n            transition = privacyRuntime.markCaptureDenied(reason),\n            source = reason,\n        )\n    }\n\n    private fun applyPrivacyTransition(\n        transition: Fold7PrivacyRuntime.Transition,\n        source: String,\n    ) {\n        if (!transition.changed) return\n\n        val current = transition.current\n        DuoDiagnostics.event(\n            "gen6-privacy",\n            "mode=${current.decision.mode} reason=${current.decision.reason} " +\n                "package=${current.packageName} workProfile=${current.isWorkProfile} " +\n                "captureDenied=${current.captureDeniedReason} source=$source",\n        )\n\n        val packageChanged =\n            transition.previous.packageName !=\n                current.packageName\n\n        if (\n            packageChanged ||\n            current.decision.mode == Fold7GlassMode.PRIVATE_FROST\n        ) {\n            // Never allow an old app's pixels to bootstrap a new app context.\n            snapshots.clear()\n            gen2.frames.clearLatest()\n        }\n\n        // Generic/non-continuity captures must also fail closed immediately.\n        for (engine in engines.values.toList()) {\n            engine.onPrivacyDecisionChanged()\n        }\n\n        // This call revokes any Gen3 frozen-frame host before a private\n        // procedural surface is admitted for the same transition.\n        reconcileContinuityCoverRendering("privacy:$source")\n    }\n\n    override fun onInterrupt() = Unit''',
        "accessibility privacy tracking",
    )

    text = replace_once(
        text,
        '''                    onContinuityFrameChanged = { frameReason ->\n                        reconcileContinuityCoverRendering(\n                            "continuity-frame:$frameReason"\n                        )\n                    },\n                )''',
        '''                    onContinuityFrameChanged = { frameReason ->\n                        reconcileContinuityCoverRendering(\n                            "continuity-frame:$frameReason"\n                        )\n                    },\n                    privacyDecision = { privacyRuntime.current().decision },\n                    onCaptureBlocked = ::onCaptureBlocked,\n                )''',
        "PanelEngine privacy wiring",
    )

    reconcile_old = '''        val privilegedReady =\n            ShizukuBridge.ready &&\n                continuity.renderOwnershipEnabled\n\n        /*\n         * Alpha2 keeps Gen3 as the semantic/exact owner, but restores the\n         * validated Fold7 snapshot/shader renderer for OPENING. The Alpha1\n         * field trace showed its LiveBlur host failing to attach on every\n         * accepted opening attempt.\n         */\n        for (engine in engines.values.toList()) {\n            engine.setContinuityCoverOwned(\n                owned =\n                    privilegedReady &&\n                        engine.isFold7CoverGeometryNow(),\n                reason = "gen3:$reason",\n            )\n        }\n\n        if (::gen3Visual.isInitialized) {\n            gen3Visual.reconcile(\n                state = continuity.state,\n                closingVisible =\n                    continuity.visualMirrorActive,\n                privilegedReady =\n                    privilegedReady,\n                reason =\n                    reason,\n            )\n        }\n\n        val openingDemand =\n            ::gen3Visual.isInitialized &&\n                gen3Visual.openingVisualDemandActive\n\n        val openingHostDisplayId =\n            if (::gen3Visual.isInitialized) {\n                gen3Visual.openingHostDisplayId\n            } else {\n                null\n            }\n\n        for (engine in engines.values.toList()) {\n            val runOpeningRenderer =\n                privilegedReady &&\n                    openingDemand &&\n                    engine.isFold7CoverGeometryNow() &&\n                    engine.display.displayId ==\n                        openingHostDisplayId\n\n            if (runOpeningRenderer) {\n                engine.beginContinuityOpeningVisual(\n                    "gen3-opening-snapshot:$reason"\n                )\n            } else {\n                engine.endContinuityOpeningVisual(\n                    "gen3-opening-not-owner:$reason"\n                )\n            }\n        }'''
    reconcile_new = '''        if (\n            earlyOpeningVisualLatched &&\n            continuity.state == Fold7ContinuityController.State.OPEN_INNER\n        ) {\n            setEarlyOpeningVisualLatched(\n                value = false,\n                reason = "native-inner",\n            )\n        }\n\n        val privilegedReady =\n            ShizukuBridge.ready &&\n                continuity.renderOwnershipEnabled\n\n        val privacy =\n            privacyRuntime.current().decision\n\n        // Gen3 closing/opening hosts may render pixels only for PUBLIC_GLASS.\n        // PRIVATE_FROST revokes the privileged pixel host and falls back to a\n        // procedural cover material owned by PanelEngine.\n        val privilegedPixelRendererReady =\n            privilegedReady &&\n                privacy.mode == Fold7GlassMode.PUBLIC_GLASS\n\n        for (engine in engines.values.toList()) {\n            engine.setContinuityCoverOwned(\n                owned =\n                    privilegedPixelRendererReady &&\n                        engine.isFold7CoverGeometryNow(),\n                reason = "gen6:$reason",\n            )\n        }\n\n        if (::gen3Visual.isInitialized) {\n            gen3Visual.reconcile(\n                state = continuity.state,\n                closingVisible = continuity.visualMirrorActive,\n                privilegedReady = privilegedPixelRendererReady,\n                reason = reason,\n            )\n        }\n\n        val semanticOpeningDemand =\n            ::gen3Visual.isInitialized &&\n                gen3Visual.openingVisualDemandActive\n\n        val openingDemand =\n            earlyOpeningVisualLatched ||\n                semanticOpeningDemand\n\n        val openingHostDisplayId =\n            if (::gen3Visual.isInitialized) {\n                gen3Visual.openingHostDisplayId\n            } else {\n                null\n            }\n\n        val privateOpeningDemand =\n            privacy.mode == Fold7GlassMode.PRIVATE_FROST &&\n                (\n                    earlyOpeningVisualLatched ||\n                        continuity.state == Fold7ContinuityController.State.OPENING_FROM_CLOSED ||\n                        continuity.state == Fold7ContinuityController.State.INNER_HANDOFF\n                    )\n\n        val privateClosingDemand =\n            privacy.mode == Fold7GlassMode.PRIVATE_FROST &&\n                continuity.state in\n                setOf(\n                    Fold7ContinuityController.State.CLOSING_INTENT,\n                    Fold7ContinuityController.State.COVER_PREWARMING,\n                    Fold7ContinuityController.State.COVER_READY_HIDDEN,\n                    Fold7ContinuityController.State.COVER_VISUAL,\n                )\n\n        for (engine in engines.values.toList()) {\n            val coverGeometry =\n                engine.isFold7CoverGeometryNow()\n\n            engine.setGen6PrivateTransitionVisual(\n                active =\n                    coverGeometry &&\n                        (privateOpeningDemand || privateClosingDemand),\n                opening = privateOpeningDemand,\n                reason = reason,\n            )\n\n            val runOpeningRenderer =\n                privilegedPixelRendererReady &&\n                    openingDemand &&\n                    coverGeometry &&\n                    (\n                        earlyOpeningVisualLatched ||\n                            engine.display.displayId == openingHostDisplayId\n                        )\n\n            if (runOpeningRenderer) {\n                engine.beginContinuityOpeningVisual(\n                    "gen6-opening-glass:$reason"\n                )\n            } else {\n                engine.endContinuityOpeningVisual(\n                    "gen6-opening-not-owner:$reason"\n                )\n            }\n        }'''
    text = replace_once(text, reconcile_old, reconcile_new, "Gen6 privacy-aware continuity reconcile")

    text = replace_once(
        text,
        '''        /** How old a panel's last picture may be and still bridge the next fold. */\n        private const val SNAPSHOT_MAX_AGE_MS = 15 * 60_000L''',
        '''        /** How old a panel's last picture may be and still bridge the next fold. */\n        private const val SNAPSHOT_MAX_AGE_MS = 15 * 60_000L\n\n        private const val GEN6_CLOSED_REST_MAX_DEG = 12f''',
        "closed-rest constant",
    )
    return text

def patch_shell_service(text: str) -> str:
    old = '''        var buffer: HardwareBuffer? = null
        try {
            buffer = result.javaClass.getMethod("getHardwareBuffer").invoke(result) as? HardwareBuffer
            val secure = runCatching {
                result.javaClass.getMethod("containsSecureLayers").invoke(result) as Boolean
            }.getOrDefault(false)
            val hardware = result.javaClass.getMethod("asBitmap").invoke(result) as? Bitmap
                ?: throw IllegalStateException("frame not readable")'''
    new = '''        var buffer: HardwareBuffer? = null
        try {
            val secure = runCatching {
                result.javaClass.getMethod("containsSecureLayers").invoke(result) as Boolean
            }.getOrElse {
                // Gen6 security contract: if secure-layer provenance cannot be
                // established, do not materialize the capture.
                true
            }

            // Gen6 privacy boundary: never materialize protected pixels.
            if (secure) {
                return Bundle().apply {
                    putBoolean("ok", true)
                    putBoolean("secure", true)
                    putInt("width", w)
                    putInt("height", h)
                    putLong("ms", SystemClock.elapsedRealtime() - t0)
                }
            }

            buffer = result.javaClass.getMethod("getHardwareBuffer").invoke(result) as? HardwareBuffer
            val hardware = result.javaClass.getMethod("asBitmap").invoke(result) as? Bitmap
                ?: throw IllegalStateException("frame not readable")'''
    return replace_once(text, old, new, "secure capture before bitmap materialization")


def patch_shizuku_bridge(text: str) -> str:
    old = '''    /** Blocking; call off the main thread. Null if unavailable or the frame had secure content. */
    fun capture(displayId: Int, excluded: List<SurfaceControl>, scale: Float): Bitmap? {
        val b = call(ShellProtocol.CAPTURE) { p ->
            p.writeInt(displayId)
            p.writeInt(excluded.size)
            excluded.forEach { p.writeTypedObject(it, 0) }
            p.writeFloat(scale)
        } ?: return null
        if (!b.getBoolean("ok")) {
            Log.w(
                TAG,
                "shell capture failed: ${b.getString("error")}",
            )
            return null
        }

        val seq =
            captureSeq.incrementAndGet()

        val captureMs =
            b.getLong("ms")

        if (
            seq == 1L ||
            seq % 20L == 0L
        ) {
            Log.i(
                TAG,
                "capture display=$displayId " +
                    "scale=$scale ${captureMs}ms",
            )
        }

        if (b.getBoolean("secure")) {
            return null
        }
        @Suppress("DEPRECATION")
        return b.getParcelable("bitmap")
    }'''
    new = '''    data class CaptureResult(
        val bitmap: Bitmap?,
        val secure: Boolean,
        val latencyMs: Long,
    )

    /** Blocking; call off the main thread. Preserves secure-layer metadata. */
    fun captureResult(
        displayId: Int,
        excluded: List<SurfaceControl>,
        scale: Float,
    ): CaptureResult? {
        val b = call(ShellProtocol.CAPTURE) { p ->
            p.writeInt(displayId)
            p.writeInt(excluded.size)
            excluded.forEach { p.writeTypedObject(it, 0) }
            p.writeFloat(scale)
        } ?: return null
        if (!b.getBoolean("ok")) {
            Log.w(TAG, "shell capture failed: ${b.getString("error")}")
            return null
        }

        val seq = captureSeq.incrementAndGet()
        val captureMs = b.getLong("ms")
        if (seq == 1L || seq % 20L == 0L) {
            Log.i(TAG, "capture display=$displayId scale=$scale ${captureMs}ms")
        }

        val secure = b.getBoolean("secure")
        @Suppress("DEPRECATION")
        val bitmap: Bitmap? = if (secure) null else b.getParcelable("bitmap")

        return CaptureResult(
            bitmap = bitmap,
            secure = secure,
            latencyMs = captureMs,
        )
    }

    /** Compatibility entry point for existing non-Gen6 capture call sites. */
    fun capture(displayId: Int, excluded: List<SurfaceControl>, scale: Float): Bitmap? =
        captureResult(displayId, excluded, scale)
            ?.takeIf { !it.secure }
            ?.bitmap'''
    return replace_once(text, old, new, "secure-aware Shizuku capture result")

def patch_accessibility_xml(text: str) -> str:
    return replace_once(
        text,
        '''    android:accessibilityFeedbackType="feedbackGeneric"\n    android:canTakeScreenshot="true"\n    android:notificationTimeout="1000"''',
        '''    android:accessibilityFeedbackType="feedbackGeneric"\n    android:accessibilityEventTypes="typeWindowStateChanged"\n    android:canTakeScreenshot="true"\n    android:notificationTimeout="100"''',
        "accessibility events",
    )


def self_test():
    patch_build('versionCode = 42\nversionName = "5.0.0-beta1-zfold7"')
    patch_snapshot_cache('''    fun ageMs(innerPanel: Boolean): Long? = entries[innerPanel]?.let { SystemClock.uptimeMillis() - it.at }\n}''')
    patch_frame_store('''    fun current(\n        cycle: Fold7CycleEnvelope.CloseCycle,''')
    patch_accessibility_xml('''    android:accessibilityFeedbackType="feedbackGeneric"\n    android:canTakeScreenshot="true"\n    android:notificationTimeout="1000"''')

    surface_marker = '''/**\n * The system's cross-window blur over the live screen: no screenshot, no\n * capture delay, content keeps moving underneath. SurfaceFlinger blurs a\n'''
    surface_out = patch_surface(surface_marker)
    require("class PublicGlassSurface" in surface_out, "PUBLIC_GLASS surface self-test")
    require("val refreshView: View" in surface_out, "PUBLIC_GLASS refresh handle self-test")
    require("class PrivateFrostSurface" in surface_out, "PRIVATE_FROST surface self-test")

    shell_fixture = '''        var buffer: HardwareBuffer? = null
        try {
            buffer = result.javaClass.getMethod("getHardwareBuffer").invoke(result) as? HardwareBuffer
            val secure = runCatching {
                result.javaClass.getMethod("containsSecureLayers").invoke(result) as Boolean
            }.getOrDefault(false)
            val hardware = result.javaClass.getMethod("asBitmap").invoke(result) as? Bitmap
                ?: throw IllegalStateException("frame not readable")'''
    shell_out = patch_shell_service(shell_fixture)
    require(
        shell_out.index("containsSecureLayers") < shell_out.index("getHardwareBuffer"),
        "secure metadata precedes buffer access",
    )
    require(
        "secure-layer provenance cannot be" in shell_out and
            "getOrElse" in shell_out,
        "secure metadata lookup fails closed",
    )

    bridge_fixture = '''    /** Blocking; call off the main thread. Null if unavailable or the frame had secure content. */
    fun capture(displayId: Int, excluded: List<SurfaceControl>, scale: Float): Bitmap? {
        val b = call(ShellProtocol.CAPTURE) { p ->
            p.writeInt(displayId)
            p.writeInt(excluded.size)
            excluded.forEach { p.writeTypedObject(it, 0) }
            p.writeFloat(scale)
        } ?: return null
        if (!b.getBoolean("ok")) {
            Log.w(
                TAG,
                "shell capture failed: ${b.getString("error")}",
            )
            return null
        }

        val seq =
            captureSeq.incrementAndGet()

        val captureMs =
            b.getLong("ms")

        if (
            seq == 1L ||
            seq % 20L == 0L
        ) {
            Log.i(
                TAG,
                "capture display=$displayId " +
                    "scale=$scale ${captureMs}ms",
            )
        }

        if (b.getBoolean("secure")) {
            return null
        }
        @Suppress("DEPRECATION")
        return b.getParcelable("bitmap")
    }'''
    bridge_out = patch_shizuku_bridge(bridge_fixture)
    require("data class CaptureResult" in bridge_out, "secure-aware capture result self-test")
    require("if (secure) null else" in bridge_out, "secure capture returns no bitmap")

    print("GEN6 ALPHA1 V2 PATCHER SELF-TEST: PASS")

def main():
    if "--self-test" in sys.argv:
        self_test()
        return

    require((ROOT / ".git").exists(), "run from repository root")

    for rel, expected in EXPECTED.items():
        path = ROOT / rel
        require(path.exists(), f"missing baseline file {rel}")
        actual = blob(path)
        require(actual == expected, f"baseline drift {rel}: expected {expected}, got {actual}")

    additions = [
        p.relative_to(PAYLOAD).as_posix()
        for p in PAYLOAD.rglob("*")
        if p.is_file()
    ]
    for rel in additions:
        require(not (ROOT / rel).exists(), f"refusing to overwrite Gen6 file {rel}")

    transforms = {
        "app/build.gradle.kts": patch_build,
        "app/src/full/java/com/duoopen/overlay/Fold7DeviceStateObserver.kt": patch_observer,
        "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt": patch_service,
        "app/src/full/java/com/duoopen/overlay/PanelEngine.kt": patch_panel,
        "app/src/full/java/com/duoopen/overlay/FoldSurface.kt": patch_surface,
        "app/src/full/java/com/duoopen/overlay/SnapshotCache.kt": patch_snapshot_cache,
        "app/src/full/java/com/duoopen/overlay/Fold7ContinuityFrameStore.kt": patch_frame_store,
        "app/src/full/res/xml/duo_accessibility.xml": patch_accessibility_xml,
        "app/src/full/java/com/duoopen/shell/ShizukuBridge.kt": patch_shizuku_bridge,
        "app/src/full/java/com/duoopen/shell/DuoShellService.kt": patch_shell_service,
    }

    for rel, fn in transforms.items():
        path = ROOT / rel
        before = path.read_text(encoding="utf-8")
        after = fn(before)
        require(after != before, f"no change produced for {rel}")
        path.write_text(after, encoding="utf-8")
        print(f"Patched {rel}")

    for src in PAYLOAD.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(PAYLOAD)
        dst = ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"Added {rel}")

    print("GEN6 ALPHA1 APPLY: PASS")
    print("Next: git diff --check && ./gradlew testFullDebugUnitTest assembleFullDebug --stacktrace")


if __name__ == "__main__":
    main()
