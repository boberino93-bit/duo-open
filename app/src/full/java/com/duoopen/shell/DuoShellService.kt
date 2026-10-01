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

    init {
        attachInterface(null, ShellProtocol.TOKEN)
    }

    override fun onTransact(
        code: Int,
        data: Parcel,
        reply: Parcel?,
        flags: Int,
    ): Boolean {
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

        if (owner < 0) {
            owner = caller
        }

        if (caller != owner) {
            throw SecurityException("wrong caller")
        }

        val out =
            reply
                ?: return false

        when (code) {
            ShellProtocol.PING -> {
                out.writeNoException()

                out.writeBundle(
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
                            "capture",
                            runCatching {
                                api().name
                            }.getOrElse {
                                "unavailable: ${it.message}"
                            },
                        )
                    }
                )
            }

            ShellProtocol.CAPTURE -> {
                val displayId =
                    data.readInt()

                val n =
                    data.readInt()

                val excluded =
                    Array(n) {
                        data.readTypedObject(
                            SurfaceControl.CREATOR
                        )
                    }

                val scale =
                    data.readFloat()

                val identity =
                    clearCallingIdentity()

                val result =
                    try {
                        capture(
                            displayId,
                            excluded
                                .filterNotNull()
                                .toTypedArray(),
                            scale,
                        )
                    } catch (t: Throwable) {
                        var root: Throwable =
                            t

                        while (root.cause != null) {
                            root =
                                root.cause!!
                        }

                        Bundle().apply {
                            putString(
                                "error",
                                "${root.javaClass.simpleName}: ${root.message}",
                            )
                        }
                    } finally {
                        excluded.forEach {
                            runCatching {
                                it?.release()
                            }
                        }

                        restoreCallingIdentity(
                            identity
                        )
                    }

                out.writeNoException()
                out.writeBundle(result)
            }

            ShellProtocol.START_ANGLES -> {
                val action =
                    data.readString()
                        ?: throw IllegalArgumentException(
                            "action"
                        )

                val callback =
                    data.readStrongBinder()
                        ?: throw IllegalArgumentException(
                            "callback"
                        )

                reader?.stop()

                reader =
                    AngleReader(
                        action,
                        callback,
                    ).also {
                        it.start()
                    }

                out.writeNoException()
            }

            ShellProtocol.STOP_ANGLES -> {
                reader?.stop()
                reader = null

                out.writeNoException()
            }

            ShellProtocol.ANGLE_STATUS -> {
                out.writeNoException()

                out.writeBundle(
                    reader?.status()
                        ?: Bundle().apply {
                            putString(
                                "state",
                                "not started",
                            )
                        }
                )
            }

            ShellProtocol.DISPLAY_PROBE -> {
                val identity =
                    clearCallingIdentity()

                val result =
                    try {
                        displayProbe()
                    } catch (t: Throwable) {
                        Bundle().apply {
                            putString(
                                "error",
                                "${t.javaClass.simpleName}: ${t.message}",
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

            ShellProtocol.ENABLE_SECONDARY_DISPLAY -> {
                val identity =
                    clearCallingIdentity()

                val result =
                    try {
                        secondaryDisplayCommand(
                            enable = true
                        )
                    } catch (t: Throwable) {
                        Bundle().apply {
                            putBoolean(
                                "ok",
                                false,
                            )

                            putString(
                                "error",
                                "${t.javaClass.simpleName}: ${t.message}",
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

            ShellProtocol.RESET_SECONDARY_DISPLAY -> {
                val identity =
                    clearCallingIdentity()

                val result =
                    try {
                        secondaryDisplayCommand(
                            enable = false
                        )
                    } catch (t: Throwable) {
                        Bundle().apply {
                            putBoolean(
                                "ok",
                                false,
                            )

                            putString(
                                "error",
                                "${t.javaClass.simpleName}: ${t.message}",
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

            ShellProtocol.MIRROR_DISPLAY -> {
                val enable =
                    data.readInt() != 0

                val identity =
                    clearCallingIdentity()

                val result =
                    try {
                        if (!enable) {
                            stopLiveMirror()

                            Bundle().apply {
                                putBoolean(
                                    "ok",
                                    true,
                                )

                                putBoolean(
                                    "enabled",
                                    false,
                                )
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
                        var root: Throwable =
                            t

                        while (root.cause != null) {
                            root =
                                root.cause!!
                        }

                        Bundle().apply {
                            putBoolean(
                                "ok",
                                false,
                            )

                            putBoolean(
                                "enabled",
                                enable,
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
                        var root: Throwable =
                            t

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

            else ->
                return super.onTransact(
                    code,
                    data,
                    reply,
                    flags,
                )
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
                TimeUnit.SECONDS,
            )

        if (!finished) {
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

    // ---- one-shot Fold7 secondary display experiment -----------------------

    private fun secondaryDisplayCommand(
        enable: Boolean,
    ): Bundle {
        val windowDisplays =
            runProbe(
                "dumpsys window displays | " +
                    "grep -E '^[[:space:]]*Display: mDisplayId=|^[[:space:]]*init='"
            )

        val foldDisplays =
            Regex(
                "Display: mDisplayId=(\\d+).*?init=(\\d+)x(\\d+)",
                setOf(
                    RegexOption.DOT_MATCHES_ALL
                ),
            ).findAll(
                windowDisplays
            ).mapNotNull { match ->
                val id =
                    match.groupValues[1]
                        .toIntOrNull()
                        ?: return@mapNotNull null

                val width =
                    match.groupValues[2]
                        .toIntOrNull()
                        ?: return@mapNotNull null

                val height =
                    match.groupValues[3]
                        .toIntOrNull()
                        ?: return@mapNotNull null

                Triple(
                    id,
                    width,
                    height,
                )
            }.filter { (_, width, height) ->
                (
                    width == 1080 &&
                        height == 2520
                    ) ||
                    (
                        width == 1968 &&
                            height == 2184
                    )
            }.toList()

        val target =
            foldDisplays.firstOrNull {
                    _,
                    width,
                    height,
                ->
                width == 1080 &&
                    height == 2520
            }

        if (target == null) {
            return Bundle().apply {
                putBoolean(
                    "ok",
                    false,
                )

                putInt(
                    "targetDisplayId",
                    -1,
                )

                putString(
                    "error",
                    "The physical Fold7 cover route (1080x2520) was not found.",
                )

                putString(
                    "windowDisplays",
                    windowDisplays,
                )
            }
        }

        val targetId =
            target.first

        val command =
            if (enable) {
                "cmd display enable-display $targetId"
            } else {
                /*
                 * Return control to Samsung instead of forcing the display off.
                 */
                "cmd display power-reset $targetId"
            }

        val commandOutput =
            runProbe(
                command
            )

        val immediatePowerOn =
            if (enable) {
                Thread.sleep(
                    40L
                )

                runCatching {
                    requestDisplayPowerInternal(
                        targetId,
                        android.view.Display.STATE_ON,
                    )
                }.getOrDefault(
                    false
                )
            } else {
                false
            }

        Thread.sleep(
            600L
        )

        val afterDisplays =
            runProbe(
                "cmd display get-displays"
            )

        val afterPhysical =
            runProbe(
                "dumpsys display | " +
                    "grep -E -i " +
                    "'DisplayDeviceInfo|mDisplayId=|mState=|" +
                    "mCommittedState=|mPhysicalDisplayId=|" +
                    "uniqueId=|state ON|state OFF' | " +
                    "head -n 220"
            )

        val visibleAfter =
            afterDisplays.contains(
                "Display id $targetId:"
            )

        val commandFailed =
            commandOutput.contains(
                "Exception",
                ignoreCase = true,
            ) ||
                commandOutput.contains(
                    "error",
                    ignoreCase = true,
                ) ||
                commandOutput.contains(
                    "not possible",
                    ignoreCase = true,
                )

        return Bundle().apply {
            putBoolean(
                "ok",
                !commandFailed,
            )

            putBoolean(
                "enable",
                enable,
            )

            putInt(
                "targetDisplayId",
                targetId,
            )

            putInt(
                "targetWidth",
                target.second,
            )

            putInt(
                "targetHeight",
                target.third,
            )

            putBoolean(
                "visibleAfter",
                visibleAfter,
            )

            putBoolean(
                "immediatePowerOn",
                immediatePowerOn,
            )

            putString(
                "command",
                command,
            )

            putString(
                "commandOutput",
                commandOutput,
            )

            putString(
                "windowDisplays",
                windowDisplays,
            )

            putString(
                "afterDisplays",
                afterDisplays,
            )

            putString(
                "afterPhysical",
                afterPhysical,
            )
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
            putBoolean(
                "ok",
                true,
            )

            putBoolean(
                "enabled",
                true,
            )

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

    private fun systemService(
        name: String,
        stub: String,
    ): Any {
        val binder =
            Class.forName(
                "android.os.ServiceManager"
            ).getMethod(
                "getService",
                String::class.java,
            ).invoke(
                null,
                name,
            ) as IBinder

        return Class.forName(
            stub
        ).getMethod(
            "asInterface",
            IBinder::class.java,
        ).invoke(
            null,
            binder,
        )!!
    }

    /**
     * Finds whichever generation of the hidden capture API this Android has:
     * `android.window.ScreenCaptureInternal` (status callback) or
     * `android.window.ScreenCapture` (plain consumer), driven through
     * `IWindowManager.captureDisplay`.
     */
    private fun api(): CaptureApi {
        captureApi?.let {
            return it
        }

        val wm =
            Class.forName(
                "android.view.IWindowManager"
            )

        val errors =
            StringBuilder()

        for (family in FAMILIES) {
            try {
                val args =
                    Class.forName(
                        "$family\$CaptureArgs"
                    )

                val builder =
                    Class.forName(
                        "$family\$CaptureArgs\$Builder"
                    )

                val listener =
                    Class.forName(
                        "$family\$ScreenCaptureListener"
                    )

                val ctor =
                    builder.getConstructor()

                builder.getMethod(
                    "setSourceCrop",
                    Rect::class.java,
                )

                builder.getMethod(
                    "setFrameScale",
                    java.lang.Float.TYPE,
                )

                builder.getMethod(
                    "setExcludeLayers",
                    Array<SurfaceControl>::class.java,
                )

                builder.getMethod(
                    "build"
                )

                var status =
                    true

                val listenerCtor =
                    try {
                        listener.getConstructor(
                            ObjIntConsumer::class.java
                        )
                    } catch (
                        _: NoSuchMethodException
                    ) {
                        status =
                            false

                        listener.getConstructor(
                            Consumer::class.java
                        )
                    }

                val capture =
                    wm.getMethod(
                        "captureDisplay",
                        Integer.TYPE,
                        args,
                        listener,
                    )

                return CaptureApi(
                    family,
                    ctor,
                    builder,
                    listenerCtor,
                    status,
                    capture,
                ).also {
                    captureApi =
                        it
                }
            } catch (
                e: ReflectiveOperationException
            ) {
                errors
                    .append(family)
                    .append(": ")
                    .append(e)
                    .append("; ")
            }
        }

        throw ClassNotFoundException(
            "no compatible display capture API: $errors"
        )
    }

    private fun capture(
        displayId: Int,
        excluded: Array<SurfaceControl>,
        scale: Float,
    ): Bundle {
        val t0 =
            SystemClock.elapsedRealtime()

        val api =
            api()

        val wm =
            systemService(
                "window",
                "android.view.IWindowManager\$Stub",
            )

        val dm =
            systemService(
                "display",
                "android.hardware.display.IDisplayManager\$Stub",
            )

        val info =
            Class.forName(
                "android.hardware.display.IDisplayManager"
            ).getMethod(
                "getDisplayInfo",
                Integer.TYPE,
            ).invoke(
                dm,
                displayId,
            )
                ?: throw IllegalStateException(
                    "no display $displayId"
                )

        val width =
            info.javaClass
                .getField(
                    "logicalWidth"
                )
                .getInt(
                    info
                )

        val height =
            info.javaClass
                .getField(
                    "logicalHeight"
                )
                .getInt(
                    info
                )

        if (
            width <= 0 ||
            height <= 0
        ) {
            throw IllegalStateException(
                "display $displayId has no size"
            )
        }

        val builder =
            api.builderCtor
                .newInstance()

        api.builder
            .getMethod(
                "setSourceCrop",
                Rect::class.java,
            )
            .invoke(
                builder,
                Rect(
                    0,
                    0,
                    width,
                    height,
                ),
            )

        api.builder
            .getMethod(
                "setFrameScale",
                java.lang.Float.TYPE,
            )
            .invoke(
                builder,
                scale.coerceIn(
                    0.1f,
                    1f,
                ),
            )

        if (excluded.isNotEmpty()) {
            api.builder
                .getMethod(
                    "setExcludeLayers",
                    Array<SurfaceControl>::class.java,
                )
                .invoke(
                    builder,
                    excluded,
                )
        }

        val args =
            api.builder
                .getMethod(
                    "build"
                )
                .invoke(
                    builder
                )

        val latch =
            CountDownLatch(
                1
            )

        var shot: Any? =
            null

        val callback: Any =
            if (api.statusCallback) {
                ObjIntConsumer<Any?> {
                        value,
                        _,
                    ->
                    shot =
                        value

                    latch.countDown()
                }
            } else {
                Consumer<Any?> { value ->
                    shot =
                        value

                    latch.countDown()
                }
            }

        val listener =
            api.listenerCtor
                .newInstance(
                    callback
                )

        api.captureDisplay.invoke(
            wm,
            displayId,
            args,
            listener,
        )

        if (
            !latch.await(
                400,
                TimeUnit.MILLISECONDS,
            )
        ) {
            throw IllegalStateException(
                "capture timed out"
            )
        }

        java.lang.ref.Reference
            .reachabilityFence(
                callback
            )

        java.lang.ref.Reference
            .reachabilityFence(
                listener
            )

        val result =
            shot
                ?: throw IllegalStateException(
                    "no frame"
                )

        var buffer: HardwareBuffer? =
            null

        try {
            buffer =
                result.javaClass
                    .getMethod(
                        "getHardwareBuffer"
                    )
                    .invoke(
                        result
                    ) as? HardwareBuffer

            val secure =
                runCatching {
                    result.javaClass
                        .getMethod(
                            "containsSecureLayers"
                        )
                        .invoke(
                            result
                        ) as Boolean
                }.getOrDefault(
                    false
                )

            val hardware =
                result.javaClass
                    .getMethod(
                        "asBitmap"
                    )
                    .invoke(
                        result
                    ) as? Bitmap
                    ?: throw IllegalStateException(
                        "frame not readable"
                    )

            val bitmap =
                hardware.copy(
                    Bitmap.Config.ARGB_8888,
                    false,
                )

            hardware.recycle()

            return Bundle().apply {
                putBoolean(
                    "ok",
                    true,
                )

                putParcelable(
                    "bitmap",
                    bitmap,
                )

                putInt(
                    "width",
                    width,
                )

                putInt(
                    "height",
                    height,
                )

                putBoolean(
                    "secure",
                    secure,
                )

                putLong(
                    "ms",
                    SystemClock.elapsedRealtime() -
                        t0,
                )
            }
        } finally {
            buffer?.close()
        }
    }

    // ---- Samsung wallpaper angle reader -----------------------------------

    /**
     * Tails logcat for the "Fold interactive" wallpaper's command log. Each
     * command the app sends makes the wallpaper log a line containing the
     * action it was sent, whether it's visible, and `mCurrentAngle=<deg>`.
     * Log format per Duo Fold Live's findings.
     */
    private class AngleReader(
        private val action: String,
        private val callback: IBinder,
    ) {
        @Volatile
        private var process: java.lang.Process? =
            null

        @Volatile
        private var stopped =
            false

        @Volatile
        private var state =
            "starting"

        private var lines =
            0

        private var parsed =
            0

        private var rejected =
            0

        private var lastAngle =
            Float.NaN

        private var lastUptime =
            0L

        fun start() {
            val thread =
                Thread(
                    {
                        var child:
                            java.lang.Process? =
                            null

                        try {
                            child =
                                ProcessBuilder(
                                    "logcat",
                                    "-v",
                                    "epoch",
                                    "-T",
                                    "1",
                                    "-s",
                                    "SprWallpaper|FoldInteractive:V",
                                    "*:S",
                                )
                                    .redirectErrorStream(
                                        true
                                    )
                                    .start()

                            process =
                                child

                            state =
                                "listening"

                            BufferedReader(
                                InputStreamReader(
                                    child.inputStream
                                )
                            ).use { input ->
                                while (!stopped) {
                                    val line =
                                        input.readLine()
                                            ?: break

                                    lines++

                                    val value =
                                        parse(
                                            line
                                        )
                                            ?: continue

                                    /*
                                     * Never treat a buffered line as current.
                                     */
                                    val epoch =
                                        line
                                            .trim()
                                            .split(
                                                Regex("\\s+"),
                                                2,
                                            )
                                            .firstOrNull()
                                            ?.toDoubleOrNull()

                                    val age =
                                        if (epoch == null) {
                                            Long.MAX_VALUE
                                        } else {
                                            System.currentTimeMillis() -
                                                (
                                                    epoch *
                                                        1000
                                                    ).toLong()
                                        }

                                    if (
                                        age < -100 ||
                                        age > 1500
                                    ) {
                                        rejected++
                                        continue
                                    }

                                    parsed++

                                    lastAngle =
                                        value

                                    lastUptime =
                                        SystemClock.uptimeMillis() -
                                            age.coerceAtLeast(
                                                0
                                            )

                                    state =
                                        "receiving"

                                    val parcel =
                                        Parcel.obtain()

                                    try {
                                        parcel.writeInterfaceToken(
                                            ShellProtocol.CALLBACK_TOKEN
                                        )

                                        parcel.writeFloat(
                                            value
                                        )

                                        parcel.writeLong(
                                            lastUptime
                                        )

                                        callback.transact(
                                            ShellProtocol.CB_ANGLE,
                                            parcel,
                                            null,
                                            IBinder.FLAG_ONEWAY,
                                        )
                                    } catch (
                                        e: Exception
                                    ) {
                                        state =
                                            "callback gone: ${e.message}"

                                        break
                                    } finally {
                                        parcel.recycle()
                                    }
                                }
                            }

                            if (!stopped) {
                                state =
                                    "log reader ended"
                            }
                        } catch (
                            e: Exception
                        ) {
                            state =
                                "reader error: $e"
                        } finally {
                            child?.destroy()
                        }
                    },
                    "duo-angle-reader",
                )

            thread.isDaemon =
                true

            thread.start()
        }

        fun stop() {
            stopped =
                true

            process?.destroy()

            state =
                "stopped"
        }

        fun status(): Bundle =
            Bundle().apply {
                putString(
                    "state",
                    state,
                )

                putInt(
                    "lines",
                    lines,
                )

                putInt(
                    "parsed",
                    parsed,
                )

                putInt(
                    "rejected",
                    rejected,
                )

                putFloat(
                    "angle",
                    lastAngle,
                )

                putLong(
                    "last",
                    lastUptime,
                )
            }

        private fun parse(
            line: String,
        ): Float? {
            if (
                !line.contains(
                    "SprWallpaper|FoldInteractive"
                ) ||
                !line.contains(
                    "onCommand:"
                )
            ) {
                return null
            }

            if (
                !(
                    line.contains(
                        "action=$action,"
                    ) ||
                        line.contains(
                            "action[$action]"
                        )
                    )
            ) {
                return null
            }

            if (
                !(
                    line.contains(
                        "isVisible=true"
                    ) ||
                        line.contains(
                            "isVisible[true]"
                        )
                    )
            ) {
                return null
            }

            val match =
                ANGLE.matcher(
                    line
                )

            if (!match.find()) {
                return null
            }

            val value =
                match.group(
                    1
                )?.toFloatOrNull()
                    ?: return null

            return if (
                value in 0f..180f
            ) {
                value
            } else {
                null
            }
        }

        private companion object {
            val ANGLE: Pattern =
                Pattern.compile(
                    "mCurrentAngle(?:=|\\[)([0-9]+(?:\\.[0-9]+)?)"
                )
        }
    }

    private companion object {
        /**
         * Shizuku asks user services to exit with this code.
         */
        const val SHIZUKU_DESTROY =
            16777115

        const val PROBE_OUTPUT_LIMIT =
            16_000

        val FAMILIES =
            listOf(
                "android.window.ScreenCaptureInternal",
                "android.window.ScreenCapture",
            )
    }
}