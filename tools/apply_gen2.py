#!/usr/bin/env python3
"""Apply Duo Open Gen2 foundation/integration to the exact audited baseline.

This script intentionally fails closed on baseline or anchor drift. It does not
commit or push. Root remains responsible for reviewing the diff, running Gradle,
field validating on Fold7, and committing only if all gates pass.
"""
from __future__ import annotations
import argparse
import hashlib
import shutil
import subprocess
from pathlib import Path

BASELINE = "586c308649258145b3da9b5ea27b726a6fb3647a"
EXPECTED_BLOBS = {
    "app/build.gradle.kts": "0ae3ead1edc3e181db0d4608edb108ed353df2cc",
    "app/src/main/java/com/duoopen/fold/HingeAngleSource.kt": "5e1caaad679d9691a60c713162448b2cfda7a3a3",
    "app/src/full/java/com/duoopen/shell/ShellProtocol.kt": "b262a5c1944fda19504c72c4a49366d44b7c79b0",
    "app/src/full/java/com/duoopen/shell/ShizukuBridge.kt": "0260da09c6d8ae80f3a21dbec041b987e4f75254",
    "app/src/full/java/com/duoopen/shell/DuoShellService.kt": "24a5357ff6c4eedfef69a7e5d8b2ee4fa18e7de3",
    "app/src/full/java/com/duoopen/shell/WallpaperAngleFeed.kt": "32a6fe6d2f68925737e4d3a518e18f7686d17458",
    "app/src/full/java/com/duoopen/lab/TransitionEvent.kt": "b4d0c72110d53106f29f54b47d6f9894d88212e5",
    "app/src/full/java/com/duoopen/lab/TransitionLab.kt": "ae60f8cfaff1632c2676266d7fad203e4f101893",
    "app/src/full/java/com/duoopen/lab/TransitionSessionWriter.kt": "f21f45bea716d486d4e7f31f15bd611b55172c2b",
    "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt": "0a6c3e85d0b3f4531eac504170be0e38a8a290de",
    "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt": "50b602a32d70ac00e0b1fec251fab1e55c53a999",
    "app/src/full/java/com/duoopen/overlay/PanelEngine.kt": "582c7ea965405a07b2dea4ea9277a86d1639e5f8",
    "app/src/full/java/com/duoopen/overlay/DisplayMirrorHost.kt": "810edd929ab020b32f171ca0338acf975d91fd92",
    "app/src/full/java/com/duoopen/overlay/SnapshotCache.kt": "4b1b6bb9837de4fb77cdc1bdc26f4a39aa72ab26",
    "app/src/full/java/com/duoopen/lab/TransitionModel.kt": "5d15fa27f8c156332df590a161dab51ceb4b2c32",
    "app/src/full/java/com/duoopen/lab/SurfaceTransactionProbe.kt": "71887824f2ebf0c60d62724ee0bbd25f35ff1078",
    ".github/workflows/build-direct-fold7.yml": "a3d25298f292953e212c10b2082b5bb07b0d9fa2",
}

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
OVERLAY = PACKAGE_ROOT / "repo_overlay"


def run(*args: str, cwd: Path) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def git_blob(repo: Path, rel: str) -> str:
    return run("git", "hash-object", rel, cwd=repo)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected anchor exactly once, found {count}")
    return text.replace(old, new, 1)


def replace_between(text: str, start_marker: str, end_marker: str, replacement: str, label: str) -> str:
    if text.count(start_marker) != 1 or text.count(end_marker) < 1:
        raise RuntimeError(f"{label}: function markers not uniquely available")
    start = text.index(start_marker)
    end = text.index(end_marker, start + len(start_marker))
    return text[:start] + replacement + text[end:]


def patch_file(repo: Path, rel: str, transform) -> None:
    p = repo / rel
    before = p.read_text()
    after = transform(before)
    if after == before:
        raise RuntimeError(f"{rel}: transform made no change")
    p.write_text(after)


def copy_overlay(repo: Path) -> None:
    for src in OVERLAY.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(OVERLAY)
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            raise RuntimeError(f"refusing to overwrite existing overlay file: {rel}")
        shutil.copy2(src, dst)


def verify(repo: Path, force: bool) -> None:
    head = run("git", "rev-parse", "HEAD", cwd=repo)
    if head != BASELINE and not force:
        raise RuntimeError(
            f"HEAD drift: expected {BASELINE}, got {head}. Reconcile before applying or use --force only after review."
        )
    for rel, expected in EXPECTED_BLOBS.items():
        actual = git_blob(repo, rel)
        if actual != expected:
            raise RuntimeError(f"blob drift {rel}: expected {expected}, got {actual}")


def patch_version(repo: Path) -> None:
    rel = "app/build.gradle.kts"
    def f(t: str) -> str:
        t = replace_once(t, "versionCode = 34", "versionCode = 35", rel)
        t = replace_once(
            t,
            'versionName = "1.3.29-zfold7-deterministic-early-wake"',
            'versionName = "2.0.0-zfold7-gen2-ownership"',
            rel,
        )
        return t
    patch_file(repo, rel, f)


def patch_protocol(repo: Path) -> None:
    rel = "app/src/full/java/com/duoopen/shell/ShellProtocol.kt"
    def f(t: str) -> str:
        return replace_once(
            t,
            "    const val COVER_PANEL_LEASE_V2 = 15\n",
            "    const val COVER_PANEL_LEASE_V2 = 15\n    const val COVER_PANEL_LEASE_V3 = 16\n",
            rel,
        )
    patch_file(repo, rel, f)


def patch_hinge_source(repo: Path) -> None:
    rel = "app/src/main/java/com/duoopen/fold/HingeAngleSource.kt"
    def f(t: str) -> str:
        t = replace_once(t, "import android.os.Build\n", "import android.os.Build\nimport android.os.Handler\n", rel)
        t = replace_once(
            t,
            "class HingeAngleSource(\n    context: Context,\n    private val onAngle: (Float) -> Unit,\n) : SensorEventListener {",
            "class HingeAngleSource(\n    context: Context,\n    private val onAngle: (Float) -> Unit,\n    private val callbackHandler: Handler? = null,\n) : SensorEventListener {",
            rel,
        )
        t = replace_once(
            t,
            "                sm.registerListener(this, c.sensor, SAMPLING_PERIOD_US)\n",
            "                if (callbackHandler != null) {\n                    sm.registerListener(this, c.sensor, SAMPLING_PERIOD_US, callbackHandler)\n                } else {\n                    sm.registerListener(this, c.sensor, SAMPLING_PERIOD_US)\n                }\n",
            rel,
        )
        return t
    patch_file(repo, rel, f)


def patch_transition_schema(repo: Path) -> None:
    rel = "app/src/full/java/com/duoopen/lab/TransitionEvent.kt"
    def f(t: str) -> str:
        return replace_once(
            t,
            "    val generation: Long? = null,\n\n    val coverLogicalId: Int? = null,",
            "    val generation: Long? = null,\n\n"
            "    // Gen2 immutable ownership / ingress correlation.\n"
            "    val serviceEpoch: Long? = null,\n"
            "    val closeCycleId: Long? = null,\n"
            "    val angleSession: Long? = null,\n"
            "    val pollSequence: Long? = null,\n"
            "    val sampleSequence: Long? = null,\n"
            "    val shellSession: Long? = null,\n"
            "    val shellRevision: Long? = null,\n"
            "    val leaseId: Long? = null,\n"
            "    val leaseEpoch: Long? = null,\n"
            "    val contentLeaseId: Long? = null,\n"
            "    val captureSequence: Long? = null,\n"
            "    val hostEpoch: Long? = null,\n"
            "    val presentationAttemptSequence: Long? = null,\n"
            "    val renderPath: String? = null,\n"
            "    val staleAtCallback: Boolean? = null,\n"
            "    val rejectionReason: String? = null,\n\n"
            "    val coverLogicalId: Int? = null,",
            rel,
        )
    patch_file(repo, rel, f)

    rel = "app/src/full/java/com/duoopen/lab/TransitionSessionWriter.kt"
    def g(t: str) -> str:
        return replace_once(
            t,
            '        put(o, "generation", e.generation)\n\n        put(o, "coverLogicalId", e.coverLogicalId)',
            '        put(o, "generation", e.generation)\n'
            '        put(o, "serviceEpoch", e.serviceEpoch)\n'
            '        put(o, "closeCycleId", e.closeCycleId)\n'
            '        put(o, "angleSession", e.angleSession)\n'
            '        put(o, "pollSequence", e.pollSequence)\n'
            '        put(o, "sampleSequence", e.sampleSequence)\n'
            '        put(o, "shellSession", e.shellSession)\n'
            '        put(o, "shellRevision", e.shellRevision)\n'
            '        put(o, "leaseId", e.leaseId)\n'
            '        put(o, "leaseEpoch", e.leaseEpoch)\n'
            '        put(o, "contentLeaseId", e.contentLeaseId)\n'
            '        put(o, "captureSequence", e.captureSequence)\n'
            '        put(o, "hostEpoch", e.hostEpoch)\n'
            '        put(o, "presentationAttemptSequence", e.presentationAttemptSequence)\n'
            '        put(o, "renderPath", e.renderPath)\n'
            '        put(o, "staleAtCallback", e.staleAtCallback)\n'
            '        put(o, "rejectionReason", e.rejectionReason)\n\n'
            '        put(o, "coverLogicalId", e.coverLogicalId)',
            rel,
        )
    patch_file(repo, rel, g)


