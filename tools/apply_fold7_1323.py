from pathlib import Path
import re


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, value: str) -> None:
    Path(path).write_text(value, encoding="utf-8")


def replace_once(value: str, old: str, new: str, label: str) -> str:
    count = value.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return value.replace(old, new, 1)


def sub_once(value: str, pattern: str, repl: str, label: str) -> str:
    out, count = re.subn(pattern, lambda _: repl, value, count=1, flags=re.DOTALL)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return out


# ---------------------------------------------------------------------------
# Build identity + tests
# ---------------------------------------------------------------------------

gradle_path = "app/build.gradle.kts"
gradle = read(gradle_path)
gradle = replace_once(gradle, "versionCode = 25", "versionCode = 27", "versionCode")
gradle = replace_once(
    gradle,
    'versionName = "1.3.21-zfold7-state-machine"',
    'versionName = "1.3.23-zfold7-explicit-state-machine"',
    "versionName",
)
if 'testImplementation("junit:junit:4.13.2")' not in gradle:
    gradle = replace_once(
        gradle,
        "dependencies {\n",
        'dependencies {\n    testImplementation("junit:junit:4.13.2")\n',
        "JUnit dependency",
    )
write(gradle_path, gradle)


# ---------------------------------------------------------------------------
# FoldOverlayService: make the explicit coordinator authoritative.
# Keep the old continuity functions temporarily as unreachable rollback code;
# no active call path may invoke them in 1.3.23.
# ---------------------------------------------------------------------------

service_path = "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"
service = read(service_path)

service = replace_once(
    service,
    "    private var angleFeed: WallpaperAngleFeed? = null\n",
    "    private var angleFeed: WallpaperAngleFeed? = null\n\n"
    "    private lateinit var continuity: Fold7ContinuityCoordinator\n",
    "continuity coordinator field",
)

service = replace_once(
    service,
    "        super.onServiceConnected()\n",
    "        super.onServiceConnected()\n"
    "        PersistentRuntimeService.ensureRunning(this)\n",
    "persistent runtime start",
)

service = replace_once(
    service,
    "        displayManager = getSystemService(DisplayManager::class.java)\n",
    "        displayManager = getSystemService(DisplayManager::class.java)\n"
    "        continuity = Fold7ContinuityCoordinator(\n"
    "            service = this,\n"
    "            displayManager = displayManager,\n"
    "            handler = handler,\n"
    "            scope = scope,\n"
    "            currentHingeAngle = { hinge.lastAngle },\n"
    "            onStatus = { message -> _secondaryDisplayStatus.value = message },\n"
    "        )\n",
    "continuity coordinator construction",
)

# Replace only the first call; the old method definition is intentionally left
# unreachable for one rollback cycle.
call_index = service.find("                        armGeometryContinuity()")
if call_index < 0:
    raise SystemExit("auto-arm call not found")
service = (
    service[:call_index]
    + "                        continuity.arm()"
    + service[call_index + len("                        armGeometryContinuity()") :]
)

service = replace_once(
    service,
    "        instance = null\n",
    "        instance = null\n\n"
    "        if (::continuity.isInitialized) {\n"
    "            continuity.destroy()\n"
    "        }\n",
    "continuity destroy",
)

service = sub_once(
    service,
    r'''    private fun onHinge\(angle: Float\) \{.*?\n    \}\n\n    /\*\* Starts engines''',
    '''    private fun onHinge(angle: Float) {
        continuity.onHinge(angle)

        for (engine in engines.values.toList()) {
            engine.onHinge(angle)
        }
    }

    /** Starts engines''',
    "replace hinge orchestration",
)

service = replace_once(
    service,
    "        if (!mirrorRequested) {\n"
    "            for (e in engines.values.toList()) {\n"
    "                e.evaluate()\n"
    "            }\n"
    "        }\n",
    "        if (!continuity.visualMirrorActive) {\n"
    "            for (e in engines.values.toList()) {\n"
    "                e.evaluate()\n"
    "            }\n"
    "        }\n",
    "engine evaluation mirror gate",
)

service = sub_once(
    service,
    r'''\n        scheduleMirrorRefresh\(\n            "sync-displays"\n        \)''',
    '''
        continuity.onTopologyChanged(
            "sync-displays"
        )''',
    "topology handoff to coordinator",
)

