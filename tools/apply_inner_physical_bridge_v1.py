#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

MARKER = "INNER_PHYSICAL_BRIDGE_V1"
SHELL_PROTOCOL = "app/src/full/java/com/duoopen/shell/ShellProtocol.kt"
SHIZUKU = "app/src/full/java/com/duoopen/shell/ShizukuBridge.kt"
SHELL = "app/src/full/java/com/duoopen/shell/DuoShellService.kt"
SERVICE = "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"
COORD = "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected one match, found {n}")
    return text.replace(old, new, 1)


def regex_once(text: str, pattern: str, repl: str, label: str) -> str:
    out, n = re.subn(pattern, repl, text, count=1, flags=re.S)
    if n != 1:
        raise RuntimeError(f"{label}: expected one regex match, found {n}")
    return out


def transform_protocol(text: str) -> str:
    if MARKER in text:
        return text
    return replace_once(
        text,
        '''    const val COVER_PANEL_GEN4 = 18

    const val CB_ANGLE = 1
}''',
        '''    const val COVER_PANEL_GEN4 = 18

    // INNER_PHYSICAL_BRIDGE_V1: bounded Fold7 experiment only.
    const val INNER_PHYSICAL_BRIDGE = 19
    const val START_LID_EVENTS = 20
    const val STOP_LID_EVENTS = 21

    const val CB_ANGLE = 1
    const val CB_LID = 2
}''',
        "protocol codes",
    )


def transform_shizuku(text: str) -> str:
    if MARKER in text:
        return text

    text = replace_once(
        text,
        '''    private var angleCallback:
        AngleCallback? = null
''',
        '''    private var angleCallback:
        AngleCallback? = null

    // INNER_PHYSICAL_BRIDGE_V1: use the hardware lid/Hall edge as an
    // infrastructure trigger. It is not hinge geometry authority.
    private class LidCallback(
        private val onLidState: (Boolean, Long) -> Unit,
    ) : Binder() {
        init {
            attachInterface(null, ShellProtocol.CALLBACK_TOKEN)
        }

        override fun onTransact(
            code: Int,
            data: Parcel,
            reply: Parcel?,
            flags: Int,
        ): Boolean {
            if (code != ShellProtocol.CB_LID) {
                return super.onTransact(code, data, reply, flags)
            }
            data.enforceInterface(ShellProtocol.CALLBACK_TOKEN)
            val closed = data.readInt() != 0
            val sourceElapsedNs =
                if (data.dataAvail() >= Long.SIZE_BYTES) {
                    data.readLong()
                } else {
                    SystemClock.elapsedRealtimeNanos()
                }
            onLidState(closed, sourceElapsedNs)
            return true
        }
    }

    private var lidCallback: LidCallback? = null
''',
        "lid callback",
    )

    text = replace_once(
        text,
        '''    fun stopAngles() {
        call(ShellProtocol.STOP_ANGLES)
        angleCallback = null
    }

    fun angleStatus(): Bundle? = call(ShellProtocol.ANGLE_STATUS)
''',
        '''    fun stopAngles() {
        call(ShellProtocol.STOP_ANGLES)
        angleCallback = null
    }

    fun startLidEvents(
        onLidState: (Boolean, Long) -> Unit,
    ): Boolean {
        val cb = LidCallback(onLidState)
        lidCallback = cb
        return call(ShellProtocol.START_LID_EVENTS) { p ->
            p.writeStrongBinder(cb)
        } != null
    }

    fun stopLidEvents() {
        call(ShellProtocol.STOP_LID_EVENTS)
        lidCallback = null
    }

    fun angleStatus(): Bundle? = call(ShellProtocol.ANGLE_STATUS)
''',
        "lid methods",
    )

    text = replace_once(
        text,
        '''    /** Wake the stable physical 1968x2184 Fold7 inner panel. Blocking; call off main. */
    fun wakeInnerDisplay(): Bundle? =
        call(
            ShellProtocol.WAKE_INNER_DISPLAY
        )
''',
        '''    /** Wake the stable physical 1968x2184 Fold7 inner panel. Blocking; call off main. */
    fun wakeInnerDisplay(
        serviceEpoch: Long = -1L,
        openingAttemptSequence: Long = -1L,
    ): Bundle? =
        call(
            ShellProtocol.WAKE_INNER_DISPLAY
        ) { parcel ->
            parcel.writeLong(serviceEpoch)
            parcel.writeLong(openingAttemptSequence)
        }

    fun releaseInnerPhysicalBridge(
        serviceEpoch: Long,
        openingAttemptSequence: Long,
        reason: String,
    ): Bundle? =
        call(ShellProtocol.INNER_PHYSICAL_BRIDGE) { parcel ->
            parcel.writeInt(2)
            parcel.writeLong(serviceEpoch)
            parcel.writeLong(openingAttemptSequence)
            parcel.writeString(reason)
        }

    fun forceReleaseInnerPhysicalBridge(
        reason: String,
    ): Bundle? =
        releaseInnerPhysicalBridge(
            serviceEpoch = -1L,
            openingAttemptSequence = -1L,
            reason = reason,
        )
''',
        "wake bridge API",
    )
    return text


