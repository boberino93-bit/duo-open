package com.duoopen.overlay

import android.accessibilityservice.AccessibilityService
import android.graphics.Bitmap
import android.hardware.display.DisplayManager
import android.os.Build
import android.os.SystemClock
import android.view.Display
import android.view.accessibility.AccessibilityWindowInfo
import com.duoopen.debug.DuoDiagnostics
import com.duoopen.shell.ShizukuBridge
import org.json.JSONObject
import java.io.File
import java.time.Instant
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicLong
import kotlin.math.roundToInt

/**
 * S1H read-only visual forensics.
 *
 * Each accepted opening schedules an alternating COVER/INNER screenshot burst.
 * We first use AccessibilityService.takeScreenshotOfWindow() as the policy gate:
 * it captures the foreground window underneath accessibility overlays and gives
 * explicit secure-window/rate-limit/invalid-display errors. Only after that gate
 * succeeds do we ask the already-authorized Shizuku shell path for a whole-display
 * composite. The shell path refuses to return a bitmap when secure layers are
 * reported. This means a managed/work app or FLAG_SECURE window is evidence, not
 * something this diagnostic path attempts to bypass.
 */
internal object VisualForensicsRecorder {
    private const val TAG_DIR = "visual-forensics"
    private const val SAVE_SCALE = 0.35f
    private const val SCREENSHOT_TIMEOUT_MS = 1_300L
    private const val MAX_ATTEMPT_DIRS = 3

    private val session = AtomicLong(0L)
    private val scheduler =
        Executors.newSingleThreadScheduledExecutor { runnable ->
            Thread(runnable, "duo-visual-forensics").apply { isDaemon = true }
        }

    private enum class Role(val width: Int, val height: Int) {
        COVER(1080, 2520),
        INNER(1968, 2184),
    }

    private data class WindowGate(
        val ok: Boolean,
        val bitmap: Bitmap?,
        val errorCode: Int,
        val status: String,
        val packageName: String?,
        val windowId: Int,
        val windowType: Int,
    )

    /** Alternating samples keep Android's ~333 ms accessibility capture limit safe. */
    private val plan =
        listOf(
            120L to Role.COVER,
            540L to Role.INNER,
            960L to Role.COVER,
            1_380L to Role.INNER,
            1_800L to Role.COVER,
            2_220L to Role.INNER,
            2_640L to Role.COVER,
            3_060L to Role.INNER,
            3_480L to Role.COVER,
            3_900L to Role.INNER,
            4_320L to Role.COVER,
            4_740L to Role.INNER,
            5_160L to Role.COVER,
            5_580L to Role.INNER,
            6_000L to Role.COVER,
            6_420L to Role.INNER,
        )

    fun start(
        service: AccessibilityService,
        displayManager: DisplayManager,
        openingGeneration: Long,
        reason: String,
    ) {
        val token = session.incrementAndGet()
        val startedUptime = SystemClock.uptimeMillis()
        val root = File(service.filesDir, TAG_DIR).apply { mkdirs() }
        prune(root)
        val attempt =
            File(
                root,
                "opening-${openingGeneration}-${System.currentTimeMillis()}",
            ).apply { mkdirs() }

        appendManifest(
            attempt,
            JSONObject()
                .put("event", "session-start")
                .put("token", token)
                .put("generation", openingGeneration)
                .put("reason", reason)
                .put("wallClock", Instant.now().toString())
                .put("uptimeMs", startedUptime)
                .put("saveScale", SAVE_SCALE)
                .put("securityModel", "accessibility-window-policy-gate-before-shell-composite"),
        )

        DuoDiagnostics.event(
            "visual-forensics",
            "START token=$token generation=$openingGeneration reason=$reason " +
                "samples=${plan.size} spanMs=${plan.last().first}",
        )

        plan.forEachIndexed { index, (delayMs, role) ->
            scheduler.schedule(
                {
                    if (session.get() != token) return@schedule
                    captureOne(
                        service = service,
                        displayManager = displayManager,
                        attempt = attempt,
                        token = token,
                        generation = openingGeneration,
                        startedUptime = startedUptime,
                        plannedMs = delayMs,
                        sequence = index + 1,
                        role = role,
                    )
                },
                delayMs,
                TimeUnit.MILLISECONDS,
            )
        }
    }