service = sub_once(
    service,
    r'''            if \(enable\) \{\n                service\.armGeometryContinuity\(\)\n            \} else \{\n                service\.runSecondaryDisplayExperiment\(\n                    enable =\n                        false,\n                    reason =\n                        "user-stop",\n                \)\n            \}''',
    '''            if (enable) {
                service.continuity.arm()
            } else {
                service.continuity.release(
                    "user-stop"
                )
            }''',
    "UI continuity control",
)

write(service_path, service)


# ---------------------------------------------------------------------------
# DuoShellService: fresh route resolution, physical identity, no logical cache.
# ---------------------------------------------------------------------------

shell_path = "app/src/full/java/com/duoopen/shell/DuoShellService.kt"
shell = read(shell_path)

if "import android.view.Display\n" not in shell:
    shell = replace_once(
        shell,
        "import android.view.SurfaceControl\n",
        "import android.view.Display\nimport android.view.SurfaceControl\n",
        "Display import",
    )

safe_secondary = r'''    // ---- Fold7 physical-panel-safe continuity ----------------------------

    private fun displayInfoForLogicalId(
        logicalDisplayId: Int,
    ): Any? {
        if (logicalDisplayId < 0) return null

        return runCatching {
            Class.forName(
                "android.hardware.display.IDisplayManager"
            ).getMethod(
                "getDisplayInfo",
                Integer.TYPE,
            ).invoke(
                displayManagerService(),
                logicalDisplayId,
            )
        }.getOrNull()
    }

    private fun currentCoverLogicalId(
        targetHint: Int,
    ): Int {
        if (
            targetHint < 0 ||
            targetHint == Display.DEFAULT_DISPLAY
        ) {
            return -1
        }

        val info =
            displayInfoForLogicalId(targetHint)
                ?: return -1

        val width =
            runCatching {
                info.javaClass
                    .getField("logicalWidth")
                    .getInt(info)
            }.getOrDefault(-1)

        val height =
            runCatching {
                info.javaClass
                    .getField("logicalHeight")
                    .getInt(info)
            }.getOrDefault(-1)

        return if (
            width == 1080 &&
            height == 2520
        ) {
            targetHint
        } else {
            -1
        }
    }

    private fun windowCoverRoutes(): List<Int> {
        val dump =
            runProbe(
                "dumpsys window displays | " +
                    "grep -E '^[[:space:]]*Display: mDisplayId=|" +
                    "^[[:space:]]*init='"
            )

        return Regex(
            "Display: mDisplayId=(\\d+).*?init=(\\d+)x(\\d+)",
            setOf(RegexOption.DOT_MATCHES_ALL),
        ).findAll(dump)
            .mapNotNull { match ->
                val id = match.groupValues[1].toIntOrNull()
                    ?: return@mapNotNull null
                val width = match.groupValues[2].toIntOrNull()
                    ?: return@mapNotNull null
                val height = match.groupValues[3].toIntOrNull()
                    ?: return@mapNotNull null

                if (
                    id != Display.DEFAULT_DISPLAY &&
                    width == 1080 &&
                    height == 2520
                ) {
                    id
                } else {
                    null
                }
            }
            .distinct()
            .toList()
    }

    /**
     * Resolve a logical route only for the immediate operation. Never cache it.
     * Samsung may remap the same logical id to the inner/default display later.
     */
    private fun resolveFreshCoverLogicalId(
        targetHint: Int,
    ): Int {
        if (
            targetHint >= 0 &&
            targetHint != Display.DEFAULT_DISPLAY &&
            targetHint in windowCoverRoutes()
        ) {
            return targetHint
        }

        return windowCoverRoutes().firstOrNull() ?: -1
    }

    private fun physicalDisplayIdFromLogical(
        logicalDisplayId: Int,
    ): Long {
        val info = displayInfoForLogicalId(logicalDisplayId) ?: return -1L

        val width = runCatching {
            info.javaClass.getField("logicalWidth").getInt(info)
        }.getOrDefault(-1)
        val height = runCatching {
            info.javaClass.getField("logicalHeight").getInt(info)
        }.getOrDefault(-1)

        if (width != 1080 || height != 2520) return -1L

        val address = runCatching {
            info.javaClass.getField("address").get(info)
        }.getOrNull() ?: return -1L

        return runCatching {
            address.javaClass
                .getMethod("getPhysicalDisplayId")
                .invoke(address) as Long
        }.getOrElse { -1L }
    }

    private fun resolveFold7CoverPhysicalDisplayId(
        targetHint: Int = -1,
    ): Long {
        if (cachedCoverPhysicalDisplayId >= 0L) {
            return cachedCoverPhysicalDisplayId
        }

        val fromAddress = physicalDisplayIdFromLogical(targetHint)
        if (fromAddress >= 0L) {
            cachedCoverPhysicalDisplayId = fromAddress
            return fromAddress
        }

        val displayDump =
            runProbe(
                "dumpsys display | " +
                    "grep -E -i 'DisplayDeviceInfo|mPhysicalDisplayId=' | " +
                    "head -n 320"
            )

        val forward =
            Regex(
                """DisplayDeviceInfo\\{[^\\n]*uniqueId=\"local:(\\d+)\"[^\\n]*1080 x 2520"""
            ).find(displayDump)
                ?.groupValues?.getOrNull(1)?.toLongOrNull()

        val reverse =
            Regex(
                """DisplayDeviceInfo\\{[^\\n]*1080 x 2520[^\\n]*uniqueId=\"local:(\\d+)\""""
            ).find(displayDump)
                ?.groupValues?.getOrNull(1)?.toLongOrNull()

        val physicalId = forward ?: reverse ?: -1L
        if (physicalId >= 0L) {
            cachedCoverPhysicalDisplayId = physicalId
        }
        return physicalId
    }

    private fun resolveCoverDisplay(): Bundle {
        val logicalId = resolveFreshCoverLogicalId(-1)
        val physicalId = resolveFold7CoverPhysicalDisplayId(logicalId)

        return Bundle().apply {
            putBoolean("ok", logicalId >= 0 || physicalId >= 0L)
            putInt("targetDisplayId", logicalId)
            putLong("physicalDisplayId", physicalId)
            putInt("targetWidth", 1080)
            putInt("targetHeight", 2520)
            if (logicalId < 0 && physicalId < 0L) {
                putString("error", "The Fold7 cover panel could not be resolved.")
            }
        }
    }

    private fun setCoverPhysicalPowerNormal(): Pair<Boolean, String?> {
        val physicalId = cachedCoverPhysicalDisplayId
        if (physicalId < 0L) {
            return false to "cover physical display id unavailable"
        }

        return runCatching {
            org.lsposed.hiddenapibypass.HiddenApiBypass
                .addHiddenApiExemptions(
                    "Landroid/view/SurfaceControl;"
                )

            val token =
                SurfaceControl::class.java
                    .getDeclaredMethod(
                        "getPhysicalDisplayToken",
                        java.lang.Long.TYPE,
                    )
                    .invoke(null, physicalId) as? IBinder
                    ?: throw IllegalStateException(
                        "no SurfaceControl token for physical display $physicalId"
                    )

            SurfaceControl::class.java
                .getDeclaredMethod(
                    "setDisplayPowerMode",
                    IBinder::class.java,
                    Integer.TYPE,
                )
                .invoke(null, token, 2)

            true to null
        }.getOrElse { error ->
            false to "${error.javaClass.simpleName}: ${error.message}"
        }
    }

    private fun secondaryDisplayCommand(
        enable: Boolean,
        targetHint: Int,
    ): Bundle {
        val t0 = SystemClock.elapsedRealtime()

        if (!enable) {
            val safeTarget = resolveFreshCoverLogicalId(targetHint)

            if (safeTarget < 0) {
                return Bundle().apply {
                    putBoolean("ok", true)
                    putBoolean("enable", false)
                    putInt("targetDisplayId", -1)
                    putInt("targetWidth", 1080)
                    putInt("targetHeight", 2520)
                    putBoolean("visibleAfter", false)
                    putString("command", "validated release skipped")
                    putString("commandOutput", "no non-default 1080x2520 route")
                    putLong("latencyMs", SystemClock.elapsedRealtime() - t0)
                }
            }

            // Re-resolve immediately before acting; abort if Samsung remapped it.
            if (safeTarget !in windowCoverRoutes()) {
                return Bundle().apply {
                    putBoolean("ok", true)
                    putBoolean("enable", false)
                    putInt("targetDisplayId", -1)
                    putString("command", "release aborted after remap")
                    putLong("latencyMs", SystemClock.elapsedRealtime() - t0)
                }
            }

            val command = "cmd display power-reset $safeTarget"
            val output = runProbe(command)
            val failed =
                output.contains("Exception", ignoreCase = true) ||
                    output.contains("error", ignoreCase = true) ||
                    output.contains("not possible", ignoreCase = true)

            return Bundle().apply {
                putBoolean("ok", !failed)
                putBoolean("enable", false)
                putInt("targetDisplayId", safeTarget)
                putInt("targetWidth", 1080)
                putInt("targetHeight", 2520)
                putBoolean("visibleAfter", false)
                putString("command", command)
                putString("commandOutput", output)
                putLong("latencyMs", SystemClock.elapsedRealtime() - t0)
            }
        }

        val targetId = resolveFreshCoverLogicalId(targetHint)
        if (targetId < 0) {
            return Bundle().apply {
                putBoolean("ok", false)
                putBoolean("enable", true)
                putInt("targetDisplayId", -1)
                putInt("targetWidth", 1080)
                putInt("targetHeight", 2520)
                putBoolean("visibleAfter", false)
                putString("error", "No fresh non-default 1080x2520 cover route was available.")
                putString("command", "fresh-route-validation")
                putString("commandOutput", "skipped")
            }
        }

        // Stable physical identity may be cached; the logical id may not.
        val physicalId = resolveFold7CoverPhysicalDisplayId(targetId)

        if (targetId !in windowCoverRoutes()) {
            return Bundle().apply {
                putBoolean("ok", false)
                putBoolean("enable", true)
                putInt("targetDisplayId", -1)
                putLong("physicalDisplayId", physicalId)
                putString("error", "Samsung remapped the cover route before enable.")
                putString("command", "pre-enable-route-revalidation")
            }
        }

        var routeEnabled = false
        var routeError: String? = null
        runCatching {
            enableConnectedDisplayInternal(targetId)
            routeEnabled = true
        }.onFailure { error ->
            routeError = "${error.javaClass.simpleName}: ${error.message}"
        }

        // Revalidate AGAIN after enable. Never power an id that now represents
        // the inner/default display.
        val stillCover = targetId in windowCoverRoutes()

        val logicalPowered =
            if (stillCover) {
                runCatching {
                    requestDisplayPowerInternal(
                        targetId,
                        Display.STATE_ON,
                    )
                }.getOrDefault(false)
            } else {
                false
            }

        val (physicalPowered, physicalPowerError) =
            setCoverPhysicalPowerNormal()

        return Bundle().apply {
            putBoolean("ok", routeEnabled || logicalPowered || physicalPowered)
            putBoolean("enable", true)
            putInt("targetDisplayId", if (stillCover) targetId else -1)
            putLong("physicalDisplayId", physicalId)
            putInt("targetWidth", 1080)
            putInt("targetHeight", 2520)
            putBoolean("visibleAfter", false)
            putBoolean("routeEnabled", routeEnabled)
            putBoolean("logicalPowered", logicalPowered)
            putBoolean("physicalPowered", physicalPowered)
            putBoolean("routeStillCover", stillCover)
            putString("command", "fresh-route one-shot Fold7 prewarm")
            putString(
                "commandOutput",
                listOfNotNull(routeError, physicalPowerError)
                    .joinToString(" | ")
                    .ifEmpty { "bounded-prewarm-fast-path" },
            )
            putLong("latencyMs", SystemClock.elapsedRealtime() - t0)
        }
    }

'''

