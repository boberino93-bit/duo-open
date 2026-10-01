#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = ROOT / path
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor in {path}, found {count}")
    p.write_text(text.replace(old, new, 1))
    print(f"patched {label}: {path}")

GRADLE = "app/build.gradle.kts"
PANEL = "app/src/full/java/com/duoopen/overlay/PanelEngine.kt"
CTRL = "app/src/full/java/com/duoopen/overlay/Fold7ContinuityController.kt"
COORD = "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"
SERVICE = "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"
FEED = "app/src/full/java/com/duoopen/shell/WallpaperAngleFeed.kt"
TEST = "app/src/test/java/com/duoopen/overlay/Fold7ContinuityControllerTest.kt"
OBSERVER = "app/src/full/java/com/duoopen/overlay/Fold7DeviceStateObserver.kt"

replace_once(
    GRADLE,
    '''        versionCode = 33
        versionName = "1.3.28-zfold7-cover-hold-fix"
''',
    '''        versionCode = 34
        versionName = "1.3.29-zfold7-deterministic-early-wake"
''',
    "version 1.3.29",
)

replace_once(
    PANEL,
    '''    /** Live blur needs no capture: the system blurs whatever is on screen. */
    private fun liveMode(): Boolean =
        DuoSettings.config.value.liveBlur &&
            runCatching { windowManager.isCrossWindowBlurEnabled }.getOrDefault(false)
''',
    '''    /**
     * Fold7 transitions must be deterministic: once a transition frame is
     * captured, changing app/system pixels underneath it must not change what
     * the user sees while the hinge is stationary.
     *
     * Other devices keep their existing live-blur option.
     */
    private fun deterministicFrozenFrameMode(): Boolean {
        val mode =
            runCatching {
                display.mode
            }.getOrNull()
                ?: return false

        return (
            mode.physicalWidth == 1968 &&
                mode.physicalHeight == 2184
            ) ||
            (
                mode.physicalWidth == 1080 &&
                    mode.physicalHeight == 2520
                )
    }

    /** Live blur needs no capture, but is intentionally disabled on Fold7. */
    private fun liveMode(): Boolean =
        !deterministicFrozenFrameMode() &&
            DuoSettings.config.value.liveBlur &&
            runCatching { windowManager.isCrossWindowBlurEnabled }.getOrDefault(false)
''',
    "Fold7 deterministic frame mode",
)

replace_once(
    PANEL,
    '''        if (bitmap != null && shellCapture()) startLiveLoop()
        phase = Phase.SHOWING
''',
    '''        if (
            bitmap != null &&
            shellCapture()
        ) {
            if (
                deterministicFrozenFrameMode()
            ) {
                com.duoopen.debug.DuoDiagnostics.event(
                    "snapshot-transition",
                    "frozen frame display=$displayId inner=$innerPanel " +
                        "size=${bitmap.width}x${bitmap.height}; live recapture suppressed",
                )
            } else {
                startLiveLoop()
            }
        }
        phase = Phase.SHOWING
''',
    "suppress Fold7 live recapture",
)

replace_once(
    CTRL,
    '''    fun onHinge(
        angle: Float,
        nowMs: Long,
        topology: Topology,
    ): Decision =
        reduce(
            angle = angle,
            nowMs = nowMs,
            topology = topology,
            sampleMotion = true,
        )

    fun onPrewarmResult(
''',
    '''    fun onHinge(
        angle: Float,
        nowMs: Long,
        topology: Topology,
    ): Decision =
        reduce(
            angle = angle,
            nowMs = nowMs,
            topology = topology,
            sampleMotion = true,
        )

    /**
     * Infrastructure-only opening edge.
     *
     * DeviceStateManager can report folded -> unfolding before Samsung's
     * precise wallpaper angle resumes. This edge may wake the physical inner
     * panel, but it NEVER changes visual geometry: [lastAngle] remains the
     * last precise angle and all rendering still waits for normal angle input.
     */
    fun onEarlyOpeningEdge(
        nowMs: Long,
        topology: Topology,
    ): Decision {
        if (
            state != State.NATIVE_COVER ||
            !topology.nativeCover
        ) {
            return decision()
        }

        direction =
            Direction.OPENING

        lastSampleMs =
            nowMs

        val angle =
            lastAngle
                .takeIf {
                    it.isFinite()
                }
                ?: 0f

        transition(
            to = State.OPENING_FROM_CLOSED,
            angle = angle,
            reason = "device-state-opening-edge",
            topology = topology,
        )

        return decision(
            listOf(
                Action.WakeInner(
                    generation
                )
            )
        )
    }

    fun onPrewarmResult(
''',
    "controller early opening edge",
)

