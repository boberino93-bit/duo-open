package com.duoopen.shell

import android.graphics.Bitmap
import android.graphics.Rect
import android.hardware.HardwareBuffer
import android.os.Binder
import android.os.Bundle
import android.os.IBinder
import android.os.Parcel
import android.os.Process
import android.os.SystemClock
import android.view.Display
import android.view.SurfaceControl
import java.io.BufferedReader
import java.io.InputStreamReader
import java.lang.reflect.Constructor
import java.lang.reflect.Method
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.function.Consumer
import java.util.function.ObjIntConsumer
import java.util.regex.Pattern

/**
 * Runs in a process Shizuku spawns with ADB (shell) privileges. Two jobs the
 * app process can't do itself:
 *
 * 1. **Display capture without the accessibility rate limit**, through the
 *    hidden `IWindowManager.captureDisplay`, with our own overlay layers
 *    excluded — so the fold can re-capture the live screen while it plays.
 * 2. **Samsung's continuous hinge angle.** Only Samsung's own components get
 *    the real angle; its "Fold interactive" home wallpaper logs it on every
 *    wallpaper command it receives (`mCurrentAngle=…`), and the shell user may
 *    read logcat. The app pings the wallpaper; this tails the log and calls
 *    back with each fresh value.
 *
 * Both techniques were worked out by Duo Fold Live
 * (github.com/joeconsorti/duo-fold-live, MIT) — the capture-API resolution
 * and the wallpaper log format in particular follow their findings.
 *
 * Nothing here is reachable without the user authorising this app in
 * Shizuku, and every transaction checks the calling uid.
 */
class DuoShellService : Binder() {

    private var owner = -1
    private var captureApi: CaptureApi? = null
    private var reader: AngleReader? = null

    private var liveMirror: SurfaceControl? = null

    @Volatile
    private var cachedCoverPhysicalDisplayId =
        -1L

    @Volatile
    private var cachedInnerPhysicalDisplayId =
        -1L

    init {
        attachInterface(null, ShellProtocol.TOKEN)
    }

