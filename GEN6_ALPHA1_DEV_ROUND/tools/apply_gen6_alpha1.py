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
    marker = '''/**\n * The system's cross-window blur over the live screen: no screenshot, no\n * capture delay, content keeps moving underneath. SurfaceFlinger blurs a\n'''
    require(marker in text, "private frost insertion")
    private_surface = r'''
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
    val view = PrivateFrostView(context)
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
                        PixelFormat.OPAQUE,
                    ),
                )
            }.onFailure {
                Log.e(TAG, "private frost addView failed", it)
            }.isSuccess
    }

    override var tilt: Float
        get() = view.tilt
        set(value) {
            view.tilt = value
        }

    override fun fadeIn(durationMs: Long) {
        // Base remains opaque from frame zero; only material highlights animate.
        materialAnimator?.cancel()
        materialAnimator =
            ValueAnimator.ofFloat(0f, 1f).apply {
                duration = durationMs
                interpolator = DecelerateInterpolator()
                addUpdateListener {
                    view.materialScale = it.animatedValue as Float
                }
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

            val foldEnergy =
                sin(
                    Math.toRadians(
                        (tilt / DuoShader.MAX_TILT * 90f).toDouble()
                    )
                ).toFloat()

            basePaint.shader =
                LinearGradient(
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

            val sheenAlpha =
                (40f + 82f * foldEnergy * materialScale)
                    .roundToInt()
                    .coerceIn(0, 150)

            sheenPaint.shader =
                LinearGradient(
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

    private companion object {
        const val TAG = "DuoOverlay"
    }
}

'''
    return text.replace(marker, private_surface + marker, 1)


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
        '''    /** Explicit CLOSED -> OPEN visual started from the device-state opening edge. */\n    private var continuityOpeningVisual = false\n\n    /** One-animation privacy fallback for ambiguous capture failure/black frames. */\n    private var gen6ForcePrivateFrost = false''',
        "PanelEngine transient private field",
    )

    marker = '''    private fun startEffect(afterSwap: Boolean, startTilt: Float? = null) {'''
    require(marker in text, "PanelEngine startEffect marker")
    helper = r'''    /** Fail closed when private mode becomes known mid-animation/capture. */
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
    text = text.replace(marker, helper + marker, 1)

    text = replace_once(
        text,
        '''    private fun startEffect(afterSwap: Boolean, startTilt: Float? = null) {\n        if (liveMode()) {''',
        '''    private fun startEffect(afterSwap: Boolean, startTilt: Float? = null) {\n        if (privacyDecision().mode == Fold7GlassMode.PRIVATE_FROST) {\n            showPrivateFrostImmediately(\n                afterSwap = afterSwap,\n                requestedTilt = startTilt,\n                reason = "private-at-effect-start",\n            )\n            return\n        }\n\n        gen6ForcePrivateFrost = false\n\n        if (liveMode()) {''',
        "startEffect privacy gate",
    )

    text = replace_once(
        text,
        '''    private fun capture(gen: Int, attempt: Int, afterSwap: Boolean, startTilt: Float?) {\n        val t0 = SystemClock.uptimeMillis()\n        captureAttempt = attempt''',
        '''    private fun capture(gen: Int, attempt: Int, afterSwap: Boolean, startTilt: Float?) {\n        val t0 = SystemClock.uptimeMillis()\n\n        if (privacyDecision().mode == Fold7GlassMode.PRIVATE_FROST) {\n            showPrivateFrostImmediately(\n                afterSwap = afterSwap,\n                requestedTilt = startTilt,\n                reason = "private-before-capture",\n            )\n            return\n        }\n\n        captureAttempt = attempt''',
        "capture privacy gate",
    )

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

    old_show = '''        val inner = innerPanel\n        val config = DuoSettings.config.value\n        val foldLine = { w: Float, h: Float, c: com.duoopen.settings.DuoConfig -> DuoShader.foldFor(inner, w, h, c) }\n        val created: FoldSurface? = if (bitmap != null) {\n            SnapshotSurface(service, windowManager, bitmap, config, foldLine).takeIf { it.attached }\n        } else {\n            LiveBlurSurface(service, windowManager, config, DuoShader.pxPerMm(service.createDisplayContext(display)), foldLine)\n                .takeIf { it.attached }\n        }'''
    new_show = '''        val inner = innerPanel\n        val privacy = privacyDecision()\n        val baseConfig = DuoSettings.config.value\n        val config =\n            if (\n                privacy.mode == Fold7GlassMode.PUBLIC_GLASS &&\n                continuityOpeningVisual &&\n                isFold7CoverGeometryNow()\n            ) {\n                baseConfig.copy(\n                    blurSpread = minOf(baseConfig.blurSpread, GEN6_PUBLIC_GLASS_MAX_BLUR_SPREAD),\n                    darkening = minOf(baseConfig.darkening, GEN6_PUBLIC_GLASS_MAX_DARKENING),\n                )\n            } else {\n                baseConfig\n            }\n        val foldLine = { w: Float, h: Float, c: com.duoopen.settings.DuoConfig -> DuoShader.foldFor(inner, w, h, c) }\n        val created: FoldSurface? =\n            when {\n                gen6ForcePrivateFrost ||\n                    privacy.mode == Fold7GlassMode.PRIVATE_FROST ->\n                    PrivateFrostSurface(service, windowManager).takeIf { it.attached }\n\n                bitmap != null ->\n                    SnapshotSurface(service, windowManager, bitmap, config, foldLine).takeIf { it.attached }\n\n                else ->\n                    LiveBlurSurface(\n                        service,\n                        windowManager,\n                        config,\n                        DuoShader.pxPerMm(service.createDisplayContext(display)),\n                        foldLine,\n                    ).takeIf { it.attached }\n            }'''
    text = replace_once(text, old_show, new_show, "surface selector")

    text = replace_once(
        text,
        '''        const val MAX_CAPTURE_ATTEMPTS = 3''',
        '''        const val MAX_CAPTURE_ATTEMPTS = 3\n\n        const val GEN6_PUBLIC_GLASS_MAX_BLUR_SPREAD = 0.035f\n        const val GEN6_PUBLIC_GLASS_MAX_DARKENING = 0.0035f''',
        "public glass constants",
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
        '''        deviceStateObserver =\n            Fold7DeviceStateObserver(\n                context = this,\n                handler = handler,\n                onWakeHint = { previousStateId, currentStateId ->\n                    val attempt =\n                        gen6OpeningAttempts.onWakeHint(\n                            previousStateId = previousStateId,\n                            currentStateId = currentStateId,\n                            nowUptimeMs = SystemClock.uptimeMillis(),\n                        )\n\n                    if (attempt != null) {\n                        val reason = "device-state:$previousStateId->$currentStateId"\n                        DuoDiagnostics.event(\n                            "gen6-opening-attempt",\n                            "WAKE_HINT attempt=${attempt.id} serviceEpoch=${attempt.serviceEpoch} " +\n                                "reason=$reason semantic=false precise=${hinge.lastAngle}",\n                        )\n                        com.duoopen.lab.TransitionLab.recordIngressStage(\n                            type = "gen6-wake-hint",\n                            serviceEpoch = serviceEpoch,\n                            presentationAttemptSequence = attempt.id,\n                            reason = reason,\n                        )\n                    }\n                },\n            ) {\n                    previousStateId,\n                    currentStateId,\n                ->''',
        "WakeHint callback",
    )

    semantic_old = '''                if (\n                    beforeOpeningState ==\n                        Fold7ContinuityController.State.NATIVE_COVER &&\n                    continuity.state ==\n                        Fold7ContinuityController.State.OPENING_FROM_CLOSED\n                ) {\n                    gen3Visual.beginOpening('''
    semantic_new = '''                if (\n                    beforeOpeningState ==\n                        Fold7ContinuityController.State.NATIVE_COVER &&\n                    continuity.state ==\n                        Fold7ContinuityController.State.OPENING_FROM_CLOSED\n                ) {\n                    gen6OpeningAttempts\n                        .markSemanticAccepted(continuity.generation)\n                        ?.let { attempt ->\n                            DuoDiagnostics.event(\n                                "gen6-opening-attempt",\n                                "SEMANTIC_ACCEPT attempt=${attempt.id} generation=${continuity.generation}",\n                            )\n                        }\n                    gen3Visual.beginOpening('''
    require(text.count(semantic_old) >= 2, "expected two semantic-opening markers")
    text = text.replace(semantic_old, semantic_new, 2)

    text = replace_once(
        text,
        '''        deviceStateObserver\n            ?.corroborateFoldedRest(\n                nativeCover =\n                    continuity.state ==\n                        Fold7ContinuityController.State.NATIVE_COVER,\n                preciseAngle =\n                    angle,\n            )\n\n        for (engine in engines.values.toList()) {''',
        '''        deviceStateObserver\n            ?.corroborateFoldedRest(\n                nativeCover =\n                    continuity.state ==\n                        Fold7ContinuityController.State.NATIVE_COVER,\n                preciseAngle =\n                    angle,\n            )\n\n        if (\n            continuity.state == Fold7ContinuityController.State.NATIVE_COVER &&\n            angle.isFinite() &&\n            angle <= GEN6_CLOSED_REST_MAX_DEG\n        ) {\n            gen6OpeningAttempts\n                .finish(\n                    reason = "corroborated-closed",\n                    nowUptimeMs = SystemClock.uptimeMillis(),\n                )\n                ?.let { terminal ->\n                    DuoDiagnostics.event(\n                        "gen6-opening-attempt",\n                        "END attempt=${terminal.attempt.id} reason=${terminal.reason}",\n                    )\n                }\n        }\n\n        for (engine in engines.values.toList()) {''',
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
        '''    override fun onAccessibilityEvent(event: AccessibilityEvent?) {\n        val foregroundPackage =\n            event\n                ?.packageName\n                ?.toString()\n                ?.takeIf { it.isNotBlank() && it != packageName }\n                ?: return\n\n        val label =\n            runCatching {\n                val info = packageManager.getApplicationInfo(foregroundPackage, 0)\n                packageManager.getApplicationLabel(info).toString()\n            }.getOrNull()\n\n        val isWorkProfile =\n            Fold7WorkProfileDetector.packageExistsInManagedProfile(\n                context = this,\n                packageName = foregroundPackage,\n            )\n\n        applyPrivacyTransition(\n            transition =\n                privacyRuntime.onForegroundApp(\n                    packageName = foregroundPackage,\n                    appLabel = label,\n                    isWorkProfile = isWorkProfile,\n                ),\n            source = "accessibility-event:${event.eventType}",\n        )\n    }\n\n    private fun onCaptureBlocked(reason: String) {\n        applyPrivacyTransition(\n            transition = privacyRuntime.markCaptureDenied(reason),\n            source = reason,\n        )\n    }\n\n    private fun applyPrivacyTransition(\n        transition: Fold7PrivacyRuntime.Transition,\n        source: String,\n    ) {\n        if (!transition.changed) return\n\n        val current = transition.current\n        DuoDiagnostics.event(\n            "gen6-privacy",\n            "mode=${current.decision.mode} reason=${current.decision.reason} " +\n                "package=${current.packageName} workProfile=${current.isWorkProfile} " +\n                "captureDenied=${current.captureDeniedReason} source=$source",\n        )\n\n        if (current.decision.mode == Fold7GlassMode.PRIVATE_FROST) {\n            snapshots.clear()\n            gen2.frames.clearLatest()\n        }\n\n        for (engine in engines.values.toList()) {\n            engine.onPrivacyDecisionChanged()\n        }\n    }\n\n    override fun onInterrupt() = Unit''',
        "accessibility privacy tracking",
    )

    text = replace_once(
        text,
        '''                    onContinuityFrameChanged = { frameReason ->\n                        reconcileContinuityCoverRendering(\n                            "continuity-frame:$frameReason"\n                        )\n                    },\n                )''',
        '''                    onContinuityFrameChanged = { frameReason ->\n                        reconcileContinuityCoverRendering(\n                            "continuity-frame:$frameReason"\n                        )\n                    },\n                    privacyDecision = { privacyRuntime.current().decision },\n                    onCaptureBlocked = ::onCaptureBlocked,\n                )''',
        "PanelEngine privacy wiring",
    )

    text = replace_once(
        text,
        '''        /** How old a panel's last picture may be and still bridge the next fold. */\n        private const val SNAPSHOT_MAX_AGE_MS = 15 * 60_000L''',
        '''        /** How old a panel's last picture may be and still bridge the next fold. */\n        private const val SNAPSHOT_MAX_AGE_MS = 15 * 60_000L\n\n        private const val GEN6_CLOSED_REST_MAX_DEG = 12f''',
        "closed-rest constant",
    )
    return text


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
    marker = '''/**\n * The system's cross-window blur over the live screen: no screenshot, no\n * capture delay, content keeps moving underneath. SurfaceFlinger blurs a\n'''
    patch_surface(marker)
    print("GEN6 ALPHA1 PATCHER SELF-TEST: PASS")


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