def transform_shell(text: str) -> str:
    if MARKER in text:
        return text

    text = replace_once(
        text,
        '''    private var captureApi: CaptureApi? = null
    private var reader: AngleReader? = null

    private var liveMirror: SurfaceControl? = null
''',
        '''    private var captureApi: CaptureApi? = null
    private var reader: AngleReader? = null
    private var lidReader: LidReader? = null

    private var liveMirror: SurfaceControl? = null
''',
        "lid reader field",
    )

    text = replace_once(
        text,
        '''    @Volatile
    private var cachedInnerPhysicalDisplayId =
        -1L

    init {
''',
        '''    @Volatile
    private var cachedInnerPhysicalDisplayId =
        -1L

    // INNER_PHYSICAL_BRIDGE_V1. This is deliberately isolated from normal
    // logical-display ownership and carries no captured/private pixels.
    private val innerPhysicalBridgeLock = Any()
    private var innerPhysicalBridge: SurfaceControl? = null
    private var innerPhysicalBridgePhysicalId = -1L
    private var innerPhysicalBridgeOwnerServiceEpoch = -1L
    private var innerPhysicalBridgeOwnerAttempt = -1L
    private val innerPhysicalBridgeLayerStack = 0x44554F

    init {
''',
        "bridge fields",
    )

    text = replace_once(
        text,
        '''        if (code == SHIZUKU_DESTROY) {
            reader?.stop()
            runCatching {
''',
        '''        if (code == SHIZUKU_DESTROY) {
            reader?.stop()
            lidReader?.stop()
            runCatching {
                stopInnerPhysicalBridge(
                    serviceEpoch = -1L,
                    openingAttempt = -1L,
                    reason = "shell-destroy",
                )
            }
            runCatching {
''',
        "destroy cleanup",
    )

    text = replace_once(
        text,
        '''            ShellProtocol.ANGLE_STATUS -> {
                out.writeNoException()
                out.writeBundle(reader?.status() ?: Bundle().apply { putString("state", "not started") })
            }
            ShellProtocol.DISPLAY_PROBE -> {
''',
        '''            ShellProtocol.ANGLE_STATUS -> {
                out.writeNoException()
                out.writeBundle(reader?.status() ?: Bundle().apply { putString("state", "not started") })
            }
            ShellProtocol.START_LID_EVENTS -> {
                val callback = data.readStrongBinder()
                    ?: throw IllegalArgumentException("lid callback")
                lidReader?.stop()
                lidReader = LidReader(callback).also { it.start() }
                out.writeNoException()
            }
            ShellProtocol.STOP_LID_EVENTS -> {
                lidReader?.stop()
                lidReader = null
                out.writeNoException()
            }
            ShellProtocol.DISPLAY_PROBE -> {
''',
        "lid transact",
    )

    text = replace_once(
        text,
        '''            ShellProtocol.WAKE_INNER_DISPLAY -> {
                val identity =
                    clearCallingIdentity()

                val result =
                    try {
                        wakeInnerPhysicalDisplay()
''',
        '''            ShellProtocol.WAKE_INNER_DISPLAY -> {
                val requestServiceEpoch =
                    if (data.dataAvail() >= Long.SIZE_BYTES) data.readLong() else -1L
                val requestOpeningAttempt =
                    if (data.dataAvail() >= Long.SIZE_BYTES) data.readLong() else -1L

                val identity =
                    clearCallingIdentity()

                val result =
                    try {
                        wakeInnerPhysicalDisplay(
                            serviceEpoch = requestServiceEpoch,
                            openingAttempt = requestOpeningAttempt,
                        )
''',
        "wake request identity",
    )

    text = replace_once(
        text,
        '''                out.writeNoException()
                out.writeBundle(result)
            }

            ShellProtocol.OPEN_MIRROR_SESSION -> {
''',
        '''                out.writeNoException()
                out.writeBundle(result)
            }

            ShellProtocol.INNER_PHYSICAL_BRIDGE -> {
                val operation = data.readInt()
                val requestServiceEpoch = data.readLong()
                val requestOpeningAttempt = data.readLong()
                val reason = data.readString() ?: "unspecified"
                val identity = clearCallingIdentity()
                val result =
                    try {
                        when (operation) {
                            2 -> stopInnerPhysicalBridge(
                                serviceEpoch = requestServiceEpoch,
                                openingAttempt = requestOpeningAttempt,
                                reason = reason,
                            )
                            3 -> innerPhysicalBridgeStatus("status")
                            else -> Bundle().apply {
                                putBoolean("ok", false)
                                putString("error", "unknown inner bridge operation $operation")
                            }
                        }
                    } catch (t: Throwable) {
                        Bundle().apply {
                            putBoolean("ok", false)
                            putString("error", "${t.javaClass.simpleName}: ${t.message}")
                        }
                    } finally {
                        restoreCallingIdentity(identity)
                    }
                out.writeNoException()
                out.writeBundle(result)
            }

            ShellProtocol.OPEN_MIRROR_SESSION -> {
''',
        "bridge transact",
    )

    helpers = r'''    private data class InnerPhysicalBridgeResult(
        val ok: Boolean,
        val active: Boolean,
        val reused: Boolean,
        val layerStack: Int,
        val error: String? = null,
    )

    private fun innerPhysicalBridgeStatus(
        operation: String,
    ): Bundle =
        synchronized(innerPhysicalBridgeLock) {
            Bundle().apply {
                putBoolean("ok", true)
                putString("operation", operation)
                putBoolean("active", innerPhysicalBridge != null)
                putLong("physicalDisplayId", innerPhysicalBridgePhysicalId)
                putLong("ownerServiceEpoch", innerPhysicalBridgeOwnerServiceEpoch)
                putLong("ownerOpeningAttempt", innerPhysicalBridgeOwnerAttempt)
                putInt("layerStack", innerPhysicalBridgeLayerStack)
            }
        }

    private fun stopInnerPhysicalBridge(
        serviceEpoch: Long,
        openingAttempt: Long,
        reason: String,
    ): Bundle =
        synchronized(innerPhysicalBridgeLock) {
            val force = serviceEpoch < 0L || openingAttempt < 0L
            val ownerMatches =
                serviceEpoch == innerPhysicalBridgeOwnerServiceEpoch &&
                    openingAttempt == innerPhysicalBridgeOwnerAttempt
            if (!force && !ownerMatches) {
                return@synchronized Bundle().apply {
                    putBoolean("ok", false)
                    putBoolean("stale", true)
                    putBoolean("active", innerPhysicalBridge != null)
                    putString("operation", "release-rejected")
                    putString("reason", reason)
                }
            }

            val layer = innerPhysicalBridge
            if (layer != null) {
                runCatching {
                    SurfaceControl.Transaction()
                        .remove(layer)
                        .apply()
                }
                runCatching { layer.release() }
            }
            innerPhysicalBridge = null
            innerPhysicalBridgePhysicalId = -1L
            innerPhysicalBridgeOwnerServiceEpoch = -1L
            innerPhysicalBridgeOwnerAttempt = -1L

            Bundle().apply {
                putBoolean("ok", true)
                putBoolean("active", false)
                putString("operation", "released")
                putString("reason", reason)
            }
        }

    private fun ensureInnerPhysicalBridge(
        physicalId: Long,
        serviceEpoch: Long,
        openingAttempt: Long,
    ): InnerPhysicalBridgeResult =
        synchronized(innerPhysicalBridgeLock) {
            if (
                innerPhysicalBridge != null &&
                innerPhysicalBridgePhysicalId == physicalId &&
                innerPhysicalBridgeOwnerServiceEpoch == serviceEpoch &&
                innerPhysicalBridgeOwnerAttempt == openingAttempt
            ) {
                return@synchronized InnerPhysicalBridgeResult(
                    ok = true,
                    active = true,
                    reused = true,
                    layerStack = innerPhysicalBridgeLayerStack,
                )
            }

            stopInnerPhysicalBridge(
                serviceEpoch = -1L,
                openingAttempt = -1L,
                reason = "superseded",
            )

            if (
                physicalId < 0L ||
                serviceEpoch < 0L ||
                openingAttempt < 0L
            ) {
                return@synchronized InnerPhysicalBridgeResult(
                    ok = false,
                    active = false,
                    reused = false,
                    layerStack = innerPhysicalBridgeLayerStack,
                    error = "missing physical/opening identity",
                )
            }

            runCatching {
                org.lsposed.hiddenapibypass.HiddenApiBypass
                    .addHiddenApiExemptions(
                        "Landroid/view/SurfaceControl;",
                        "Landroid/view/SurfaceControl\\$Builder;",
                        "Landroid/view/SurfaceControl\\$Transaction;",
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

                val builder =
                    SurfaceControl.Builder()
                        .setName("DuoInnerPhysicalBridge")
                builder.javaClass
                    .getDeclaredMethod("setColorLayer")
                    .apply { isAccessible = true }
                    .invoke(builder)
                val layer = builder.build()

                val tx = SurfaceControl.Transaction()
                val txClass = tx.javaClass

                txClass.getDeclaredMethod(
                    "setLayerStack",
                    SurfaceControl::class.java,
                    Integer.TYPE,
                ).apply { isAccessible = true }
                    .invoke(tx, layer, innerPhysicalBridgeLayerStack)

                txClass.getDeclaredMethod(
                    "setColor",
                    SurfaceControl::class.java,
                    FloatArray::class.java,
                ).apply { isAccessible = true }
                    .invoke(
                        tx,
                        layer,
                        floatArrayOf(0.05f, 0.72f, 0.95f),
                    )

                txClass.getDeclaredMethod(
                    "setWindowCrop",
                    SurfaceControl::class.java,
                    Rect::class.java,
                ).apply { isAccessible = true }
                    .invoke(
                        tx,
                        layer,
                        Rect(0, 0, 1968, 2184),
                    )

                tx.setLayer(layer, Int.MAX_VALUE - 64)
                tx.show(layer)

                txClass.getDeclaredMethod(
                    "setDisplayLayerStack",
                    IBinder::class.java,
                    Integer.TYPE,
                ).apply { isAccessible = true }
                    .invoke(
                        tx,
                        token,
                        innerPhysicalBridgeLayerStack,
                    )

                txClass.getDeclaredMethod(
                    "setDisplayProjection",
                    IBinder::class.java,
                    Integer.TYPE,
                    Rect::class.java,
                    Rect::class.java,
                ).apply { isAccessible = true }
                    .invoke(
                        tx,
                        token,
                        0,
                        Rect(0, 0, 1968, 2184),
                        Rect(0, 0, 1968, 2184),
                    )

                tx.apply()

                innerPhysicalBridge = layer
                innerPhysicalBridgePhysicalId = physicalId
                innerPhysicalBridgeOwnerServiceEpoch = serviceEpoch
                innerPhysicalBridgeOwnerAttempt = openingAttempt

                InnerPhysicalBridgeResult(
                    ok = true,
                    active = true,
                    reused = false,
                    layerStack = innerPhysicalBridgeLayerStack,
                )
            }.getOrElse { error ->
                innerPhysicalBridge = null
                innerPhysicalBridgePhysicalId = -1L
                innerPhysicalBridgeOwnerServiceEpoch = -1L
                innerPhysicalBridgeOwnerAttempt = -1L
                InnerPhysicalBridgeResult(
                    ok = false,
                    active = false,
                    reused = false,
                    layerStack = innerPhysicalBridgeLayerStack,
                    error = "${error.javaClass.simpleName}: ${error.message}",
                )
            }
        }

'''

    text = replace_once(
        text,
        '''    private fun wakeInnerPhysicalDisplay(): Bundle {
''',
        helpers + '''    private fun wakeInnerPhysicalDisplay(
        serviceEpoch: Long,
        openingAttempt: Long,
    ): Bundle {
''',
        "bridge helpers and wake signature",
    )

    text = replace_once(
        text,
        '''        val physicalPowerMs =
            SystemClock.elapsedRealtime() - physicalStart

        var logicalId = -1
''',
        '''        val physicalPowerMs =
            SystemClock.elapsedRealtime() - physicalStart

        val bridge =
            if (powered) {
                ensureInnerPhysicalBridge(
                    physicalId = physicalId,
                    serviceEpoch = serviceEpoch,
                    openingAttempt = openingAttempt,
                )
            } else {
                InnerPhysicalBridgeResult(
                    ok = false,
                    active = false,
                    reused = false,
                    layerStack = innerPhysicalBridgeLayerStack,
                    error = "physical display did not power",
                )
            }

        var logicalId = -1
''',
        "start bridge after physical wake",
    )

    text = replace_once(
        text,
        '''            putBoolean("physicalPowered", powered)
            putLong("physicalPowerMs", physicalPowerMs)
            putInt("routeProbeCount", routeProbeCount)
''',
        '''            putBoolean("physicalPowered", powered)
            putLong("physicalPowerMs", physicalPowerMs)
            putBoolean("physicalBridgeOk", bridge.ok)
            putBoolean("physicalBridgeActive", bridge.active)
            putBoolean("physicalBridgeReused", bridge.reused)
            putInt("physicalBridgeLayerStack", bridge.layerStack)
            if (bridge.error != null) putString("physicalBridgeError", bridge.error)
            putInt("routeProbeCount", routeProbeCount)
''',
        "bridge result telemetry",
    )

    lid_reader = r'''    /**
     * Event-driven hardware lid/Hall reader. Linux input SW_LID is 1 when the
     * magnetic lid condition is closed and 0 when it releases. This signal is
     * used only to begin an opening attempt; it never supplies hinge geometry.
     */
    private class LidReader(
        private val callback: IBinder,
    ) {
        @Volatile
        private var process: java.lang.Process? = null

        @Volatile
        private var stopped = false

        private var lastClosed: Boolean? = null

        private val lidPattern =
            Pattern.compile("\\bSW_LID\\b\\s+([0-9a-fA-F]+)")

        fun start() {
            stopped = false
            Thread {
                runCatching {
                    val p =
                        ProcessBuilder(
                            "/system/bin/getevent",
                            "-ql",
                        )
                            .redirectErrorStream(true)
                            .start()
                    process = p
                    BufferedReader(
                        InputStreamReader(
                            p.inputStream
                        )
                    ).use { input ->
                        while (!stopped) {
                            val line =
                                input.readLine()
                                    ?: break
                            val matcher =
                                lidPattern.matcher(
                                    line
                                )
                            if (!matcher.find()) {
                                continue
                            }
                            val raw =
                                matcher.group(1)
                                    ?.toLongOrNull(16)
                                    ?: continue
                            val closed =
                                raw != 0L
                            if (lastClosed == closed) {
                                continue
                            }
                            lastClosed = closed
                            send(
                                closed = closed,
                                sourceElapsedNs =
                                    SystemClock.elapsedRealtimeNanos(),
                            )
                        }
                    }
                }
                process = null
            }.apply {
                name = "duo-lid-reader"
                isDaemon = true
                start()
            }
        }

        fun stop() {
            stopped = true
            runCatching {
                process?.destroy()
            }
            process = null
        }

        private fun send(
            closed: Boolean,
            sourceElapsedNs: Long,
        ) {
            val parcel = Parcel.obtain()
            try {
                parcel.writeInterfaceToken(
                    ShellProtocol.CALLBACK_TOKEN
                )
                parcel.writeInt(
                    if (closed) 1 else 0
                )
                parcel.writeLong(
                    sourceElapsedNs
                )
                callback.transact(
                    ShellProtocol.CB_LID,
                    parcel,
                    null,
                    IBinder.FLAG_ONEWAY,
                )
            } finally {
                parcel.recycle()
            }
        }
    }

'''
    text = replace_once(
        text,
        '''    private class AngleReader(
''',
        lid_reader + '''    private class AngleReader(
''',
        "lid reader class",
    )
    return text