def patch_transition_lab(repo: Path) -> None:
    rel = "app/src/full/java/com/duoopen/lab/TransitionLab.kt"
    def f(t: str) -> str:
        t = replace_once(
            t,
            "    fun recordSamsungSample(\n"
            "        angleDegrees: Float,\n"
            "        sourceUptimeMs: Long,\n"
            "        binderArrivalTimeNs: Long,\n"
            "        consumerDeliveryTimeNs: Long =\n"
            "            TransitionClock.nowNs(),\n"
            "    ): HingeSampleRecord? {",
            "    fun recordSamsungSample(\n"
            "        angleDegrees: Float,\n"
            "        sourceUptimeMs: Long,\n"
            "        binderArrivalTimeNs: Long,\n"
            "        consumerDeliveryTimeNs: Long =\n"
            "            TransitionClock.nowNs(),\n"
            "        angleSession: Long? = null,\n"
            "        pollSequence: Long? = null,\n"
            "        sampleSequence: Long? = null,\n"
            "    ): HingeSampleRecord? {",
            rel + ":recordSamsungSample signature",
        )
        t = replace_once(
            t,
            "            record.toEvent(\n                reason =\n                    \"Samsung FoldInteractive logcat sample\",\n            )\n",
            "            record.toEvent(\n                reason =\n                    \"Samsung FoldInteractive logcat sample\",\n            ).copy(\n                angleSession = angleSession,\n                pollSequence = pollSequence,\n                sampleSequence = sampleSequence,\n            )\n",
            rel + ":Samsung event identity",
        )
        marker = "    fun recordSyntheticEndpoint(\n"
        method = '''    /** Gen2 sparse ingress/ownership event with immutable IDs. */\n    fun recordIngressStage(\n        type: String,\n        timeNs: Long = TransitionClock.nowNs(),\n        angleSession: Long? = null,\n        pollSequence: Long? = null,\n        sampleSequence: Long? = null,\n        serviceEpoch: Long? = null,\n        closeCycleId: Long? = null,\n        shellSession: Long? = null,\n        shellRevision: Long? = null,\n        leaseId: Long? = null,\n        leaseEpoch: Long? = null,\n        contentLeaseId: Long? = null,\n        captureSequence: Long? = null,\n        hostEpoch: Long? = null,\n        presentationAttemptSequence: Long? = null,\n        renderPath: String? = null,\n        staleAtCallback: Boolean? = null,\n        rejectionReason: String? = null,\n        reason: String? = null,\n        valueNs: Long? = null,\n        valueFloat: Float? = null,\n    ) {\n        if (level == LabLevel.OFF) return\n        writer?.record(\n            TransitionEvent(\n                timeNs = timeNs,\n                type = type,\n                serviceEpoch = serviceEpoch,\n                closeCycleId = closeCycleId,\n                angleSession = angleSession,\n                pollSequence = pollSequence,\n                sampleSequence = sampleSequence,\n                shellSession = shellSession,\n                shellRevision = shellRevision,\n                leaseId = leaseId,\n                leaseEpoch = leaseEpoch,\n                contentLeaseId = contentLeaseId,\n                captureSequence = captureSequence,\n                hostEpoch = hostEpoch,\n                presentationAttemptSequence = presentationAttemptSequence,\n                renderPath = renderPath,\n                staleAtCallback = staleAtCallback,\n                rejectionReason = rejectionReason,\n                reason = reason,\n                valueNs = valueNs,\n                valueFloat = valueFloat,\n            )\n        )\n    }\n\n'''
        t = replace_once(t, marker, method + marker, rel + ":recordIngressStage")
        return t
    patch_file(repo, rel, f)


def activate_angle_gen2(repo: Path) -> None:
    draft = repo / "GEN2_IMPORT_SUPPORT/WallpaperAngleFeed.Gen2.draft.kt"
    if not draft.is_file():
        raise RuntimeError("Gen2 WallpaperAngleFeed draft missing from audited baseline")
    text = draft.read_text()
    text = text.replace("ShizukuBridge.startAngles(\n", "ShizukuBridge.startAnglesSequenced(\n", 1)
    active = repo / "app/src/full/java/com/duoopen/shell/WallpaperAngleFeed.kt"
    active.write_text(text)


def patch_overlay_service_angle_control(repo: Path) -> None:
    rel = "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"
    def f(t: str) -> str:
        t = replace_once(t, "import android.os.Handler\n", "import android.os.Handler\nimport android.os.HandlerThread\n", rel)
        t = replace_once(t, "import kotlinx.coroutines.flow.asStateFlow\n", "import kotlinx.coroutines.flow.asStateFlow\nimport java.util.concurrent.atomic.AtomicBoolean\n", rel)
        t = replace_once(
            t,
            "    private val handler = Handler(Looper.getMainLooper())\n    private val scope = MainScope()",
            "    private val handler = Handler(Looper.getMainLooper())\n"
            "    private val controlThread = HandlerThread(\"duo-fold7-angle-control\").apply { start() }\n"
            "    private val controlHandler = Handler(controlThread.looper)\n"
            "    private val hingeDeliveryPending = AtomicBoolean(false)\n"
            "    @Volatile private var latestControlAngle = Float.NaN\n"
            "    private val scope = MainScope()",
            rel,
        )
        t = replace_once(
            t,
            "        hinge = HingeAngleSource(this) { onHinge(it) }\n        hinge.start()",
            "        hinge = HingeAngleSource(\n"
            "            context = this,\n"
            "            onAngle = ::enqueueHingeFromControl,\n"
            "            callbackHandler = controlHandler,\n"
            "        )\n"
            "        hinge.start()",
            rel,
        )
        t = replace_once(
            t,
            "        angleFeed = WallpaperAngleFeed(this, handler, hinge)",
            "        angleFeed = WallpaperAngleFeed(\n"
            "            context = this,\n"
            "            mainHandler = handler,\n"
            "            controlHandler = controlHandler,\n"
            "            hinge = hinge,\n"
            "        )",
            rel,
        )
        t = replace_once(t, "?.kickPreciseBurst(\n", "?.kickBurst(\n", rel)
        marker = "    private fun onHinge(angle: Float) {\n"
        method = '''    /** Latest-only bridge from the serialized Fold7 control thread to main. */\n    private fun enqueueHingeFromControl(angle: Float) {\n        latestControlAngle = angle\n        if (!hingeDeliveryPending.compareAndSet(false, true)) return\n\n        handler.post {\n            while (true) {\n                val delivered = latestControlAngle\n                onHinge(delivered)\n                hingeDeliveryPending.set(false)\n\n                if (latestControlAngle == delivered ||\n                    !hingeDeliveryPending.compareAndSet(false, true)\n                ) {\n                    break\n                }\n            }\n        }\n    }\n\n'''
        t = replace_once(t, marker, method + marker, rel + ":coalescer")
        t = replace_once(
            t,
            "        scope.cancel()\n        super.onDestroy()",
            "        scope.cancel()\n        controlThread.quitSafely()\n        super.onDestroy()",
            rel,
        )
        return t
    patch_file(repo, rel, f)



def patch_overlay_service_gen2(repo: Path) -> None:
    rel = "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"
    def f(t: str) -> str:
        t = replace_once(t, "import android.content.IntentFilter\n", "import android.content.IntentFilter\nimport android.graphics.Bitmap\n", rel + ":Bitmap import")
        t = replace_once(t, "import android.os.Looper\n", "import android.os.Looper\nimport android.os.SystemClock\n", rel + ":SystemClock import")
        t = replace_once(
            t,
            "    private val snapshots = SnapshotCache(maxAgeMs = SNAPSHOT_MAX_AGE_MS)\n",
            "    private val snapshots = SnapshotCache(maxAgeMs = SNAPSHOT_MAX_AGE_MS)\n"
            "    private val serviceEpoch =\n"
            "        SystemClock.elapsedRealtimeNanos().takeIf { it > 0L } ?: 1L\n"
            "    private val gen2 =\n"
            "        Fold7Gen2Kernel<Bitmap>(serviceEpoch)\n",
            rel + ":kernel",
        )
        start = "            currentHingeAngle = { hinge.lastAngle },\n            frozenInnerFrame = {\n"
        end = "            onStatus = { message -> _secondaryDisplayStatus.value = message },\n"
        replacement = "            currentHingeAngle = { hinge.lastAngle },\n            gen2 = gen2,\n"
        t = replace_between(t, start, end, replacement, rel + ":coordinator kernel")
        t = replace_once(
            t,
            "                    cache = snapshots,\n",
            "                    cache = snapshots,\n"
            "                    continuityFrames = gen2.frames,\n"
            "                    activeCloseCycle = { gen2.activeCycle },\n",
            rel + ":PanelEngine Gen2 args",
        )
        for event in ("added", "removed", "changed"):
            old = (
                "                scheduleDisplaySync(\n"
                f"                    \"display-{event}:$displayId\"\n"
                "                )"
            )
            new = (
                "                if (::continuity.isInitialized) {\n"
                "                    continuity.onTopologyFastLane(\n"
                f"                        \"display-{event}:$displayId\"\n"
                "                    )\n"
                "                }\n"
                "                scheduleDisplaySync(\n"
                f"                    \"display-{event}:$displayId\"\n"
                "                )"
            )
            t = replace_once(t, old, new, rel + f":fast lane {event}")
        return t
    patch_file(repo, rel, f)


