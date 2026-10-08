package com.duoopen.debug

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import android.hardware.display.DisplayManager
import android.os.Bundle
import android.os.SystemClock
import android.view.Display
import android.view.SurfaceControl
import com.duoopen.shell.ShizukuBridge
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.io.File
import java.security.MessageDigest
import java.time.Instant
import java.util.Locale

/**
 * S1H visual evidence recorder. Diagnostic-only: no display power, routing,
 * animation, ownership, or transition state is changed here.
 *
 * Each accepted opening gets a sparse four-sample burst from two independent
 * capture paths:
 *  - logical-excluded: IWindowManager capture of a current logical display,
 *    excluding Duo Open surfaces when handles are available;
 *  - physical-screencap: /system/bin/screencap -d using the stable physical
 *    Fold7 display id, even when no logical route exists.
 *
 * The second path is not a policy bypass. Android secure-content and enterprise
 * screen-capture restrictions remain authoritative. We export enough policy,
 * profile, focus, route and raw backend evidence to distinguish a protected
 * work app from route absence, timeout/backend failure, and a dark/blank frame.
 */
object VisualForensics {
    private const val MARKER = "STABILIZATION_S1H_VISUAL_FORENSICS_V1"
    private const val SCALE = 0.50f
    private val OFFSETS_MS = longArrayOf(0L, 500L, 1_200L, 2_500L)
    private const val MAX_SESSIONS = 5
    private const val RETENTION_MS = 24L * 60L * 60L * 1_000L

    private val lock = Any()
    private var activeGeneration = Long.MIN_VALUE

    private data class Route(val id: Int, val state: Int)
    private data class Metrics(val mean: Double, val range: Int, val dark: Double)
    private data class PolicyContext(
        val raw: Bundle?,
        val devicePolicy: String,
        val users: String,
        val topActivity: String,
        val secureWindows: String,
        val topUser: Int?,
        val managedUsers: Set<Int>,
        val captureRestricted: Boolean,
        val secureHint: Boolean,
    )

    private data class Record(
        val sample: Int,
        val targetMs: Long,
        val actualMs: Long,
        val panel: String,
        val backend: String,
        val logicalId: Int,
        val physicalId: Long,
        val displayState: Int,
        val exclusions: Int,
        val rawStatus: String,
        val secure: Boolean,
        val error: String?,
        val file: String?,
        val bytes: Long,
        val sha256: String?,
        val meanLuma: Double?,
        val lumaRange: Int?,
        val darkFraction: Double?,
    )

    fun beginOpeningBurst(
        context: Context,
        displayManager: DisplayManager,
        scope: CoroutineScope,
        openingGeneration: Long,
        reason: String,
        excludedLayers: List<SurfaceControl>,
    ) {
        synchronized(lock) {
            if (activeGeneration == openingGeneration) return
            activeGeneration = openingGeneration
        }

        val app = context.applicationContext
        val startedElapsed = SystemClock.elapsedRealtime()
        val wall = System.currentTimeMillis()
        val safeReason = reason.replace(Regex("[^A-Za-z0-9._-]"), "_").take(48)
        val root = File(app.filesDir, "visual-forensics").apply { mkdirs() }
        prune(root)
        val session = File(root, "opening-g$openingGeneration-$wall-$safeReason").apply { mkdirs() }
        val exclusions = excludedLayers.toList()

        File(session, "README.txt").writeText(
            buildString {
                appendLine("Duo Open S1H visual forensic burst")
                appendLine("marker=$MARKER")
                appendLine("started=${Instant.now()}")
                appendLine("generation=$openingGeneration")
                appendLine("reason=$reason")
                appendLine("sampleOffsetsMs=${OFFSETS_MS.joinToString(",")}")
                appendLine("captureScale=$SCALE")
                appendLine("overlayExclusionsAtStart=${exclusions.size}")
                appendLine()
                appendLine("logical-excluded requires a current logical route and excludes Duo Open surfaces when possible.")
                appendLine("physical-screencap targets the stable physical display id and cannot exclude Duo Open surfaces.")
                appendLine("Existing hidden logical capture has a 400ms callback timeout.")
                appendLine("Secure logical frames are never persisted.")
                appendLine("FLAG_SECURE/protected content and device/profile-owner policy remain enforced; this recorder does not bypass them.")
                appendLine("Low-information/dark pixels are an observation only, not proof of failure.")
            }
        )

        DuoDiagnostics.event("visual-forensics", "burst-start generation=$openingGeneration reason=$reason exclusions=${exclusions.size}")

        scope.launch(Dispatchers.IO) {
            val records = mutableListOf<Record>()
            val physical = runCatching { ShizukuBridge.resolveCoverDisplay() }.getOrNull()
            val coverPhysical = physical?.getLong("physicalDisplayId", -1L) ?: -1L
            val innerPhysical = physical?.getLong("innerPhysicalDisplayId", -1L) ?: -1L

            File(session, "physical-identities.txt").writeText(
                "coverPhysicalDisplayId=$coverPhysical\n" +
                    "innerPhysicalDisplayId=$innerPhysical\n" +
                    "resolveOk=${physical?.getBoolean("ok", false) == true}\n" +
                    "resolveLogicalHint=${physical?.getInt("targetDisplayId", -1) ?: -1}\n" +
                    "resolveError=${physical?.getString("error")}\n"
            )

            OFFSETS_MS.forEachIndexed { index, target ->
                if (!isCurrent(openingGeneration)) return@launch
                val wait = target - (SystemClock.elapsedRealtime() - startedElapsed)
                if (wait > 0L) delay(wait)
                if (!isCurrent(openingGeneration)) return@launch
                val actual = SystemClock.elapsedRealtime() - startedElapsed
                val routes = routes(displayManager)

                for (panel in listOf("cover", "inner")) {
                    val route = routes[panel]
                    val physicalId = if (panel == "cover") coverPhysical else innerPhysical

                    val logical = if (route == null) {
                        Record(index, target, actual, panel, "logical-excluded", -1, physicalId,
                            Display.STATE_UNKNOWN, exclusions.size, "NO_LOGICAL_ROUTE", false, null,
                            null, 0L, null, null, null, null)
                    } else {
                        captureLogical(session, index, target, actual, panel, route, physicalId, exclusions)
                    }
                    records += logical

                    val physicalRecord = capturePhysical(session, index, target, actual, panel, route, physicalId)
                    records += physicalRecord
                }
            }

            val policy = capturePolicyContext()
            writePolicy(session, policy)
            writeManifest(session, records, policy)
            DuoDiagnostics.event("visual-forensics", "burst-complete generation=$openingGeneration records=${records.size}")
        }
    }