replace_once(
    COORD,
    '''    fun onTopologyChanged(reason: String) {
''',
    '''    /**
     * Wake-only ingress from DeviceStateManager.
     *
     * The controller refuses this unless native cover ownership is currently
     * confirmed. It does not synthesize a hinge angle.
     */
    fun onEarlyOpeningEdge(
        reason: String,
    ) {
        val decision =
            controller.onEarlyOpeningEdge(
                nowMs =
                    SystemClock.uptimeMillis(),
                topology =
                    topology(),
            )

        if (
            decision.actions.isNotEmpty()
        ) {
            DuoDiagnostics.event(
                "early-wake",
                "accepted reason=$reason generation=${decision.generation} " +
                    "precise=${currentHingeAngle()}",
            )
        } else {
            DuoDiagnostics.event(
                "early-wake",
                "ignored reason=$reason state=${controller.state} " +
                    "precise=${currentHingeAngle()}",
            )
        }

        apply(decision)
    }

    fun onTopologyChanged(reason: String) {
''',
    "coordinator early opening edge",
)

replace_once(
    FEED,
    '''    /** Re-check the anchor after a panel swap. */
    fun onDisplayChanged() {
        if (running) runCatching { ensureAnchor() }
    }

    private fun onAngle(
''',
    '''    /** Re-check the anchor after a panel swap. */
    fun onDisplayChanged() {
        if (running) runCatching { ensureAnchor() }
    }

    /**
     * Device-state edges are allowed to accelerate acquisition, never to
     * provide geometry. Force the adaptive poller into its 8 ms burst and
     * request a wallpaper sample immediately.
     */
    fun kickPreciseBurst(
        reason: String,
    ) {
        if (!running) return

        val now =
            SystemClock.uptimeMillis()

        lastAngleChangeUptime =
            now

        com.duoopen.debug.DuoDiagnostics.event(
            "early-wake",
            "precise-burst reason=$reason pollMs=$ACTIVE_POLL_MS",
        )

        handler.removeCallbacks(
            poll
        )

        handler.post(
            poll
        )
    }

    private fun onAngle(
''',
    "precise angle burst hook",
)

observer_path = ROOT / OBSERVER
if observer_path.exists():
    raise SystemExit(f"{OBSERVER}: already exists")