def patch_panel_engine_gen2(repo: Path) -> None:
    rel = "app/src/full/java/com/duoopen/overlay/PanelEngine.kt"
    def f(t: str) -> str:
        t = replace_once(
            t,
            "    /** Last capture of each panel kind, shared by all engines (see [SnapshotCache]). */\n"
            "    private val cache: SnapshotCache,\n"
            ") {",
            "    /** Last capture of each panel kind, shared by all engines (see [SnapshotCache]). */\n"
            "    private val cache: SnapshotCache,\n"
            "    /** Exact-cycle Fold7 continuity authority; separate from generic visual bridging. */\n"
            "    private val continuityFrames: Fold7ContinuityFrameStore<Bitmap>,\n"
            "    private val activeCloseCycle: () -> Fold7CycleEnvelope.CloseCycle?,\n"
            ") {",
            rel + ":constructor",
        )
        marker = "    /** Live blur is intentionally disabled on Fold7. */\n"
        helper = '''    private fun beginContinuityCapture(
        source: Fold7ContinuityFrameStore.Source,
        requestStartedUptimeMs: Long,
    ): Fold7ContinuityFrameStore.CaptureTicket? {
        if (!innerPanel || !deterministicFrozenFrameMode()) return null
        val cycle = activeCloseCycle() ?: return null
        val mode = runCatching { display.mode }.getOrNull() ?: return null
        return continuityFrames.beginCapture(
            cycle = cycle,
            width = mode.physicalWidth,
            height = mode.physicalHeight,
            requestStartedUptimeMs = requestStartedUptimeMs,
            source = source,
        )
    }

'''
        t = replace_once(t, marker, helper + marker, rel + ":capture helper")
        t = replace_once(
            t,
            "        if (shellCapture()) {\n            scope.launch {",
            "        if (shellCapture()) {\n"
            "            val continuityTicket =\n"
            "                beginContinuityCapture(\n"
            "                    source = Fold7ContinuityFrameStore.Source.SHIZUKU,\n"
            "                    requestStartedUptimeMs = t0,\n"
            "                )\n"
            "            scope.launch {",
            rel + ":shell ticket",
        )
        t = replace_once(
            t,
            "                onCaptured(bitmap, afterSwap, startTilt, t0)\n",
            "                onCaptured(\n"
            "                    bitmap = bitmap,\n"
            "                    afterSwap = afterSwap,\n"
            "                    startTilt = startTilt,\n"
            "                    t0 = t0,\n"
            "                    continuityTicket = continuityTicket,\n"
            "                    capturedUptimeMs = t0,\n"
            "                    timestampQuality = Fold7ContinuityFrameStore.TimestampQuality.REQUEST_BOUNDED,\n"
            "                )\n",
            rel + ":shell publish",
        )
        t = replace_once(
            t,
            "    ) {\n        service.takeScreenshot(displayId, service.mainExecutor, object : AccessibilityService.TakeScreenshotCallback {",
            "    ) {\n"
            "        val continuityRequestStarted = SystemClock.uptimeMillis()\n"
            "        val continuityTicket =\n"
            "            beginContinuityCapture(\n"
            "                source = Fold7ContinuityFrameStore.Source.ACCESSIBILITY,\n"
            "                requestStartedUptimeMs = continuityRequestStarted,\n"
            "            )\n"
            "        service.takeScreenshot(displayId, service.mainExecutor, object : AccessibilityService.TakeScreenshotCallback {",
            rel + ":accessibility ticket",
        )
        access_repl = (
            "onCaptured(\n"
            "                        bitmap = bitmap,\n"
            "                        afterSwap = afterSwap,\n"
            "                        startTilt = startTilt,\n"
            "                        t0 = t0,\n"
            "                        continuityTicket = continuityTicket ?: beginContinuityCapture(\n"
            "                            source = Fold7ContinuityFrameStore.Source.ACCESSIBILITY,\n"
            "                            requestStartedUptimeMs = continuityRequestStarted,\n"
            "                        ),\n"
            "                        capturedUptimeMs = result.timestamp,\n"
            "                        timestampQuality = Fold7ContinuityFrameStore.TimestampQuality.EXACT_CAPTURE,\n"
            "                    )"
        )
        needle = "onCaptured(bitmap, afterSwap, startTilt, t0)"
        count = t.count(needle)
        if count != 2:
            raise RuntimeError(f"{rel}: expected 2 accessibility onCaptured anchors after shell patch, found {count}")
        t = t.replace(needle, access_repl, 2)
        old_sig = "    private fun onCaptured(bitmap: Bitmap, afterSwap: Boolean, startTilt: Float?, t0: Long) {\n        cache.put(innerPanel, bitmap)\n"
        new_sig = '''    private fun onCaptured(
        bitmap: Bitmap,
        afterSwap: Boolean,
        startTilt: Float?,
        t0: Long,
        continuityTicket: Fold7ContinuityFrameStore.CaptureTicket?,
        capturedUptimeMs: Long,
        timestampQuality: Fold7ContinuityFrameStore.TimestampQuality,
    ) {
        cache.put(innerPanel, bitmap)

        if (continuityTicket != null) {
            val lease =
                continuityFrames.publish(
                    ticket = continuityTicket,
                    capturedUptimeMs = capturedUptimeMs,
                    completedUptimeMs = SystemClock.uptimeMillis(),
                    timestampQuality = timestampQuality,
                    payload = bitmap,
                )

            com.duoopen.debug.DuoDiagnostics.event(
                "snapshot-transition",
                if (lease != null) {
                    "Gen2 continuity frame published " +
                        "serviceEpoch=${lease.serviceEpoch} closeCycle=${lease.closeCycleId} " +
                        "capture=${lease.captureSequence} content=${lease.contentLeaseId} " +
                        "source=${lease.source} quality=${lease.timestampQuality}"
                } else {
                    "Gen2 continuity frame rejected as stale " +
                        "serviceEpoch=${continuityTicket.serviceEpoch} " +
                        "closeCycle=${continuityTicket.closeCycleId} " +
                        "capture=${continuityTicket.captureSequence}"
                },
            )
        }
'''
        t = replace_once(t, old_sig, new_sig, rel + ":onCaptured signature")
        return t
    patch_file(repo, rel, f)


