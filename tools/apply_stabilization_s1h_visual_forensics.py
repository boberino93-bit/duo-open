#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

PROTOCOL = Path("app/src/full/java/com/duoopen/shell/ShellProtocol.kt")
SHELL = Path("app/src/full/java/com/duoopen/shell/DuoShellService.kt")
BRIDGE = Path("app/src/full/java/com/duoopen/shell/ShizukuBridge.kt")
SERVICE = Path("app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt")
VISUAL = Path("app/src/full/java/com/duoopen/debug/VisualForensics.kt")
EXPORTER = Path("app/src/main/java/com/duoopen/debug/DebugBundleExporter.kt")
MARKER = "STABILIZATION_S1H_VISUAL_FORENSICS_V1"


def once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected one match, found {n}")
    return text.replace(old, new, 1)


def transform_protocol(text: str) -> str:
    if "CAPTURE_PHYSICAL_FORENSIC" in text:
        return text
    return once(
        text,
        "    const val COVER_PANEL_GEN4 = 18\n\n    const val CB_ANGLE = 1\n",
        "    const val COVER_PANEL_GEN4 = 18\n\n"
        "    // STABILIZATION_S1H_VISUAL_FORENSICS_V1: read-only physical screenshot evidence.\n"
        "    const val CAPTURE_PHYSICAL_FORENSIC = 19\n\n"
        "    const val CB_ANGLE = 1\n",
        "protocol",
    )