    fun cancel(reason: String) {
        val token = session.incrementAndGet()
        DuoDiagnostics.event(
            "visual-forensics",
            "CANCEL token=$token reason=$reason",
        )
    }

    private fun captureOne(
        service: AccessibilityService,
        displayManager: DisplayManager,
        attempt: File,
        token: Long,
        generation: Long,
        startedUptime: Long,
        plannedMs: Long,
        sequence: Int,
        role: Role,
    ) {
        val actualMs = SystemClock.uptimeMillis() - startedUptime
        val display =
            displayManager.displays.firstOrNull { candidate ->
                val mode = runCatching { candidate.mode }.getOrNull()
                mode != null &&
                    mode.physicalWidth == role.width &&
                    mode.physicalHeight == role.height
            }

        if (display == null) {
            recordNoPixels(
                attempt, token, generation, sequence, role, plannedMs, actualMs,
                displayId = -1,
                status = "NO_LOGICAL_DISPLAY",
                errorCode = -1,
                packageName = null,
                extra = displaySummary(displayManager),
            )
            return
        }

        val gate = policyGate(service, display.displayId)
        if (!gate.ok || gate.bitmap == null) {
            recordNoPixels(
                attempt, token, generation, sequence, role, plannedMs, actualMs,
                displayId = display.displayId,
                status = gate.status,
                errorCode = gate.errorCode,
                packageName = gate.packageName,
                extra =
                    "windowId=${gate.windowId} windowType=${gate.windowType}; " +
                        "consult forensicCapturePolicy/forensicUsers for enterprise/work-profile evidence",
            )
            return
        }

        val prefix =
            "%02d-%05dms-%s-d%d".format(
                sequence,
                actualMs.coerceAtLeast(0L),
                role.name.lowercase(),
                display.displayId,
            )

        val underlayFile = File(attempt, "$prefix-window-underlay.png")
        val underlayOk = saveScaledPng(gate.bitmap, underlayFile)

        // The policy gate already succeeded. The shell composite is supplemental:
        // it includes wallpaper/SystemUI/our overlay and is useful for comparison.
        val composite =
            if (ShizukuBridge.ready) {
                runCatching {
                    ShizukuBridge.captureDiagnostic(
                        displayId = display.displayId,
                        excluded = emptyList(),
                        scale = SAVE_SCALE,
                    )
                }.getOrNull()
            } else {
                null
            }

        var compositeFile: File? = null
        if (
            composite?.ok == true &&
            !composite.secure &&
            composite.bitmap != null
        ) {
            compositeFile = File(attempt, "$prefix-display-composite.png")
            composite.bitmap.useBitmap { bitmap ->
                bitmap.outputPng(compositeFile)
            }
        } else {
            composite?.bitmap?.let { bitmap ->
                if (!bitmap.isRecycled) runCatching { bitmap.recycle() }
            }
        }

        appendManifest(
            attempt,
            JSONObject()
                .put("event", "capture")
                .put("token", token)
                .put("generation", generation)
                .put("sequence", sequence)
                .put("role", role.name)
                .put("plannedMs", plannedMs)
                .put("actualMs", actualMs)
                .put("displayId", display.displayId)
                .put("display", displaySummary(display))
                .put("windowGate", "OK")
                .put("windowId", gate.windowId)
                .put("windowType", gate.windowType)
                .put("package", gate.packageName)
                .put("windowUnderlaySaved", underlayOk)
                .put("windowUnderlayFile", underlayFile.takeIf { underlayOk }?.name)
                .put("compositeAttempted", composite != null)
                .put("compositeOk", composite?.ok == true)
                .put("compositeSecure", composite?.secure == true)
                .put("compositeStatus", composite?.captureStatus ?: -1)
                .put("compositeApi", composite?.captureApi)
                .put("compositeMs", composite?.captureMs ?: -1L)
                .put("compositeError", composite?.error)
                .put("compositeFile", compositeFile?.name)
                .put("wallClock", Instant.now().toString()),
        )

        DuoDiagnostics.event(
            "visual-forensics",
            "capture seq=$sequence role=${role.name} plannedMs=$plannedMs actualMs=$actualMs " +
                "display=${display.displayId} package=${gate.packageName} " +
                "windowSaved=$underlayOk compositeOk=${composite?.ok == true} " +
                "compositeSecure=${composite?.secure == true} compositeError=${composite?.error}",
        )
    }

