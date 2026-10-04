package com.duoopen.overlay

import android.accessibilityservice.AccessibilityService
import android.app.admin.DevicePolicyManager
import android.graphics.Bitmap
import android.hardware.display.DisplayManager
import android.os.Handler
import android.os.SystemClock
import android.os.UserManager
import android.view.SurfaceControl
import com.duoopen.debug.DuoDiagnostics
import com.duoopen.shell.ShizukuBridge
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import java.io.File
import java.time.Instant
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicLong
import kotlin.math.max

/**
 * S1H read-only visual forensics.
 *
 * Captures a timestamped burst of both Fold7 panel routes after an accepted
 * opening edge. Successful Shizuku captures exclude Duo Open's own overlay
 * when an engine route is available, so the stored frame represents content
 * underneath the overlay.
 *
 * Screenshot failures are not collapsed into "black frame": the manifest keeps
 * route state, DevicePolicy evidence, AccessibilityService screenshot result,
 * and read-only wallpaper/widget/window/compositor evidence. Secure/protected
 * content is fail-closed and is never persisted by the diagnostic recorder.
 */
internal class Fold7VisualForensics(
    private val service: AccessibilityService,
    private val displayManager: DisplayManager,
    private val handler: Handler,
    private val scope: CoroutineScope,
    private val excludedLayersForDisplay: (Int) -> List<SurfaceControl>,
) {
    private data class Target(
        val panel: String,
        val displayId: Int,
        val state: Int,
        val width: Int,
        val height: Int,
        val excluded: List<SurfaceControl>,
    )

    private data class MetadataEvidence(
        val probeAvailable: Boolean,
        val capturePolicy: String,
        val secureWindowEvidence: Boolean,
        val screenCapturePolicyEvidence: Boolean,
        val managedProfileEvidence: Boolean,
        val protectedLayerEvidence: Boolean,
    )

    private data class LocalPolicyEvidence(
        val screenCaptureDisabled: Boolean?,
        val managedProfile: Boolean?,
        val contentCaptureRestricted: Boolean?,
    )

    private data class AccessibilityClassification(
        val attempted: Boolean,
        val result: String,
        val errorCode: Int,
        val elapsedMs: Long,
    )

    private val burstSequence = AtomicLong(0L)
    @Volatile private var lastGeneration = -1L
    private val lastAccessibilityProbeByPanel = mutableMapOf<String, Long>()

    fun startOpeningBurst(
        reason: String,
        generation: Long,
    ) {
        if (!ShizukuBridge.ready) {
            DuoDiagnostics.event(
                "visual-forensics",
                "burst skipped generation=$generation reason=$reason shizuku-not-ready",
            )
            return
        }

        synchronized(this) {
            if (generation == lastGeneration) return
            lastGeneration = generation
            lastAccessibilityProbeByPanel.clear()
        }

        val burstId = burstSequence.incrementAndGet()
        val startedElapsed = SystemClock.elapsedRealtime()
        val startedWall = System.currentTimeMillis()
        val root =
            File(
                service.filesDir,
                "visual-forensics/burst-${startedWall}-g${generation}",
            ).apply { mkdirs() }

        pruneOldBursts(root.parentFile)

        writeTextSafe(
            File(root, "README.txt"),
            buildString {
                appendLine("Duo Open S1H visual-forensics burst")
                appendLine("generation=$generation")
                appendLine("reason=$reason")
                appendLine("started=${Instant.ofEpochMilli(startedWall)}")
                appendLine("captureScale=$CAPTURE_SCALE")
                appendLine("encoding=WEBP_LOSSY quality=$WEBP_QUALITY")
                appendLine("sampleOffsetsMs=${SAMPLE_OFFSETS_MS.joinToString(",")}")
                appendLine("securePolicy=secure/protected captures are never intentionally persisted")
                appendLine("overlayPolicy=own overlay SurfaceControl excluded from Shizuku frame when available")
                appendLine("fallbackPolicy=AccessibilityService screenshot is classification-only and is never written")
                appendLine("failurePolicy=ROUTE_ABSENT, secure-window, admin policy, rate-limit, invalid-display and generic capture failures remain distinct")
            },
        )

        appendManifest(
            root,
            listOf(
                "event=BURST_START",
                "burst=$burstId",
                "generation=$generation",
                "reason=${clean(reason)}",
                "elapsedMs=0",
                "wall=${Instant.ofEpochMilli(startedWall)}",
            ),
        )

        SAMPLE_OFFSETS_MS.forEachIndexed { index, offset ->
            handler.postDelayed(
                {
                    if (burstSequence.get() != burstId) return@postDelayed

                    // Snapshot Display objects and overlay exclusions on main;
                    // capture/encoding/dumps run on IO afterwards.
                    val targets = snapshotTargets()
                    val elapsed = SystemClock.elapsedRealtime() - startedElapsed
                    val collectMetadata = index in METADATA_SAMPLE_INDEXES

                    scope.launch(Dispatchers.IO) {
                        if (burstSequence.get() != burstId) return@launch

                        val metadata =
                            if (collectMetadata) {
                                captureMetadata(
                                    root = root,
                                    index = index,
                                    offsetMs = offset,
                                    elapsedMs = elapsed,
                                )
                            } else {
                                null
                            }

                        captureExpectedPanel(
                            root = root,
                            burstId = burstId,
                            generation = generation,
                            reason = reason,
                            index = index,
                            offsetMs = offset,
                            elapsedMs = elapsed,
                            panel = "cover",
                            expectedWidth = 1080,
                            expectedHeight = 2520,
                            targets = targets,
                            metadata = metadata,
                        )

                        captureExpectedPanel(
                            root = root,
                            burstId = burstId,
                            generation = generation,
                            reason = reason,
                            index = index,
                            offsetMs = offset,
                            elapsedMs = elapsed,
                            panel = "inner",
                            expectedWidth = 1968,
                            expectedHeight = 2184,
                            targets = targets,
                            metadata = metadata,
                        )
                    }
                },
                offset,
            )
        }

        DuoDiagnostics.event(
            "visual-forensics",
            "burst scheduled id=$burstId generation=$generation reason=$reason " +
                "samples=${SAMPLE_OFFSETS_MS.joinToString(",")}",
        )
    }

    fun stop(reason: String) {
        val next = burstSequence.incrementAndGet()
        DuoDiagnostics.event(
            "visual-forensics",
            "burst stop reason=$reason token=$next",
        )
    }

    private fun snapshotTargets(): List<Target> =
        displayManager.displays.mapNotNull { display ->
            val mode = runCatching { display.mode }.getOrNull()
                ?: return@mapNotNull null
            val geometry = mode.physicalWidth to mode.physicalHeight
            if (
                geometry != (1080 to 2520) &&
                geometry != (1968 to 2184)
            ) {
                return@mapNotNull null
            }

            Target(
                panel = if (geometry == (1968 to 2184)) "inner" else "cover",
                displayId = display.displayId,
                state = display.state,
                width = mode.physicalWidth,
                height = mode.physicalHeight,
                excluded = runCatching {
                    excludedLayersForDisplay(display.displayId)
                }.getOrDefault(emptyList()),
            )
        }

    private fun captureMetadata(
        root: File,
        index: Int,
        offsetMs: Long,
        elapsedMs: Long,
    ): MetadataEvidence {
        val bundle = runCatching {
            ShizukuBridge.visualForensicsProbe()
        }.getOrNull()

        val wallpaper = bundle?.getString("wallpaper").orEmpty()
        val appWidgets = bundle?.getString("appWidgets").orEmpty()
        val windowRendering = bundle?.getString("windowRendering").orEmpty()
        val surfaceLayers = bundle?.getString("surfaceLayers").orEmpty()
        val capturePolicy = bundle?.getString("capturePolicy").orEmpty()
        val topActivity = bundle?.getString("topActivity").orEmpty()

        writeTextSafe(
            File(root, "metadata-%02d-%04dms.txt".format(index, offsetMs)),
            buildString {
                appendLine("sampleIndex=$index")
                appendLine("scheduledOffsetMs=$offsetMs")
                appendLine("actualElapsedMs=$elapsedMs")
                appendLine("generated=${Instant.now()}")
                appendLine("probeAvailable=${bundle != null}")
                appendLine()
                appendLine("=== WALLPAPER ===")
                appendLine(wallpaper)
                appendLine()
                appendLine("=== APP WIDGETS / HOSTS ===")
                appendLine(appWidgets)
                appendLine()
                appendLine("=== WINDOW RENDERING ===")
                appendLine(windowRendering)
                appendLine()
                appendLine("=== SURFACEFLINGER LAYERS / SECURITY ===")
                appendLine(surfaceLayers)
                appendLine()
                appendLine("=== CAPTURE POLICY / USERS / SECURE WINDOWS ===")
                appendLine(capturePolicy)
                appendLine()
                appendLine("=== TOP ACTIVITY / DISPLAY OWNERSHIP ===")
                appendLine(topActivity)
            },
        )

        val policyLower = capturePolicy.lowercase()
        val surfaceLower = surfaceLayers.lowercase()

        return MetadataEvidence(
            probeAvailable = bundle != null,
            capturePolicy = capturePolicy,
            secureWindowEvidence =
                policyLower.contains("flag_secure") ||
                    policyLower.contains("secure=true"),
            screenCapturePolicyEvidence =
                policyLower.contains("screen_capture_disabled=true") ||
                    policyLower.contains("screencapturedisabled=true") ||
                    policyLower.contains("policy_disable_screen_capture") ||
                    policyLower.contains("no_screen_capture"),
            managedProfileEvidence =
                policyLower.contains("managed") &&
                    policyLower.contains("profile"),
            protectedLayerEvidence =
                surfaceLower.contains("protected") ||
                    surfaceLower.contains("drm") ||
                    surfaceLower.contains("secure"),
        )
    }

    private fun captureExpectedPanel(
        root: File,
        burstId: Long,
        generation: Long,
        reason: String,
        index: Int,
        offsetMs: Long,
        elapsedMs: Long,
        panel: String,
        expectedWidth: Int,
        expectedHeight: Int,
        targets: List<Target>,
        metadata: MetadataEvidence?,
    ) {
        val target = targets.firstOrNull {
            it.width == expectedWidth && it.height == expectedHeight
        }

        if (target == null) {
            appendManifest(
                root,
                listOf(
                    "event=CAPTURE",
                    "burst=$burstId",
                    "generation=$generation",
                    "sample=$index",
                    "scheduledOffsetMs=$offsetMs",
                    "actualElapsedMs=$elapsedMs",
                    "panel=$panel",
                    "displayId=-1",
                    "displayState=ABSENT",
                    "classification=ROUTE_ABSENT",
                    "reason=${clean(reason)}",
                ),
            )
            DuoDiagnostics.event(
                "visual-forensics",
                "sample=$index offset=$offsetMs panel=$panel class=ROUTE_ABSENT",
            )
            return
        }

        val policy = localPolicyEvidence()
        val started = SystemClock.elapsedRealtime()
        val bitmap = runCatching {
            ShizukuBridge.capture(
                target.displayId,
                target.excluded,
                CAPTURE_SCALE,
            )
        }.getOrNull()
        val shellMs = SystemClock.elapsedRealtime() - started

        val accessibility =
            if (bitmap == null) {
                classifyWithAccessibility(
                    panel = panel,
                    displayId = target.displayId,
                )
            } else {
                AccessibilityClassification(
                    attempted = false,
                    result = "NOT_NEEDED",
                    errorCode = 0,
                    elapsedMs = 0L,
                )
            }

        var classification =
            classifyCaptureFailure(
                bitmap = bitmap,
                accessibility = accessibility,
                policy = policy,
                metadata = metadata,
            )
        var fileName = ""
        var frameStats = ""

        if (bitmap != null) {
            frameStats = frameStats(bitmap)
            val file = File(
                root,
                "%02d-%04dms-%s-d%d.webp".format(
                    index,
                    offsetMs,
                    panel,
                    target.displayId,
                ),
            )

            val encoded = runCatching {
                file.outputStream().buffered().use { out ->
                    bitmap.compress(
                        Bitmap.CompressFormat.WEBP_LOSSY,
                        WEBP_QUALITY,
                        out,
                    )
                }
            }.getOrDefault(false)

            if (encoded && file.isFile && file.length() > 0L) {
                fileName = file.name
                classification = "CAPTURED"
            } else {
                classification = "ENCODE_FAILED"
                runCatching { file.delete() }
            }
        }

        appendManifest(
            root,
            listOf(
                "event=CAPTURE",
                "burst=$burstId",
                "generation=$generation",
                "sample=$index",
                "scheduledOffsetMs=$offsetMs",
                "actualElapsedMs=$elapsedMs",
                "panel=$panel",
                "displayId=${target.displayId}",
                "displayState=${target.state}",
                "geometry=${target.width}x${target.height}",
                "excludedLayers=${target.excluded.size}",
                "classification=$classification",
                "shizukuBitmap=${bitmap != null}",
                "shizukuCaptureMs=$shellMs",
                "a11yAttempted=${accessibility.attempted}",
                "a11yResult=${accessibility.result}",
                "a11yErrorCode=${accessibility.errorCode}",
                "a11yMs=${accessibility.elapsedMs}",
                "dpmScreenCaptureDisabled=${policy.screenCaptureDisabled}",
                "currentUserManagedProfile=${policy.managedProfile}",
                "contentCaptureRestricted=${policy.contentCaptureRestricted}",
                "metadataProbeAvailable=${metadata?.probeAvailable}",
                "metadataScreenCapturePolicy=${metadata?.screenCapturePolicyEvidence}",
                "metadataManagedProfile=${metadata?.managedProfileEvidence}",
                "metadataSecureWindow=${metadata?.secureWindowEvidence}",
                "metadataProtectedLayer=${metadata?.protectedLayerEvidence}",
                "file=${clean(fileName)}",
                "frameStats=${clean(frameStats)}",
                "reason=${clean(reason)}",
            ),
        )

        DuoDiagnostics.event(
            "visual-forensics",
            "sample=$index offset=$offsetMs panel=$panel display=${target.displayId} " +
                "state=${target.state} class=$classification shizukuBitmap=${bitmap != null} " +
                "shellMs=$shellMs a11y=${accessibility.result}:${accessibility.errorCode} " +
                "dpm=${policy.screenCaptureDisabled} managed=${policy.managedProfile} file=$fileName",
        )

        runCatching { bitmap?.recycle() }
    }

    private fun localPolicyEvidence(): LocalPolicyEvidence {
        val dpm = service.getSystemService(DevicePolicyManager::class.java)
        val userManager = service.getSystemService(UserManager::class.java)

        return LocalPolicyEvidence(
            screenCaptureDisabled = runCatching {
                dpm?.getScreenCaptureDisabled(null)
            }.getOrNull(),
            managedProfile = runCatching {
                userManager?.isManagedProfile
            }.getOrNull(),
            contentCaptureRestricted = runCatching {
                userManager?.userRestrictions
                    ?.getBoolean(UserManager.DISALLOW_CONTENT_CAPTURE)
            }.getOrNull(),
        )
    }

    private fun classifyWithAccessibility(
        panel: String,
        displayId: Int,
    ): AccessibilityClassification {
        val now = SystemClock.elapsedRealtime()
        synchronized(lastAccessibilityProbeByPanel) {
            val last = lastAccessibilityProbeByPanel[panel] ?: Long.MIN_VALUE
            if (now - last < ACCESSIBILITY_CLASSIFIER_MIN_INTERVAL_MS) {
                return AccessibilityClassification(
                    attempted = false,
                    result = "RATE_GUARDED",
                    errorCode = AccessibilityService.ERROR_TAKE_SCREENSHOT_INTERVAL_TIME_SHORT,
                    elapsedMs = 0L,
                )
            }
            lastAccessibilityProbeByPanel[panel] = now
        }

        val latch = CountDownLatch(1)
        var errorCode = 0
        var result = "CALLBACK_TIMEOUT"
        val started = SystemClock.elapsedRealtime()

        runCatching {
            service.takeScreenshot(
                displayId,
                service.mainExecutor,
                object : AccessibilityService.TakeScreenshotCallback {
                    override fun onSuccess(
                        screenshot: AccessibilityService.ScreenshotResult,
                    ) {
                        result = "SUCCESS"
                        runCatching { screenshot.hardwareBuffer.close() }
                        latch.countDown()
                    }

                    override fun onFailure(code: Int) {
                        errorCode = code
                        result = accessibilityErrorName(code)
                        latch.countDown()
                    }
                },
            )
        }.onFailure { error ->
            result = "THREW_${error.javaClass.simpleName}"
            latch.countDown()
        }

        latch.await(ACCESSIBILITY_CLASSIFIER_TIMEOUT_MS, TimeUnit.MILLISECONDS)
        return AccessibilityClassification(
            attempted = true,
            result = result,
            errorCode = errorCode,
            elapsedMs = SystemClock.elapsedRealtime() - started,
        )
    }

    private fun accessibilityErrorName(code: Int): String =
        when (code) {
            AccessibilityService.ERROR_TAKE_SCREENSHOT_INTERNAL_ERROR ->
                "INTERNAL_ERROR"
            AccessibilityService.ERROR_TAKE_SCREENSHOT_NO_ACCESSIBILITY_ACCESS ->
                "NO_ACCESSIBILITY_ACCESS"
            AccessibilityService.ERROR_TAKE_SCREENSHOT_INTERVAL_TIME_SHORT ->
                "INTERVAL_TOO_SHORT"
            AccessibilityService.ERROR_TAKE_SCREENSHOT_INVALID_DISPLAY ->
                "INVALID_DISPLAY"
            AccessibilityService.ERROR_TAKE_SCREENSHOT_INVALID_WINDOW ->
                "INVALID_WINDOW"
            AccessibilityService.ERROR_TAKE_SCREENSHOT_SECURE_WINDOW ->
                "SECURE_WINDOW"
            else ->
                "UNKNOWN_$code"
        }

    private fun classifyCaptureFailure(
        bitmap: Bitmap?,
        accessibility: AccessibilityClassification,
        policy: LocalPolicyEvidence,
        metadata: MetadataEvidence?,
    ): String {
        if (bitmap != null) return "CAPTURED"

        if (
            accessibility.errorCode ==
                AccessibilityService.ERROR_TAKE_SCREENSHOT_SECURE_WINDOW
        ) {
            return "FLAG_SECURE_OR_SECURE_WINDOW"
        }

        if (
            policy.screenCaptureDisabled == true ||
            metadata?.screenCapturePolicyEvidence == true
        ) {
            val managed =
                policy.managedProfile == true ||
                    metadata?.managedProfileEvidence == true
            return if (managed) {
                "MANAGED_PROFILE_SCREEN_CAPTURE_POLICY"
            } else {
                "DEVICE_POLICY_SCREEN_CAPTURE_DISABLED"
            }
        }

        if (metadata?.secureWindowEvidence == true) {
            return "FLAG_SECURE_WINDOW_EVIDENCE"
        }

        if (metadata?.protectedLayerEvidence == true) {
            return "PROTECTED_OR_SECURE_LAYER_EVIDENCE"
        }

        return when (accessibility.result) {
            "SUCCESS" ->
                "SHIZUKU_CAPTURE_FAILED_ACCESSIBILITY_ALLOWED"
            "INVALID_DISPLAY" ->
                "ACCESSIBILITY_INVALID_DISPLAY"
            "NO_ACCESSIBILITY_ACCESS" ->
                "ACCESSIBILITY_PERMISSION_MISSING"
            "INTERNAL_ERROR" ->
                "ACCESSIBILITY_INTERNAL_ERROR"
            "INTERVAL_TOO_SHORT", "RATE_GUARDED" ->
                "CAPTURE_FAILED_CLASSIFIER_RATE_LIMITED"
            else ->
                "CAPTURE_FAILED_UNCLASSIFIED_${clean(accessibility.result)}"
        }
    }

    private fun frameStats(bitmap: Bitmap): String {
        if (bitmap.width <= 0 || bitmap.height <= 0) return "invalid"

        val stepX = max(1, bitmap.width / 32)
        val stepY = max(1, bitmap.height / 32)
        var count = 0L
        var sum = 0.0
        var sumSq = 0.0
        var minL = 255.0
        var maxL = 0.0
        var nonBlack = 0L

        var y = stepY / 2
        while (y < bitmap.height) {
            var x = stepX / 2
            while (x < bitmap.width) {
                val p = bitmap.getPixel(x, y)
                val r = (p shr 16) and 0xff
                val g = (p shr 8) and 0xff
                val b = p and 0xff
                val luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
                count++
                sum += luma
                sumSq += luma * luma
                minL = kotlin.math.min(minL, luma)
                maxL = kotlin.math.max(maxL, luma)
                if (luma >= 8.0) nonBlack++
                x += stepX
            }
            y += stepY
        }

        if (count == 0L) return "empty"
        val mean = sum / count
        val variance = (sumSq / count) - (mean * mean)
        val nonBlackPct = (100.0 * nonBlack) / count
        return "mean=%.2f,var=%.2f,min=%.2f,max=%.2f,nonBlack=%.1f%%".format(
            mean,
            variance.coerceAtLeast(0.0),
            minL,
            maxL,
            nonBlackPct,
        )
    }

    private fun appendManifest(root: File, fields: List<String>) {
        runCatching {
            File(root, "manifest.tsv")
                .appendText(fields.joinToString("\t") + "\n")
        }
    }

    private fun writeTextSafe(file: File, text: String) {
        runCatching {
            file.parentFile?.mkdirs()
            file.writeText(text)
        }
    }

    private fun clean(value: String): String =
        value
            .replace('\t', ' ')
            .replace('\n', ' ')
            .replace('\r', ' ')
            .take(2000)

    private fun pruneOldBursts(parent: File?) {
        parent
            ?.listFiles()
            .orEmpty()
            .filter { it.isDirectory && it.name.startsWith("burst-") }
            .sortedByDescending { it.lastModified() }
            .drop(MAX_BURSTS_RETAINED - 1)
            .forEach { directory ->
                runCatching { directory.deleteRecursively() }
            }
    }

    private companion object {
        val SAMPLE_OFFSETS_MS = longArrayOf(
            100L,
            250L,
            500L,
            750L,
            1_000L,
            1_500L,
            2_250L,
            3_250L,
            4_500L,
            6_000L,
        )

        val METADATA_SAMPLE_INDEXES = setOf(0, 4, 7, 9)

        const val CAPTURE_SCALE = 0.35f
        const val WEBP_QUALITY = 88
        const val MAX_BURSTS_RETAINED = 4
        const val ACCESSIBILITY_CLASSIFIER_MIN_INTERVAL_MS = 450L
        const val ACCESSIBILITY_CLASSIFIER_TIMEOUT_MS = 750L
    }
}