def patch_bridge_v3(repo: Path) -> None:
    rel = "app/src/full/java/com/duoopen/shell/ShizukuBridge.kt"
    def f(t: str) -> str:
        t = replace_once(
            t,
            "    private val captureSeq =\n        java.util.concurrent.atomic.AtomicLong()\n",
            "    private val captureSeq =\n        java.util.concurrent.atomic.AtomicLong()\n\n"
            "    private val connectionEpochCounter =\n        java.util.concurrent.atomic.AtomicLong()\n\n"
            "    @Volatile\n    var connectionEpoch: Long = 0L\n        private set\n",
            rel,
        )
        t = replace_once(
            t,
            "            service = binder\n            binding = false",
            "            service = binder\n            connectionEpoch = connectionEpochCounter.incrementAndGet()\n            binding = false",
            rel,
        )
        t = replace_once(
            t,
            "            service = null\n            binding = false\n            Log.i(TAG, \"shell service disconnected\")",
            "            service = null\n            connectionEpoch = connectionEpochCounter.incrementAndGet()\n            binding = false\n            Log.i(TAG, \"shell service disconnected\")",
            rel,
        )
        t = replace_once(
            t,
            "    private val deadListener = Shizuku.OnBinderDeadListener { service = null; refresh() }",
            "    private val deadListener = Shizuku.OnBinderDeadListener {\n        service = null\n        connectionEpoch = connectionEpochCounter.incrementAndGet()\n        refresh()\n    }",
            rel,
        )
        t = replace_once(
            t,
            "    fun unbind() {\n        runCatching { Shizuku.unbindUserService(args(), connection, true) }\n        service = null\n    }",
            "    fun unbind() {\n        runCatching { Shizuku.unbindUserService(args(), connection, true) }\n        service = null\n        connectionEpoch = connectionEpochCounter.incrementAndGet()\n    }",
            rel + ":unbind epoch",
        )
        marker = "    fun requestDisplayPower(\n"
        methods = '''    fun prewarmSecondaryDisplayV3(\n        ownerGeneration: Long,\n        reason: String = "prewarm",\n    ): Bundle? =\n        call(ShellProtocol.COVER_PANEL_LEASE_V3) { parcel ->\n            parcel.writeInt(1)\n            parcel.writeLong(0L)\n            parcel.writeLong(0L)\n            parcel.writeLong(0L)\n            parcel.writeLong(ownerGeneration)\n            parcel.writeString(reason)\n        }\n\n    fun ensureSecondaryDisplayHeldV3(\n        token: com.duoopen.overlay.Fold7CoverLeaseSnapshotGate.LeaseToken,\n        reason: String,\n    ): Bundle? =\n        call(ShellProtocol.COVER_PANEL_LEASE_V3) { parcel ->\n            parcel.writeInt(5)\n            parcel.writeLong(token.shellSession)\n            parcel.writeLong(token.leaseId)\n            parcel.writeLong(token.leaseEpoch)\n            parcel.writeLong(token.ownerGeneration)\n            parcel.writeString(reason)\n        }\n\n    fun releaseSecondaryDisplayV3(\n        token: com.duoopen.overlay.Fold7CoverLeaseSnapshotGate.LeaseToken,\n        reason: String,\n    ): Bundle? =\n        call(ShellProtocol.COVER_PANEL_LEASE_V3) { parcel ->\n            parcel.writeInt(2)\n            parcel.writeLong(token.shellSession)\n            parcel.writeLong(token.leaseId)\n            parcel.writeLong(token.leaseEpoch)\n            parcel.writeLong(token.ownerGeneration)\n            parcel.writeString(reason)\n        }\n\n    fun reconcileSecondaryDisplayLeaseV3(\n        shellSession: Long,\n        reason: String,\n    ): Bundle? =\n        call(ShellProtocol.COVER_PANEL_LEASE_V3) { parcel ->\n            parcel.writeInt(3)\n            parcel.writeLong(shellSession)\n            parcel.writeLong(0L)\n            parcel.writeLong(0L)\n            parcel.writeLong(-1L)\n            parcel.writeString(reason)\n        }\n\n    fun secondaryDisplayLeaseStatusV3(\n        shellSession: Long,\n    ): Bundle? =\n        call(ShellProtocol.COVER_PANEL_LEASE_V3) { parcel ->\n            parcel.writeInt(4)\n            parcel.writeLong(shellSession)\n            parcel.writeLong(0L)\n            parcel.writeLong(0L)\n            parcel.writeLong(-1L)\n            parcel.writeString("status")\n        }\n\n'''
        t = replace_once(t, marker, methods + marker, rel + ":V3 methods")
        return t
    patch_file(repo, rel, f)


def patch_shell_v3(repo: Path) -> None:
    rel = "app/src/full/java/com/duoopen/shell/DuoShellService.kt"
    def f(t: str) -> str:
        t = replace_once(
            t,
            "    private val coverPanelLease =\n        Fold7CoverPanelLease()\n",
            "    private val coverPanelLease =\n        Fold7CoverPanelLease()\n\n"
            "    private val shellSession =\n        (SystemClock.elapsedRealtimeNanos().takeIf { it > 0L } ?: 1L)\n\n"
            "    private val coverMutationRevision =\n        java.util.concurrent.atomic.AtomicLong(0L)\n",
            rel,
        )
        t = replace_once(
            t,
            '                    putInt("pid", Process.myPid())\n                    putString("capture",',
            '                    putInt("pid", Process.myPid())\n                    putLong("shellSession", shellSession)\n                    putString("capture",',
            rel,
        )
        marker = "            ShellProtocol.MIRROR_DISPLAY -> {\n"
        handler = '''            ShellProtocol.COVER_PANEL_LEASE_V3 -> {\n                val operation = data.readInt()\n                val requestShellSession = data.readLong()\n                val requestLeaseId = data.readLong()\n                val requestLeaseEpoch = data.readLong()\n                val ownerGeneration = data.readLong()\n                val reason = data.readString() ?: "unspecified"\n                val identity = clearCallingIdentity()\n                val result =\n                    try {\n                        runCoverMutation {\n                            val base = when (operation) {\n                                1 -> prewarmCoverLeaseV2(ownerGeneration)\n                                2 -> {\n                                    val snapshot = coverPanelLease.snapshot()\n                                    if (!matchesCoverToken(requestShellSession, requestLeaseId, requestLeaseEpoch, ownerGeneration, snapshot)) {\n                                        coverLeaseBundle("release-v3-stale-token", false).apply { putBoolean("stale", true) }\n                                    } else {\n                                        releaseCoverLeaseV2(ownerGeneration, reason)\n                                    }\n                                }\n                                3 -> {\n                                    if (requestShellSession != 0L && requestShellSession != shellSession) {\n                                        coverLeaseBundle("reconcile-v3-stale-session", false).apply { putBoolean("stale", true) }\n                                    } else {\n                                        reconcileCoverLeaseV2(reason)\n                                    }\n                                }\n                                4 -> {\n                                    if (requestShellSession != 0L && requestShellSession != shellSession) {\n                                        coverLeaseBundle("status-v3-stale-session", false).apply { putBoolean("stale", true) }\n                                    } else {\n                                        coverLeaseBundle("status-v3", true)\n                                    }\n                                }\n                                5 -> {\n                                    val snapshot = coverPanelLease.snapshot()\n                                    if (!matchesCoverToken(requestShellSession, requestLeaseId, requestLeaseEpoch, ownerGeneration, snapshot)) {\n                                        coverLeaseBundle("ensure-v3-stale-token", false).apply { putBoolean("stale", true) }\n                                    } else {\n                                        ensureHeldCoverRouteV2(ownerGeneration, reason)\n                                    }\n                                }\n                                else -> Bundle().apply {\n                                    putBoolean("ok", false)\n                                    putString("error", "unknown cover lease V3 operation $operation")\n                                }\n                            }\n                            stampCoverLeaseV3(base)\n                        }\n                    } catch (t: Throwable) {\n                        stampCoverLeaseV3(failureBundle("cover-lease-v3", t))\n                    } finally {\n                        restoreCallingIdentity(identity)\n                    }\n                out.writeNoException()\n                out.writeBundle(result)\n            }\n\n'''
        t = replace_once(t, marker, handler + marker, rel + ":V3 transact")
        marker2 = "    private fun secondaryDisplayCommand(\n"
        helpers = '''    private fun matchesCoverToken(
        requestShellSession: Long,
        requestLeaseId: Long,
        requestLeaseEpoch: Long,
        ownerGeneration: Long,
        snapshot: Fold7CoverPanelLease.Snapshot,
    ): Boolean =
        requestShellSession == shellSession &&
            requestLeaseId == snapshot.leaseId &&
            requestLeaseEpoch == snapshot.epoch &&
            ownerGeneration == snapshot.ownerGeneration &&
            snapshot.state != Fold7CoverPanelLease.State.IDLE

    private fun stampCoverLeaseV3(
        bundle: Bundle,
        advanceRevision: Boolean = true,
    ): Bundle {
        val snapshot = coverPanelLease.snapshot()
        val held =
            snapshot.state != Fold7CoverPanelLease.State.IDLE &&
                snapshot.physicalId != null

        bundle.putLong("shellSession", shellSession)
        bundle.putLong(
            "shellRevision",
            if (advanceRevision) {
                coverMutationRevision.incrementAndGet()
            } else {
                coverMutationRevision.get()
            },
        )
        bundle.putString("leaseState", snapshot.state.name)
        bundle.putLong("leaseId", snapshot.leaseId)
        bundle.putLong("leaseEpoch", snapshot.epoch)
        bundle.putLong("ownerGeneration", snapshot.ownerGeneration)
        bundle.putLong("physicalDisplayId", snapshot.physicalId ?: -1L)
        bundle.putBoolean("physicalLeaseHeld", held)

        val explicitRouteFact =
            bundle.containsKey("routeStillCover")

        val routeReady =
            if (explicitRouteFact) {
                bundle.getBoolean("routeStillCover", false) &&
                    (
                        bundle.getBoolean("routeEnabled", false) ||
                            bundle.getBoolean("logicalPowered", false)
                        )
            } else if (held) {
                val route =
                    runCatching { directCoverRoute() }.getOrNull()
                val innerDefault =
                    directGeometry(Display.DEFAULT_DISPLAY) ==
                        (1968 to 2184)
                val observed =
                    innerDefault &&
                        route != null &&
                        route.second == snapshot.physicalId
                if (observed) {
                    bundle.putInt("targetDisplayId", route!!.first)
                }
                observed
            } else {
                false
            }

        bundle.putBoolean("routeReady", routeReady)
        return bundle
    }

'''
        t = replace_once(t, marker2, helpers + marker2, rel + ":V3 helpers")
        return t
    patch_file(repo, rel, f)