def transform_service(text: str) -> str:
    if MARKER in text:
        return text

    text = replace_once(
        text,
        '''    private var angleFeed: WallpaperAngleFeed? = null

    private var deviceStateObserver:
''',
        '''    private var angleFeed: WallpaperAngleFeed? = null

    // INNER_PHYSICAL_BRIDGE_V1: SW_LID is an opening-edge trigger only.
    // Measured/FoldInteractive angle remains geometry authority.
    private var lidEventsStarted = false

    private var deviceStateObserver:
''',
        "service lid field",
    )

    helper = r'''    private fun handleEarlyOpeningEdge(
        reason: String,
    ) {
        DuoDiagnostics.event(
            "early-wake",
            "opening edge reason=$reason " +
                "continuity=${continuity.state} " +
                "precise=${hinge.lastAngle}",
        )

        angleFeed
            ?.kickBurst(reason)

        val beforeOpeningState =
            continuity.state

        continuity
            .onEarlyOpeningEdge(reason)

        if (
            beforeOpeningState ==
                Fold7ContinuityController.State.NATIVE_COVER &&
            continuity.state ==
                Fold7ContinuityController.State.OPENING_FROM_CLOSED
        ) {
            gen3Visual.beginOpening(
                generation = continuity.generation,
                reason = reason,
            )
        }

        reconcileContinuityCoverRendering(
            "early-opening:$reason"
        )
    }

    private fun startLidEventsIfNeeded() {
        if (lidEventsStarted || !ShizukuBridge.ready) {
            return
        }

        lidEventsStarted =
            ShizukuBridge.startLidEvents {
                    closed,
                    sourceElapsedNs,
                ->
                val arrivalNs =
                    SystemClock.elapsedRealtimeNanos()
                DuoDiagnostics.event(
                    "lid-edge",
                    "closed=$closed sourceNs=$sourceElapsedNs " +
                        "arrivalNs=$arrivalNs lagMs=" +
                        "${(arrivalNs - sourceElapsedNs).coerceAtLeast(0L) / 1_000_000.0}",
                )

                handler.post {
                    if (closed) {
                        scope.launch(Dispatchers.IO) {
                            ShizukuBridge
                                .forceReleaseInnerPhysicalBridge(
                                    "lid-closed"
                                )
                        }
                    } else {
                        handleEarlyOpeningEdge(
                            "lid-switch-open"
                        )
                    }
                }
            }

        DuoDiagnostics.event(
            "lid-edge",
            "reader-started=$lidEventsStarted",
        )
    }

    private fun stopLidEvents() {
        if (!lidEventsStarted) return
        ShizukuBridge.stopLidEvents()
        lidEventsStarted = false
    }

'''
    text = replace_once(
        text,
        '''    override fun onServiceConnected() {
''',
        helper + '''    override fun onServiceConnected() {
''',
        "early edge helper",
    )

    pattern = r'''            \) \{
                    previousStateId,
                    currentStateId,
                ->
                val reason =
                    "device-state:\$previousStateId->\$currentStateId"

                DuoDiagnostics\.event\(
                    "early-wake",
                    "opening edge reason=\$reason " \+
                        "continuity=\$\{continuity\.state\} " \+
                        "precise=\$\{hinge\.lastAngle\}",
                \)

                angleFeed
                    \?\.kickBurst\(
                        reason
                    \)

                val beforeOpeningState =
                    continuity\.state

                continuity
                    \.onEarlyOpeningEdge\(
                        reason
                    \)

                if \(
                    beforeOpeningState ==
                        Fold7ContinuityController\.State\.NATIVE_COVER &&
                    continuity\.state ==
                        Fold7ContinuityController\.State\.OPENING_FROM_CLOSED
                \) \{
                    gen3Visual\.beginOpening\(
                        generation = continuity\.generation,
                        reason = "device-state:\$reason",
                    \)
                \}

                reconcileContinuityCoverRendering\(
                    "early-opening:\$reason"
                \)
            \}\.also \{'''
    repl = '''            ) {
                    previousStateId,
                    currentStateId,
                ->
                handleEarlyOpeningEdge(
                    "device-state:$previousStateId->$currentStateId"
                )
            }.also {'''
    text = regex_once(
        text,
        pattern,
        repl,
        "device state callback extraction",
    )

    text = replace_once(
        text,
        '''                    continuity.onPrivilegedReady()
                    primeCoverRoute(
''',
        '''                    continuity.onPrivilegedReady()
                    startLidEventsIfNeeded()
                    primeCoverRoute(
''',
        "start lid when privileged",
    )

    text = replace_once(
        text,
        '''                } else {
                    setEarlyOpeningVisualLatched(
''',
        '''                } else {
                    stopLidEvents()
                    setEarlyOpeningVisualLatched(
''',
        "stop lid when unavailable",
    )

    text = replace_once(
        text,
        '''        deviceStateObserver
            ?.stop()
''',
        '''        stopLidEvents()

        deviceStateObserver
            ?.stop()
''',
        "destroy lid cleanup",
    )

    return text