    override fun onTransact(code: Int, data: Parcel, reply: Parcel?, flags: Int): Boolean {
        if (code == INTERFACE_TRANSACTION) {
            reply?.writeString(ShellProtocol.TOKEN)
            return true
        }
        if (code == SHIZUKU_DESTROY) {
            reader?.stop()
            stopLiveMirror()
            System.exit(0)
            return true
        }
        data.enforceInterface(ShellProtocol.TOKEN)
        val caller = getCallingUid()
        if (owner < 0) owner = caller
        if (caller != owner) throw SecurityException("wrong caller")
        val out = reply ?: return false
        when (code) {
            ShellProtocol.PING -> {
                out.writeNoException()
                out.writeBundle(Bundle().apply {
                    putInt("uid", Process.myUid())
                    putInt("pid", Process.myPid())
                    putString("capture", runCatching { api().name }.getOrElse { "unavailable: ${it.message}" })
                })
            }
            ShellProtocol.CAPTURE -> {
                val displayId = data.readInt()
                val n = data.readInt()
                val excluded = Array(n) { data.readTypedObject(SurfaceControl.CREATOR) }
                val scale = data.readFloat()
                val identity = clearCallingIdentity()
                val result = try {
                    capture(displayId, excluded.filterNotNull().toTypedArray(), scale)
                } catch (t: Throwable) {
                    var c: Throwable = t
                    while (c.cause != null) c = c.cause!!
                    Bundle().apply { putString("error", "${c.javaClass.simpleName}: ${c.message}") }
                } finally {
                    excluded.forEach { runCatching { it?.release() } }
                    restoreCallingIdentity(identity)
                }
                out.writeNoException()
                out.writeBundle(result)
            }
            ShellProtocol.START_ANGLES -> {
                val action = data.readString() ?: throw IllegalArgumentException("action")
                val callback = data.readStrongBinder() ?: throw IllegalArgumentException("callback")
                reader?.stop()
                reader = AngleReader(action, callback).also { it.start() }
                out.writeNoException()
            }
            ShellProtocol.STOP_ANGLES -> {
                reader?.stop()
                reader = null
                out.writeNoException()
            }
            ShellProtocol.ANGLE_STATUS -> {
                out.writeNoException()
                out.writeBundle(reader?.status() ?: Bundle().apply { putString("state", "not started") })
            }
            ShellProtocol.DISPLAY_PROBE -> {
                val identity = clearCallingIdentity()
                val result = try {
                    displayProbe()
                } catch (t: Throwable) {
                    Bundle().apply {
                        putString(
                            "error",
                            "${t.javaClass.simpleName}: ${t.message}",
                        )
                    }
                } finally {
                    restoreCallingIdentity(identity)
                }

                out.writeNoException()
                out.writeBundle(result)
            }
            ShellProtocol.ENABLE_SECONDARY_DISPLAY -> {
                val targetHint =
                    if (
                        data.dataAvail() >=
                            Integer.BYTES
                    ) {
                        data.readInt()
                    } else {
                        -1
                    }

                val identity =
                    clearCallingIdentity()

                val result =
                    try {
                        secondaryDisplayCommand(
                            enable = true,
                            targetHint = targetHint,
                        )
                    } catch (t: Throwable) {
                        Bundle().apply {
                            putBoolean("ok", false)
                            putString(
                                "error",
                                "${t.javaClass.simpleName}: ${t.message}",
                            )
                        }
                    } finally {
                        restoreCallingIdentity(identity)
                    }

                out.writeNoException()
                out.writeBundle(result)
            }

            ShellProtocol.RESET_SECONDARY_DISPLAY -> {
                val targetHint =
                    if (
                        data.dataAvail() >=
                            Integer.BYTES
                    ) {
                        data.readInt()
                    } else {
                        -1
                    }

                val identity =
                    clearCallingIdentity()

                val result =
                    try {
                        secondaryDisplayCommand(
                            enable = false,
                            targetHint = targetHint,
                        )
                    } catch (t: Throwable) {
                        Bundle().apply {
                            putBoolean("ok", false)
                            putString(
                                "error",
                                "${t.javaClass.simpleName}: ${t.message}",
                            )
                        }
                    } finally {
                        restoreCallingIdentity(identity)
                    }

                out.writeNoException()
                out.writeBundle(result)
            }

            ShellProtocol.RESOLVE_COVER_DISPLAY -> {
                val identity =
                    clearCallingIdentity()

                val result =
                    try {
                        resolveCoverDisplay()
                    } catch (t: Throwable) {
                        Bundle().apply {
                            putBoolean("ok", false)
                            putInt(
                                "targetDisplayId",
                                -1,
                            )
                            putString(
                                "error",
                                "${t.javaClass.simpleName}: ${t.message}",
                            )
                        }
                    } finally {
                        restoreCallingIdentity(identity)
                    }

                out.writeNoException()
                out.writeBundle(result)
            }

            ShellProtocol.WAKE_INNER_DISPLAY -> {
                val identity =
                    clearCallingIdentity()

                val result =
                    try {
                        wakeInnerPhysicalDisplay()
                    } catch (t: Throwable) {
                        Bundle().apply {
                            putBoolean("ok", false)
                            putLong("physicalDisplayId", -1L)
                            putString(
                                "error",
                                "${t.javaClass.simpleName}: ${t.message}",
                            )
                        }
                    } finally {
                        restoreCallingIdentity(identity)
                    }

                out.writeNoException()
                out.writeBundle(result)
            }

            ShellProtocol.MIRROR_DISPLAY -> {
                val enable = data.readInt() != 0
                val identity = clearCallingIdentity()

                val result = try {
                    if (!enable) {
                        stopLiveMirror()

                        Bundle().apply {
                            putBoolean("ok", true)
                            putBoolean("enabled", false)
                        }
                    } else {
                        val sourceDisplayId =
                            data.readInt()

                        createLiveMirror(
                            sourceDisplayId =
                                sourceDisplayId,
                        )
                    }
                } catch (t: Throwable) {
                    var root: Throwable = t

                    while (root.cause != null) {
                        root = root.cause!!
                    }

                    Bundle().apply {
                        putBoolean("ok", false)
                        putBoolean("enabled", enable)
                        putString(
                            "error",
                            "${root.javaClass.simpleName}: ${root.message}",
                        )
                    }
                } finally {
                    restoreCallingIdentity(identity)
                }

                out.writeNoException()
                out.writeBundle(result)
            }

            ShellProtocol.REQUEST_DISPLAY_POWER -> {
                val displayId =
                    data.readInt()

                val requestedState =
                    data.readInt()

                val identity =
                    clearCallingIdentity()

                val result =
                    try {
                        val routeEnabled =
                            if (
                                requestedState ==
                                    android.view.Display.STATE_ON
                            ) {
                                runCatching {
                                    enableConnectedDisplayInternal(
                                        displayId
                                    )
                                }.isSuccess
                            } else {
                                false
                            }

                        val powered =
                            requestDisplayPowerInternal(
                                displayId,
                                requestedState,
                            )

                        Bundle().apply {
                            putBoolean(
                                "ok",
                                powered,
                            )
                            putBoolean(
                                "routeEnabled",
                                routeEnabled,
                            )
                            putInt(
                                "displayId",
                                displayId,
                            )
                            putInt(
                                "requestedState",
                                requestedState,
                            )
                        }
                    } catch (t: Throwable) {
                        var root: Throwable = t

                        while (root.cause != null) {
                            root =
                                root.cause!!
                        }

                        Bundle().apply {
                            putBoolean(
                                "ok",
                                false,
                            )
                            putInt(
                                "displayId",
                                displayId,
                            )
                            putInt(
                                "requestedState",
                                requestedState,
                            )
                            putString(
                                "error",
                                "${root.javaClass.simpleName}: ${root.message}",
                            )
                        }
                    } finally {
                        restoreCallingIdentity(
                            identity
                        )
                    }

                out.writeNoException()
                out.writeBundle(result)
            }

            else -> return super.onTransact(code, data, reply, flags)
        }
        return true
    }