def transform_shell(text: str) -> str:
    if MARKER in text:
        return text
    if "STABILIZATION_S1G_FORENSIC_SUPERSET_V1" not in text:
        raise RuntimeError("S1G forensic superset must be applied before S1H")
    for forbidden in ("STABILIZATION_S1C_ACTIVE_TRANSFER_V1", "STABILIZATION_S1D_REAL_INNER_EDGE_V1"):
        if forbidden in text:
            raise RuntimeError(f"S1H cannot stack mutation marker {forbidden}")

    text = once(
        text,
        """                out.writeNoException()\n                out.writeBundle(result)\n            }\n            ShellProtocol.START_ANGLES -> {\n""",
        """                out.writeNoException()\n                out.writeBundle(result)\n            }\n            ShellProtocol.CAPTURE_PHYSICAL_FORENSIC -> {\n                // STABILIZATION_S1H_VISUAL_FORENSICS_V1\n                val physicalDisplayId = data.readLong()\n                val identity = clearCallingIdentity()\n                val result = try {\n                    capturePhysicalForensics(physicalDisplayId)\n                } catch (t: Throwable) {\n                    var root: Throwable = t\n                    while (root.cause != null) root = root.cause!!\n                    Bundle().apply {\n                        putBoolean(\"ok\", false)\n                        putString(\"status\", \"SCREENCAP_EXCEPTION\")\n                        putString(\"error\", \"${root.javaClass.simpleName}: ${root.message}\")\n                    }\n                } finally {\n                    restoreCallingIdentity(identity)\n                }\n                @Suppress(\"DEPRECATION\")\n                val fd: android.os.ParcelFileDescriptor? = result.getParcelable(\"fd\")\n                out.writeNoException()\n                try { out.writeBundle(result) } finally { runCatching { fd?.close() } }\n            }\n            ShellProtocol.START_ANGLES -> {\n""",
        "physical transaction",
    )

    text = once(
        text,
        """            putString(\n                \"window_displays\",\n                runProbe(\n                    \"dumpsys window displays | head -n 250\"\n                ),\n            )\n        }\n""",
        """            putString(\n                \"window_displays\",\n                runProbe(\n                    \"dumpsys window displays | head -n 250\"\n                ),\n            )\n\n            // S1H read-only screen-capture policy/profile/window context.\n            putString(\"device_policy_capture\", runProbe(\n                \"dumpsys device_policy 2>/dev/null | grep -E -i 'Device Owner|Profile Owner|user(Id)?[=: ]|screen.?capture|screen_capture|no_screen_capture|DISALLOW_SCREEN_CAPTURE|setScreenCaptureDisabled' | head -n 260\"\n            ))\n            putString(\"user_profiles\", runProbe(\n                \"dumpsys user 2>/dev/null | grep -E -i 'UserInfo\\\\{|profileGroupId|profileBadge|managed|work|quiet|running|state=' | head -n 220\"\n            ))\n            putString(\"top_activity_user\", runProbe(\n                \"dumpsys activity activities 2>/dev/null | grep -E -i 'topResumedActivity|mResumedActivity|mCurrentFocus|ActivityRecord\\\\{|Task\\\\{' | head -n 120\"\n            ))\n            putString(\"secure_windows\", runProbe(\n                \"dumpsys window windows 2>/dev/null | grep -E -i 'mCurrentFocus|mFocusedApp|FLAG_SECURE|secure=true|secure layer|isSecure|mAttrs' | head -n 180\"\n            ))\n            putString(\"capture_backend\", runCatching { api().name }\n                .getOrElse { \"unavailable: ${it.javaClass.simpleName}:${it.message}\" })\n        }\n""",
        "policy context",
    )

    helper = r'''    // STABILIZATION_S1H_VISUAL_FORENSICS_V1: physical-display diagnostic only.
    // Uses the platform screencap command and therefore preserves Android secure/policy behavior.
    private fun capturePhysicalForensics(physicalDisplayId: Long): Bundle {
        val started = SystemClock.elapsedRealtime()
        if (physicalDisplayId < 0L) return Bundle().apply {
            putBoolean("ok", false); putString("status", "INVALID_PHYSICAL_ID")
            putLong("physicalDisplayId", physicalDisplayId)
        }
        val temp = java.io.File.createTempFile("duo-s1h-${Process.myPid()}-", ".png", java.io.File("/data/local/tmp"))
        var process: java.lang.Process? = null
        try {
            process = ProcessBuilder(
                "/system/bin/screencap", "-p", "-d", physicalDisplayId.toString(), temp.absolutePath
            ).redirectErrorStream(true).start()
            val finished = process.waitFor(1800L, TimeUnit.MILLISECONDS)
            if (!finished) {
                process.destroyForcibly()
                return Bundle().apply {
                    putBoolean("ok", false); putString("status", "SCREENCAP_TIMEOUT")
                    putString("error", "physical screencap timed out after 1800ms")
                    putLong("physicalDisplayId", physicalDisplayId)
                    putLong("ms", SystemClock.elapsedRealtime() - started)
                }
            }
            val output = runCatching { process.inputStream.bufferedReader().use { it.readText() } }
                .getOrDefault("").take(4000)
            val exit = process.exitValue()
            val size = temp.length()
            if (exit != 0 || size < 8L) return Bundle().apply {
                putBoolean("ok", false)
                putString("status", if (exit != 0) "SCREENCAP_EXIT_$exit" else "SCREENCAP_EMPTY")
                putString("error", output.ifBlank { if (exit != 0) "screencap exited $exit" else "screencap produced no PNG bytes" })
                putLong("physicalDisplayId", physicalDisplayId); putLong("fileBytes", size)
                putLong("ms", SystemClock.elapsedRealtime() - started)
            }
            val header = ByteArray(8)
            val read = java.io.FileInputStream(temp).use { it.read(header) }
            val png = read == 8 && header.contentEquals(byteArrayOf(
                0x89.toByte(), 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a
            ))
            if (!png) return Bundle().apply {
                putBoolean("ok", false); putString("status", "SCREENCAP_NOT_PNG")
                putString("error", "screencap output did not have a PNG signature")
                putLong("physicalDisplayId", physicalDisplayId); putLong("fileBytes", size)
                putLong("ms", SystemClock.elapsedRealtime() - started)
            }
            val fd = android.os.ParcelFileDescriptor.open(temp, android.os.ParcelFileDescriptor.MODE_READ_ONLY)
            return Bundle().apply {
                putBoolean("ok", true); putString("status", "CAPTURED")
                putLong("physicalDisplayId", physicalDisplayId); putLong("fileBytes", size)
                putLong("ms", SystemClock.elapsedRealtime() - started)
                putString("commandOutput", output); putParcelable("fd", fd)
            }
        } finally {
            runCatching { process?.destroy() }
            runCatching { temp.delete() }
        }
    }

'''
    text = once(
        text,
        "    // ---- Samsung wallpaper angle reader -------------------------------------\n",
        helper + "    // ---- Samsung wallpaper angle reader -------------------------------------\n",
        "physical helper",
    )
    return text