def patch_coordinator_gen2(repo: Path) -> None:
    rel = "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"
    def f(t: str) -> str:
        t = replace_once(
            t,
            "    private val currentHingeAngle: () -> Float,\n    private val frozenInnerFrame: () -> android.graphics.Bitmap?,\n    private val onStatus: (String) -> Unit,",
            "    private val currentHingeAngle: () -> Float,\n    private val gen2: Fold7Gen2Kernel<android.graphics.Bitmap>,\n    private val onStatus: (String) -> Unit,",
            rel + ":constructor",
        )

        t = replace_once(
            t,
            "    @Volatile private var coverLeaseOwnerGeneration = -1L\n"
            "    @Volatile private var coverRouteReassertInFlight = false\n"
            "    @Volatile private var destroyed = false\n",
            "    @Volatile private var coverLeaseOwnerGeneration = -1L\n"
            "    @Volatile private var coverRouteReassertInFlight = false\n"
            "    @Volatile private var prewarmInFlightGeneration = -1L\n"
            "    @Volatile private var prewarmInFlightConnectionEpoch = -1L\n"
            "    @Volatile private var destroyed = false\n",
            rel + ":prewarm gate fields",
        )

        # Replace topology handling with a cheap immediate lane plus the existing heavier reconciliation lane.
        start = "    fun onTopologyChanged(reason: String) {\n"
        end = "    fun release(reason: String) {\n"
        replacement = '''    fun onTopologyFastLane(reason: String) {
        val angle =
            currentHingeAngle()
                .takeIf { it.isFinite() }
                ?: inferredRestAngle()

        val decision =
            controller.onTopology(
                angle = angle,
                nowMs = SystemClock.uptimeMillis(),
                topology = topology(),
            )

        apply(decision)
        observeCoverReadiness("fast:$reason")

        if (
            controller.state in setOf(
                Fold7ContinuityController.State.COVER_PREWARMING,
                Fold7ContinuityController.State.COVER_READY_HIDDEN,
                Fold7ContinuityController.State.COVER_VISUAL,
            ) &&
            gen2.coverReadiness.state != Fold7CoverReadiness.State.READY
        ) {
            ensureCoverRouteHeld("fast:$reason")
        }

        if (visualMirrorActive) {
            syncMirrorHost(
                reason = "fast:$reason",
                generation = mirrorGeneration,
            )
        }
    }

    fun onTopologyChanged(reason: String) {
        onTopologyFastLane(reason)
        reconcileCoverLease("topology:$reason")
    }

'''
        t = replace_between(t, start, end, replacement, rel + ":topology fast lane")

        # Manual arm/release are explicit continuity lifetime boundaries.
        t = replace_once(
            t,
            "    fun arm() {\n        destroyed = false\n",
            "    fun arm() {\n"
            "        gen2.cancelActiveCycle()\n"
            "        destroyed = false\n",
            rel + ":manual arm cycle invalidation",
        )
        t = replace_once(
            t,
            "    fun release(reason: String) {\n        val generation = controller.generation\n",
            "    fun release(reason: String) {\n"
            "        gen2.cancelActiveCycle()\n"
            "        val generation = controller.generation\n",
            rel + ":manual release cycle invalidation",
        )

        # Exact V3 cleanup on destroy; never fall back to a raw physical OFF.
        old = '''        val coverOwner = coverLeaseOwnerGeneration
        if (ShizukuBridge.ready) {
            Thread(
                {
                    runCatching {
                        if (coverOwner >= 0L) {
                            ShizukuBridge.releaseSecondaryDisplayV2(coverOwner, "destroy")
                        } else {
                            ShizukuBridge.reconcileSecondaryDisplayLeaseV2("destroy")
                        }
                    }
                },
                "duo-cover-lease-destroy",
            ).apply { isDaemon = true }.start()
        }
'''
        new = '''        val coverToken = gen2.coverAuthority.acceptedToken
        val coverShellSession =
            gen2.coverAuthority.acceptedSnapshot?.shellSession ?: 0L
        if (ShizukuBridge.ready) {
            Thread(
                {
                    runCatching {
                        if (coverToken != null) {
                            ShizukuBridge.releaseSecondaryDisplayV3(coverToken, "destroy")
                        } else {
                            ShizukuBridge.reconcileSecondaryDisplayLeaseV3(
                                coverShellSession,
                                "destroy",
                            )
                        }
                    }
                },
                "duo-cover-lease-destroy",
            ).apply { isDaemon = true }.start()
        }
        gen2.destroy()
'''
        t = replace_once(t, old, new, rel + ":destroy V3")

        start = "    fun onPrivilegedReady() {\n"
        end = "    private fun apply(\n"
        replacement = '''    fun onPrivilegedReady() {
        if (destroyed) return
        gen2.coverAuthority.onConnectionEpoch(
            ShizukuBridge.connectionEpoch
        )
        ensureMirrorSession("shizuku-ready")
        reconcileCoverLease("shizuku-ready")

        if (
            controller.state ==
                Fold7ContinuityController.State.COVER_PREWARMING &&
            gen2.activeCycle != null
        ) {
            beginPrewarm(controller.generation)
        }
    }

    fun onPrivilegedUnavailable() {
        mirrorSession = 0L
        mirrorSessionOpening = false
        mirrorSequence.set(0L)
        coverRouteReassertInFlight = false
        prewarmInFlightGeneration = -1L
        prewarmInFlightConnectionEpoch = -1L
        gen2.coverAuthority.onConnectionEpoch(
            ShizukuBridge.connectionEpoch
        )
        gen2.coverReadiness.invalidate()
    }

'''
        t = replace_between(t, start, end, replacement, rel + ":privileged lifecycle")

        # Replace prewarm with V3 authority + readiness, keeping the controller in PREWARMING while route publication is late.
        start = "    private fun beginPrewarm(\n"
        end = "    private fun showMirror(\n"
        replacement = '''    private fun beginPrewarm(
        generation: Long,
    ) {
        if (!controller.isGenerationCurrent(generation)) return

        val cycle = gen2.activeCycle
        if (!ShizukuBridge.ready || cycle == null) {
            val decision =
                controller.onPrewarmResult(
                    requestGeneration = generation,
                    ok = false,
                    nowMs = SystemClock.uptimeMillis(),
                    topology = topology(),
                )
            apply(decision)
            return
        }

        val requestConnectionEpoch = ShizukuBridge.connectionEpoch
        if (
            prewarmInFlightGeneration == generation &&
            prewarmInFlightConnectionEpoch == requestConnectionEpoch
        ) {
            return
        }
        prewarmInFlightGeneration = generation
        prewarmInFlightConnectionEpoch = requestConnectionEpoch

        onStatus("Fold7 cover prewarming; mirror remains hidden.")

        scope.launch(Dispatchers.IO) {
            if (!controller.isGenerationCurrent(generation)) {
                DuoDiagnostics.event(
                    "fold7-state",
                    "prewarm-stale-before-shell generation=$generation " +
                        "current=${controller.generation}",
                )
                handler.post {
                    if (
                        prewarmInFlightGeneration == generation &&
                        prewarmInFlightConnectionEpoch == requestConnectionEpoch
                    ) {
                        prewarmInFlightGeneration = -1L
                        prewarmInFlightConnectionEpoch = -1L
                    }
                }
                return@launch
            }

            val result =
                runCatching {
                    ShizukuBridge.prewarmSecondaryDisplayV3(generation)
                }.getOrNull()

            handler.post {
                if (
                    prewarmInFlightGeneration == generation &&
                    prewarmInFlightConnectionEpoch == requestConnectionEpoch
                ) {
                    prewarmInFlightGeneration = -1L
                    prewarmInFlightConnectionEpoch = -1L
                }

                if (!controller.isGenerationCurrent(generation)) {
                    return@post
                }

                val acceptance =
                    acceptCoverLeaseSnapshot(
                        result = result,
                        connectionEpoch = requestConnectionEpoch,
                        reason = "prewarm",
                    )

                val snapshot = acceptance.snapshot
                val token = acceptance.token
                val currentCycle = gen2.activeCycle

                if (
                    !acceptance.accepted ||
                    snapshot == null ||
                    token == null ||
                    currentCycle == null ||
                    currentCycle != cycle ||
                    !snapshot.physicalLeaseHeld
                ) {
                    val decision =
                        controller.onPrewarmResult(
                            requestGeneration = generation,
                            ok = false,
                            nowMs = SystemClock.uptimeMillis(),
                            topology = topology(),
                        )
                    apply(decision)
                    return@post
                }

                val demand =
                    Fold7CoverReadiness.Demand(
                        serviceEpoch = currentCycle.serviceEpoch,
                        closeCycleId = currentCycle.closeCycleId,
                        transitionGeneration = generation,
                        leaseToken = token,
                        expectedLogicalId = snapshot.targetLogicalId,
                    )

                gen2.coverReadiness.begin(
                    demand = demand,
                    shellRouteReady = snapshot.routeReady,
                )

                observeCoverReadiness("prewarm-result")

                if (
                    controller.state ==
                        Fold7ContinuityController.State.COVER_PREWARMING &&
                    gen2.coverReadiness.state != Fold7CoverReadiness.State.READY
                ) {
                    scheduleReadinessWatchdog(currentCycle.closeCycleId)
                }
            }
        }
    }

'''
        t = replace_between(t, start, end, replacement, rel + ":prewarm V3")

        # Pass exact-cycle frame leases and cycle identity into the presentation host.
        old = '''                    frozenFrameProvider = frozenInnerFrame,
                    onStatus = onStatus,
'''
        new = '''                    frozenFrameProvider = { width, height ->
                        gen2.activeCycle?.let { cycle ->
                            gen2.frames.current(
                                cycle = cycle,
                                nowUptimeMs = SystemClock.uptimeMillis(),
                                maxAgeMs = FROZEN_FRAME_MAX_AGE_MS,
                                width = width,
                                height = height,
                            )
                        }
                    },
                    currentCycle = { gen2.activeCycle },
                    onStatus = onStatus,
'''
        t = replace_once(t, old, new, rel + ":host provenance args")

        # Fence old mirror-session opens by the Shizuku connection epoch.
        old = '''        mirrorSessionOpening = true
        scope.launch(Dispatchers.IO) {
            val result =
'''
        new = '''        mirrorSessionOpening = true
        val requestConnectionEpoch = ShizukuBridge.connectionEpoch
        scope.launch(Dispatchers.IO) {
            val result =
'''
        t = replace_once(t, old, new, rel + ":mirror connection capture")
        old = '''            handler.post {
                mirrorSessionOpening = false
                if (destroyed) return@post
                if (session <= 0L) {
'''
        new = '''            handler.post {
                mirrorSessionOpening = false
                if (destroyed) return@post
                if (requestConnectionEpoch != ShizukuBridge.connectionEpoch) {
                    DuoDiagnostics.event(
                        "live-mirror",
                        "stale session-open result reason=$reason " +
                            "requestConnection=$requestConnectionEpoch " +
                            "currentConnection=${ShizukuBridge.connectionEpoch}",
                    )
                    return@post
                }
                if (session <= 0L) {
'''
        t = replace_once(t, old, new, rel + ":mirror connection gate")

        # Replace V2 owner-generation snapshot/reassert/release helpers with V3 exact tokens + readiness.
        start = "    private fun updateCoverLeaseSnapshot(\n"
        end = "    private data class DisplaySnapshot(\n"
        replacement = '''    private fun acceptCoverLeaseSnapshot(
        result: android.os.Bundle?,
        connectionEpoch: Long,
        reason: String,
    ): Fold7CoverLeaseSnapshotGate.Acceptance {
        if (result == null) {
            return Fold7CoverLeaseSnapshotGate.Acceptance(
                accepted = false,
                reason = "null-result",
                token = gen2.coverAuthority.acceptedToken,
                snapshot = gen2.coverAuthority.acceptedSnapshot,
            )
        }

        val snapshot =
            Fold7CoverLeaseSnapshotGate.Snapshot(
                connectionEpoch = connectionEpoch,
                shellSession = result.getLong("shellSession", 0L),
                shellRevision = result.getLong("shellRevision", 0L),
                leaseState = result.getString("leaseState") ?: "UNKNOWN",
                leaseId = result.getLong("leaseId", -1L),
                leaseEpoch = result.getLong("leaseEpoch", -1L),
                ownerGeneration = result.getLong("ownerGeneration", -1L),
                physicalDisplayId = result.getLong("physicalDisplayId", -1L),
                targetLogicalId = result.getInt("targetDisplayId", -1),
                physicalLeaseHeld = result.getBoolean("physicalLeaseHeld", false),
                routeReady = result.getBoolean("routeReady", false),
                ok = result.getBoolean("ok", false),
            )

        val acceptance =
            gen2.coverAuthority.accept(snapshot)

        coverLeaseOwnerGeneration =
            acceptance.token?.ownerGeneration ?: -1L

        DuoDiagnostics.event(
            "fold7-state",
            "cover-lease-v3 reason=$reason accepted=${acceptance.accepted} " +
                "decision=${acceptance.reason} state=${snapshot.leaseState} " +
                "connection=${snapshot.connectionEpoch} shell=${snapshot.shellSession} " +
                "revision=${snapshot.shellRevision} lease=${snapshot.leaseId} " +
                "epoch=${snapshot.leaseEpoch} owner=${snapshot.ownerGeneration} " +
                "physical=${snapshot.physicalDisplayId} logical=${snapshot.targetLogicalId} " +
                "held=${snapshot.physicalLeaseHeld} routeReady=${snapshot.routeReady}",
        )

        if (acceptance.accepted) {
            val demand = gen2.coverReadiness.currentDemand
            val token = acceptance.token
            if (
                demand != null &&
                token != null &&
                demand.leaseToken == token
            ) {
                gen2.coverReadiness.updateShell(
                    demand = demand,
                    shellRouteReady = snapshot.routeReady,
                    expectedLogicalId = snapshot.targetLogicalId,
                )
            }
        }

        return acceptance
    }

    private fun observeCoverReadiness(
        reason: String,
    ) {
        val cycle = gen2.activeCycle ?: return
        val demand = gen2.coverReadiness.currentDemand ?: return

        val t = topology()
        val result =
            gen2.coverReadiness.observe(
                serviceEpoch = cycle.serviceEpoch,
                closeCycleId = cycle.closeCycleId,
                topology =
                    Fold7CoverReadiness.Topology(
                        innerActive = t.innerActive,
                        coverActive = t.coverActive,
                        innerIsDefault = t.innerIsDefault,
                        coverIsDefault = t.coverIsDefault,
                        coverLogicalId = t.coverLogicalId,
                    ),
            )

        DuoDiagnostics.event(
            "fold7-readiness",
            "reason=$reason state=${result.state} decision=${result.reason} " +
                "serviceEpoch=${cycle.serviceEpoch} closeCycle=${cycle.closeCycleId} " +
                "generation=${demand.transitionGeneration} expectedLogical=${demand.expectedLogicalId} " +
                "coverLogical=${t.coverLogicalId} coverActive=${t.coverActive}",
        )

        if (
            result.becameReady &&
            controller.state == Fold7ContinuityController.State.COVER_PREWARMING &&
            controller.isGenerationCurrent(demand.transitionGeneration)
        ) {
            val decision =
                controller.onPrewarmResult(
                    requestGeneration = demand.transitionGeneration,
                    ok = true,
                    nowMs = SystemClock.uptimeMillis(),
                    topology = t,
                )
            apply(decision)
        }
    }

    private fun scheduleReadinessWatchdog(
        closeCycleId: Long,
    ) {
        handler.postDelayed(
            {
                val cycle = gen2.activeCycle
                if (
                    destroyed ||
                    cycle == null ||
                    cycle.closeCycleId != closeCycleId ||
                    controller.state != Fold7ContinuityController.State.COVER_PREWARMING ||
                    gen2.coverReadiness.state == Fold7CoverReadiness.State.READY
                ) {
                    return@postDelayed
                }

                observeCoverReadiness("watchdog")
                if (gen2.coverReadiness.state != Fold7CoverReadiness.State.READY) {
                    ensureCoverRouteHeld("readiness-watchdog")
                }
            },
            READINESS_WATCHDOG_MS,
        )
    }

    private fun ensureCoverRouteHeld(
        reason: String,
    ) {
        if (
            destroyed ||
            !ShizukuBridge.ready ||
            coverRouteReassertInFlight
        ) {
            return
        }

        if (
            controller.state !in setOf(
                Fold7ContinuityController.State.COVER_PREWARMING,
                Fold7ContinuityController.State.COVER_READY_HIDDEN,
                Fold7ContinuityController.State.COVER_VISUAL,
            )
        ) {
            return
        }

        val token =
            gen2.coverAuthority.acceptedToken
                ?: run {
                    DuoDiagnostics.event(
                        "fold7-state",
                        "cover-route-reassert skipped reason=$reason token=none",
                    )
                    return
                }

        val requestGeneration = controller.generation
        val requestConnectionEpoch = ShizukuBridge.connectionEpoch
        coverRouteReassertInFlight = true

        scope.launch(Dispatchers.IO) {
            val result =
                runCatching {
                    ShizukuBridge.ensureSecondaryDisplayHeldV3(
                        token = token,
                        reason = reason,
                    )
                }.getOrNull()

            handler.post {
                coverRouteReassertInFlight = false

                if (
                    destroyed ||
                    requestConnectionEpoch != ShizukuBridge.connectionEpoch
                ) {
                    return@post
                }

                val acceptance =
                    acceptCoverLeaseSnapshot(
                        result = result,
                        connectionEpoch = requestConnectionEpoch,
                        reason = "route-reassert:$reason",
                    )

                DuoDiagnostics.event(
                    "fold7-state",
                    "cover-route-reassert complete reason=$reason " +
                        "generation=$requestGeneration currentGeneration=${controller.generation} " +
                        "accepted=${acceptance.accepted} decision=${acceptance.reason}",
                )

                if (acceptance.accepted) {
                    observeCoverReadiness("route-reassert:$reason")
                }
            }
        }
    }

    private fun releaseCoverLease(
        reason: String,
    ) {
        if (!ShizukuBridge.ready) return
        val token = gen2.coverAuthority.acceptedToken
        val shellSession =
            gen2.coverAuthority.acceptedSnapshot?.shellSession ?: 0L
        val requestConnectionEpoch = ShizukuBridge.connectionEpoch

        scope.launch(Dispatchers.IO) {
            val result =
                if (token != null) {
                    ShizukuBridge.releaseSecondaryDisplayV3(token, reason)
                } else {
                    ShizukuBridge.reconcileSecondaryDisplayLeaseV3(
                        shellSession,
                        reason,
                    )
                }

            handler.post {
                if (requestConnectionEpoch != ShizukuBridge.connectionEpoch) {
                    return@post
                }
                acceptCoverLeaseSnapshot(
                    result = result,
                    connectionEpoch = requestConnectionEpoch,
                    reason = reason,
                )
            }
        }
    }

    private fun reconcileCoverLease(
        reason: String,
    ) {
        if (destroyed || !ShizukuBridge.ready) return
        val shellSession =
            gen2.coverAuthority.acceptedSnapshot?.shellSession ?: 0L
        val requestConnectionEpoch = ShizukuBridge.connectionEpoch

        scope.launch(Dispatchers.IO) {
            val result =
                ShizukuBridge.reconcileSecondaryDisplayLeaseV3(
                    shellSession,
                    reason,
                )
                    ?: ShizukuBridge.secondaryDisplayLeaseStatusV3(shellSession)

            handler.post {
                if (requestConnectionEpoch != ShizukuBridge.connectionEpoch) {
                    return@post
                }
                val acceptance =
                    acceptCoverLeaseSnapshot(
                        result = result,
                        connectionEpoch = requestConnectionEpoch,
                        reason = reason,
                    )
                if (acceptance.accepted) {
                    observeCoverReadiness("reconcile:$reason")
                }
            }
        }
    }

'''
        t = replace_between(t, start, end, replacement, rel + ":V3/readiness helpers")

        # Correlate state transitions to the stable physical close cycle.
        old = '''    private fun logTransition(
        transition: Fold7ContinuityController.Transition,
    ) {
        val t = transition.topology
'''
        new = '''    private fun logTransition(
        transition: Fold7ContinuityController.Transition,
    ) {
        val cycleChange =
            gen2.onTransition(
                from = transition.from,
                to = transition.to,
                nowUptimeMs = SystemClock.uptimeMillis(),
            )

        cycleChange.started?.let { cycle ->
            DuoDiagnostics.event(
                "fold7-cycle",
                "START serviceEpoch=${cycle.serviceEpoch} " +
                    "closeCycle=${cycle.closeCycleId} generation=${transition.generation}",
            )
        }
        cycleChange.ended?.let { cycle ->
            DuoDiagnostics.event(
                "fold7-cycle",
                "END serviceEpoch=${cycle.serviceEpoch} " +
                    "closeCycle=${cycle.closeCycleId} generation=${transition.generation} " +
                    "target=${transition.to}",
            )
        }

        val t = transition.topology
'''
        t = replace_once(t, old, new, rel + ":cycle transition")

        t = replace_once(
            t,
            "        const val COVER_ROUTE_REASSERT_SETTLE_MS = 32L\n",
            "        const val READINESS_WATCHDOG_MS = 80L\n"
            "        const val FROZEN_FRAME_MAX_AGE_MS = 10_000L\n",
            rel + ":timers",
        )
        return t
    patch_file(repo, rel, f)