    // ---- read-only display probe -------------------------------------------

    private fun displayProbe(): Bundle =
        Bundle().apply {

            putInt(
                "uid",
                Process.myUid(),
            )

            putInt(
                "pid",
                Process.myPid(),
            )

            putString(
                "identity",
                runProbe(
                    "id"
                ),
            )

            putString(
                "cmd_display",
                runProbe(
                    "cmd display get-displays"
                ),
            )

            putString(
                "cmd_display_help",
                runProbe(
                    "cmd display help"
                ),
            )

            putString(
                "surfaceflinger",
                runProbe(
                    "dumpsys SurfaceFlinger --display-id"
                ),
            )

            putString(
                "display_filtered",
                runProbe(
                    "dumpsys display | " +
                        "grep -E -i " +
                        "'DisplayDeviceInfo|LogicalDisplay|uniqueId=|" +
                        "displayId|mDisplayId|state=|type=|address=|" +
                        "modeId|supportedModes|Built-in|fold|rear' | " +
                        "head -n 300"
                ),
            )

            putString(
                "window_displays",
                runProbe(
                    "dumpsys window displays | head -n 250"
                ),
            )
        }

    private fun runProbe(
        command: String,
    ): String {

        val process =
            ProcessBuilder(
                "sh",
                "-c",
                "$command 2>&1",
            ).start()

        val output =
            process.inputStream
                .bufferedReader()
                .use {
                    it.readText()
                }

        val finished =
            process.waitFor(
                3,
                java.util.concurrent.TimeUnit.SECONDS,
            )

        if (
            !finished
        ) {
            process.destroyForcibly()

            return (
                "timeout after 3000ms\n" +
                    output.take(
                        PROBE_OUTPUT_LIMIT
                    )
                )
        }

        return (
            "exit=${process.exitValue()}\n" +
                output.take(
                    PROBE_OUTPUT_LIMIT
                )
            )
    }

    // ---- Fold7 physical-panel-safe continuity ----------------------------

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

    private fun physicalDisplayIdForGeometry(
        width: Int,
        height: Int,
    ): Long {
        val displayDump =
            runProbe(
                "dumpsys display | " +
                    "grep -E -i 'DisplayDeviceInfo|uniqueId=' | " +
                    "head -n 400"
            )

        val forward =
            Regex(
                """DisplayDeviceInfo\{[^\n]*uniqueId="local:(\d+)"[^\n]*$width\s*x\s*$height"""
            ).find(displayDump)
                ?.groupValues
                ?.getOrNull(1)
                ?.toLongOrNull()

        val reverse =
            Regex(
                """DisplayDeviceInfo\{[^\n]*$width\s*x\s*$height[^\n]*uniqueId="local:(\d+)""""
            ).find(displayDump)
                ?.groupValues
                ?.getOrNull(1)
                ?.toLongOrNull()

        return forward ?: reverse ?: -1L
    }