def transform_bridge(text: str) -> str:
    if "data class ForensicCaptureOutcome" in text:
        return text
    block = r'''    // STABILIZATION_S1H_VISUAL_FORENSICS_V1: preserve capture failure semantics.
    data class ForensicCaptureOutcome(
        val ok: Boolean, val status: String, val secureLayers: Boolean,
        val bitmap: Bitmap?, val error: String?, val captureMs: Long,
        val sourceWidth: Int, val sourceHeight: Int,
    )

    data class PhysicalForensicCaptureOutcome(
        val ok: Boolean, val status: String, val error: String?,
        val captureMs: Long, val sourceBytes: Long, val commandOutput: String?,
    )

    fun captureForensics(displayId: Int, excluded: List<SurfaceControl>, scale: Float): ForensicCaptureOutcome {
        val b = call(ShellProtocol.CAPTURE) { p ->
            p.writeInt(displayId); p.writeInt(excluded.size)
            excluded.forEach { p.writeTypedObject(it, 0) }; p.writeFloat(scale)
        } ?: return ForensicCaptureOutcome(false, "CAPTURE_BACKEND_UNAVAILABLE", false, null,
            "Shizuku shell service unavailable", -1L, -1, -1)
        val shellOk = b.getBoolean("ok", false)
        val secure = b.getBoolean("secure", false)
        val error = b.getString("error")
        @Suppress("DEPRECATION") val bitmap: Bitmap? = b.getParcelable("bitmap")
        if (secure) {
            bitmap?.recycle()
            return ForensicCaptureOutcome(false, "SECURE_LAYER_BLOCKED", true, null, error,
                b.getLong("ms", -1L), b.getInt("width", -1), b.getInt("height", -1))
        }
        if (!shellOk || bitmap == null) {
            bitmap?.recycle()
            val lower = error.orEmpty().lowercase()
            val status = when {
                lower.contains("timeout") -> "CAPTURE_TIMEOUT"
                lower.contains("no display") -> "NO_LOGICAL_DISPLAY"
                lower.contains("permission") || lower.contains("security") -> "CAPTURE_PERMISSION_OR_POLICY_ERROR"
                else -> "CAPTURE_FAILED"
            }
            return ForensicCaptureOutcome(false, status, false, null, error ?: "capture returned no bitmap",
                b.getLong("ms", -1L), b.getInt("width", -1), b.getInt("height", -1))
        }
        return ForensicCaptureOutcome(true, "CAPTURED", false, bitmap, null,
            b.getLong("ms", -1L), b.getInt("width", -1), b.getInt("height", -1))
    }

    fun capturePhysicalForensics(physicalDisplayId: Long, destination: java.io.File): PhysicalForensicCaptureOutcome {
        val b = call(ShellProtocol.CAPTURE_PHYSICAL_FORENSIC) { it.writeLong(physicalDisplayId) }
            ?: return PhysicalForensicCaptureOutcome(false, "CAPTURE_BACKEND_UNAVAILABLE",
                "Shizuku shell service unavailable", -1L, 0L, null)
        val ok = b.getBoolean("ok", false)
        val status = b.getString("status") ?: if (ok) "CAPTURED" else "CAPTURE_FAILED"
        val error = b.getString("error")
        val ms = b.getLong("ms", -1L)
        val output = b.getString("commandOutput")
        @Suppress("DEPRECATION") val fd: android.os.ParcelFileDescriptor? = b.getParcelable("fd")
        if (!ok || fd == null) {
            runCatching { fd?.close() }
            return PhysicalForensicCaptureOutcome(false, if (ok) "SCREENCAP_NO_FD" else status,
                error ?: if (fd == null) "physical screencap returned no file descriptor" else null,
                ms, b.getLong("fileBytes", 0L), output)
        }
        return runCatching {
            destination.parentFile?.mkdirs()
            val copied = android.os.ParcelFileDescriptor.AutoCloseInputStream(fd).use { input ->
                destination.outputStream().buffered().use { outputStream -> input.copyTo(outputStream) }
            }
            PhysicalForensicCaptureOutcome(copied > 0L,
                if (copied > 0L) "CAPTURED" else "SCREENCAP_COPY_EMPTY",
                if (copied > 0L) null else "physical screencap FD contained no bytes", ms, copied, output)
        }.getOrElse { e ->
            runCatching { fd.close() }; runCatching { destination.delete() }
            PhysicalForensicCaptureOutcome(false, "SCREENCAP_COPY_FAILED",
                "${e.javaClass.simpleName}: ${e.message}", ms, 0L, output)
        }
    }

'''
    return once(
        text,
        "    /** Receives angles from the shell-side wallpaper log reader. */\n",
        block + "    /** Receives angles from the shell-side wallpaper log reader. */\n",
        "bridge capture outcomes",
    )


