#!/usr/bin/env python3
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]


def fail(msg: str):
    raise SystemExit(f"ERROR: {msg}")


def replace_exact(path: Path, old: str, new: str, count: int = 1):
    text = path.read_text()
    found = text.count(old)
    if found != count:
        fail(f"{path}: expected {count} occurrences, found {found}: {old[:100]!r}")
    path.write_text(text.replace(old, new, count))


def replace_between(path: Path, start: str, end: str, replacement: str):
    text = path.read_text()
    if text.count(start) != 1:
        fail(f"{path}: expected exactly one start marker {start!r}")
    if text.count(end) != 1:
        fail(f"{path}: expected exactly one end marker {end!r}")
    a = text.index(start)
    b = text.index(end, a + len(start))
    path.write_text(text[:a] + replacement + text[b:])


def replace_first(path: Path, old: str, new: str):
    text = path.read_text()
    if old not in text:
        fail(f"{path}: missing text for first replacement: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1))


def require(path: Path, needle: str, count: int | None = None):
    text = path.read_text()
    actual = text.count(needle)
    if count is None:
        if actual == 0:
            fail(f"{path}: missing required text {needle!r}")
    elif actual != count:
        fail(f"{path}: expected {count} occurrences of {needle!r}, found {actual}")


def copy_payload(src_rel: str, dst_rel: str):
    src = ROOT / "payload" / src_rel
    dst = ROOT / dst_rel
    if not src.is_file():
        fail(f"missing payload {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_test(src_rel: str, dst_rel: str):
    src = ROOT / "test_payload" / src_rel
    dst = ROOT / dst_rel
    if not src.is_file():
        fail(f"missing test payload {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

# ---------------------------------------------------------------------------
# New pure authority + ordered ingress mailbox + focused tests.
# ---------------------------------------------------------------------------
copy_payload(
    "Fold7AngleAuthority.kt",
    "app/src/main/java/com/duoopen/fold/Fold7AngleAuthority.kt",
)
copy_payload(
    "Fold7HingeIngressBatch.kt",
    "app/src/full/java/com/duoopen/overlay/Fold7HingeIngressBatch.kt",
)
copy_payload(
    "HingeAngleSource.kt",
    "app/src/main/java/com/duoopen/fold/HingeAngleSource.kt",
)
copy_test(
    "Fold7AngleAuthorityTest.kt",
    "app/src/test/java/com/duoopen/fold/Fold7AngleAuthorityTest.kt",
)
copy_test(
    "Fold7HingeIngressBatchTest.kt",
    "app/src/test/java/com/duoopen/overlay/Fold7HingeIngressBatchTest.kt",
)

# ---------------------------------------------------------------------------
# WallpaperAngleFeed: preserve reader identity + source timestamps, but make
# HingeAngleSource/Fold7AngleAuthority the only arbitration owner.
# ---------------------------------------------------------------------------
p = ROOT / "app/src/full/java/com/duoopen/shell/WallpaperAngleFeed.kt"

replace_first(
    p,
    "hinge.clearExternal()",
    'hinge.expireExternal("reader-stale")',
)

replace_exact(
    p,
    """        controlHandler.post {\n            if (!isCurrent(session)) {\n                return@post\n            }\n\n            pipeline.startSession()\n""",
    """        controlHandler.post {\n            if (!isCurrent(session)) {\n                return@post\n            }\n\n            hinge.beginExternalSession(session)\n            pipeline.startSession()\n""",
)

replace_exact(
    p,
    """        controlHandler.post {\n            pipeline.invalidateSession()\n            hinge.clearExternal()\n\n            TransitionLab.recordIngressStage(\n""",
    """        controlHandler.post {\n            pipeline.invalidateSession()\n            hinge.revokeExternalSession(\n                session = oldSession,\n                reason = \"feed-stop\",\n            )\n\n            TransitionLab.recordIngressStage(\n""",
)

replace_exact(
    p,
    """        hinge.feedExternal(angle)\n\n        scheduleEndpointBridge(\n            angle = angle,\n""",
    """        hinge.feedExternal(\n            session = session,\n            sequence = sample.sampleSequence,\n            angle = angle,\n            sourceUptimeMs = sourceUptime,\n            receivedUptimeMs = now,\n        )\n\n        scheduleEndpointBridge(\n            session = session,\n            angle = angle,\n""",
)

replace_exact(
    p,
    """    private fun scheduleEndpointBridge(\n        angle: Float,\n""",
    """    private fun scheduleEndpointBridge(\n        session: Long,\n        angle: Float,\n""",
)

replace_exact(
    p,
    """                if (\n                    !running ||\n                    endpointBridgeGeneration != generation ||\n""",
    """                if (\n                    !isCurrent(session) ||\n                    endpointBridgeGeneration != generation ||\n""",
)

replace_exact(
    p,
    """                hinge.feedExternal(target)\n""",
    """                hinge.feedSyntheticExternal(\n                    session = session,\n                    angle = target,\n                    sourceUptimeMs = SystemClock.uptimeMillis(),\n                    reason = \"endpoint-bridge\",\n                )\n""",
)

# ---------------------------------------------------------------------------
# FoldOverlayService: replace latest-only semantic coalescing with bounded,
# ordered source-time replay. Rendering still receives only the final sample in
# each drained batch. Overflow invalidates temporary continuity ownership and
# rearms from latest authoritative geometry/topology.
# ---------------------------------------------------------------------------
p = ROOT / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"

replace_exact(
    p,
    "import java.util.concurrent.atomic.AtomicBoolean",
    "",
)

replace_exact(
    p,
    """    private val controlHandler = Handler(controlThread.looper)\n    private val hingeDeliveryPending = AtomicBoolean(false)\n    @Volatile private var latestControlAngle = Float.NaN\n    private val scope = MainScope()\n""",
    """    private val controlHandler = Handler(controlThread.looper)\n    private val hingeIngress = Fold7HingeIngressBatch()\n    private val scope = MainScope()\n""",
)

replace_exact(
    p,
    """        hinge = HingeAngleSource(\n            context = this,\n            onAngle = ::enqueueHingeFromControl,\n            callbackHandler = controlHandler,\n        )\n""",
    """        hinge = HingeAngleSource(\n            context = this,\n            onAngle = { },\n            onAuthoritativeSample = ::enqueueHingeFromControl,\n            callbackHandler = controlHandler,\n        )\n""",
)

bridge_start = "    /** Latest-only bridge from the serialized Fold7 control thread to main. */"
bridge_end = "    /** Starts engines for panels that lit up, stops those that went dark, then lets each re-evaluate. */"

new_bridge = """    /**\n     * Ordered bridge from the serialized Fold7 control thread to main.\n     * Semantic samples are replayed in source-observation order; render work is\n     * intentionally collapsed to the final angle in each drain.\n     */\n    private fun enqueueHingeFromControl(\n        sample: HingeAngleSource.AuthoritativeSample,\n    ) {\n        val shouldPost =\n            hingeIngress.offer(\n                angle = sample.angle,\n                observedUptimeMs = sample.observedUptimeMs,\n            )\n\n        DuoDiagnostics.event(\n            \"angle-authority\",\n            \"accepted source=${sample.source} angle=${sample.angle} \" +\n                \"observed=${sample.observedUptimeMs} delivered=${sample.deliveredUptimeMs} \" +\n                \"coarse=${sample.coarse} reason=${sample.reason}\",\n        )\n\n        if (!shouldPost) return\n\n        handler.post {\n            drainHingeIngress()\n        }\n    }\n\n    private fun drainHingeIngress() {\n        val drain =\n            hingeIngress.drain()\n\n        if (drain.samples.isEmpty()) return\n\n        val now = SystemClock.uptimeMillis()\n        val first = drain.samples.first()\n        val last = drain.samples.last()\n\n        DuoDiagnostics.event(\n            \"hinge-ingress\",\n            \"batch size=${drain.samples.size} overflow=${drain.overflowed} \" +\n                \"dropped=${drain.droppedSamples} seq=${first.sequence}->${last.sequence} \" +\n                \"oldestAgeMs=${(now - first.observedUptimeMs).coerceAtLeast(0L)} \" +\n                \"newestAgeMs=${(now - last.observedUptimeMs).coerceAtLeast(0L)}\",\n        )\n\n        if (drain.overflowed) {\n            DuoDiagnostics.event(\n                \"hinge-ingress\",\n                \"OVERFLOW fail-closed dropped=${drain.droppedSamples}; \" +\n                    \"revoking temporary continuity authority and resyncing\",\n            )\n\n            continuity.release(\"hinge-ingress-overflow\")\n            if (ShizukuBridge.ready) {\n                continuity.arm()\n            }\n\n            primeContinuityFrameIfNeeded(\"hinge-overflow-resync\")\n            reconcileContinuityCoverRendering(\"hinge-overflow-resync\")\n\n            val latest = hinge.lastAngle\n            if (latest.isFinite()) {\n                gen3Visual.onHinge(latest)\n                deviceStateObserver?.corroborateFoldedRest(\n                    nativeCover =\n                        continuity.state ==\n                            Fold7ContinuityController.State.NATIVE_COVER,\n                    preciseAngle = latest,\n                )\n                for (engine in engines.values.toList()) {\n                    engine.onHinge(latest)\n                }\n            }\n            return\n        }\n\n        for (sample in drain.samples) {\n            val beforeState =\n                continuity.state\n\n            continuity.onHinge(\n                angle = sample.angle,\n                observedUptimeMs = sample.observedUptimeMs,\n            )\n\n            if (\n                beforeState ==\n                    Fold7ContinuityController.State.NATIVE_COVER &&\n                continuity.state ==\n                    Fold7ContinuityController.State.OPENING_FROM_CLOSED\n            ) {\n                gen3Visual.beginOpening(\n                    generation = continuity.generation,\n                    reason = \"authoritative-hinge-opening-edge\",\n                )\n            }\n        }\n\n        val angle = last.angle\n\n        primeContinuityFrameIfNeeded(\n            \"hinge:$angle\"\n        )\n\n        reconcileContinuityCoverRendering(\n            \"hinge:$angle\"\n        )\n\n        gen3Visual.onHinge(\n            angle\n        )\n\n        deviceStateObserver\n            ?.corroborateFoldedRest(\n                nativeCover =\n                    continuity.state ==\n                        Fold7ContinuityController.State.NATIVE_COVER,\n                preciseAngle =\n                    angle,\n            )\n\n        for (engine in engines.values.toList()) {\n            engine.onHinge(angle)\n        }\n    }\n"""
replace_between(p, bridge_start, bridge_end, new_bridge)

# Reset pending semantic ingress on service teardown.
replace_exact(
    p,
    """        scope.cancel()\n        controlThread.quitSafely()\n        super.onDestroy()\n""",
    """        scope.cancel()\n        hingeIngress.reset()\n        controlThread.quitSafely()\n        super.onDestroy()\n""",
)

replace_exact(
    p,
    """    fun angleFeedStatus(): String =\n        angleFeed?.status ?: \"Idle\"\n""",
    """    fun angleFeedStatus(): String =\n        hinge.statusText() + \" · \" + (angleFeed?.status ?: \"Reader idle\")\n\n    fun authoritativeHingeAngle(): Float =\n        hinge.lastAngle\n\n    fun hingeReport(): String =\n        hinge.report()\n""",
)

# Required Fold7 transport: a stale saved toggle must not silently disable geometry.
replace_exact(
    p,
    """        val want =\n            DuoSettings.config.value.shizukuAngle &&\n                ShizukuBridge.ready\n""",
    """        val want =\n            ShizukuBridge.ready\n""",
)

# ---------------------------------------------------------------------------
# Fold7 capture is a product invariant. Shizuku is used whenever it is ready;
# stale saved user toggles must not silently force the slower capture path.
# ---------------------------------------------------------------------------
p = ROOT / "app/src/full/java/com/duoopen/overlay/PanelEngine.kt"
replace_exact(
    p,
    "private fun shellCapture(): Boolean = DuoSettings.config.value.shizukuCapture && ShizukuBridge.ready",
    "private fun shellCapture(): Boolean = ShizukuBridge.ready",
)

# ---------------------------------------------------------------------------
# Coordinator: semantic timing comes from source observation, not main drain.
# ---------------------------------------------------------------------------
p = ROOT / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"
replace_exact(
    p,
    """    fun onHinge(angle: Float) {\n        val decision =\n            controller.onHinge(\n                angle = angle,\n                nowMs = SystemClock.uptimeMillis(),\n                topology = topology(),\n            )\n""",
    """    fun onHinge(\n        angle: Float,\n        observedUptimeMs: Long = SystemClock.uptimeMillis(),\n    ) {\n        val decision =\n            controller.onHinge(\n                angle = angle,\n                nowMs = observedUptimeMs,\n                topology = topology(),\n            )\n""",
)

# ---------------------------------------------------------------------------
# UI bridge: full edition reads the service-authoritative angle. Lite can keep
# its local sensor for wallpaper preview; full no longer runs a duplicate one.
# ---------------------------------------------------------------------------
p = ROOT / "app/src/full/java/com/duoopen/overlay/OverlayFeature.kt"
replace_exact(
    p,
    """    /** Status of the continuous-angle reader, from the running service. */\n    fun angleFeedStatus(): String = FoldOverlayService.instance?.angleFeedStatus() ?: \"Service not running\"\n\n    /** Flush Transition Lab before packaging a user-visible debug export. */\n""",
    """    /** Service-owned authoritative Fold7 geometry. */\n    fun authoritativeHingeAngle(): Float =\n        FoldOverlayService.instance?.authoritativeHingeAngle() ?: Float.NaN\n\n    /** Status of the one authoritative angle owner plus its current transport. */\n    fun angleFeedStatus(): String =\n        FoldOverlayService.instance?.angleFeedStatus() ?: \"Service not running\"\n\n    fun hingeReport(): String =\n        FoldOverlayService.instance?.hingeReport() ?: \"Duo Open accessibility service is not running.\"\n\n    /** Flush Transition Lab before packaging a user-visible debug export. */\n""",
)

p = ROOT / "app/src/lite/java/com/duoopen/overlay/OverlayFeature.kt"
replace_exact(
    p,
    """    fun foldWallpaperActive(context: Context): Boolean = false\n    fun angleFeedStatus(): String = \"\"\n\n    fun flushDebugLogs(): Boolean = true\n""",
    """    fun foldWallpaperActive(context: Context): Boolean = false\n    fun authoritativeHingeAngle(): Float = Float.NaN\n    fun angleFeedStatus(): String = \"Lite edition local sensor\"\n    fun hingeReport(): String = \"Lite edition local sensor\"\n\n    fun flushDebugLogs(): Boolean = true\n""",
)

# ---------------------------------------------------------------------------
# DuoApp: stop constructing a second sensor in the full edition and poll the
# service-owned authoritative angle for preview/diagnostics.
# ---------------------------------------------------------------------------
p = ROOT / "app/src/main/java/com/duoopen/ui/DuoApp.kt"
replace_exact(
    p,
    """    var hingeAngle by remember { mutableFloatStateOf(Float.NaN) }\n    val hinge =\n        remember {\n            HingeAngleSource(\n                context = context.applicationContext,\n                onAngle = { angle ->\n                    hingeAngle = angle\n                },\n            )\n        }\n\n    DisposableEffect(hinge) {\n        hinge.start()\n        onDispose {\n            hinge.stop()\n        }\n    }\n\n    var simulate by\n        rememberSaveable {\n            mutableStateOf(\n                hinge.sensor == null\n            )\n        }\n""",
    """    var localHingeAngle by remember { mutableFloatStateOf(Float.NaN) }\n    val hinge =\n        remember {\n            if (OverlayFeature.AVAILABLE) {\n                null\n            } else {\n                HingeAngleSource(\n                    context = context.applicationContext,\n                    onAngle = { angle ->\n                        localHingeAngle = angle\n                    },\n                )\n            }\n        }\n\n    DisposableEffect(hinge) {\n        hinge?.start()\n        onDispose {\n            hinge?.stop()\n        }\n    }\n\n    val serviceHingeAngle by\n        produceState(\n            Float.NaN,\n            OverlayFeature.AVAILABLE,\n        ) {\n            if (!OverlayFeature.AVAILABLE) {\n                value = Float.NaN\n                return@produceState\n            }\n            while (true) {\n                value = OverlayFeature.authoritativeHingeAngle()\n                kotlinx.coroutines.delay(50)\n            }\n        }\n\n    var simulate by\n        rememberSaveable {\n            mutableStateOf(\n                !OverlayFeature.AVAILABLE && hinge?.sensor == null\n            )\n        }\n""",
)

replace_exact(
    p,
    """    val angle =\n        if (\n            simulate ||\n            hinge.sensor == null\n        ) {\n            simulatedAngle\n        } else {\n            hingeAngle\n        }\n""",
    """    val angle =\n        if (OverlayFeature.AVAILABLE) {\n            serviceHingeAngle\n        } else if (\n            simulate ||\n            hinge?.sensor == null\n        ) {\n            simulatedAngle\n        } else {\n            localHingeAngle\n        }\n""",
)

replace_exact(
    p,
    """    val onCover =\n        !simulate &&\n            hinge.sensor != null &&\n            !context.display.isInnerPanel()\n""",
    """    val onCover =\n        if (OverlayFeature.AVAILABLE) {\n            !context.display.isInnerPanel()\n        } else {\n            !simulate &&\n                hinge?.sensor != null &&\n                !context.display.isInnerPanel()\n        }\n""",
)

# ---------------------------------------------------------------------------
# ControlSheet: nullable local sensor. Full edition displays service truth and
# hides simulation (which would otherwise create a second geometry model).
# ---------------------------------------------------------------------------
p = ROOT / "app/src/main/java/com/duoopen/ui/ControlSheet.kt"
replace_exact(p, "hinge: HingeAngleSource,", "hinge: HingeAngleSource?,")

# Fold7 exposes one validated renderer, not a user-selectable live-blur engine.
replace_between(
    p,
    """            if (overlayAvailable) {\n                Divider()\n                Section(\n                    \"How it's drawn\",""",
    """            Divider()\n            Section(\"Look\")""",
    """            if (overlayAvailable) {\n                Divider()\n                Section(\n                    \"Glass renderer\",\n                    \"Fold7 uses one deterministic frozen-frame AGSL glass path.\",\n                )\n                Hint(\n                    \"Cross-window live blur is disabled on Fold7 because field testing showed unreliable attachment and weaker physical-glass geometry.\"\n                )\n            }\n\n""",
)

# Shizuku capture and FoldInteractive fallback are required infrastructure, not
# optional effect switches. Keep only status/setup controls.
replace_between(
    p,
    """                if (shizukuReady) {""",
    """            }\n\n            Divider()\n\n            Section(\n                \"Hinge sensor\",""",
    """                if (shizukuReady) {\n                    Spacer(\n                        Modifier.height(8.dp)\n                    )\n\n                    Hint(\n                        \"Fold7 capture and precise-angle transport are enabled automatically while Shizuku is ready.\"\n                    )\n\n                    Spacer(\n                        Modifier.height(6.dp)\n                    )\n\n                    Hint(\n                        if (foldWallpaperActive) {\n                            angleFeedStatus()\n                        } else {\n                            \"Samsung Fold interactive wallpaper is still the temporary precise-angle fallback. Set it as the home wallpaper, then return here. \" +\n                                angleFeedStatus()\n                        },\n                        warn = !foldWallpaperActive,\n                    )\n\n                    if (!foldWallpaperActive) {\n                        TextButton(\n                            onClick = onOpenWallpaperSettings\n                        ) {\n                            Text(\"Open wallpaper settings\")\n                        }\n                    }\n                }\n\n""",
)
replace_exact(p, """    val hasSensor =\n        hinge.sensor != null\n""", """    val hasSensor =\n        hinge?.sensor != null\n""")
replace_exact(
    p,
    """    val sensorStatus by\n        produceState(\n            hinge.statusText(),\n            hinge,\n        ) {\n            while (true) {\n                delay(250)\n                value =\n                    hinge.statusText()\n            }\n        }\n""",
    """    val sensorStatus by\n        produceState(\n            hinge?.statusText() ?: angleFeedStatus(),\n            hinge,\n        ) {\n            while (true) {\n                delay(250)\n                value =\n                    hinge?.statusText() ?: angleFeedStatus()\n            }\n        }\n""",
)
replace_exact(p, "hinge.isCoarse", "hinge?.isCoarse == true")
replace_exact(
    p,
    "hinge.report()",
    "hinge?.report() ?: angleFeedStatus()",
)
# Full Fold7 build no longer exposes simulation as a production control.
replace_exact(
    p,
    """            Row(\n                verticalAlignment =\n                    Alignment.CenterVertically\n            ) {\n                Column(\n                    Modifier.weight(1f)\n                ) {\n                    Text(\n                        \"Simulate the hinge\",\n                        style =\n                            MaterialTheme\n                                .typography\n                                .titleSmall,\n                    )\n\n                    Hint(\n                        \"Drive the preview above with a slider instead of the real hinge.\"\n                    )\n                }\n\n                Switch(\n                    checked =\n                        simulate,\n                    onCheckedChange =\n                        onSimulateChange,\n                    enabled =\n                        hasSensor,\n                )\n            }\n\n            if (simulate) {\n                LabeledSlider(\n                    label = \"Hinge angle\",\n                    hint = null,\n                    valueText =\n                        \"${simulatedAngle.roundToInt()}°\",\n                    value =\n                        simulatedAngle,\n                    onValueChange =\n                        onSimulatedAngleChange,\n                    range =\n                        60f..180f,\n                )\n            }\n""",
    """            if (!overlayAvailable) {\n                Row(\n                    verticalAlignment =\n                        Alignment.CenterVertically\n                ) {\n                    Column(\n                        Modifier.weight(1f)\n                    ) {\n                        Text(\n                            \"Simulate the hinge\",\n                            style =\n                                MaterialTheme\n                                    .typography\n                                    .titleSmall,\n                        )\n\n                        Hint(\n                            \"Drive the wallpaper preview with a slider instead of the real hinge.\"\n                        )\n                    }\n\n                    Switch(\n                        checked =\n                            simulate,\n                        onCheckedChange =\n                            onSimulateChange,\n                        enabled =\n                            hasSensor,\n                    )\n                }\n\n                if (simulate) {\n                    LabeledSlider(\n                        label = \"Hinge angle\",\n                        hint = null,\n                        valueText =\n                            \"${simulatedAngle.roundToInt()}°\",\n                        value =\n                            simulatedAngle,\n                        onValueChange =\n                            onSimulatedAngleChange,\n                        range =\n                            60f..180f,\n                    )\n                }\n            }\n""",
)

# ---------------------------------------------------------------------------
# Fold7 glass renderer: align producer and AGSL to the same 60-degree optical
# domain and force bilinear sampling for BitmapShader -> RuntimeShader inputs.
# ---------------------------------------------------------------------------
p = ROOT / "app/src/main/java/com/duoopen/fold/DuoShader.kt"
replace_exact(p, "    const val MAX_TILT = 89.5f\n", "    const val MAX_TILT = 60f\n")

for rel in [
    "app/src/full/java/com/duoopen/overlay/FoldOverlayView.kt",
]:
    p = ROOT / rel
    text = p.read_text()
    old1 = "BitmapShader(snapshot, Shader.TileMode.DECAL, Shader.TileMode.DECAL)"
    if old1 in text:
        text = text.replace(
            old1,
            old1 + ".apply { setFilterMode(BitmapShader.FILTER_MODE_LINEAR) }",
        )
    old2 = "BitmapShader(bitmap, Shader.TileMode.DECAL, Shader.TileMode.DECAL)"
    if old2 in text:
        text = text.replace(
            old2,
            old2 + ".apply { setFilterMode(BitmapShader.FILTER_MODE_LINEAR) }",
        )
    p.write_text(text)

# ---------------------------------------------------------------------------
# Version bump.
# ---------------------------------------------------------------------------
p = ROOT / "app/build.gradle.kts"
replace_exact(p, "        versionCode = 39\n", "        versionCode = 40\n")
replace_exact(p, '        versionName = "3.0.0-alpha2-zfold7"\n', '        versionName = "3.0.0-alpha3-zfold7"\n')

# ---------------------------------------------------------------------------
# Fail-closed postconditions.
# ---------------------------------------------------------------------------
require(ROOT / "app/src/main/java/com/duoopen/fold/HingeAngleSource.kt", "Fold7AngleAuthority()", 1)
require(ROOT / "app/src/main/java/com/duoopen/fold/HingeAngleSource.kt", "public shadow", None)
require(ROOT / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt", "Fold7HingeIngressBatch()", 1)
require(ROOT / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt", "OVERFLOW fail-closed", 1)
require(ROOT / "app/src/full/java/com/duoopen/overlay/PanelEngine.kt", "private fun shellCapture(): Boolean = ShizukuBridge.ready", 1)
require(ROOT / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt", "observedUptimeMs", None)
require(ROOT / "app/src/full/java/com/duoopen/shell/WallpaperAngleFeed.kt", "hinge.feedExternal(\n            session = session", 1)
require(ROOT / "app/src/full/java/com/duoopen/shell/WallpaperAngleFeed.kt", "hinge.feedSyntheticExternal", 1)
require(ROOT / "app/src/main/java/com/duoopen/fold/DuoShader.kt", "const val MAX_TILT = 60f", 1)
require(ROOT / "app/src/full/java/com/duoopen/overlay/FoldOverlayView.kt", "FILTER_MODE_LINEAR", None)
require(ROOT / "app/src/main/java/com/duoopen/ui/DuoApp.kt", "OverlayFeature.authoritativeHingeAngle()", 1)
require(ROOT / "app/src/main/java/com/duoopen/ui/ControlSheet.kt", "if (!overlayAvailable)", None)
require(ROOT / "app/src/main/java/com/duoopen/ui/ControlSheet.kt", "Glass renderer", 1)
for forbidden_ui in ["Live blur", "Fast live capture", "Continuous hinge angle (Samsung)"]:
    if forbidden_ui in (ROOT / "app/src/main/java/com/duoopen/ui/ControlSheet.kt").read_text():
        fail(f"ControlSheet: obsolete Fold7 production toggle survived: {forbidden_ui}")
require(ROOT / "app/build.gradle.kts", "versionCode = 40", 1)
require(ROOT / "app/build.gradle.kts", 'versionName = "3.0.0-alpha3-zfold7"', 1)

# Old semantic-loss bridge must be gone.
for path, forbidden in [
    (ROOT / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt", "latestControlAngle"),
    (ROOT / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt", "hingeDeliveryPending"),
    (ROOT / "app/src/main/java/com/duoopen/fold/HingeAngleSource.kt", "EXTERNAL_STALE_MS"),
]:
    if forbidden in path.read_text():
        fail(f"{path}: forbidden Alpha2 mechanism survived: {forbidden}")

print("GEN3 ALPHA3 PATCH: PASS")