    private fun resolveFold7CoverPhysicalDisplayId(
        targetHint: Int = -1,
    ): Long {
        if (cachedCoverPhysicalDisplayId >= 0L) {
            return cachedCoverPhysicalDisplayId
        }

        val fromAddress =
            physicalDisplayIdFromLogical(
                targetHint
            )

        if (fromAddress >= 0L) {
            cachedCoverPhysicalDisplayId =
                fromAddress
            return fromAddress
        }

        val physicalId =
            physicalDisplayIdForGeometry(
                width = 1080,
                height = 2520,
            )

        if (physicalId >= 0L) {
            cachedCoverPhysicalDisplayId =
                physicalId
        }

        return physicalId
    }

    private fun resolveFold7InnerPhysicalDisplayId(): Long {
        if (cachedInnerPhysicalDisplayId >= 0L) {
            return cachedInnerPhysicalDisplayId
        }

        val physicalId =
            physicalDisplayIdForGeometry(
                width = 1968,
                height = 2184,
            )

        if (physicalId >= 0L) {
            cachedInnerPhysicalDisplayId =
                physicalId
        }

        return physicalId
    }

    private fun resolveCoverDisplay(): Bundle {
        val logicalId =
            resolveFreshCoverLogicalId(-1)

        /*
         * This command is called once when Shizuku becomes ready, outside the
         * physical hinge transition path. Resolve/cache BOTH stable physical
         * panel identities here so the first real 3° inner wake and 174° cover
         * prewarm do not have to spawn a cold dumpsys process first.
         *
         * Only physical ids are cached. Logical ids remain one-shot.
         */
        val physicalId =
            resolveFold7CoverPhysicalDisplayId(
                logicalId
            )

        val innerPhysicalId =
            resolveFold7InnerPhysicalDisplayId()

        return Bundle().apply {
            putBoolean(
                "ok",
                logicalId >= 0 ||
                    physicalId >= 0L,
            )
            putInt(
                "targetDisplayId",
                logicalId,
            )
            putLong(
                "physicalDisplayId",
                physicalId,
            )
            putLong(
                "innerPhysicalDisplayId",
                innerPhysicalId,
            )
            putInt("targetWidth", 1080)
            putInt("targetHeight", 2520)
            if (
                logicalId < 0 &&
                physicalId < 0L
            ) {
                putString(
                    "error",
                    "The Fold7 cover panel could not be resolved.",
                )
            }
        }
    }

    private fun setPhysicalPowerNormal(
        physicalId: Long,
    ): Pair<Boolean, String?> {
        if (physicalId < 0L) {
            return false to "physical display id unavailable"
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
            false to
                "${error.javaClass.simpleName}: ${error.message}"
        }
    }

    private fun setCoverPhysicalPowerNormal():
        Pair<Boolean, String?> =
        setPhysicalPowerNormal(
            cachedCoverPhysicalDisplayId
        )

    private fun wakeInnerPhysicalDisplay(): Bundle {
        val t0 =
            SystemClock.elapsedRealtime()

        val physicalId =
            resolveFold7InnerPhysicalDisplayId()

        val (powered, error) =
            setPhysicalPowerNormal(
                physicalId
            )

        return Bundle().apply {
            putBoolean("ok", powered)
            putLong(
                "physicalDisplayId",
                physicalId,
            )
            putInt("targetWidth", 1968)
            putInt("targetHeight", 2184)
            putBoolean(
                "physicalPowered",
                powered,
            )
            putString(
                "command",
                "Fold7 physical inner early wake",
            )
            if (error != null) {
                putString(
                    "error",
                    error,
                )
            }
            putLong(
                "latencyMs",
                SystemClock.elapsedRealtime() -
                    t0,
            )
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

        /*
         * Wake the stable physical cover FIRST.
         *
         * Samsung may not create the 1080x2520 logical route until after the
         * physical panel is powered. Requiring that route first creates a
         * circular dependency and makes the cover appear much too late.
         */
        val physicalId =
            resolveFold7CoverPhysicalDisplayId(
                targetHint
            )

        val (
            physicalPowered,
            physicalPowerError
        ) =
            setPhysicalPowerNormal(
                physicalId
            )

        val targetId =
            resolveFreshCoverLogicalId(
                targetHint
            )

        if (targetId < 0) {
            return Bundle().apply {
                putBoolean(
                    "ok",
                    physicalPowered,
                )
                putBoolean("enable", true)
                putInt(
                    "targetDisplayId",
                    -1,
                )
                putLong(
                    "physicalDisplayId",
                    physicalId,
                )
                putInt("targetWidth", 1080)
                putInt("targetHeight", 2520)
                putBoolean(
                    "visibleAfter",
                    false,
                )
                putBoolean(
                    "routeEnabled",
                    false,
                )
                putBoolean(
                    "logicalPowered",
                    false,
                )
                putBoolean(
                    "physicalPowered",
                    physicalPowered,
                )
                putBoolean(
                    "routeStillCover",
                    false,
                )
                putString(
                    "command",
                    "physical-first Fold7 cover prewarm",
                )
                putString(
                    "commandOutput",
                    physicalPowerError
                        ?: "physical cover wake accepted; logical route pending",
                )
                if (!physicalPowered) {
                    putString(
                        "error",
                        physicalPowerError
                            ?: "Cover physical wake failed and no logical route exists.",
                    )
                }
                putLong(
                    "latencyMs",
                    SystemClock.elapsedRealtime() -
                        t0,
                )
            }
        }

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
            putString("command", "physical-first fresh-route Fold7 prewarm")
            putString(
                "commandOutput",
                listOfNotNull(routeError, physicalPowerError)
                    .joinToString(" | ")
                    .ifEmpty { "bounded-prewarm-fast-path" },
            )
            putLong("latencyMs", SystemClock.elapsedRealtime() - t0)
        }
    }