    private fun isCurrent(generation: Long): Boolean =
        synchronized(lock) { activeGeneration == generation }

    private fun routes(dm: DisplayManager): Map<String, Route> {
        val out = mutableMapOf<String, Route>()
        dm.displays.forEach { display ->
            val mode = runCatching { display.mode }.getOrNull() ?: return@forEach
            val w = mode.physicalWidth
            val h = mode.physicalHeight
            fun matches(a: Int, b: Int) = (w == a && h == b) || (w == b && h == a)
            when {
                matches(1080, 2520) -> out["cover"] = Route(display.displayId, display.state)
                matches(1968, 2184) -> out["inner"] = Route(display.displayId, display.state)
            }
        }
        return out
    }

    private fun captureLogical(
        session: File,
        sample: Int,
        target: Long,
        actual: Long,
        panel: String,
        route: Route,
        physicalId: Long,
        exclusions: List<SurfaceControl>,
    ): Record {
        /*
         * The S1H recorder was merged without the proposed captureForensics()
         * bridge transaction. Use the existing read-only logical capture path
         * instead of calling a nonexistent API. A null result can mean backend
         * unavailability or protected content; current ShellProtocol cannot
         * distinguish those causes, so the status remains explicitly ambiguous.
         */
        val bitmap = runCatching {
            ShizukuBridge.capture(route.id, exclusions, SCALE)
        }.getOrElse { error ->
            return Record(sample, target, actual, panel, "logical-excluded", route.id, physicalId,
                route.state, exclusions.size, "CAPTURE_CALL_EXCEPTION", false,
                "${error.javaClass.simpleName}: ${error.message}", null, 0L, null, null, null, null)
        }

        if (bitmap == null) {
            return Record(sample, target, actual, panel, "logical-excluded", route.id, physicalId,
                route.state, exclusions.size, "CAPTURE_UNAVAILABLE_OR_SECURE", false,
                "Current ShizukuBridge CAPTURE transaction does not expose secure/backend attribution",
                null, 0L, null, null, null, null)
        }

        val name = "s${sample}-${target}ms-${panel}-logical-excluded.png"
        val file = File(session, name)
        return try {
            val metric = metrics(bitmap)
            file.outputStream().buffered().use { output -> bitmap.compress(Bitmap.CompressFormat.PNG, 100, output) }
            Record(sample, target, actual, panel, "logical-excluded", route.id, physicalId,
                route.state, exclusions.size, "CAPTURED", false, null, name, file.length(), sha256(file),
                metric.mean, metric.range, metric.dark)
        } catch (error: Throwable) {
            runCatching { file.delete() }
            Record(sample, target, actual, panel, "logical-excluded", route.id, physicalId,
                route.state, exclusions.size, "PERSIST_FAILED", false,
                "${error.javaClass.simpleName}: ${error.message}", null, 0L, null, null, null, null)
        } finally {
            bitmap.recycle()
        }
    }