shell = sub_once(
    shell,
    r'''    // ---- Fold7 physical-panel-safe continuity -+\n.*?    // ---- live logical-display mirror -+''',
    safe_secondary + "    // ---- live logical-display mirror ---------------------------------------",
    "replace Fold7 shell continuity section",
)

write(shell_path, shell)


# ---------------------------------------------------------------------------
# Fold7 visual calibration: remove the generic 6-degree cover dead zone.
# ---------------------------------------------------------------------------

shader_path = "app/src/main/java/com/duoopen/fold/DuoShader.kt"
shader = read(shader_path)

if "FOLD7_COVER_CLOSED_VISUAL_HINGE" not in shader:
    shader = replace_once(
        shader,
        "    const val COVER_VISUAL_MAX_HINGE = 135f\n",
        "    const val COVER_VISUAL_MAX_HINGE = 135f\n"
        "    const val FOLD7_COVER_CLOSED_VISUAL_HINGE = 0.5f\n",
        "Fold7 cover visual origin",
    )

shader = sub_once(
    shader,
    r'''    fun coverTiltForHinge\(hingeDegrees: Float, config: DuoConfig\): Float \{.*?\n    \}''',
    '''    fun coverTiltForHinge(hingeDegrees: Float, config: DuoConfig): Float {
        val progress =
            ((hingeDegrees - FOLD7_COVER_CLOSED_VISUAL_HINGE) /
                (PANEL_ON_HINGE - FOLD7_COVER_CLOSED_VISUAL_HINGE))
                .coerceIn(0f, 1f)

        return (progress * MAX_TILT * config.intensity)
            .coerceIn(0f, MAX_TILT)
    }''',
    "native cover visual calibration",
)