    // ---- live logical-display mirror ---------------------------------------

    private fun stopLiveMirror() {
        val current =
            liveMirror
                ?: return

        liveMirror =
            null

        runCatching {
            SurfaceControl.Transaction().use { tx ->
                tx.reparent(
                    current,
                    null,
                )
                tx.apply()
            }
        }

        runCatching {
            current.release()
        }
    }

    private fun createLiveMirror(
        sourceDisplayId: Int,
    ): Bundle {
        stopLiveMirror()

        val wm =
            systemService(
                "window",
                "android.view.IWindowManager\$Stub",
            )

        runCatching {
            org.lsposed.hiddenapibypass.HiddenApiBypass
                .addHiddenApiExemptions(
                    "Landroid/view/SurfaceControl;"
                )
        }

        val mirror =
            SurfaceControl::class.java
                .getDeclaredConstructor()
                .let { constructor ->
                    constructor.isAccessible =
                        true

                    constructor.newInstance()
                }

        val mirrored =
            Class.forName(
                "android.view.IWindowManager"
            ).getMethod(
                "mirrorDisplay",
                Integer.TYPE,
                SurfaceControl::class.java,
            ).invoke(
                wm,
                sourceDisplayId,
                mirror,
            ) as? Boolean
                ?: false

        if (
            !mirrored ||
            !mirror.isValid
        ) {
            runCatching {
                mirror.release()
            }

            throw IllegalStateException(
                "WindowManager mirrorDisplay($sourceDisplayId) returned no valid surface"
            )
        }

        liveMirror =
            mirror

        return Bundle().apply {
            putBoolean("ok", true)
            putBoolean("enabled", true)
            putInt(
                "sourceDisplayId",
                sourceDisplayId,
            )

            /*
             * SurfaceControl is Parcelable. This duplicates the handle into the
             * normal app process, which can then attach it to its own window
             * using AttachedSurfaceControl.buildReparentTransaction().
             */
            putParcelable(
                "mirrorSurface",
                mirror,
            )
        }
    }

    private fun displayManagerService(): Any =
        systemService(
            "display",
            "android.hardware.display.IDisplayManager\$Stub",
        )

    private fun enableConnectedDisplayInternal(
        displayId: Int,
    ) {
        val dm =
            displayManagerService()

        Class.forName(
            "android.hardware.display.IDisplayManager"
        ).getMethod(
            "enableConnectedDisplay",
            Integer.TYPE,
        ).invoke(
            dm,
            displayId,
        )
    }

    private fun requestDisplayPowerInternal(
        displayId: Int,
        requestedState: Int,
    ): Boolean {
        val dm =
            displayManagerService()

        val method =
            Class.forName(
                "android.hardware.display.IDisplayManager"
            ).getMethod(
                "requestDisplayPower",
                Integer.TYPE,
                Integer.TYPE,
            )

        return (
            method.invoke(
                dm,
                displayId,
                requestedState,
            ) as? Boolean
            ) == true
    }

    // ---- capture -----------------------------------------------------------

