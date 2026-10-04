package com.duoopen.overlay

import android.content.Context
import android.graphics.Bitmap
import android.hardware.display.DisplayManager
import android.os.Handler
import android.os.SystemClock
import android.view.SurfaceControl
import com.duoopen.debug.DuoDiagnostics
import com.duoopen.shell.ShizukuBridge
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import java.io.File
import java.time.Instant
import java.util.concurrent.atomic.AtomicLong
import kotlin.math.max

/**
 * S1H read-only visual forensics.
 *
 * Captures a timestamped burst of both Fold7 panel routes after an accepted
 * opening edge. The capture uses the same overlay exclusion SurfaceControl as
 * the renderer, so successful frames show what is actually underneath Duo Open.
 *
 * Protected content is fail-closed: secure frames are never persisted. Capture
 * failures are retained as structured manifest rows with raw callback status and
 * policy/window evidence so ROUTE_ABSENT, FLAG_SECURE, managed-profile policy,
 * timeout, and API failures are not collapsed into the same "black screenshot".
 */
internal class Fold7VisualForensics(
    private val context: Context,
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

    private val burstSequence = AtomicLong(0L)
    @Volatile private var lastGeneration = -1L

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
        }

        val burstId = burstSequence.incrementAndGet()
        val startedElapsed = SystemClock.elapsedRealtime()
        val startedWall = System.currentTimeMillis()
        val root =
            File(
                context.filesDir,
                "visual-forensics/burst-${startedWall}-g${generation}",
            ).apply {
                mkdirs()
            }

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
                appendLine("securePolicy=secure/protected captures are never persisted")
                appendLine("overlayPolicy=own overlay layer excluded when a PanelEngine route exists")
                appendLine("failurePolicy=manifest records raw callback/policy evidence instead of assuming every failure is secure content")
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
            val mode =
                runCatching { display.mode }
                    .getOrNull()
                    ?: return@mapNotNull null
            val geometry = mode.physicalWidth to mode.physicalHeight
            if (
                geometry != (1080 to 2520) &&
                geometry != (1968 to 2184)
            ) {
                return@mapNotNull null
            }

            Target(
                panel =
                    if (geometry == (1968 to 2184)) "inner" else "cover",
                displayId = display.displayId,
                state = display.state,
                width = mode.physicalWidth,
                height = mode.physicalHeight,
                excluded =
                    runCatching {
                        excludedLayersForDisplay(display.displayId)
                    }.getOrDefault(emptyList()),
            )
        }

    private data class MetadataEvidence(
        val capturePolicy: String,
        val secureWindowEvidence: Boolean,
        val screenCapturePolicyEvidence: Boolean,
        val managedProfileEvidence: Boolean,
        val protectedLayerEvidence: Boolean,
    )

    private fun captureMetadata(
        root: File,
        index: Int,
        offsetMs: Long,
        elapsedMs: Long,
    ): MetadataEvidence {
        val bundle =
            runCatching {
                ShizukuBridge.visualForensicsProbe()
            }.getOrNull()

        val wallpaper = bundle?.getString("wallpaper").orEmpty()
        val appWidgets = bundle?.getString("appWidgets").orEmpty()
        val windowRendering = bundle?.getString("windowRendering").orEmpty()
        val surfaceLayers = bundle?.getString("surfaceLayers").orEmpty()
        val capturePolicy = bundle?.getString("capturePolicy").orEmpty()
        val topActivity = bundle?.getString("topActivity").orEmpty()

        val text =
            buildString {
                appendLine("sampleIndex=$index")
                appendLine("scheduledOffsetMs=$offsetMs")
                appendLine("actualElapsedMs=$elapsedMs")
                appendLine("generated=${Instant.now()}")
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
            }

        writeTextSafe(
            File(
                root,
                "metadata-%02d-%04dms.txt".format(index, offsetMs),
            ),
            text,
        )

        val policyLower = capturePolicy.lowercase()
        val surfaceLower = surfaceLayers.lowercase()

        return MetadataEvidence(
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
        val target =
            targets.firstOrNull {
                it.width == expectedWidth &&
                    it.height == expectedHeight
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

        val started = SystemClock.elapsedRealtime()
        val capture =
            ShizukuBridge.captureDiagnostic(
                displayId = target.displayId,
                excluded = target.excluded,
                scale = CAPTURE_SCALE,
            )
        val totalMs = SystemClock.elapsedRealtime() - started

        var classification =
            classifyCapture(
                capture = capture,
                metadata = metadata,
            )
        var fileName = ""
        var frameStats = ""

        val bitmap = capture.bitmap
        if (
            capture.ok &&
            !capture.secure &&
            bitmap != null
        ) {
            frameStats = frameStats(bitmap)
            val file =
                File(
                    root,
                    "%02d-%04dms-%s-d%d.webp".format(
                        index,
                        offsetMs,
                        panel,
                        target.displayId,
                    ),
                )

            val encoded =
                runCatching {
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
                "shellClass=${clean(capture.classification)}",
                "callbackStatus=${capture.callbackStatus}",
                "secure=${capture.secure}",
                "captureApi=${clean(capture.captureApi.orEmpty())}",
                "captureMs=${capture.captureMs}",
                "totalMs=$totalMs",
                "bitmap=${capture.bitmap != null}",
                "file=${clean(fileName)}",
                "frameStats=${clean(frameStats)}",
                "policyScreenCaptureDisabled=${metadata?.screenCapturePolicyEvidence}",
                "policyManagedProfile=${metadata?.managedProfileEvidence}",
                "secureWindowEvidence=${metadata?.secureWindowEvidence}",
                "protectedLayerEvidence=${metadata?.protectedLayerEvidence}",
                "error=${clean(capture.error.orEmpty())}",
                "reason=${clean(reason)}",
            ),
        )

        DuoDiagnostics.event(
            "visual-forensics",
            "sample=$index offset=$offsetMs panel=$panel display=${target.displayId} " +
                "state=${target.state} class=$classification shell=${capture.classification} " +
                "status=${capture.callbackStatus} secure=${capture.secure} " +
                "captureMs=${capture.captureMs} totalMs=$totalMs file=$fileName",
        )

        runCatching {
            bitmap?.recycle()
        }
    }

    private fun classifyCapture(
        capture: ShizukuBridge.DiagnosticCapture,
        metadata: MetadataEvidence?,
    ): String {
        if (capture.secure) return "SECURE_LAYER_BLOCKED"

        if (!capture.ok) {
            if (metadata?.screenCapturePolicyEvidence == true) {
                return if (metadata.managedProfileEvidence) {
                    "MANAGED_PROFILE_SCREEN_CAPTURE_POLICY"
                } else {
                    "DEVICE_POLICY_SCREEN_CAPTURE_DISABLED"
                }
            }
            if (metadata?.secureWindowEvidence == true) {
                return "FLAG_SECURE_WINDOW"
            }
            if (metadata?.protectedLayerEvidence == true) {
                return "PROTECTED_OR_SECURE_LAYER_EVIDENCE"
            }
            return capture.classification
        }

        if (capture.bitmap == null) {
            return "CAPTURE_OK_NO_PERSISTABLE_BITMAP"
        }

        return "CAPTURED"
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

    private fun appendManifest(
        root: File,
        fields: List<String>,
    ) {
        runCatching {
            File(root, "manifest.tsv")
                .appendText(
                    fields.joinToString("\t") + "\n"
                )
        }
    }

    private fun writeTextSafe(
        file: File,
        text: String,
    ) {
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
                runCatching {
                    directory.deleteRecursively()
                }
            }
    }

    private companion object {
        val SAMPLE_OFFSETS_MS =
            longArrayOf(
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

        val METADATA_SAMPLE_INDEXES =
            setOf(0, 4, 7, 9)

        const val CAPTURE_SCALE = 0.35f
        const val WEBP_QUALITY = 88
        const val MAX_BURSTS_RETAINED = 4
    }
}