    private fun policyGate(
        service: AccessibilityService,
        displayId: Int,
    ): WindowGate {
        if (Build.VERSION.SDK_INT < 34) {
            return WindowGate(
                ok = false,
                bitmap = null,
                errorCode = -34,
                status = "WINDOW_CAPTURE_API_UNAVAILABLE",
                packageName = null,
                windowId = -1,
                windowType = -1,
            )
        }

        val windows =
            runCatching {
                service.windowsOnAllDisplays.get(displayId).orEmpty()
            }.getOrDefault(emptyList())

        val target =
            windows.firstOrNull {
                it.type == AccessibilityWindowInfo.TYPE_APPLICATION &&
                    (it.isFocused || it.isActive)
            }
                ?: windows.firstOrNull {
                    it.type == AccessibilityWindowInfo.TYPE_APPLICATION
                }
                ?: windows.firstOrNull {
                    it.type != AccessibilityWindowInfo.TYPE_ACCESSIBILITY_OVERLAY &&
                        (it.isFocused || it.isActive)
                }
                ?: windows.firstOrNull {
                    it.type != AccessibilityWindowInfo.TYPE_ACCESSIBILITY_OVERLAY
                }

        if (target == null) {
            return WindowGate(
                ok = false,
                bitmap = null,
                errorCode = -4,
                status = "NO_TARGET_WINDOW_UNDER_OVERLAY",
                packageName = null,
                windowId = -1,
                windowType = -1,
            )
        }

        val packageName =
            runCatching { target.root?.packageName?.toString() }
                .getOrNull()

        val latch = CountDownLatch(1)
        var screenshot: AccessibilityService.ScreenshotResult? = null
        var errorCode = 0

        runCatching {
            service.takeScreenshotOfWindow(
                target.id,
                service.mainExecutor,
                object : AccessibilityService.TakeScreenshotCallback {
                    override fun onSuccess(screenshotResult: AccessibilityService.ScreenshotResult) {
                        screenshot = screenshotResult
                        latch.countDown()
                    }

                    override fun onFailure(error: Int) {
                        errorCode = error
                        latch.countDown()
                    }
                },
            )
        }.onFailure {
            return WindowGate(
                ok = false,
                bitmap = null,
                errorCode = -5,
                status = "WINDOW_CAPTURE_THROW:${it.javaClass.simpleName}",
                packageName = packageName,
                windowId = target.id,
                windowType = target.type,
            )
        }

        if (!latch.await(SCREENSHOT_TIMEOUT_MS, TimeUnit.MILLISECONDS)) {
            return WindowGate(
                ok = false,
                bitmap = null,
                errorCode = -2,
                status = "WINDOW_CAPTURE_TIMEOUT",
                packageName = packageName,
                windowId = target.id,
                windowType = target.type,
            )
        }

        if (errorCode != 0) {
            return WindowGate(
                ok = false,
                bitmap = null,
                errorCode = errorCode,
                status = accessibilityError(errorCode),
                packageName = packageName,
                windowId = target.id,
                windowType = target.type,
            )
        }

        val result = screenshot
            ?: return WindowGate(
                ok = false,
                bitmap = null,
                errorCode = -6,
                status = "WINDOW_CAPTURE_NO_RESULT",
                packageName = packageName,
                windowId = target.id,
                windowType = target.type,
            )

        val buffer = result.hardwareBuffer
        val bitmap =
            try {
                val hardware = Bitmap.wrapHardwareBuffer(buffer, result.colorSpace)
                hardware?.copy(Bitmap.Config.ARGB_8888, false)
            } finally {
                runCatching { buffer.close() }
            }

        return WindowGate(
            ok = bitmap != null,
            bitmap = bitmap,
            errorCode = if (bitmap != null) 0 else -7,
            status = if (bitmap != null) "OK" else "WINDOW_CAPTURE_UNREADABLE_BUFFER",
            packageName = packageName,
            windowId = target.id,
            windowType = target.type,
        )
    }