observer_path.write_text(r'''package com.duoopen.overlay

import android.content.Context
import android.os.Handler
import com.duoopen.debug.DuoDiagnostics
import java.lang.reflect.Proxy
import java.util.LinkedHashSet
import java.util.concurrent.Executor

/**
 * Fold7 wake-only device-state observer.
 *
 * Samsung's state identifiers are intentionally treated as opaque. On modern
 * Android we reflect DeviceState's OUTER_PRIMARY fold property. If that is not
 * available, the currently observed identifier is learned as folded only when
 * the app independently corroborates native-cover topology + a precise <=12°
 * closed-rest angle.
 *
 * A folded -> non-folded edge is infrastructure input only. It never becomes
 * hinge geometry.
 */
internal class Fold7DeviceStateObserver(
    private val context: Context,
    private val handler: Handler,
    private val onOpeningEdge: (
        previousStateId: Int,
        currentStateId: Int,
    ) -> Unit,
) {
    private var manager: Any? = null
    private var callback: Any? = null
    private var callbackClass: Class<*>? = null
    private var started = false

    private var lastStateId: Int? = null
    private var lastFolded: Boolean? = null

    private val learnedFoldedStateIds =
        LinkedHashSet<Int>()

    fun start() {
        if (started) return

        runCatching {
            org.lsposed.hiddenapibypass.HiddenApiBypass
                .addHiddenApiExemptions(
                    "Landroid/hardware/devicestate/"
                )
        }

        val result =
            runCatching {
                val localManager =
                    context.getSystemService(
                        DEVICE_STATE_SERVICE
                    )
                        ?: error(
                            "device_state service unavailable"
                        )

                val localCallbackClass =
                    Class.forName(
                        "android.hardware.devicestate.DeviceStateManager\$DeviceStateCallback"
                    )

                val localCallback =
                    Proxy.newProxyInstance(
                        context.classLoader,
                        arrayOf(
                            localCallbackClass
                        ),
                    ) {
                            proxy,
                            method,
                            args,
                        ->
                        when (
                            method.name
                        ) {
                            "onDeviceStateChanged",
                            "onStateChanged",
                            -> {
                                val raw =
                                    args
                                        ?.firstOrNull()

                                val id =
                                    stateIdentifier(
                                        raw
                                    )

                                if (id != null) {
                                    handleState(
                                        id = id,
                                        rawState = raw,
                                    )
                                }

                                null
                            }

                            "hashCode" ->
                                System.identityHashCode(
                                    proxy
                                )

                            "equals" ->
                                proxy ===
                                    args
                                        ?.firstOrNull()

                            "toString" ->
                                "Fold7DeviceStateObserverCallback"

                            else ->
                                null
                        }
                    }

                val register =
                    localManager
                        .javaClass
                        .methods
                        .firstOrNull {
                            it.name ==
                                "registerCallback" &&
                                it.parameterCount ==
                                    2
                        }
                        ?: error(
                            "registerCallback unavailable"
                        )

                register.isAccessible =
                    true

                val executor =
                    Executor { runnable ->
                        handler.post(
                            runnable
                        )
                    }

                register.invoke(
                    localManager,
                    executor,
                    localCallback,
                )

                manager =
                    localManager

                callback =
                    localCallback

                callbackClass =
                    localCallbackClass

                started =
                    true
            }

        result.onSuccess {
            DuoDiagnostics.event(
                "early-wake",
                "device-state observer registered",
            )
        }.onFailure { error ->
            DuoDiagnostics.event(
                "early-wake",
                "device-state observer unavailable " +
                    "error=${error.javaClass.simpleName}:${error.message}",
            )
        }
    }

    fun stop() {
        if (!started) return

        val localManager =
            manager

        val localCallback =
            callback

        runCatching {
            if (
                localManager != null &&
                localCallback != null
            ) {
                val unregister =
                    localManager
                        .javaClass
                        .methods
                        .firstOrNull {
                            it.name ==
                                "unregisterCallback" &&
                                it.parameterCount ==
                                    1
                        }

                unregister?.apply {
                    isAccessible =
                        true
                }?.invoke(
                    localManager,
                    localCallback,
                )
            }
        }

        started =
            false

        manager =
            null

        callback =
            null

        callbackClass =
            null
    }

    /**
     * Learn an opaque folded identifier only from independently confirmed
     * physical facts. No Samsung state number is ever hardcoded.
     */
    fun corroborateFoldedRest(
        nativeCover: Boolean,
        preciseAngle: Float,
    ) {
        if (
            !nativeCover ||
            !preciseAngle.isFinite() ||
            preciseAngle >
                CLOSED_MAX_DEG
        ) {
            return
        }

        val id =
            lastStateId
                ?: return

        val learned =
            learnedFoldedStateIds
                .add(
                    id
                )

        lastFolded =
            true

        if (learned) {
            DuoDiagnostics.event(
                "early-wake",
                "learned folded device-state id=$id " +
                    "from native-cover precise=$preciseAngle",
            )
        }
    }

    private fun handleState(
        id: Int,
        rawState: Any?,
    ) {
        val previousId =
            lastStateId

        val previousFolded =
            lastFolded

        val propertyFolded =
            foldedFromDeviceStateProperty(
                rawState
            )

        val inferredFolded =
            propertyFolded
                ?: when {
                    id in learnedFoldedStateIds ->
                        true

                    previousId != null &&
                        previousId in
                            learnedFoldedStateIds &&
                        id != previousId ->
                        false

                    else ->
                        null
                }

        lastStateId =
            id

        if (inferredFolded != null) {
            lastFolded =
                inferredFolded
        }

        DuoDiagnostics.event(
            "early-wake",
            "device-state previous=$previousId current=$id " +
                "folded=$inferredFolded source=" +
                (
                    if (propertyFolded != null) {
                        "property"
                    } else {
                        "learned"
                    }
                    ),
        )

        if (
            previousId != null &&
            previousFolded == true &&
            inferredFolded == false
        ) {
            onOpeningEdge(
                previousId,
                id,
            )
        }
    }

    private fun stateIdentifier(
        rawState: Any?,
    ): Int? =
        when (
            rawState
        ) {
            null ->
                null

            is Number ->
                rawState
                    .toInt()

            else ->
                runCatching {
                    (
                        rawState
                            .javaClass
                            .getMethod(
                                "getIdentifier"
                            )
                            .invoke(
                                rawState
                            ) as Number
                        )
                        .toInt()
                }.getOrNull()
        }

    /**
     * Android 15+ DeviceState exposes a semantic fold property. Reflection
     * keeps this source-compatible with older callback shapes.
     */
    private fun foldedFromDeviceStateProperty(
        rawState: Any?,
    ): Boolean? {
        if (
            rawState == null ||
            rawState is Number
        ) {
            return null
        }

        return runCatching {
            val stateClass =
                Class.forName(
                    "android.hardware.devicestate.DeviceState"
                )

            if (
                !stateClass
                    .isInstance(
                        rawState
                    )
            ) {
                return@runCatching null
            }

            val property =
                stateClass
                    .getField(
                        "PROPERTY_FOLDABLE_DISPLAY_CONFIGURATION_OUTER_PRIMARY"
                    )
                    .getInt(
                        null
                    )

            stateClass
                .getMethod(
                    "hasProperty",
                    Integer.TYPE,
                )
                .invoke(
                    rawState,
                    property,
                ) as Boolean
        }.getOrNull()
    }

    private companion object {
        const val DEVICE_STATE_SERVICE =
            "device_state"

        const val CLOSED_MAX_DEG =
            12f
    }
}
''')