    private fun capturePhysical(
        session: File,
        sample: Int,
        target: Long,
        actual: Long,
        panel: String,
        route: Route?,
        physicalId: Long,
    ): Record {
        if (physicalId < 0L) {
            return Record(sample, target, actual, panel, "physical-screencap", route?.id ?: -1, physicalId,
                route?.state ?: Display.STATE_UNKNOWN, 0, "NO_PHYSICAL_ID", false, null,
                null, 0L, null, null, null, null)
        }

        /*
         * capturePhysicalForensics() and its shell transaction were never
         * implemented in the current bridge/protocol. Do not invent a command
         * path or silently bypass Android capture policy. Preserve the forensic
         * record as an explicit unavailable backend until that protocol is
         * designed and reviewed.
         */
        return Record(sample, target, actual, panel, "physical-screencap", route?.id ?: -1, physicalId,
            route?.state ?: Display.STATE_UNKNOWN, 0, "PHYSICAL_BACKEND_UNAVAILABLE", false,
            "Current ShellProtocol has no physical screencap forensic transaction",
            null, 0L, null, null, null, null)
    }

    private fun capturePolicyContext(): PolicyContext {
        val raw = runCatching { ShizukuBridge.displayProbe() }.getOrNull()
        val devicePolicy = raw?.getString("device_policy_capture").orEmpty()
        val users = raw?.getString("user_profiles").orEmpty()
        val topActivity = raw?.getString("top_activity_user").orEmpty()
        val secureWindows = raw?.getString("secure_windows").orEmpty()

        val topUser = Regex("(?:^|\\s)u(\\d+)").find(topActivity)?.groupValues?.getOrNull(1)?.toIntOrNull()
        val managedUsers = Regex("(?i)(?:profile owner|managed profile|work profile)[^\\n]{0,160}?(?:user(?:Id)?\\s*[=:]?\\s*|u)(\\d+)")
            .findAll(devicePolicy + "\n" + users)
            .mapNotNull { it.groupValues.getOrNull(1)?.toIntOrNull() }
            .toSet()

        val restricted = devicePolicy.lineSequence().any { line ->
            val s = line.lowercase(Locale.ROOT)
            val capture = s.contains("screen capture") || s.contains("screencapture") ||
                s.contains("screen_capture") || s.contains("no_screen_capture")
            val denied = s.contains("=true") || s.contains(": true") || s.contains("disabled") ||
                s.contains("disallow") || s.contains("no_screen_capture")
            val falseValue = s.contains("=false") || s.contains(": false")
            capture && denied && !falseValue
        }
        val secureHint = secureWindows.lineSequence().any { line ->
            val s = line.lowercase(Locale.ROOT)
            s.contains("flag_secure") || s.contains("secure=true") ||
                s.contains("secure layer") || s.contains("is secure")
        }

        return PolicyContext(raw, devicePolicy, users, topActivity, secureWindows,
            topUser, managedUsers, restricted, secureHint)
    }

    private fun writePolicy(session: File, context: PolicyContext) {
        File(session, "capture-context.txt").writeText(
            buildString {
                appendLine("generated=${Instant.now()}")
                appendLine("topUserId=${context.topUser}")
                appendLine("managedProfileUserIds=${context.managedUsers.sorted().joinToString(",")}")
                appendLine("screenCaptureRestricted=${context.captureRestricted}")
                appendLine("secureWindowHint=${context.secureHint}")
                appendLine("captureBackend=${context.raw?.getString("capture_backend") ?: "<unavailable>"}")
                appendLine("\n=== device_policy_capture ===\n${context.devicePolicy.ifBlank { "<unavailable>" }}")
                appendLine("\n=== user_profiles ===\n${context.users.ifBlank { "<unavailable>" }}")
                appendLine("\n=== top_activity_user ===\n${context.topActivity.ifBlank { "<unavailable>" }}")
                appendLine("\n=== secure_windows ===\n${context.secureWindows.ifBlank { "<unavailable>" }}")
            }
        )
    }