    private class CaptureApi(
        val name: String,
        val builderCtor: Constructor<*>,
        val builder: Class<*>,
        val listenerCtor: Constructor<*>,
        val statusCallback: Boolean,
        val captureDisplay: Method,
    )

    private fun systemService(name: String, stub: String): Any {
        val binder = Class.forName("android.os.ServiceManager").getMethod("getService", String::class.java)
            .invoke(null, name) as IBinder
        return Class.forName(stub).getMethod("asInterface", IBinder::class.java).invoke(null, binder)!!
    }

    /**
     * Finds whichever generation of the hidden capture API this Android has:
     * `android.window.ScreenCaptureInternal` (status callback) or
     * `android.window.ScreenCapture` (plain consumer), driven through
     * `IWindowManager.captureDisplay`.
     */
    private fun api(): CaptureApi {
        captureApi?.let { return it }
        val wm = Class.forName("android.view.IWindowManager")
        val errors = StringBuilder()
        for (family in FAMILIES) {
            try {
                val args = Class.forName("$family\$CaptureArgs")
                val builder = Class.forName("$family\$CaptureArgs\$Builder")
                val listener = Class.forName("$family\$ScreenCaptureListener")
                val ctor = builder.getConstructor()
                builder.getMethod("setSourceCrop", Rect::class.java)
                builder.getMethod("setFrameScale", java.lang.Float.TYPE)
                builder.getMethod("setExcludeLayers", Array<SurfaceControl>::class.java)
                builder.getMethod("build")
                var status = true
                val lctor = try {
                    listener.getConstructor(ObjIntConsumer::class.java)
                } catch (e: NoSuchMethodException) {
                    status = false
                    listener.getConstructor(Consumer::class.java)
                }
                val capture = wm.getMethod("captureDisplay", Integer.TYPE, args, listener)
                return CaptureApi(family, ctor, builder, lctor, status, capture).also { captureApi = it }
            } catch (e: ReflectiveOperationException) {
                errors.append(family).append(": ").append(e).append("; ")
            }
        }
        throw ClassNotFoundException("no compatible display capture API: $errors")
    }

    private fun capture(displayId: Int, excluded: Array<SurfaceControl>, scale: Float): Bundle {
        val t0 = SystemClock.elapsedRealtime()
        val api = api()
        val wm = systemService("window", "android.view.IWindowManager\$Stub")
        val dm = systemService("display", "android.hardware.display.IDisplayManager\$Stub")
        val info = Class.forName("android.hardware.display.IDisplayManager").getMethod("getDisplayInfo", Integer.TYPE)
            .invoke(dm, displayId) ?: throw IllegalStateException("no display $displayId")
        val w = info.javaClass.getField("logicalWidth").getInt(info)
        val h = info.javaClass.getField("logicalHeight").getInt(info)
        if (w <= 0 || h <= 0) throw IllegalStateException("display $displayId has no size")

        val b = api.builderCtor.newInstance()
        api.builder.getMethod("setSourceCrop", Rect::class.java).invoke(b, Rect(0, 0, w, h))
        api.builder.getMethod("setFrameScale", java.lang.Float.TYPE).invoke(b, scale.coerceIn(0.1f, 1f))
        if (excluded.isNotEmpty()) {
            api.builder.getMethod("setExcludeLayers", Array<SurfaceControl>::class.java).invoke(b, excluded)
        }
        val args = api.builder.getMethod("build").invoke(b)

        val latch = CountDownLatch(1)
        var shot: Any? = null
        val callback: Any = if (api.statusCallback) {
            ObjIntConsumer<Any?> { s, _ -> shot = s; latch.countDown() }
        } else {
            Consumer<Any?> { s -> shot = s; latch.countDown() }
        }
        val listener = api.listenerCtor.newInstance(callback)
        api.captureDisplay.invoke(wm, displayId, args, listener)
        if (!latch.await(400, TimeUnit.MILLISECONDS)) throw IllegalStateException("capture timed out")
        java.lang.ref.Reference.reachabilityFence(callback)
        java.lang.ref.Reference.reachabilityFence(listener)
        val result = shot ?: throw IllegalStateException("no frame")

        var buffer: HardwareBuffer? = null
        try {
            buffer = result.javaClass.getMethod("getHardwareBuffer").invoke(result) as? HardwareBuffer
            val secure = runCatching {
                result.javaClass.getMethod("containsSecureLayers").invoke(result) as Boolean
            }.getOrDefault(false)
            val hardware = result.javaClass.getMethod("asBitmap").invoke(result) as? Bitmap
                ?: throw IllegalStateException("frame not readable")
            val bitmap = hardware.copy(Bitmap.Config.ARGB_8888, false)
            hardware.recycle()
            return Bundle().apply {
                putBoolean("ok", true)
                putParcelable("bitmap", bitmap)
                putInt("width", w)
                putInt("height", h)
                putBoolean("secure", secure)
                putLong("ms", SystemClock.elapsedRealtime() - t0)
            }
        } finally {
            buffer?.close()
        }
    }