replace_once(
    SERVICE,
    '''    private var angleFeed: WallpaperAngleFeed? = null

    private lateinit var continuity: Fold7ContinuityCoordinator
''',
    '''    private var angleFeed: WallpaperAngleFeed? = null

    private var deviceStateObserver:
        Fold7DeviceStateObserver? =
        null

    private lateinit var continuity: Fold7ContinuityCoordinator
''',
    "service device-state field",
)

replace_once(
    SERVICE,
    '''        ShizukuBridge.init(this)
        angleFeed = WallpaperAngleFeed(this, handler, hinge)
        scope.launch {
''',
    '''        ShizukuBridge.init(this)
        angleFeed = WallpaperAngleFeed(this, handler, hinge)

        deviceStateObserver =
            Fold7DeviceStateObserver(
                context = this,
                handler = handler,
            ) {
                    previousStateId,
                    currentStateId,
                ->
                val reason =
                    "device-state:$previousStateId->$currentStateId"

                DuoDiagnostics.event(
                    "early-wake",
                    "opening edge reason=$reason " +
                        "continuity=${continuity.state} " +
                        "precise=${hinge.lastAngle}",
                )

                angleFeed
                    ?.kickPreciseBurst(
                        reason
                    )

                continuity
                    .onEarlyOpeningEdge(
                        reason
                    )
            }.also {
                it.start()
            }

        DuoDiagnostics.event(
            "service-lifecycle",
            "accessibility-connected",
        )

        scope.launch {
''',
    "service start device-state observer",
)

replace_once(
    SERVICE,
    '''    override fun onDestroy() {
        instance = null

        if (::continuity.isInitialized) {
''',
    '''    override fun onDestroy() {
        DuoDiagnostics.event(
            "service-lifecycle",
            "accessibility-destroy begin",
        )

        instance = null

        deviceStateObserver
            ?.stop()

        deviceStateObserver =
            null

        if (::continuity.isInitialized) {
''',
    "service lifecycle and observer stop",
)

replace_once(
    SERVICE,
    '''    private fun onHinge(angle: Float) {
        continuity.onHinge(angle)

        for (engine in engines.values.toList()) {
''',
    '''    private fun onHinge(angle: Float) {
        continuity.onHinge(angle)

        deviceStateObserver
            ?.corroborateFoldedRest(
                nativeCover =
                    continuity.state ==
                        Fold7ContinuityController.State.NATIVE_COVER,
                preciseAngle =
                    angle,
            )

        for (engine in engines.values.toList()) {
''',
    "closed-rest corroboration on hinge",
)