    private fun accessibilityError(code: Int): String =
        when (code) {
            AccessibilityService.ERROR_TAKE_SCREENSHOT_INTERNAL_ERROR ->
                "ACCESSIBILITY_INTERNAL_ERROR"
            AccessibilityService.ERROR_TAKE_SCREENSHOT_NO_ACCESSIBILITY_ACCESS ->
                "NO_ACCESSIBILITY_SCREENSHOT_ACCESS"
            AccessibilityService.ERROR_TAKE_SCREENSHOT_INTERVAL_TIME_SHORT ->
                "ACCESSIBILITY_RATE_LIMIT"
            AccessibilityService.ERROR_TAKE_SCREENSHOT_INVALID_DISPLAY ->
                "INVALID_LOGICAL_DISPLAY"
            AccessibilityService.ERROR_TAKE_SCREENSHOT_INVALID_WINDOW ->
                "INVALID_TARGET_WINDOW"
            AccessibilityService.ERROR_TAKE_SCREENSHOT_SECURE_WINDOW ->
                "SECURE_WINDOW_OR_ENTERPRISE_POLICY_BLOCKED"
            else -> "ACCESSIBILITY_ERROR_$code"
        }

    private fun recordNoPixels(
        attempt: File,
        token: Long,
        generation: Long,
        sequence: Int,
        role: Role,
        plannedMs: Long,
        actualMs: Long,
        displayId: Int,
        status: String,
        errorCode: Int,
        packageName: String?,
        extra: String,
    ) {
        appendManifest(
            attempt,
            JSONObject()
                .put("event", "capture")
                .put("token", token)
                .put("generation", generation)
                .put("sequence", sequence)
                .put("role", role.name)
                .put("plannedMs", plannedMs)
                .put("actualMs", actualMs)
                .put("displayId", displayId)
                .put("status", status)
                .put("errorCode", errorCode)
                .put("package", packageName)
                .put("pixelsPersisted", false)
                .put("detail", extra)
                .put("wallClock", Instant.now().toString()),
        )
        DuoDiagnostics.event(
            "visual-forensics",
            "capture seq=$sequence role=${role.name} plannedMs=$plannedMs actualMs=$actualMs " +
                "display=$displayId status=$status errorCode=$errorCode package=$packageName",
        )
    }

    private fun saveScaledPng(bitmap: Bitmap, file: File): Boolean =
        bitmap.useBitmap { original ->
            val width = (original.width * SAVE_SCALE).roundToInt().coerceAtLeast(1)
            val height = (original.height * SAVE_SCALE).roundToInt().coerceAtLeast(1)
            val scaled =
                if (width == original.width && height == original.height) {
                    original
                } else {
                    Bitmap.createScaledBitmap(original, width, height, true)
                }
            try {
                scaled.outputPng(file)
            } finally {
                if (scaled !== original && !scaled.isRecycled) {
                    runCatching { scaled.recycle() }
                }
            }
        }

    private fun Bitmap.outputPng(file: File): Boolean =
        runCatching {
            file.parentFile?.mkdirs()
            file.outputStream().buffered().use { out ->
                check(compress(Bitmap.CompressFormat.PNG, 100, out))
            }
            true
        }.getOrDefault(false)

    private inline fun <T> Bitmap.useBitmap(block: (Bitmap) -> T): T =
        try {
            block(this)
        } finally {
            if (!isRecycled) runCatching { recycle() }
        }

    private fun appendManifest(attempt: File, json: JSONObject) {
        runCatching {
            File(attempt, "capture-manifest.jsonl")
                .appendText(json.toString() + "\n")
        }
    }

    private fun displaySummary(displayManager: DisplayManager): String =
        displayManager.displays.joinToString(" | ") { displaySummary(it) }

    private fun displaySummary(display: Display): String {
        val mode = runCatching { display.mode }.getOrNull()
        return if (mode == null) {
            "id=${display.displayId} name=${display.name} state=${display.state}"
        } else {
            "id=${display.displayId} name=${display.name} state=${display.state} " +
                "${mode.physicalWidth}x${mode.physicalHeight}@${mode.refreshRate}"
        }
    }

    private fun prune(root: File) {
        val dirs =
            root.listFiles()
                .orEmpty()
                .filter { it.isDirectory }
                .sortedByDescending { it.lastModified() }
        dirs.drop(MAX_ATTEMPT_DIRS - 1).forEach { old ->
            runCatching { old.deleteRecursively() }
        }
    }
}