def transform_coordinator(text: str) -> str:
    if MARKER in text:
        return text
    if "INNER_WAKE_PROBE_V1" not in text:
        raise RuntimeError("inner wake probe v1 must be applied before bridge v1")

    text = replace_once(
        text,
        '''                    ShizukuBridge.wakeInnerDisplay()
''',
        '''                    ShizukuBridge.wakeInnerDisplay(
                        serviceEpoch = openingKey.serviceEpoch,
                        openingAttemptSequence =
                            openingKey.openingAttemptSequence,
                    )
''',
        "pass opening identity to shell",
    )

    text = replace_once(
        text,
        '''                if (topologyNow.innerActive) {
                    openingWakeGate.complete(openingKey)
''',
        '''                if (topologyNow.innerActive) {
                    scope.launch(Dispatchers.IO) {
                        ShizukuBridge.releaseInnerPhysicalBridge(
                            serviceEpoch = openingKey.serviceEpoch,
                            openingAttemptSequence =
                                openingKey.openingAttemptSequence,
                            reason = "topology-inner-active",
                        )
                    }
                    openingWakeGate.complete(openingKey)
''',
        "release bridge on topology ready",
    )

    text = replace_once(
        text,
        '''    fun release(reason: String) {
        openingWakeGate.invalidate()
        armRequested = false
''',
        '''    fun release(reason: String) {
        scope.launch(Dispatchers.IO) {
            ShizukuBridge.forceReleaseInnerPhysicalBridge(
                "continuity-release:$reason"
            )
        }
        openingWakeGate.invalidate()
        armRequested = false
''',
        "release bridge on continuity release",
    )

    text = replace_once(
        text,
        '''    fun destroy() {
        openingWakeGate.invalidate()
        destroyed = true
''',
        '''    fun destroy() {
        scope.launch(Dispatchers.IO) {
            ShizukuBridge.forceReleaseInnerPhysicalBridge(
                "continuity-destroy"
            )
        }
        openingWakeGate.invalidate()
        destroyed = true
''',
        "release bridge on destroy",
    )

    text = replace_once(
        text,
        '''    fun onPrivilegedUnavailable() {
        openingWakeGate.invalidate()
        val previousState =
''',
        '''    fun onPrivilegedUnavailable() {
        scope.launch(Dispatchers.IO) {
            ShizukuBridge.forceReleaseInnerPhysicalBridge(
                "privileged-unavailable"
            )
        }
        openingWakeGate.invalidate()
        val previousState =
''',
        "release bridge on privilege loss",
    )
    return text