    private fun writeManifest(session: File, records: List<Record>, context: PolicyContext) {
        val file = File(session, "manifest.tsv")
        file.writeText("sample\ttargetMs\tactualMs\tpanel\tbackend\tlogicalId\tphysicalId\tdisplayState\trawStatus\tclassification\tsecure\tfile\tbytes\tsha256\tmeanLuma\tlumaRange\tdarkFraction\terror\n")
        records.forEach { r ->
            file.appendText(listOf(
                r.sample, r.targetMs, r.actualMs, r.panel, r.backend, r.logicalId, r.physicalId,
                r.displayState, r.rawStatus, classify(r, context), r.secure, r.file.orEmpty(), r.bytes,
                r.sha256.orEmpty(), r.meanLuma?.let { "%.2f".format(Locale.US, it) }.orEmpty(),
                r.lumaRange ?: "", r.darkFraction?.let { "%.4f".format(Locale.US, it) }.orEmpty(),
                sanitize(r.error)
            ).joinToString("\t") + "\n")
        }
    }

    private fun classify(record: Record, context: PolicyContext): String {
        if (record.rawStatus == "NO_LOGICAL_ROUTE") return "ROUTE_ABSENT_NOT_CAPTURE_FAILURE"
        if (record.rawStatus == "NO_PHYSICAL_ID") return "PHYSICAL_ID_RESOLUTION_FAILED"
        if (record.secure || record.rawStatus == "SECURE_LAYER_BLOCKED") return "SECURE_OR_PROTECTED_CONTENT_BLOCKED"

        val managed = context.topUser != null && context.topUser in context.managedUsers
        if (record.rawStatus != "CAPTURED") {
            if (context.captureRestricted && managed) return "WORK_PROFILE_SCREEN_CAPTURE_POLICY_BLOCKED"
            if (context.captureRestricted) return "DEVICE_POLICY_SCREEN_CAPTURE_BLOCKED"
            if (context.secureHint) return "SECURE_WINDOW_OR_PROTECTED_CONTENT_SUSPECTED"
            val e = record.error.orEmpty().lowercase(Locale.ROOT)
            if (e.contains("timeout") || e.contains("timed out")) return "CAPTURE_BACKEND_TIMEOUT"
            if (e.contains("permission") || e.contains("security")) return "CAPTURE_PERMISSION_OR_POLICY_ERROR"
            return "CAPTURE_BACKEND_OR_PANEL_FAILURE"
        }

        val low = record.meanLuma != null && record.lumaRange != null && record.darkFraction != null &&
            record.lumaRange <= 8 && record.darkFraction >= 0.98
        if (low) {
            if (context.captureRestricted && managed) return "CAPTURED_REDACTED_OR_DARK_WORK_PROFILE_POLICY_POSSIBLE"
            if (context.captureRestricted) return "CAPTURED_REDACTED_OR_DARK_DEVICE_POLICY_POSSIBLE"
            if (context.secureHint) return "CAPTURED_REDACTED_OR_DARK_SECURE_WINDOW_POSSIBLE"
            if (record.backend == "physical-screencap" && record.logicalId < 0) {
                return "CAPTURED_LOW_INFORMATION_PHYSICAL_WITHOUT_LOGICAL_ROUTE"
            }
            return "CAPTURED_LOW_INFORMATION_FRAME"
        }
        return "CAPTURED_USABLE_FRAME"
    }

    private fun metrics(bitmap: Bitmap): Metrics {
        val sx = (bitmap.width / 48).coerceAtLeast(1)
        val sy = (bitmap.height / 48).coerceAtLeast(1)
        var count = 0L
        var sum = 0.0
        var min = 255
        var max = 0
        var dark = 0L
        var y = 0
        while (y < bitmap.height) {
            var x = 0
            while (x < bitmap.width) {
                val p = bitmap.getPixel(x, y)
                val l = (Color.red(p) * 299 + Color.green(p) * 587 + Color.blue(p) * 114) / 1000
                count++
                sum += l
                min = minOf(min, l)
                max = maxOf(max, l)
                if (l <= 5) dark++
                x += sx
            }
            y += sy
        }
        if (count == 0L) return Metrics(0.0, 0, 1.0)
        return Metrics(sum / count, max - min, dark.toDouble() / count.toDouble())
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().buffered().use { input ->
            val buffer = ByteArray(32 * 1024)
            while (true) {
                val n = input.read(buffer)
                if (n <= 0) break
                digest.update(buffer, 0, n)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private fun sanitize(value: String?): String = value.orEmpty()
        .replace('\t', ' ').replace('\n', ' ').replace('\r', ' ').take(1200)

    private fun prune(root: File) {
        val now = System.currentTimeMillis()
        root.listFiles().orEmpty().filter { it.isDirectory }
            .sortedByDescending { it.lastModified() }
            .forEachIndexed { index, dir ->
                if (index >= MAX_SESSIONS || now - dir.lastModified() > RETENTION_MS) {
                    runCatching { dir.deleteRecursively() }
                }
            }
    }
}