shader = sub_once(
    shader,
    r'''    fun concurrentCoverTiltForHinge\(hingeDegrees: Float, config: DuoConfig\): Float \{.*?\n    \}''',
    '''    fun concurrentCoverTiltForHinge(hingeDegrees: Float, config: DuoConfig): Float {
        if (hingeDegrees >= COVER_VISUAL_MAX_HINGE) return 0f

        val progress =
            ((hingeDegrees - FOLD7_COVER_CLOSED_VISUAL_HINGE) /
                (COVER_VISUAL_MAX_HINGE - FOLD7_COVER_CLOSED_VISUAL_HINGE))
                .coerceIn(0f, 1f)

        val bump =
            kotlin.math.sin(Math.PI * progress).toFloat()

        return (bump * MAX_TILT * config.intensity)
            .coerceIn(0f, MAX_TILT)
    }''',
    "concurrent cover visual calibration",
)

write(shader_path, shader)


# ---------------------------------------------------------------------------
# PanelEngine: fully-open latch without changing the successful inner curve.
# ---------------------------------------------------------------------------

panel_path = "app/src/full/java/com/duoopen/overlay/PanelEngine.kt"
panel = read(panel_path)

# Native cover and concurrent cover both get the low leave threshold. The
# Fold7-specific visual origin below provides the noise margin.
panel = panel.replace(
    "if (!innerPanel && concurrentCover()) {",
    "if (!innerPanel) {",
    1,
)