def apply(repo: Path, check: bool) -> None:
    paths = {
        SHELL_PROTOCOL: transform_protocol,
        SHIZUKU: transform_shizuku,
        SHELL: transform_shell,
        SERVICE: transform_service,
        COORD: transform_coordinator,
    }
    changed = {}
    for rel, fn in paths.items():
        path = repo / rel
        if not path.exists():
            raise RuntimeError(f"missing {rel}")
        before = path.read_text(encoding="utf-8")
        after = fn(before)
        changed[rel] = after
        if not check:
            path.write_text(after, encoding="utf-8")

    required = {
        SHELL_PROTOCOL: "START_LID_EVENTS",
        SHIZUKU: "forceReleaseInnerPhysicalBridge",
        SHELL: "DuoInnerPhysicalBridge",
        SERVICE: "lid-switch-open",
        COORD: "topology-inner-active",
    }
    for rel, needle in required.items():
        if needle not in changed[rel]:
            raise RuntimeError(f"{rel}: required marker {needle!r} missing")


def self_test() -> None:
    seq = [1, 1, 0, 0, 1]
    changed = []
    last = None
    for raw in seq:
        closed = raw != 0
        if closed != last:
            changed.append(closed)
            last = closed
    assert changed == [True, False, True]
    assert [not x for x in changed].count(True) == 1

    active = (7, 11)
    assert active == (7, 11)
    retry = (7, 11)
    assert retry == active
    active = (7, 12)
    stale_release = (7, 11)
    assert stale_release != active
    print("inner physical bridge v1 model: PASS")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=".")
    p.add_argument("--check", action="store_true")
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if args.self_test:
        self_test()
    if not args.self_test or args.check:
        apply(Path(args.repo).resolve(), args.check)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
