from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]

def replace_exact(path: Path, old: str, new: str, count: int = 1):
    text = path.read_text()
    actual = text.count(old)
    if actual != count:
        raise SystemExit(f"{path}: expected {count} occurrences, found {actual}: {old[:120]!r}")
    path.write_text(text.replace(old, new, count))

# --- Add new pure Gen5 runtime/test files ---
for src_rel, dst_rel in [
    ("payload_gen5/main/com/duoopen/fold/Fold7VirtualHingeGen5.kt", "app/src/main/java/com/duoopen/fold/Fold7VirtualHingeGen5.kt"),
    ("payload_gen5/main/com/duoopen/fold/Fold7VisualStateLut.kt", "app/src/main/java/com/duoopen/fold/Fold7VisualStateLut.kt"),
    ("payload_gen5/full/com/duoopen/overlay/Fold7RightPaneComposer.kt", "app/src/full/java/com/duoopen/overlay/Fold7RightPaneComposer.kt"),
    ("payload_gen5/test/com/duoopen/fold/Fold7VirtualHingeGen5Test.kt", "app/src/test/java/com/duoopen/fold/Fold7VirtualHingeGen5Test.kt"),
]:
    src = ROOT / src_rel
    dst = ROOT / dst_rel
    if dst.exists():
        raise SystemExit(f"refusing to overwrite pre-existing Gen5 file: {dst_rel}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

# --- Version ---
p = ROOT / "app/build.gradle.kts"
replace_exact(p, 'versionCode = 41', 'versionCode = 42')
replace_exact(p, 'versionName = "4.0.0-alpha1-zfold7"', 'versionName = "5.0.0-beta1-zfold7"')

# --- FoldOverlayService: preserve source-observation time into Gen5 visual clock ---
p = ROOT / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"
replace_exact(
    p,
    """        for (engine in engines.values.toList()) {\n            engine.onHinge(angle)\n        }\n""",
    """        for (engine in engines.values.toList()) {\n            engine.onHinge(\n                angle = angle,\n                observedUptimeMs = last.observedUptimeMs,\n            )\n        }\n""",
    count=1,
)

# --- PanelEngine Gen5 opening integration ---
p = ROOT / "app/src/full/java/com/duoopen/overlay/PanelEngine.kt"
replace_exact(p, "import android.view.Display\n", "import android.view.Choreographer\nimport android.view.Display\nimport android.view.Surface\n")
replace_exact(
    p,
    "import com.duoopen.fold.DuoShader\n",
    "import com.duoopen.fold.DuoShader\nimport com.duoopen.fold.Fold7VirtualHingeGen5\nimport com.duoopen.fold.Fold7VisualStateLut\n",
)

replace_exact(
    p,
    """    /** Explicit CLOSED -> OPEN visual started from the device-state opening edge. */\n    private var continuityOpeningVisual = false\n\n""",
    """    /** Explicit CLOSED -> OPEN visual started from the device-state opening edge. */\n    private var continuityOpeningVisual = false\n\n    /** Gen5 is visual-only: it never owns continuity state or panel authority. */\n    private val gen5VirtualHinge = Fold7VirtualHingeGen5()\n    private val gen5VisualLut = Fold7VisualStateLut()\n    private var gen5FramePosted = false\n    private var gen5FrameCount = 0L\n    private var gen5LastMode: Fold7VirtualHingeGen5.Mode? = null\n    private var gen5RefreshRoot: SurfaceControl? = null\n    private var gen5OwnedOpeningBitmap: Bitmap? = null\n\n    private val gen5FrameCallback =\n        object : Choreographer.FrameCallback {\n            override fun doFrame(frameTimeNanos: Long) {\n                if (\n                    !continuityOpeningVisual ||\n                    phase != Phase.SHOWING ||\n                    !isFold7CoverGeometryNow()\n                ) {\n                    gen5FramePosted = false\n                    return\n                }\n\n                val nowNs = SystemClock.uptimeMillis() * 1_000_000L\n                val effectiveHz =\n                    runCatching { display.mode.refreshRate }\n                        .getOrDefault(60f)\n                        .takeIf { it.isFinite() && it >= 30f }\n                        ?: 60f\n                val frameNs = (1_000_000_000.0 / effectiveHz).toLong()\n                val target = gen5VirtualHinge.targetForFrame(\n                    callbackTimeNs = nowNs,\n                    expectedPresentationTimeNs = nowNs + frameNs,\n                )\n                val visual = gen5VisualLut.stateFor(target.angleDegrees)\n                val tilt =\n                    (visual.rightPaneTiltDegrees *\n                        DuoSettings.config.value.intensity.coerceAtMost(1f))\n                        .coerceIn(0f, DuoShader.MAX_TILT)\n\n                surface?.tilt = tilt\n                gen5FrameCount++\n\n                if (\n                    gen5LastMode != target.mode ||\n                    target.slewLimited ||\n                    gen5FrameCount % GEN5_TELEMETRY_EVERY_N_FRAMES == 0L\n                ) {\n                    com.duoopen.debug.DuoDiagnostics.event(\n                        "gen5-virtual-hinge",\n                        "frame=$gen5FrameCount physical=${hinge.lastAngle} " +\n                            "virtual=${target.angleDegrees} desired=${target.desiredAngleDegrees} " +\n                            "tilt=$tilt mode=${target.mode} confidence=${target.confidence} " +\n                            "ageMs=${target.measurementAgeMs} correction=${target.correctionDegrees} " +\n                            "slewLimited=${target.slewLimited} leadNs=${target.predictedLeadNs} " +\n                            "requestedHz=$GEN5_REQUESTED_HZ effectiveHz=$effectiveHz",\n                    )\n                }\n                gen5LastMode = target.mode\n\n                Choreographer.getInstance().postFrameCallback(this)\n            }\n        }\n\n""",
)

replace_exact(
    p,
    "fun onHinge(angle: Float) {",
    "fun onHinge(\n        angle: Float,\n        observedUptimeMs: Long = SystemClock.uptimeMillis(),\n    ) {",
)

replace_exact(
    p,
    """        if (\n            isFold7CoverGeometryNow() &&\n            continuityCoverOwned\n        ) {\n            lastRawHingeAngle = angle\n            lastHingeMoveMs = SystemClock.uptimeMillis()\n\n            if (\n                !continuityOpeningVisual &&\n                phase != Phase.IDLE\n            ) {\n""",
    """        if (\n            isFold7CoverGeometryNow() &&\n            continuityCoverOwned\n        ) {\n            lastRawHingeAngle = angle\n            val deliveredUptimeMs = SystemClock.uptimeMillis()\n            lastHingeMoveMs = deliveredUptimeMs\n\n            if (continuityOpeningVisual && angle.isFinite()) {\n                val result = gen5VirtualHinge.addSample(\n                    Fold7VirtualHingeGen5.Sample(\n                        sourceTimeNs = observedUptimeMs.coerceAtMost(deliveredUptimeMs) * 1_000_000L,\n                        deliveryTimeNs = deliveredUptimeMs * 1_000_000L,\n                        angleDegrees = angle,\n                    )\n                )\n                if (result.reversal || result.oscillationGuardEntered || result.reacquiring) {\n                    com.duoopen.debug.DuoDiagnostics.event(\n                        "gen5-virtual-hinge",\n                        "sample angle=$angle observed=$observedUptimeMs delivered=$deliveredUptimeMs " +\n                            "reversal=${result.reversal} oscillation=${result.oscillationGuardEntered} " +\n                            "reacquiring=${result.reacquiring}",\n                    )\n                }\n            }\n\n            if (\n                !continuityOpeningVisual &&\n                phase != Phase.IDLE\n            ) {\n""",
)

replace_exact(
    p,
    """        com.duoopen.debug.DuoDiagnostics.event(\n            "cover-opening-visual",\n            "START display=$displayId reason=$reason precise=${hinge.lastAngle}",\n        )\n\n        startEffect(\n            afterSwap = false,\n            startTilt = COVER_OPEN_IMMEDIATE_TILT,\n        )\n""",
    """        val nowNs = SystemClock.uptimeMillis() * 1_000_000L\n        val seed =\n            hinge.lastAngle\n                .takeIf { it.isFinite() && it <= Fold7VirtualHingeGen5.BLIND_SEED_MAX_DEG }\n                ?: Fold7VirtualHingeGen5.CLOSED_SEED_DEG\n        gen5VirtualHinge.startOpening(nowNs, seed)\n        gen5FrameCount = 0L\n        gen5LastMode = null\n\n        com.duoopen.debug.DuoDiagnostics.event(\n            "cover-opening-visual",\n            "START display=$displayId reason=$reason precise=${hinge.lastAngle} seed=$seed gen5=true",\n        )\n\n        recycleGen5OpeningBitmap()\n        val cachedInner =\n            cache.get(\n                innerPanel = true,\n                width = Fold7RightPaneComposer.INNER_WIDTH,\n                height = Fold7RightPaneComposer.INNER_HEIGHT,\n            )\n        val canonicalRight =\n            cachedInner?.let(Fold7RightPaneComposer::fromInner)\n\n        if (canonicalRight != null) {\n            gen5OwnedOpeningBitmap = canonicalRight\n            phase = Phase.CAPTURING\n            present(\n                bitmap = canonicalRight,\n                afterSwap = false,\n                startTilt = COVER_OPEN_IMMEDIATE_TILT,\n                t0 = SystemClock.uptimeMillis(),\n            )\n            com.duoopen.debug.DuoDiagnostics.event(\n                "gen5-split-pane",\n                "opening bootstrap uses cached canonical right pane " +\n                    "crop=${Fold7RightPaneComposer.RIGHT_PANE_LEFT}..${Fold7RightPaneComposer.RIGHT_PANE_RIGHT}",\n            )\n        } else {\n            startEffect(\n                afterSwap = false,\n                startTilt = COVER_OPEN_IMMEDIATE_TILT,\n            )\n            com.duoopen.debug.DuoDiagnostics.event(\n                "gen5-split-pane",\n                "canonical right pane unavailable; falling back to current cover capture",\n            )\n        }\n""",
)

replace_exact(
    p,
    """        continuityOpeningVisual = false\n        captureGen++\n\n        if (\n""",
    """        continuityOpeningVisual = false\n        captureGen++\n        stopGen5OpeningClock()\n\n        if (\n""",
    count=1,
)

replace_exact(
    p,
    """        restArmed = true\n        panelSwitched = false\n\n        com.duoopen.debug.DuoDiagnostics.event(\n            "cover-opening-visual",\n            "END display=$displayId reason=$reason precise=${hinge.lastAngle}",\n        )\n""",
    """        restArmed = true\n        panelSwitched = false\n        recycleGen5OpeningBitmap()\n\n        com.duoopen.debug.DuoDiagnostics.event(\n            "cover-opening-visual",\n            "END display=$displayId reason=$reason precise=${hinge.lastAngle} gen5=true",\n        )\n""",
)

old_show = """        follower = TiltFollower { t ->\n            created.tilt = t\n            if (t < DuoShader.FLAT_EPSILON && !demoRunning) dismiss(fadeMs = FADE_OUT_FLAT_MS)\n        }.also {\n            it.snap(startTilt)\n\n            if (\n                hinge.externalActive &&\n                easeTo == null\n            ) {\n                it.tauS =\n                    SAMSUNG_LIVE_TAU_S\n            }\n        }\n        lastHingeMoveMs = SystemClock.uptimeMillis()\n\n        val explicitOpeningVisual =\n            continuityOpeningVisual &&\n                isFold7CoverGeometryNow()\n\n        val explicitOpeningPeak =\n            DuoShader.MAX_TILT *\n                config.intensity.coerceAtMost(1f)\n\n        timedResolve =\n            easeTo != null ||\n                explicitOpeningVisual\n\n        when {\n            explicitOpeningVisual -> {\n                follower?.tauS =\n                    CONTINUITY_OPENING_TAU_S\n\n                follower?.setTarget(\n                    explicitOpeningPeak\n                )\n\n                /*\n                 * Lifetime is owned by FoldOverlayService, not this renderer.\n                 * The service owns the semantic opening latch and its one-shot\n                 * timeout, so display callbacks cannot restart a timed-out\n                 * animation behind our back.\n                 */\n            }\n\n            easeTo != null -> {\n"""
new_show = """        val explicitOpeningVisual =\n            continuityOpeningVisual &&\n                isFold7CoverGeometryNow()\n\n        if (explicitOpeningVisual) {\n            follower?.cancel()\n            follower = null\n            startGen5OpeningFrameLoop()\n            (created as? SnapshotSurface)?.let(::requestGen5RefreshRate)\n        } else {\n            follower = TiltFollower { t ->\n                created.tilt = t\n                if (t < DuoShader.FLAT_EPSILON && !demoRunning) dismiss(fadeMs = FADE_OUT_FLAT_MS)\n            }.also {\n                it.snap(startTilt)\n\n                if (\n                    hinge.externalActive &&\n                    easeTo == null\n                ) {\n                    it.tauS =\n                        SAMSUNG_LIVE_TAU_S\n                }\n            }\n        }\n        lastHingeMoveMs = SystemClock.uptimeMillis()\n\n        timedResolve =\n            easeTo != null ||\n                explicitOpeningVisual\n\n        when {\n            explicitOpeningVisual -> {\n                /*\n                 * Gen5 renders directly at vsync from the visual-only virtual\n                 * hinge. Do not feed the predicted angle back through the\n                 * legacy TiltFollower; double smoothing would reintroduce the\n                 * latency this path is designed to remove.\n                 */\n            }\n\n            easeTo != null -> {\n"""
replace_exact(p, old_show, new_show)

helpers = r'''
    private fun startGen5OpeningFrameLoop() {
        if (gen5FramePosted) return
        gen5FramePosted = true
        Choreographer.getInstance().postFrameCallback(gen5FrameCallback)
    }

    private fun stopGen5OpeningClock() {
        if (gen5FramePosted) {
            Choreographer.getInstance().removeFrameCallback(gen5FrameCallback)
        }
        gen5FramePosted = false
        gen5VirtualHinge.stop()
        clearGen5RefreshRate()
    }

    private fun requestGen5RefreshRate(snapshot: SnapshotSurface) {
        snapshot.view.post {
            if (!continuityOpeningVisual) return@post
            val root = rootSurfaceControl(snapshot.view)
            if (root == null) {
                com.duoopen.debug.DuoDiagnostics.event(
                    "gen5-refresh",
                    "request skipped display=$displayId rootSurfaceControl=null",
                )
                return@post
            }

            val supported =
                runCatching {
                    display.supportedModes.joinToString(",") {
                        "${it.modeId}:${it.refreshRate}"
                    }
                }.getOrDefault("unknown")

            runCatching {
                SurfaceControl.Transaction()
                    .setFrameRate(
                        root,
                        GEN5_REQUESTED_HZ,
                        Surface.FRAME_RATE_COMPATIBILITY_DEFAULT,
                        Surface.CHANGE_FRAME_RATE_ONLY_IF_SEAMLESS,
                    )
                    .apply()
                gen5RefreshRoot = root
            }.onSuccess {
                com.duoopen.debug.DuoDiagnostics.event(
                    "gen5-refresh",
                    "requested=$GEN5_REQUESTED_HZ seamlessOnly=true " +
                        "effective=${display.mode.refreshRate} supported=[$supported]",
                )
            }.onFailure {
                com.duoopen.debug.DuoDiagnostics.event(
                    "gen5-refresh",
                    "request failed error=${it.javaClass.simpleName}:${it.message} " +
                        "effective=${display.mode.refreshRate} supported=[$supported]",
                )
            }
        }
    }

    private fun clearGen5RefreshRate() {
        val root = gen5RefreshRoot ?: return
        gen5RefreshRoot = null
        runCatching {
            SurfaceControl.Transaction()
                .setFrameRate(
                    root,
                    0f,
                    Surface.FRAME_RATE_COMPATIBILITY_DEFAULT,
                    Surface.CHANGE_FRAME_RATE_ONLY_IF_SEAMLESS,
                )
                .apply()
        }
        com.duoopen.debug.DuoDiagnostics.event(
            "gen5-refresh",
            "cleared requestedHz=$GEN5_REQUESTED_HZ effective=${runCatching { display.mode.refreshRate }.getOrNull()}",
        )
    }

    private fun recycleGen5OpeningBitmap() {
        val bitmap = gen5OwnedOpeningBitmap
        gen5OwnedOpeningBitmap = null
        if (bitmap != null && !bitmap.isRecycled) {
            runCatching { bitmap.recycle() }
        }
    }

'''
replace_exact(p, "    private fun clearOverlayState() {\n", helpers + "    private fun clearOverlayState() {\n")

replace_exact(
    p,
    """    fun destroy() {\n        captureGen++ // orphan any capture in flight\n        removeOverlay()\n        Log.i(TAG, "engine display=$displayId destroyed")\n    }\n""",
    """    fun destroy() {\n        captureGen++ // orphan any capture in flight\n        stopGen5OpeningClock()\n        removeOverlay()\n        recycleGen5OpeningBitmap()\n        Log.i(TAG, "engine display=$displayId destroyed")\n    }\n""",
)

replace_exact(
    p,
    """        const val COVER_OPEN_IMMEDIATE_TILT = 0.15f\n        const val CONTINUITY_OPENING_TAU_S = 0.09f\n""",
    """        const val COVER_OPEN_IMMEDIATE_TILT = 0.15f\n        const val GEN5_REQUESTED_HZ = 120f\n        const val GEN5_TELEMETRY_EVERY_N_FRAMES = 4L\n""",
)


# Legacy 1.3.16 workflow retirement is human-committed by the import package.
# CI intentionally never edits .github/workflows/** because GITHUB_TOKEN lacks workflows permission.

# --- Simplified app home UI ---
home = ROOT / "app/src/main/java/com/duoopen/ui/HomePreview.kt"
home.write_text(r'''package com.duoopen.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.roundToInt

private val Glass = Color.White.copy(alpha = 0.14f)
private val GlassEdge = Color.White.copy(alpha = 0.22f)
private val Dim = Color.White.copy(alpha = 0.76f)

/** Product-facing Duo Open home screen; engineering controls live in Settings. */
@Composable
fun HomePreview(
    image: ImageBitmap?,
    hingeAngle: Float,
    paneTilt: Float,
    simulated: Boolean,
    wallpaperActive: Boolean,
    overlayEnabled: Boolean,
    shizukuReady: Boolean,
    onTest: () -> Unit,
    onSetWallpaper: () -> Unit,
    onTune: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val ready = overlayEnabled && shizukuReady
    val status = when {
        !overlayEnabled -> "Setup needed"
        !shizukuReady -> "Shizuku needed"
        hingeAngle.isNaN() -> "Waiting for hinge"
        else -> "Ready"
    }
    val detail = when {
        !overlayEnabled -> "Turn on Duo Open accessibility to enable full-screen continuity."
        !shizukuReady -> "Start or authorize Shizuku for Fold7 panel control and precise hinge data."
        hingeAngle.isNaN() -> "The service is running; waiting for a hinge sample."
        simulated -> "Simulation active · ${hingeAngle.roundToInt()}°"
        else -> "Fold7 continuity active · hinge ${hingeAngle.roundToInt()}°"
    }

    Box(modifier.fillMaxSize().background(Color(0xFF0D0A1C))) {
        if (image != null) {
            Image(
                bitmap = image,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )
        }
        Box(
            Modifier
                .fillMaxSize()
                .background(
                    Brush.verticalGradient(
                        0f to Color.Black.copy(alpha = 0.52f),
                        0.45f to Color.Black.copy(alpha = 0.18f),
                        1f to Color.Black.copy(alpha = 0.58f),
                    )
                )
        )

        Column(
            Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .navigationBarsPadding()
                .padding(horizontal = 24.dp, vertical = 20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                "DUO OPEN",
                color = Color.White,
                fontSize = 16.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 3.sp,
            )
            Text(
                "Fold continuity for Galaxy Z Fold7",
                color = Dim,
                fontSize = 14.sp,
            )

            Spacer(Modifier.weight(1f))

            Column(
                Modifier
                    .widthIn(max = 440.dp)
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(28.dp))
                    .background(Glass)
                    .border(1.dp, GlassEdge, RoundedCornerShape(28.dp))
                    .padding(horizontal = 22.dp, vertical = 24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(
                    status,
                    color = Color.White,
                    fontSize = 34.sp,
                    fontWeight = FontWeight.SemiBold,
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    detail,
                    color = Dim,
                    fontSize = 14.sp,
                    textAlign = TextAlign.Center,
                )
                Spacer(Modifier.height(18.dp))
                Text(
                    "Accessibility ${if (overlayEnabled) "ON" else "OFF"}  ·  " +
                        "Shizuku ${if (shizukuReady) "READY" else "OFF"}  ·  " +
                        "Visual ${if (paneTilt < 0.05f) "FLAT" else "ACTIVE"}",
                    color = if (ready) Color.White else Dim,
                    fontSize = 12.sp,
                    textAlign = TextAlign.Center,
                )
            }

            Spacer(Modifier.weight(1f))

            Row(
                Modifier.widthIn(max = 440.dp).fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Button(
                    onClick = onTest,
                    enabled = overlayEnabled,
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Color.White,
                        contentColor = Color(0xFF14121F),
                    ),
                ) {
                    Text("Test fold")
                }
                FilledTonalButton(
                    onClick = onTune,
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.filledTonalButtonColors(
                        containerColor = Glass,
                        contentColor = Color.White,
                    ),
                ) {
                    Text("Settings")
                }
            }

            TextButton(onClick = onSetWallpaper) {
                Text(if (wallpaperActive) "Wallpaper settings" else "Set Duo wallpaper")
            }
        }
    }
}
''')

# --- Wire simplified home UI and diagnostics fallback ---
p = ROOT / "app/src/main/java/com/duoopen/ui/DuoApp.kt"
replace_exact(
    p,
    """            wallpaperActive = wallpaperActive,\n            onSetWallpaper = setWallpaper,\n            onTune = {\n                showSheet = true\n            },\n""",
    """            wallpaperActive = wallpaperActive,\n            overlayEnabled = overlayEnabled,\n            shizukuReady = OverlayFeature.shizukuReady(),\n            onTest = {\n                scope.launch {\n                    if (!OverlayFeature.playDemo()) {\n                        Toast.makeText(\n                            context,\n                            "Turn on Duo Open accessibility first",\n                            Toast.LENGTH_SHORT,\n                        ).show()\n                    }\n                }\n            },\n            onSetWallpaper = setWallpaper,\n            onTune = {\n                showSheet = true\n            },\n""",
)

old_send = """                onSendDebugBundle = {\n                    diagnosticUploadStatus =\n                        "Sending diagnostic data…"\n\n                    scope.launch {\n                        val upload =\n                            withContext(\n                                Dispatchers.IO\n                            ) {\n                                runCatching {\n                                    OverlayFeature\n                                        .flushDebugLogs()\n\n                                    val bundle =\n                                        DebugBundleExporter\n                                            .create(\n                                                context.applicationContext\n                                            )\n\n                                    DebugBundleUploader\n                                        .upload(\n                                            context.applicationContext,\n                                            bundle.file,\n                                        )\n                                }\n                            }\n\n                        upload\n                            .onSuccess { receipt ->\n                                diagnosticUploadStatus =\n                                    "Diagnostic received: ${receipt.diagnosticId} · ${receipt.sha256.take(12)}…"\n                            }\n                            .onFailure { error ->\n                                diagnosticUploadStatus =\n                                    "Send failed: ${error.message ?: error.javaClass.simpleName}"\n                            }\n                    }\n                },\n"""
new_send = """                onSendDebugBundle = {\n                    val configured = DebugBundleUploader.isConfigured()\n                    diagnosticUploadStatus =\n                        if (configured) {\n                            "Sending diagnostic data…"\n                        } else {\n                            "Preparing diagnostic bundle to share…"\n                        }\n\n                    scope.launch {\n                        if (!configured) {\n                            val bundle =\n                                withContext(Dispatchers.IO) {\n                                    OverlayFeature.flushDebugLogs()\n                                    DebugBundleExporter.create(context.applicationContext)\n                                }\n                            runCatching {\n                                DebugBundleExporter.share(context, bundle.file)\n                            }.onSuccess {\n                                diagnosticUploadStatus =\n                                    "Upload endpoint is not configured; opened the Android share sheet instead."\n                            }.onFailure { error ->\n                                diagnosticUploadStatus =\n                                    "Share failed: ${error.message ?: error.javaClass.simpleName}"\n                            }\n                            return@launch\n                        }\n\n                        val upload =\n                            withContext(Dispatchers.IO) {\n                                runCatching {\n                                    OverlayFeature.flushDebugLogs()\n                                    val bundle =\n                                        DebugBundleExporter.create(context.applicationContext)\n                                    DebugBundleUploader.upload(\n                                        context.applicationContext,\n                                        bundle.file,\n                                    )\n                                }\n                            }\n\n                        upload\n                            .onSuccess { receipt ->\n                                diagnosticUploadStatus =\n                                    "Diagnostic received: ${receipt.diagnosticId} · ${receipt.sha256.take(12)}…"\n                            }\n                            .onFailure { error ->\n                                diagnosticUploadStatus =\n                                    "Send failed: ${error.message ?: error.javaClass.simpleName}"\n                            }\n                    }\n                },\n"""
replace_exact(p, old_send, new_send)

# --- Keep diagnostics action usable when remote upload is not configured ---
p = ROOT / "app/src/main/java/com/duoopen/ui/ControlSheet.kt"
replace_exact(
    p,
    """            OutlinedButton(\n                onClick =\n                    onSendDebugBundle,\n                enabled =\n                    diagnosticUploadEnabled,\n                modifier =\n                    Modifier.fillMaxWidth(),\n            ) {\n                Text(\n                    "Send diagnostic data"\n                )\n            }\n""",
    """            OutlinedButton(\n                onClick =\n                    onSendDebugBundle,\n                modifier =\n                    Modifier.fillMaxWidth(),\n            ) {\n                Text(\n                    if (diagnosticUploadEnabled) {\n                        "Send diagnostic data"\n                    } else {\n                        "Share diagnostic data"\n                    }\n                )\n            }\n""",
)
replace_exact(
    p,
    """                    } else {\n                        "Diagnostic upload is not configured in this build. Manual export still works."\n                    },\n""",
    """                    } else {\n                        "Remote upload is not configured in this build. This button still creates the same diagnostic ZIP and opens Android sharing."\n                    },\n""",
)

print("GEN5 BETA1 PATCH: APPLIED")