def patch_display_mirror_host_gen2(repo: Path) -> None:
    rel = "app/src/full/java/com/duoopen/overlay/DisplayMirrorHost.kt"
    def f(t: str) -> str:
        t = replace_once(t, "import android.hardware.display.DisplayManager\n", "import android.hardware.SyncFence\nimport android.hardware.display.DisplayManager\n", rel + ":SyncFence import")
        t = replace_once(t, "import android.os.SystemClock\n", "import android.os.Build\nimport android.os.SystemClock\n", rel + ":Build import")
        t = replace_once(
            t,
            "    private val nextMirrorSequence: () -> Long,\n    private val frozenFrameProvider: () -> Bitmap?,\n    private val onStatus: (String) -> Unit,",
            "    private val nextMirrorSequence: () -> Long,\n"
            "    private val frozenFrameProvider: (Int, Int) -> Fold7ContinuityFrameStore.FrameLease<Bitmap>?,\n"
            "    private val currentCycle: () -> Fold7CycleEnvelope.CloseCycle?,\n"
            "    private val onStatus: (String) -> Unit,",
            rel + ":constructor",
        )
        t = replace_once(
            t,
            "    private var frozenFrame: Bitmap? = null\n",
            "    private var frozenFrame: Bitmap? = null\n"
            "    private var frozenFrameLease: Fold7ContinuityFrameStore.FrameLease<Bitmap>? = null\n"
            "    private val presentationLease = Fold7PresentationLease()\n"
            "    private val hostEpoch = presentationLease.openHost()\n"
            "    private var activePresentation: Fold7PresentationLease.Identity? = null\n",
            rel + ":presentation fields",
        )
        old = '''            override fun onDraw(
                canvas: Canvas,
            ) {
                drawFrozenFrame(
                    canvas
                )
            }
'''
        new = '''            override fun onDraw(
                canvas: Canvas,
            ) {
                drawFrozenFrame(
                    canvas
                )

                activePresentation?.let { identity ->
                    val accepted = presentationLease.onDraw(identity)
                    recordPresentationStage(
                        type = "presentation-draw",
                        identity = identity,
                        accepted = accepted,
                    )
                }
            }
'''
        t = replace_once(t, old, new, rel + ":frozen draw identity")
        t = replace_once(
            t,
            "        frozenFrame =\n            null\n\n        frozenPaneView.visibility =",
            "        activePresentation?.let(presentationLease::invalidateAttempt)\n        frozenFrame =\n            null\n        frozenFrameLease =\n            null\n        activePresentation =\n            null\n\n        frozenPaneView.visibility =",
            rel + ":clear frame lease",
        )
        t = replace_once(
            t,
            "                frozenFrameProvider()\n",
            "                frozenFrameProvider(sourceWidth, sourceHeight)\n",
            rel + ":frame provider args",
        )
        # Candidate is now a typed lease; use its payload for bitmap validation/draw.
        old = '''        if (
            candidate.isRecycled ||
            candidate.width !=
                sourceWidth ||
            candidate.height !=
                sourceHeight
        ) {
'''
        new = '''        val candidateBitmap = candidate.payload

        if (
            candidateBitmap.isRecycled ||
            candidateBitmap.width !=
                sourceWidth ||
            candidateBitmap.height !=
                sourceHeight
        ) {
'''
        t = replace_once(t, old, new, rel + ":candidate bitmap")
        t = t.replace("actual=${candidate.width}x${candidate.height}", "actual=${candidateBitmap.width}x${candidateBitmap.height}", 1)
        t = t.replace("recycled=${candidate.isRecycled}", "recycled=${candidateBitmap.isRecycled}", 1)
        t = replace_once(
            t,
            "        frozenFrame =\n            candidate\n",
            "        frozenFrame =\n            candidateBitmap\n        frozenFrameLease =\n            candidate\n",
            rel + ":bind typed lease",
        )
        t = replace_once(
            t,
            "        frozenPaneView.visibility =\n            View.VISIBLE\n\n        frozenPaneView.invalidate()\n",
            "        frozenPaneView.visibility =\n            View.VISIBLE\n\n"
            "        val presentation =\n"
            "            presentationLease.begin(\n"
            "                serviceEpoch = candidate.serviceEpoch,\n"
            "                closeCycleId = candidate.closeCycleId,\n"
            "                contentLeaseId = candidate.contentLeaseId,\n"
            "                renderPath = Fold7PresentationLease.RenderPath.FROZEN_VIEW,\n"
            "            )\n"
            "        activePresentation = presentation\n"
            "        recordPresentationStage(\n"
            "            type = \"presentation-attempt\",\n"
            "            identity = presentation,\n"
            "            accepted = true,\n"
            "        )\n"
            "        frozenPaneView.viewTreeObserver.registerFrameCommitCallback {\n"
            "            frozenPaneView.post {\n"
            "                val accepted = presentationLease.onFrameCommit(presentation)\n"
            "                recordPresentationStage(\n"
            "                    type = \"presentation-frame-commit\",\n"
            "                    identity = presentation,\n"
            "                    accepted = accepted,\n"
            "                )\n"
            "            }\n"
            "        }\n\n"
            "        frozenPaneView.invalidate()\n",
            rel + ":frozen presentation start",
        )
        t = t.replace("source=${candidate.width}x${candidate.height}", "source=${candidateBitmap.width}x${candidateBitmap.height}", 1)

        # Start an immutable live-mirror presentation attempt before transaction callbacks are registered.
        anchor = '''            transaction
                .setLayer(mirror, 10_000)
                .setAlpha(mirror, 1f)
                .setVisibility(mirror, true)

            val labToken =
'''
        replacement = '''            transaction
                .setLayer(mirror, 10_000)
                .setAlpha(mirror, 1f)
                .setVisibility(mirror, true)

            val presentation =
                currentCycle()?.let { cycle ->
                    presentationLease.begin(
                        serviceEpoch = cycle.serviceEpoch,
                        closeCycleId = cycle.closeCycleId,
                        contentLeaseId = mirrorLeaseId,
                        renderPath = Fold7PresentationLease.RenderPath.LIVE_MIRROR,
                    )
                }

            if (presentation != null) {
                activePresentation = presentation
                recordPresentationStage(
                    type = "presentation-attempt",
                    identity = presentation,
                    accepted = true,
                )

                if (Build.VERSION.SDK_INT >= 33) {
                    transaction.addTransactionCommittedListener(
                        service.mainExecutor,
                    ) {
                        hostView.post {
                            val accepted =
                                presentationLease.onTransactionCommit(presentation)
                            recordPresentationStage(
                                type = "presentation-transaction-commit",
                                identity = presentation,
                                accepted = accepted,
                            )
                        }
                    }
                }

                if (Build.VERSION.SDK_INT >= 35) {
                    transaction.addTransactionCompletedListener(
                        service.mainExecutor,
                    ) { stats ->
                        val fence = stats.presentFence
                        var presented = false
                        try {
                            if (fence.isValid) {
                                val signal = fence.signalTime
                                presented =
                                    signal != SyncFence.SIGNAL_TIME_INVALID &&
                                        signal != SyncFence.SIGNAL_TIME_PENDING
                            }
                        } finally {
                            fence.close()
                        }

                        hostView.post {
                            val accepted =
                                if (presented) {
                                    presentationLease.onPresented(presentation)
                                } else {
                                    presentationLease.isCurrent(presentation)
                                }
                            recordPresentationStage(
                                type = if (presented) {
                                    "presentation-presented"
                                } else {
                                    "presentation-completed-no-present-fence"
                                },
                                identity = presentation,
                                accepted = accepted,
                            )
                        }
                    }
                }
            }

            val labToken =
'''
        t = replace_once(t, anchor, replacement, rel + ":live presentation transaction")

        # Helper emits immutable attempt IDs into Transition Lab and diagnostics.
        marker = "    private fun releaseAppMirror() {\n"
        helper = '''    private fun recordPresentationStage(
        type: String,
        identity: Fold7PresentationLease.Identity,
        accepted: Boolean,
    ) {
        TransitionLab.recordIngressStage(
            type = type,
            serviceEpoch = identity.serviceEpoch,
            closeCycleId = identity.closeCycleId,
            contentLeaseId = identity.contentLeaseId,
            hostEpoch = identity.hostEpoch,
            presentationAttemptSequence = identity.attemptSequence,
            renderPath = identity.renderPath.name,
            staleAtCallback = !accepted,
            rejectionReason = if (accepted) null else "stale-presentation-attempt",
        )

        com.duoopen.debug.DuoDiagnostics.event(
            "presentation",
            "$type accepted=$accepted " +
                "serviceEpoch=${identity.serviceEpoch} closeCycle=${identity.closeCycleId} " +
                "content=${identity.contentLeaseId} host=${identity.hostEpoch} " +
                "attempt=${identity.attemptSequence} path=${identity.renderPath}",
        )
    }

'''
        t = replace_once(t, marker, helper + marker, rel + ":presentation recorder")

        # Detach makes every outstanding presentation callback inert before releasing surfaces/windows.
        t = replace_once(
            t,
            "    fun detach() {\n        requestShellStop(\"host-detach\")",
            "    fun detach() {\n"
            "        presentationLease.invalidateHost(hostEpoch)\n"
            "        activePresentation = null\n"
            "        requestShellStop(\"host-detach\")",
            rel + ":presentation invalidate",
        )
        return t
    patch_file(repo, rel, f)