if "private var innerOpenLatched" not in panel:
    panel = replace_once(
        panel,
        "    private var liveLoop = false\n",
        "    private var liveLoop = false\n\n"
        "    private var innerOpenLatched = false\n",
        "inner open latch field",
    )

panel = replace_once(
    panel,
    "        lastRawHingeAngle =\n            angle\n\n",
    "        lastRawHingeAngle =\n            angle\n\n"
    "        if (innerPanel) {\n"
    "            if (angle >= INNER_OPEN_LATCH_DEG) {\n"
    "                if (!innerOpenLatched) {\n"
    "                    com.duoopen.debug.DuoDiagnostics.event(\n"
    "                        \"inner-open\",\n"
    "                        \"latched angle=$angle; removing flat overlay without fade\",\n"
    "                    )\n"
    "                }\n"
    "                innerOpenLatched = true\n"
    "                restArmed = true\n"
    "                panelSwitched = false\n"
    "                if (phase != Phase.IDLE) removeOverlay()\n"
    "                return\n"
    "            }\n\n"
    "            if (innerOpenLatched) {\n"
    "                if (angle > INNER_OPEN_REARM_DEG) return\n"
    "                innerOpenLatched = false\n"
    "                restArmed = true\n"
    "                panelSwitched = false\n"
    "            }\n"
    "        }\n\n",
    "inner-open onHinge latch",
)

if "INNER_OPEN_LATCH_DEG = 172f" not in panel:
    panel = replace_once(
        panel,
        "        const val COVER_OPEN_IMMEDIATE_TILT = 0.15f\n",
        "        const val COVER_OPEN_IMMEDIATE_TILT = 0.15f\n"
        "        const val INNER_OPEN_LATCH_DEG = 172f\n"
        "        const val INNER_OPEN_REARM_DEG = 166f\n",
        "inner-open constants",
    )

write(panel_path, panel)

print("1.3.23 explicit Fold7 state-machine pass applied")