    // ---- Samsung wallpaper angle reader -------------------------------------

    /**
     * Tails logcat for the "Fold interactive" wallpaper's command log. Each
     * command the app sends makes the wallpaper log a line containing the
     * action it was sent, whether it's visible, and `mCurrentAngle=<deg>`.
     * Log format per Duo Fold Live's findings.
     */
    private class AngleReader(private val action: String, private val callback: IBinder) {
        @Volatile private var process: java.lang.Process? = null
        @Volatile private var stopped = false
        @Volatile private var state = "starting"
        private var lines = 0
        private var parsed = 0
        private var rejected = 0
        private var lastAngle = Float.NaN
        private var lastUptime = 0L

        fun start() {
            val thread = Thread({
                var child: java.lang.Process? = null
                try {
                    child = ProcessBuilder(
                        "logcat", "-v", "epoch", "-T", "1", "-s", "SprWallpaper|FoldInteractive:V", "*:S",
                    ).redirectErrorStream(true).start()
                    process = child
                    state = "listening"
                    BufferedReader(InputStreamReader(child.inputStream)).use { input ->
                        while (!stopped) {
                            val line = input.readLine() ?: break
                            lines++
                            val value = parse(line) ?: continue
                            // Never treat a buffered line as current.
                            val epoch = line.trim().split(Regex("\\s+"), 2).firstOrNull()?.toDoubleOrNull()
                            val age = if (epoch == null) Long.MAX_VALUE else System.currentTimeMillis() - (epoch * 1000).toLong()
                            if (age < -100 || age > 1500) {
                                rejected++
                                continue
                            }
                            parsed++
                            lastAngle = value
                            lastUptime = SystemClock.uptimeMillis() - age.coerceAtLeast(0)
                            state = "receiving"
                            val p = Parcel.obtain()
                            try {
                                p.writeInterfaceToken(ShellProtocol.CALLBACK_TOKEN)
                                p.writeFloat(value)
                                p.writeLong(lastUptime)
                                callback.transact(ShellProtocol.CB_ANGLE, p, null, IBinder.FLAG_ONEWAY)
                            } catch (e: Exception) {
                                state = "callback gone: ${e.message}"
                                break
                            } finally {
                                p.recycle()
                            }
                        }
                    }
                    if (!stopped) state = "log reader ended"
                } catch (e: Exception) {
                    state = "reader error: $e"
                } finally {
                    child?.destroy()
                }
            }, "duo-angle-reader")
            thread.isDaemon = true
            thread.start()
        }

        fun stop() {
            stopped = true
            process?.destroy()
            state = "stopped"
        }

        fun status(): Bundle = Bundle().apply {
            putString("state", state)
            putInt("lines", lines)
            putInt("parsed", parsed)
            putInt("rejected", rejected)
            putFloat("angle", lastAngle)
            putLong("last", lastUptime)
        }

        private fun parse(line: String): Float? {
            if (!line.contains("SprWallpaper|FoldInteractive") || !line.contains("onCommand:")) return null
            if (!(line.contains("action=$action,") || line.contains("action[$action]"))) return null
            if (!(line.contains("isVisible=true") || line.contains("isVisible[true]"))) return null
            val m = ANGLE.matcher(line)
            if (!m.find()) return null
            val v = m.group(1)?.toFloatOrNull() ?: return null
            return if (v in 0f..180f) v else null
        }

        private companion object {
            val ANGLE: Pattern = Pattern.compile("mCurrentAngle(?:=|\\[)([0-9]+(?:\\.[0-9]+)?)")
        }
    }

    private companion object {
        /** Shizuku asks user services to exit with this code. */
        const val SHIZUKU_DESTROY = 16777115

        const val PROBE_OUTPUT_LIMIT =
            16_000

        val FAMILIES = listOf("android.window.ScreenCaptureInternal", "android.window.ScreenCapture")
    }
}