def transform_service(text: str) -> str:
    if "VisualForensics.beginOpeningBurst" in text:
        return text
    text = once(
        text,
        "import com.duoopen.debug.DuoDiagnostics\n",
        "import com.duoopen.debug.DuoDiagnostics\nimport com.duoopen.debug.VisualForensics\n",
        "service import",
    )
    old = '''        if (
            beforeOpeningState !=
                Fold7ContinuityController.State.OPENING_FROM_CLOSED &&
            continuity.state ==
                Fold7ContinuityController.State.OPENING_FROM_CLOSED
        ) {
            gen3Visual.beginOpening(
                generation = continuity.generation,
                reason = reason,
            )
        }
'''
    new = old[:-2] + '''

            // STABILIZATION_S1H_VISUAL_FORENSICS_V1: diagnostic-only sparse screenshot burst.
            val forensicExclusions = engines.values.flatMap { engine ->
                runCatching { engine.captureExclusionLayers() }.getOrDefault(emptyList())
            }
            VisualForensics.beginOpeningBurst(
                context = applicationContext,
                displayManager = displayManager,
                scope = scope,
                openingGeneration = continuity.generation,
                reason = reason,
                excludedLayers = forensicExclusions,
            )
        }
'''
    return once(text, old, new, "accepted opening burst")


def validate(protocol: str, shell: str, bridge: str, service: str, visual: str, exporter: str) -> None:
    checks = {
        "protocol": (protocol, ["CAPTURE_PHYSICAL_FORENSIC = 19"]),
        "shell": (shell, ["capturePhysicalForensics(physicalDisplayId)", '"/system/bin/screencap"', '"-d"',
                           'putString("device_policy_capture"', 'putString("secure_windows"',
                           'putString("capture_backend"', "ParcelFileDescriptor.MODE_READ_ONLY"]),
        "bridge": (bridge, ["data class ForensicCaptureOutcome", "fun captureForensics(",
                             "fun capturePhysicalForensics(", "ParcelFileDescriptor.AutoCloseInputStream",
                             '"SECURE_LAYER_BLOCKED"']),
        "service": (service, ["import com.duoopen.debug.VisualForensics", "VisualForensics.beginOpeningBurst(",
                               "engine.captureExclusionLayers()"]),
        "visual": (visual, ["object VisualForensics", "logical-excluded", "physical-screencap",
                             "WORK_PROFILE_SCREEN_CAPTURE_POLICY_BLOCKED", "SECURE_OR_PROTECTED_CONTENT_BLOCKED",
                             "ROUTE_ABSENT_NOT_CAPTURE_FAILURE"]),
        "exporter": (exporter, ["visualForensicSessions", '"visual-forensics/${session.name}"',
                                 "Recent timestamped panel screenshots"]),
    }
    for label, (text, needles) in checks.items():
        for needle in needles:
            if needle not in text:
                raise RuntimeError(f"missing {label} invariant: {needle}")
    for forbidden in ("STABILIZATION_S1C_ACTIVE_TRANSFER_V1", "STABILIZATION_S1D_REAL_INNER_EDGE_V1"):
        if forbidden in shell:
            raise RuntimeError(f"S1H unexpectedly stacked mutation marker: {forbidden}")


def apply(repo: Path, check: bool) -> None:
    for path in (PROTOCOL, SHELL, BRIDGE, SERVICE, VISUAL, EXPORTER):
        if not (repo / path).exists():
            raise RuntimeError(f"required S1H file missing: {path}")
    protocol = transform_protocol((repo / PROTOCOL).read_text())
    shell = transform_shell((repo / SHELL).read_text())
    bridge = transform_bridge((repo / BRIDGE).read_text())
    service = transform_service((repo / SERVICE).read_text())
    visual = (repo / VISUAL).read_text()
    exporter = (repo / EXPORTER).read_text()
    validate(protocol, shell, bridge, service, visual, exporter)
    if not check:
        (repo / PROTOCOL).write_text(protocol)
        (repo / SHELL).write_text(shell)
        (repo / BRIDGE).write_text(bridge)
        (repo / SERVICE).write_text(service)


def self_test() -> None:
    p = "object ShellProtocol {\n    const val COVER_PANEL_GEN4 = 18\n\n    const val CB_ANGLE = 1\n}\n"
    assert "CAPTURE_PHYSICAL_FORENSIC" in transform_protocol(p)
    b = "object ShizukuBridge {\n    /** Receives angles from the shell-side wallpaper log reader. */\n}\n"
    assert "ForensicCaptureOutcome" in transform_bridge(b)
    print("stabilization S1H visual forensics transformer self-test: PASS")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=".")
    p.add_argument("--check", action="store_true")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        self_test()
        if not a.check:
            return 0
    apply(Path(a.repo).resolve(), a.check)
    print("stabilization S1H visual forensics: " + ("source shape verified" if a.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
