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
import java.util.concurrent.Executors
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

    private val mirrorLeaseArbiter =
        Fold7MirrorLeaseArbiter()

    private val mirrorMutationExecutor =
        Executors.newSingleThreadExecutor { runnable ->
            Thread(runnable, "duo-mirror-mutation").apply {
                isDaemon = true
            }
        }

    private val coverPanelLease =
        Fold7CoverPanelLease()

    private val coverMutationExecutor =
        Executors.newSingleThreadExecutor { runnable ->
            Thread(runnable, "duo-cover-lease-mutation").apply {
                isDaemon = true
            }
        }

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
            runCatching {
                mirrorMutationExecutor.submit {
                    stopLiveMirror()
                }.get(1, TimeUnit.SECONDS)
            }
            mirrorMutationExecutor.shutdownNow()
            coverMutationExecutor.shutdownNow()
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

            ShellProtocol.OPEN_MIRROR_SESSION -> {
                val identity = clearCallingIdentity()
                val result =
                    try {
                        runMirrorMutation {
                            openMirrorSessionV2()
                        }
                    } catch (t: Throwable) {
                        failureBundle("open-mirror-session", t)
                    } finally {
                        restoreCallingIdentity(identity)
                    }
                out.writeNoException()
                out.writeBundle(result)
            }

            ShellProtocol.MIRROR_DISPLAY_V2 -> {
                val operation = data.readInt()
                val session = data.readLong()
                val sequence = data.readLong()
                val leaseId = data.readLong()
                val sourceDisplayId =
                    if (operation == 1 && data.dataAvail() >= Integer.BYTES) {
                        data.readInt()
                    } else {
                        -1
                    }

                val identity = clearCallingIdentity()
                val result =
                    try {
                        runMirrorMutation {
                            when (operation) {
                                1 -> startLiveMirrorV2(session, sequence, leaseId, sourceDisplayId)
                                0 -> stopLiveMirrorV2(session, sequence, leaseId)
                                2 -> forceStopLiveMirrorV2(session, sequence)
                                else -> Bundle().apply {
                                    putBoolean("ok", false)
                                    putString("error", "unknown mirror V2 operation $operation")
                                }
                            }
                        }
                    } catch (t: Throwable) {
                        failureBundle("mirror-v2", t)
                    } finally {
                        restoreCallingIdentity(identity)
                    }

                out.writeNoException()
                out.writeBundle(result)
            }

            ShellProtocol.COVER_PANEL_LEASE_V2 -> {
                val operation = data.readInt()
                val ownerGeneration = data.readLong()
                val reason = data.readString() ?: "unspecified"
                val identity = clearCallingIdentity()
                val result =
                    try {
                        runCoverMutation {
                            when (operation) {
                                1 -> prewarmCoverLeaseV2(ownerGeneration)
                                2 -> releaseCoverLeaseV2(ownerGeneration, reason)
                                3 -> reconcileCoverLeaseV2(reason)
                                4 -> coverLeaseBundle("status", true)
                                5 -> ensureHeldCoverRouteV2(ownerGeneration, reason)
                                else -> Bundle().apply {
                                    putBoolean("ok", false)
                                    putString("error", "unknown cover lease V2 operation $operation")
                                }
                            }
                        }
                    } catch (t: Throwable) {
                        failureBundle("cover-lease-v2", t)
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
                    if (mirrorLeaseArbiter.snapshot().activeSession > 0L) {
                        Bundle().apply {
                            putBoolean("ok", false)
                            putBoolean("enabled", enable)
                            putString("error", "legacy mirror mutation rejected while V2 session is active")
                        }
                    } else if (!enable) {
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

    private fun failureBundle(
        operation: String,
        error: Throwable,
    ): Bundle {
        var root = error
        while (root.cause != null) root = root.cause!!
        return Bundle().apply {
            putBoolean("ok", false)
            putString("operation", operation)
            putString("error", "${root.javaClass.simpleName}: ${root.message}")
        }
    }

    private fun runMirrorMutation(
        block: () -> Bundle,
    ): Bundle =
        mirrorMutationExecutor.submit<Bundle> { block() }
            .get(4, TimeUnit.SECONDS)

    private fun runCoverMutation(
        block: () -> Bundle,
    ): Bundle =
        coverMutationExecutor.submit<Bundle> { block() }
            .get(4, TimeUnit.SECONDS)

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

    private fun logicalDisplayIdsDirect(): IntArray {
        val dm = displayManagerService()
        val api = Class.forName("android.hardware.display.IDisplayManager")

        val withDisabled =
            api.methods.firstOrNull { method ->
                method.name == "getDisplayIds" &&
                    method.parameterCount == 1 &&
                    method.parameterTypes[0] == java.lang.Boolean.TYPE
            }

        val noArgs =
            api.methods.firstOrNull { method ->
                method.name == "getDisplayIds" &&
                    method.parameterCount == 0
            }

        val value =
            when {
                withDisabled != null -> withDisabled.invoke(dm, true)
                noArgs != null -> noArgs.invoke(dm)
                else -> null
            }

        return value as? IntArray ?: intArrayOf()
    }

    private fun directGeometry(
        logicalId: Int,
    ): Pair<Int, Int>? {
        val info = displayInfoForLogicalId(logicalId) ?: return null
        val width = runCatching {
            info.javaClass.getField("logicalWidth").getInt(info)
        }.getOrDefault(-1)
        val height = runCatching {
            info.javaClass.getField("logicalHeight").getInt(info)
        }.getOrDefault(-1)
        return if (width > 0 && height > 0) width to height else null
    }

    private fun directCoverRoute(): Pair<Int, Long>? {
        val directIds =
            runCatching { logicalDisplayIdsDirect().toList() }
                .getOrDefault(emptyList())

        val candidates =
            directIds.mapNotNull { id ->
                if (id == Display.DEFAULT_DISPLAY) return@mapNotNull null
                if (directGeometry(id) != (1080 to 2520)) return@mapNotNull null
                id to physicalDisplayIdFromLogical(id)
            }

        val ownedPhysical =
            coverPanelLease.snapshot().physicalId
                ?: cachedCoverPhysicalDisplayId.takeIf { it >= 0L }

        candidates.firstOrNull { (_, physical) ->
            ownedPhysical != null && physical == ownedPhysical
        }?.let { return it }

        candidates.firstOrNull()?.let { return it }

        // Compatibility fallback only when hidden direct enumeration is unavailable.
        val legacyId = resolveFreshCoverLogicalId(-1)
        return if (legacyId >= 0) {
            legacyId to physicalDisplayIdFromLogical(legacyId)
        } else {
            null
        }
    }

    private fun coverLeaseTopology(): Fold7CoverPanelLease.Topology {
        val defaultGeometry = directGeometry(Display.DEFAULT_DISPLAY)
        val route = directCoverRoute()

        return Fold7CoverPanelLease.Topology(
            nativeCover = defaultGeometry == (1080 to 2520),
            innerIsDefault = defaultGeometry == (1968 to 2184),
            coverSecondaryLogicalId = route?.first,
            coverSecondaryPhysicalId = route?.second?.takeIf { it >= 0L },
        )
    }

    private fun executeCoverLeaseActions(
        actions: List<Fold7CoverPanelLease.Action>,
    ): Boolean? {
        var lastResetResult: Boolean? = null
        for (action in actions) {
            when (action) {
                is Fold7CoverPanelLease.Action.PowerPhysicalCover -> Unit
                is Fold7CoverPanelLease.Action.ResetLogicalCoverPower -> {
                    val fresh = coverLeaseTopology()
                    val ownedPhysical = coverPanelLease.snapshot().physicalId
                    val stillSafe =
                        fresh.innerIsDefault &&
                            fresh.coverSecondaryLogicalId == action.logicalId &&
                            fresh.coverSecondaryPhysicalId != null &&
                            (ownedPhysical == null || fresh.coverSecondaryPhysicalId == ownedPhysical)

                    val ok =
                        stillSafe &&
                            runCatching {
                                requestDisplayPowerInternal(
                                    action.logicalId,
                                    Display.STATE_UNKNOWN,
                                )
                            }.getOrDefault(false)

                    lastResetResult = ok
                    coverPanelLease.onLogicalResetResult(
                        action.leaseId,
                        action.epoch,
                        action.logicalId,
                        ok,
                    )
                }
            }
        }
        return lastResetResult
    }

    private fun coverLeaseBundle(
        operation: String,
        ok: Boolean,
        resetResult: Boolean? = null,
    ): Bundle {
        val snapshot = coverPanelLease.snapshot()
        return Bundle().apply {
            putBoolean("ok", ok)
            putString("operation", operation)
            putString("leaseState", snapshot.state.name)
            putLong("leaseId", snapshot.leaseId)
            putLong("leaseEpoch", snapshot.epoch)
            putLong("ownerGeneration", snapshot.ownerGeneration)
            putLong("physicalDisplayId", snapshot.physicalId ?: -1L)
            putString("pendingReleaseReason", snapshot.pendingReleaseReason)
            putBoolean("released", snapshot.state == Fold7CoverPanelLease.State.IDLE)
            putBoolean(
                "releasePending",
                snapshot.state == Fold7CoverPanelLease.State.RELEASE_PENDING ||
                    snapshot.state == Fold7CoverPanelLease.State.UNKNOWN_RECOVERY,
            )
            if (resetResult != null) putBoolean("logicalResetOk", resetResult)
        }
    }

    private data class CoverRouteActivation(
        val logicalId: Int,
        val physicalId: Long,
        val routeEnabled: Boolean,
        val logicalPowered: Boolean,
        val stillSafe: Boolean,
        val error: String?,
    ) {
        val ok: Boolean
            get() =
                stillSafe &&
                    (routeEnabled || logicalPowered)
    }

    /**
     * Physical NORMAL is only the first half of a Fold7 cover prewarm.
     *
     * Samsung can expose the 1080x2520 cover as a disabled logical route after
     * the physical panel wakes. The legacy working path immediately enabled
     * that route and requested STATE_ON. Gen2 ownership originally stopped
     * after physical NORMAL, which left the lease HELD but gave Android no
     * active destination for DisplayMirrorHost.
     *
     * Resolve the logical route fresh, require that it still maps to the exact
     * physical cover owned by the lease, enable it, re-resolve/revalidate, then
     * request logical STATE_ON. No logical display id is retained.
     */
    private fun activateOwnedCoverRouteAfterPhysicalWake(
        ownedPhysicalId: Long,
    ): CoverRouteActivation {
        if (ownedPhysicalId < 0L) {
            return CoverRouteActivation(
                logicalId = -1,
                physicalId = ownedPhysicalId,
                routeEnabled = false,
                logicalPowered = false,
                stillSafe = false,
                error = "owned physical cover id unavailable",
            )
        }

        var route: Pair<Int, Long>? = null

        // Give Samsung a small bounded window to publish the disabled logical
        // route after physical NORMAL. This runs on the serialized cover
        // mutation executor, never on the app main thread.
        for (attempt in 0 until 6) {
            val candidate =
                runCatching {
                    directCoverRoute()
                }.getOrNull()

            if (
                candidate != null &&
                candidate.first != Display.DEFAULT_DISPLAY &&
                candidate.second == ownedPhysicalId
            ) {
                route = candidate
                break
            }

            if (attempt < 5) {
                Thread.sleep(8L)
            }
        }

        val resolved =
            route
                ?: return CoverRouteActivation(
                    logicalId = -1,
                    physicalId = ownedPhysicalId,
                    routeEnabled = false,
                    logicalPowered = false,
                    stillSafe = false,
                    error = "physical cover woke but no matching 1080x2520 logical route appeared",
                )

        val logicalId = resolved.first

        var routeEnabled = false
        var routeError: String? = null

        runCatching {
            enableConnectedDisplayInternal(logicalId)
            routeEnabled = true
        }.onFailure { error ->
            routeError =
                "${error.javaClass.simpleName}: ${error.message}"
        }

        // Never trust the logical id after a mutating display-manager call.
        // Samsung may remap it synchronously.
        val after =
            runCatching {
                directCoverRoute()
            }.getOrNull()

        val innerStillDefault =
            directGeometry(Display.DEFAULT_DISPLAY) ==
                (1968 to 2184)

        val stillSafe =
            innerStillDefault &&
                after?.first == logicalId &&
                after.second == ownedPhysicalId

        val logicalPowered =
            if (stillSafe) {
                runCatching {
                    requestDisplayPowerInternal(
                        logicalId,
                        Display.STATE_ON,
                    )
                }.getOrElse { error ->
                    routeError =
                        listOfNotNull(
                            routeError,
                            "${error.javaClass.simpleName}: ${error.message}",
                        ).joinToString(" | ")
                    false
                }
            } else {
                false
            }

        return CoverRouteActivation(
            logicalId = logicalId,
            physicalId = ownedPhysicalId,
            routeEnabled = routeEnabled,
            logicalPowered = logicalPowered,
            stillSafe = stillSafe,
            error =
                when {
                    !stillSafe ->
                        "cover logical route remapped before STATE_ON"
                    routeError != null ->
                        routeError
                    else ->
                        null
                },
        )
    }

    private fun prewarmCoverLeaseV2(
        ownerGeneration: Long,
    ): Bundle {
        if (ownerGeneration < 0L) {
            return coverLeaseBundle("prewarm", false)
        }

        val actions =
            coverPanelLease.beginPrewarm(ownerGeneration)

        var physicalOk = true
        var physicalError: String? = null

        for (action in actions) {
            if (action is Fold7CoverPanelLease.Action.PowerPhysicalCover) {
                val physicalId =
                    resolveFold7CoverPhysicalDisplayId(-1)

                val (powered, error) =
                    setPhysicalPowerNormal(physicalId)

                physicalOk = powered
                physicalError = error

                val followUp =
                    coverPanelLease.onPhysicalPrewarmResult(
                        action.leaseId,
                        action.epoch,
                        powered,
                        physicalId.takeIf { it >= 0L },
                        coverLeaseTopology(),
                    )

                executeCoverLeaseActions(followUp)
            }
        }

        val snapshot =
            coverPanelLease.snapshot()

        val leaseHeld =
            snapshot.state !=
                Fold7CoverPanelLease.State.IDLE

        val activation =
            if (
                physicalOk &&
                leaseHeld
            ) {
                activateOwnedCoverRouteAfterPhysicalWake(
                    snapshot.physicalId ?: -1L
                )
            } else {
                CoverRouteActivation(
                    logicalId = -1,
                    physicalId = snapshot.physicalId ?: -1L,
                    routeEnabled = false,
                    logicalPowered = false,
                    stillSafe = false,
                    error =
                        physicalError
                            ?: "cover lease was not established",
                )
            }

        /*
         * A physical-only success is not enough for the app continuity path:
         * DisplayMirrorHost needs a usable logical cover destination.
         *
         * If Samsung publishes the logical route a few milliseconds late,
         * this call remains bounded and the controller may retry without
         * issuing another physical wake because beginPrewarm() adopts HELD
         * ownership.
         */
        val ok =
            physicalOk &&
                leaseHeld &&
                activation.ok

        return coverLeaseBundle(
            operation = "prewarm",
            ok = ok,
        ).apply {
            putInt(
                "targetDisplayId",
                if (activation.stillSafe) {
                    activation.logicalId
                } else {
                    -1
                },
            )
            putBoolean(
                "physicalPowered",
                physicalOk,
            )
            putBoolean(
                "routeEnabled",
                activation.routeEnabled,
            )
            putBoolean(
                "logicalPowered",
                activation.logicalPowered,
            )
            putBoolean(
                "routeStillCover",
                activation.stillSafe,
            )
            putString(
                "command",
                "lease-owned physical+logical Fold7 cover prewarm",
            )
            putString(
                "error",
                activation.error
                    ?: physicalError,
            )
        }
    }

    /**
     * Keep an existing HELD cover lease alive without transferring ownership.
     *
     * The caller must still own the exact HELD lease. The stable physical
     * cover id is taken from that lease, physical NORMAL is reasserted, and a
     * fresh non-default 1080x2520 logical route must map back to the same
     * physical id before enable / STATE_ON.
     */
    private fun ensureHeldCoverRouteV2(
        ownerGeneration: Long,
        reason: String,
    ): Bundle {
        val before =
            coverPanelLease.snapshot()

        if (
            before.state !=
                Fold7CoverPanelLease.State.HELD
        ) {
            return coverLeaseBundle(
                "ensure-held:$reason",
                false,
            ).apply {
                putBoolean("stale", true)
                putString(
                    "error",
                    "cover lease is ${before.state}, not HELD",
                )
            }
        }

        if (
            ownerGeneration < 0L ||
            ownerGeneration !=
                before.ownerGeneration
        ) {
            return coverLeaseBundle(
                "ensure-held:$reason",
                false,
            ).apply {
                putBoolean("stale", true)
                putString(
                    "error",
                    "cover lease owner changed",
                )
            }
        }

        val physicalId =
            before.physicalId
                ?: -1L

        val (
            physicalPowered,
            physicalError,
        ) =
            setPhysicalPowerNormal(
                physicalId
            )

        val activation =
            if (physicalPowered) {
                activateOwnedCoverRouteAfterPhysicalWake(
                    physicalId
                )
            } else {
                CoverRouteActivation(
                    logicalId = -1,
                    physicalId = physicalId,
                    routeEnabled = false,
                    logicalPowered = false,
                    stillSafe = false,
                    error =
                        physicalError
                            ?: "physical cover reassert failed",
                )
            }

        val ok =
            physicalPowered &&
                activation.ok

        return coverLeaseBundle(
            operation =
                "ensure-held:$reason",
            ok = ok,
        ).apply {
            putInt(
                "targetDisplayId",
                if (activation.stillSafe) {
                    activation.logicalId
                } else {
                    -1
                },
            )
            putBoolean(
                "physicalPowered",
                physicalPowered,
            )
            putBoolean(
                "routeEnabled",
                activation.routeEnabled,
            )
            putBoolean(
                "logicalPowered",
                activation.logicalPowered,
            )
            putBoolean(
                "routeStillCover",
                activation.stillSafe,
            )
            putString(
                "command",
                "lease-owned Fold7 cover hold reassert",
            )
            putString(
                "error",
                activation.error
                    ?: physicalError,
            )
        }
    }

    private fun releaseCoverLeaseV2(
        ownerGeneration: Long,
        reason: String,
    ): Bundle {
        val before = coverPanelLease.snapshot()
        if (before.state == Fold7CoverPanelLease.State.IDLE) {
            return coverLeaseBundle("release", true)
        }
        if (ownerGeneration != before.ownerGeneration) {
            return coverLeaseBundle("release-stale-owner", false)
        }

        val actions = coverPanelLease.requestRelease(
            ownerGeneration,
            reason,
            coverLeaseTopology(),
        )
        val reset = executeCoverLeaseActions(actions)
        return coverLeaseBundle("release", true, reset)
    }

    private fun reconcileCoverLeaseV2(
        reason: String,
    ): Bundle {
        val actions = coverPanelLease.onTopology(coverLeaseTopology())
        val reset = executeCoverLeaseActions(actions)
        return coverLeaseBundle("reconcile:$reason", true, reset)
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

    private fun releaseMirrorSurface(
        mirror: SurfaceControl?,
    ) {
        val current = mirror ?: return
        runCatching {
            SurfaceControl.Transaction().use { tx ->
                tx.reparent(current, null)
                tx.apply()
            }
        }
        runCatching { current.release() }
    }

    private fun stopLiveMirror() {
        val current = liveMirror ?: return
        liveMirror = null
        releaseMirrorSurface(current)
    }

    private fun createMirrorCandidate(
        sourceDisplayId: Int,
    ): SurfaceControl {
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
                    constructor.isAccessible = true
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
            ) as? Boolean ?: false

        if (!mirrored || !mirror.isValid) {
            runCatching { mirror.release() }
            throw IllegalStateException(
                "WindowManager mirrorDisplay($sourceDisplayId) returned no valid surface"
            )
        }

        return mirror
    }

    private fun openMirrorSessionV2(): Bundle {
        val previous = liveMirror
        liveMirror = null
        val opened = mirrorLeaseArbiter.openSession()
        releaseMirrorSurface(previous)
        return Bundle().apply {
            putBoolean("ok", true)
            putLong("mirrorSession", opened.session)
            putLong("releasedPreviousLease", opened.previousLeaseId ?: -1L)
        }
    }

    private fun startLiveMirrorV2(
        session: Long,
        sequence: Long,
        leaseId: Long,
        sourceDisplayId: Int,
    ): Bundle {
        val ticket =
            mirrorLeaseArbiter.reserveStart(
                session, sequence, leaseId, sourceDisplayId,
            ) ?: return Bundle().apply {
                putBoolean("ok", false)
                putBoolean("stale", true)
                putString("decision", "start-rejected")
            }

        val candidate =
            try {
                createMirrorCandidate(sourceDisplayId)
            } catch (t: Throwable) {
                mirrorLeaseArbiter.failStart(ticket)
                return failureBundle("mirror-candidate-preserved-current", t).apply {
                    putString("decision", "candidate-failed-preserved-current")
                    putLong("mirrorSession", session)
                    putLong("mirrorSequence", sequence)
                    putLong("mirrorLeaseId", leaseId)
                }
            }

        val committed = mirrorLeaseArbiter.commitStart(ticket)
        if (!committed.accepted) {
            releaseMirrorSurface(candidate)
            return Bundle().apply {
                putBoolean("ok", false)
                putBoolean("stale", true)
                putString("decision", committed.reason)
            }
        }

        val previous = liveMirror
        liveMirror = candidate
        if (previous !== candidate) releaseMirrorSurface(previous)

        return Bundle().apply {
            putBoolean("ok", true)
            putBoolean("enabled", true)
            putString("decision", committed.reason)
            putLong("mirrorSession", session)
            putLong("mirrorSequence", sequence)
            putLong("mirrorLeaseId", leaseId)
            putLong("previousLeaseId", committed.previousLeaseId ?: -1L)
            putInt("sourceDisplayId", sourceDisplayId)
            putParcelable("mirrorSurface", candidate)
        }
    }

    private fun stopLiveMirrorV2(
        session: Long,
        sequence: Long,
        leaseId: Long,
    ): Bundle {
        val result = mirrorLeaseArbiter.stop(session, sequence, leaseId)
        if (result.releaseCurrent) {
            val current = liveMirror
            liveMirror = null
            releaseMirrorSurface(current)
        }
        return Bundle().apply {
            putBoolean("ok", result.accepted)
            putBoolean("enabled", !result.releaseCurrent)
            putString("decision", result.reason)
            putLong("mirrorSession", session)
            putLong("mirrorSequence", sequence)
            putLong("mirrorLeaseId", leaseId)
        }
    }

    private fun forceStopLiveMirrorV2(
        session: Long,
        sequence: Long,
    ): Bundle {
        val result = mirrorLeaseArbiter.forceStop(session, sequence)
        if (result.releaseCurrent) {
            val current = liveMirror
            liveMirror = null
            releaseMirrorSurface(current)
        }
        return Bundle().apply {
            putBoolean("ok", result.accepted)
            putBoolean("enabled", false)
            putString("decision", result.reason)
            putLong("mirrorSession", session)
            putLong("mirrorSequence", sequence)
        }
    }

    /** Legacy fallback used only before a V2 session is opened. */
    private fun createLiveMirror(
        sourceDisplayId: Int,
    ): Bundle {
        stopLiveMirror()
        val mirror = createMirrorCandidate(sourceDisplayId)
        liveMirror = mirror
        return Bundle().apply {
            putBoolean("ok", true)
            putBoolean("enabled", true)
            putInt("sourceDisplayId", sourceDisplayId)
            putParcelable("mirrorSurface", mirror)
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
    private class AngleReader(
        private val actionPrefix: String,
        private val callback: IBinder,
    ) {
        @Volatile private var process: java.lang.Process? = null
        @Volatile private var stopped = false
        @Volatile private var state = "starting"
        private var lines = 0
        private var parsed = 0
        private var rejected = 0
        private var lastAngle = Float.NaN
        private var lastUptime = 0L
        private var lastPollSequence = 0L

        private data class ParsedAngle(
            val angle: Float,
            val pollSequence: Long,
        )

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
                            val parsedLine = parse(line) ?: continue
                            // Never treat a buffered line as current.
                            val epoch = line.trim().split(Regex("\\s+"), 2).firstOrNull()?.toDoubleOrNull()
                            val age = if (epoch == null) Long.MAX_VALUE else System.currentTimeMillis() - (epoch * 1000).toLong()
                            if (age < -100 || age > 1500) {
                                rejected++
                                continue
                            }
                            parsed++
                            lastAngle = parsedLine.angle
                            lastPollSequence = parsedLine.pollSequence
                            lastUptime = SystemClock.uptimeMillis() - age.coerceAtLeast(0)
                            state = "receiving"
                            val p = Parcel.obtain()
                            try {
                                p.writeInterfaceToken(ShellProtocol.CALLBACK_TOKEN)
                                p.writeFloat(parsedLine.angle)
                                p.writeLong(lastUptime)
                                p.writeLong(parsedLine.pollSequence)
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
            putLong("pollSequence", lastPollSequence)
        }

        private fun parse(line: String): ParsedAngle? {
            if (!line.contains("SprWallpaper|FoldInteractive") || !line.contains("onCommand:")) return null
            if (!(line.contains("isVisible=true") || line.contains("isVisible[true]"))) return null

            val actionMatch = ACTION.matcher(line)
            if (!actionMatch.find()) return null
            val action = actionMatch.group(1) ?: return null

            val pollSequence =
                when {
                    action == actionPrefix -> 0L
                    action.startsWith("$actionPrefix:") ->
                        action.substring(actionPrefix.length + 1).toLongOrNull()
                            ?: return null
                    else -> return null
                }

            val angleMatch = ANGLE.matcher(line)
            if (!angleMatch.find()) return null
            val value = angleMatch.group(1)?.toFloatOrNull() ?: return null
            if (value !in 0f..180f) return null

            return ParsedAngle(
                angle = value,
                pollSequence = pollSequence,
            )
        }

        private companion object {
            val ACTION: Pattern =
                Pattern.compile("action(?:=|\\[)([^,\\]]+)")
            val ANGLE: Pattern =
                Pattern.compile("mCurrentAngle(?:=|\\[)([0-9]+(?:\\.[0-9]+)?)")
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