def patch_workflow(repo: Path) -> None:
    rel = ".github/workflows/build-direct-fold7.yml"
    def f(t: str) -> str:
        t = t.replace("Build Direct Fold7 1.3.25 Debug Export", "Build Direct Fold7 Gen2 Debug Export", 1)
        t = t.replace("Validate direct-source 1.3.25 debug-export architecture", "Validate direct-source Gen2 ownership architecture", 1)
        t = t.replace("versionCode = 30", "versionCode = 35", 1)
        t = t.replace('versionName = \\\"1.3.25-zfold7-debug-export\\\"', 'versionName = \\\"2.0.0-zfold7-gen2-ownership\\\"', 1)
        # The source file actually contains ordinary shell single quotes around the grep literal.
        t = t.replace('versionName = "1.3.25-zfold7-debug-export"', 'versionName = "2.0.0-zfold7-gen2-ownership"')
        t = t.replace("DuoOpen-ZFold7-1.3.25-debug-export-debug.apk", "DuoOpen-ZFold7-2.0.0-gen2-debug.apk")
        t = t.replace("APK-SHA256-1.3.25-debug-export.txt", "APK-SHA256-2.0.0-gen2.txt")
        t = t.replace("BUILD-INFO-1.3.25-debug-export.txt", "BUILD-INFO-2.0.0-gen2.txt")
        t = t.replace("version=1.3.25-zfold7-debug-export", "version=2.0.0-zfold7-gen2-ownership")
        t = t.replace("versionCode=30", "versionCode=35")
        t = t.replace("DuoOpen-ZFold7-1.3.25-debug-export", "DuoOpen-ZFold7-2.0.0-gen2")
        t = t.replace("Direct-source Fold7 1.3.25 debug-export validation passed.", "Direct-source Fold7 Gen2 validation passed.")
        architecture_anchor = "          grep -F 'WAKE_INNER_DISPLAY' \"$PROTOCOL\"\n"
        gen2_checks = (
            architecture_anchor +
            "          grep -F 'COVER_PANEL_LEASE_V3' \"$PROTOCOL\"\n" +
            "          grep -F 'Fold7Gen2Kernel' \"$SERVICE\"\n" +
            "          grep -F 'duo-fold7-angle-control' \"$SERVICE\"\n" +
            "          grep -F 'startAnglesSequenced' \"$ANGLE_FEED\"\n" +
            "          grep -F 'recordIngressStage' \"$TRANSITION_LAB\"\n" +
            "          grep -F 'Fold7CoverLeaseSnapshotGate' \"$COORDINATOR\"\n"
        )
        if architecture_anchor not in t:
            raise RuntimeError(f"{rel}: Gen2 workflow architecture anchor missing")
        t = t.replace(architecture_anchor, gen2_checks, 1)
        return t
    patch_file(repo, rel, f)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", type=Path)
    ap.add_argument("--force", action="store_true", help="allow HEAD mismatch; blob checks still mandatory")
    ap.add_argument("--check-only", action="store_true")
    args = ap.parse_args()
    repo = args.repo.resolve()
    verify(repo, args.force)
    print(f"baseline verified: {BASELINE}")
    if args.check_only:
        return

    copy_overlay(repo)
    patch_version(repo)
    patch_protocol(repo)
    patch_hinge_source(repo)
    patch_transition_schema(repo)
    patch_transition_lab(repo)
    activate_angle_gen2(repo)
    patch_overlay_service_angle_control(repo)
    patch_overlay_service_gen2(repo)
    patch_panel_engine_gen2(repo)
    patch_bridge_v3(repo)
    patch_shell_v3(repo)
    patch_coordinator_gen2(repo)
    patch_display_mirror_host_gen2(repo)
    patch_workflow(repo)

    print("Gen2 foundation applied. No commit was created.")
    print("NEXT: review git diff; then run ./gradlew testFullDebugUnitTest assembleFullDebug --stacktrace")


if __name__ == "__main__":
    main()