replace_once(
    SERVICE,
    '''        continuity.onTopologyChanged(
            "sync-displays"
        )
    }
''',
    '''        continuity.onTopologyChanged(
            "sync-displays"
        )

        deviceStateObserver
            ?.corroborateFoldedRest(
                nativeCover =
                    continuity.state ==
                        Fold7ContinuityController.State.NATIVE_COVER,
                preciseAngle =
                    hinge.lastAngle,
            )
    }
''',
    "closed-rest corroboration on topology",
)

replace_once(
    SERVICE,
    '''            ShizukuBridge.state.collect { state ->
                syncAngleFeed()

                if (
''',
    '''            ShizukuBridge.state.collect { state ->
                DuoDiagnostics.event(
                    "service-lifecycle",
                    "shizuku-state=${state.javaClass.simpleName}",
                )

                syncAngleFeed()

                if (
''',
    "Shizuku lifecycle telemetry",
)

replace_once(
    TEST,
    '''    @Test
    fun openingFromClosedWakesInnerAtThreeDegrees() {
''',
    '''    @Test
    fun deviceStateOpeningEdgeWakesBeforePreciseAngle() {
        val c =
            Fold7ContinuityController()

        c.reset(
            0f,
            0L,
            closedTopology,
        )

        val edge =
            c.onEarlyOpeningEdge(
                nowMs = 5L,
                topology = closedTopology,
            )

        assertEquals(
            Fold7ContinuityController.State.OPENING_FROM_CLOSED,
            c.state,
        )

        assertEquals(
            1,
            edge.actions.count {
                it is Fold7ContinuityController.Action.WakeInner
            },
        )

        val duplicate =
            c.onEarlyOpeningEdge(
                nowMs = 10L,
                topology = closedTopology,
            )

        assertTrue(
            duplicate.actions.isEmpty()
        )
    }

    @Test
    fun deviceStateOpeningEdgeIsIgnoredWhenNotNativeCover() {
        val c =
            Fold7ContinuityController()

        c.reset(
            179f,
            0L,
            openTopology,
        )

        val edge =
            c.onEarlyOpeningEdge(
                nowMs = 5L,
                topology = openTopology,
            )

        assertEquals(
            Fold7ContinuityController.State.OPEN_INNER,
            c.state,
        )

        assertTrue(
            edge.actions.isEmpty()
        )
    }

    @Test
    fun openingFromClosedWakesInnerAtThreeDegrees() {
''',
    "controller early-edge tests",
)

# Postconditions.
checks = {
    GRADLE: [
        'versionCode = 34',
        'versionName = "1.3.29-zfold7-deterministic-early-wake"',
    ],
    PANEL: [
        'private fun deterministicFrozenFrameMode(): Boolean',
        '"snapshot-transition"',
        '"live recapture suppressed"',
    ],
    CTRL: [
        'fun onEarlyOpeningEdge(',
        'reason = "device-state-opening-edge"',
    ],
    COORD: [
        'fun onEarlyOpeningEdge(',
        '"accepted reason=$reason',
    ],
    FEED: [
        'fun kickPreciseBurst(',
        '"precise-burst reason=$reason',
    ],
    SERVICE: [
        'Fold7DeviceStateObserver(',
        'kickPreciseBurst(',
        'corroborateFoldedRest(',
        '"service-lifecycle"',
    ],
    TEST: [
        'fun deviceStateOpeningEdgeWakesBeforePreciseAngle()',
        'fun deviceStateOpeningEdgeIsIgnoredWhenNotNativeCover()',
    ],
    OBSERVER: [
        'PROPERTY_FOLDABLE_DISPLAY_CONFIGURATION_OUTER_PRIMARY',
        'learnedFoldedStateIds',
        'context.getSystemService(',
    ],
}

for path, needles in checks.items():
    text = (ROOT / path).read_text()
    for needle in needles:
        if needle not in text:
            raise SystemExit(f"{path}: missing postcondition {needle!r}")

print("Fold7 1.3.29 deterministic-frame + early-wake patch complete.")
