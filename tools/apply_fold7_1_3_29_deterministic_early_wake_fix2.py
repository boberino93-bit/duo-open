#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = ROOT / path
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"{label}: expected exactly one anchor in {path}, found {count}"
        )
    p.write_text(text.replace(old, new, 1))
    print(f"patched {label}: {path}")

GRADLE = "app/build.gradle.kts"
PANEL = "app/src/full/java/com/duoopen/overlay/PanelEngine.kt"
CTRL = "app/src/full/java/com/duoopen/overlay/Fold7ContinuityController.kt"
COORD = "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"
SERVICE = "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"
FEED = "app/src/full/java/com/duoopen/shell/WallpaperAngleFeed.kt"
HOST = "app/src/full/java/com/duoopen/overlay/DisplayMirrorHost.kt"
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
     * Other device geometries keep the existing live-blur option.
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

    /** Live blur is intentionally disabled on Fold7. */
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
    HOST,
    '''import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.Rect
''',
    '''import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.Rect
''',
    "frozen host graphics imports",
)

replace_once(
    HOST,
    '''    private val mirrorLeaseId: Long,
    private val nextMirrorSequence: () -> Long,
    private val onStatus: (String) -> Unit,
''',
    '''    private val mirrorLeaseId: Long,
    private val nextMirrorSequence: () -> Long,
    private val frozenFrameProvider: () -> Bitmap?,
    private val onStatus: (String) -> Unit,
''',
    "frozen frame provider",
)

replace_once(
    HOST,
    '''    private var lastLoggedAngleBucket = Int.MIN_VALUE
    private var lastLoggedDirection = ""

    private val hostView =
''',
    '''    private var lastLoggedAngleBucket = Int.MIN_VALUE
    private var lastLoggedDirection = ""

    /**
     * Snapshot path for Fold7 continuity.
     *
     * The bitmap is normally owned by SnapshotCache, so this host never
     * recycles it. The reference is dropped on detach.
     */
    private var frozenFrame: Bitmap? = null

    private val frozenPaint =
        Paint(
            Paint.ANTI_ALIAS_FLAG or
                Paint.FILTER_BITMAP_FLAG
        )

    private val frozenPaneView =
        object : View(context) {
            override fun onDraw(
                canvas: Canvas,
            ) {
                drawFrozenFrame(
                    canvas
                )
            }
        }.apply {
            visibility =
                View.GONE
            importantForAccessibility =
                View.IMPORTANT_FOR_ACCESSIBILITY_NO
        }

    private val hostView =
''',
    "frozen host fields",
)

replace_once(
    HOST,
    '''            importantForAccessibility =
                View.IMPORTANT_FOR_ACCESSIBILITY_NO

            addOnAttachStateChangeListener(
''',
    '''            importantForAccessibility =
                View.IMPORTANT_FOR_ACCESSIBILITY_NO

            addView(
                frozenPaneView,
                FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.MATCH_PARENT,
                    FrameLayout.LayoutParams.MATCH_PARENT,
                ),
            )

            addOnAttachStateChangeListener(
''',
    "attach frozen pane view",
)

replace_once(
    HOST,
    '''                        generation++
                        mirrorSourceKey = null
                        releaseAppMirror()

                        com.duoopen.debug.DuoDiagnostics.event(
''',
    '''                        generation++
                        mirrorSourceKey = null
                        clearFrozenFrame()
                        releaseAppMirror()

                        com.duoopen.debug.DuoDiagnostics.event(
''',
    "clear frozen frame on window detach",
)

replace_once(
    HOST,
    '''    private fun findInnerDisplay(): Display? =
''',
    '''    /**
     * Draw the same canonical left-pane crop used by setGeometry:
     * 1968x2184 inner -> left 984px pane -> crop outer edge to 936x2184,
     * which is exactly the cover's 3:7 aspect ratio.
     */
    private fun drawFrozenFrame(
        canvas: Canvas,
    ) {
        val bitmap =
            frozenFrame
                ?.takeIf {
                    !it.isRecycled
                }
                ?: return

        val destinationWidth =
            frozenPaneView.width

        val destinationHeight =
            frozenPaneView.height

        if (
            destinationWidth <= 0 ||
            destinationHeight <= 0
        ) {
            return
        }

        val paneWidth =
            (bitmap.width / 2)
                .coerceAtLeast(1)

        val paneHeight =
            bitmap.height
                .coerceAtLeast(1)

        val canonicalPaneWidth =
            (
                paneHeight.toLong() *
                    destinationWidth.toLong() /
                    destinationHeight.toLong()
                )
                .toInt()
                .coerceIn(
                    1,
                    paneWidth,
                )

        val sourceLeft =
            paneWidth -
                canonicalPaneWidth

        val sourceRect =
            Rect(
                sourceLeft,
                0,
                paneWidth,
                paneHeight,
            )

        val destinationRect =
            Rect(
                0,
                0,
                destinationWidth,
                destinationHeight,
            )

        canvas.drawBitmap(
            bitmap,
            sourceRect,
            destinationRect,
            frozenPaint,
        )
    }

    private fun clearFrozenFrame() {
        frozenFrame =
            null

        frozenPaneView.visibility =
            View.GONE

        frozenPaneView.invalidate()
    }

    private fun tryBindFrozenFrame(
        sourceKey: String,
        sourceWidth: Int,
        sourceHeight: Int,
        reason: String,
    ): Boolean {
        val candidate =
            runCatching {
                frozenFrameProvider()
            }.getOrNull()
                ?: return false

        if (
            candidate.isRecycled ||
            candidate.width !=
                sourceWidth ||
            candidate.height !=
                sourceHeight
        ) {
            com.duoopen.debug.DuoDiagnostics.event(
                "snapshot-transition",
                "continuity frame rejected reason=$reason " +
                    "expected=${sourceWidth}x$sourceHeight " +
                    "actual=${candidate.width}x${candidate.height} " +
                    "recycled=${candidate.isRecycled}",
            )
            return false
        }

        if (appMirror != null) {
            requestShellStop(
                "promote-frozen:$reason"
            )
            releaseAppMirror()
        }

        frozenFrame =
            candidate

        mirrorSourceKey =
            sourceKey

        frozenPaneView.visibility =
            View.VISIBLE

        frozenPaneView.invalidate()

        onStatus(
            "FROZEN LEFT PANE: inner snapshot → cover $displayId."
        )

        com.duoopen.debug.DuoDiagnostics.event(
            "snapshot-transition",
            "continuity frozen frame bound reason=$reason " +
                "source=${candidate.width}x${candidate.height} " +
                "destination=$displayId hinge=$latestHingeAngle",
        )

        return true
    }

    private fun findInnerDisplay(): Display? =
''',
    "frozen frame drawing and binding",
)

replace_once(
    HOST,
    '''        val sourceKey =
            "inner=${source.displayId}:${sourceWidth}x$sourceHeight;" +
                "cover=$displayId"

        val current = appMirror
''',
    '''        val sourceKey =
            "inner=${source.displayId}:${sourceWidth}x$sourceHeight;" +
                "cover=$displayId"

        val existingFrozen =
            frozenFrame

        if (
            mirrorSourceKey ==
                sourceKey &&
            existingFrozen != null &&
            !existingFrozen.isRecycled
        ) {
            frozenPaneView.invalidate()
            return
        }

        if (
            frozenFrame != null &&
            mirrorSourceKey !=
                sourceKey
        ) {
            clearFrozenFrame()
        }

        /*
         * Deterministic Fold7 path. The snapshot was captured by PanelEngine
         * near the start of hinge travel, before Samsung can continue mutating
         * the live inner composition underneath a stationary fold.
         *
         * If no fresh snapshot exists, retain the old live mirror path as a
         * compatibility fallback (secure-content/capture failure).
         */
        if (
            tryBindFrozenFrame(
                sourceKey = sourceKey,
                sourceWidth = sourceWidth,
                sourceHeight = sourceHeight,
                reason = reason,
            )
        ) {
            return
        }

        com.duoopen.debug.DuoDiagnostics.event(
            "snapshot-transition",
            "continuity frozen frame unavailable; " +
                "falling back to live mirror reason=$reason",
        )

        val current = appMirror
''',
    "prefer frozen continuity frame",
)

replace_once(
    HOST,
    '''                releaseAppMirror()
                appMirror = mirror
                mirrorSourceKey = sourceKey
''',
    '''                clearFrozenFrame()
                releaseAppMirror()
                appMirror = mirror
                mirrorSourceKey = sourceKey
''',
    "clear frozen frame before live fallback",
)

replace_once(
    HOST,
    '''        requestShellStop("host-detach")
        generation++
        mirrorSourceKey = null
        releaseAppMirror()
''',
    '''        requestShellStop("host-detach")
        generation++
        mirrorSourceKey = null
        clearFrozenFrame()
        releaseAppMirror()
''',
    "clear frozen frame on host detach",
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
     * DeviceStateManager can report fully-closed -> not-fully-closed before
     * Samsung's precise wallpaper angle resumes. This may wake the physical
     * inner panel, but never supplies visual geometry.
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
    '''    private val scope: CoroutineScope,
    private val currentHingeAngle: () -> Float,
    private val onStatus: (String) -> Unit,
''',
    '''    private val scope: CoroutineScope,
    private val currentHingeAngle: () -> Float,
    private val frozenInnerFrame: () -> android.graphics.Bitmap?,
    private val onStatus: (String) -> Unit,
''',
    "coordinator frozen frame provider",
)

replace_once(
    COORD,
    '''    fun onTopologyChanged(reason: String) {
''',
    '''    /**
     * Wake-only ingress from DeviceStateManager.
     *
     * The controller refuses this unless native cover ownership is currently
     * confirmed. No synthetic hinge value is generated.
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
    COORD,
    '''                    mirrorLeaseId = mirrorLeaseCounter.incrementAndGet(),
                    nextMirrorSequence = { mirrorSequence.incrementAndGet() },
                    onStatus = onStatus,
''',
    '''                    mirrorLeaseId = mirrorLeaseCounter.incrementAndGet(),
                    nextMirrorSequence = { mirrorSequence.incrementAndGet() },
                    frozenFrameProvider = frozenInnerFrame,
                    onStatus = onStatus,
''',
    "wire frozen frame into continuity host",
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
     * Device-state edges accelerate acquisition only. Force the adaptive
     * poller into its 8 ms burst and request a wallpaper sample immediately.
     */
    fun kickPreciseBurst(
        reason: String,
    ) {
        if (!running) return

        lastAngleChangeUptime =
            SystemClock.uptimeMillis()

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
 * Samsung state identifiers remain opaque. The first choice is Android's
 * semantic physical fold posture properties:
 *
 * - FOLD_IN_CLOSED
 * - FOLD_IN_HALF_OPEN
 * - FOLD_IN_OPEN
 *
 * If those properties are unavailable, a state id is learned as "folded"
 * only from independently confirmed native-cover topology + precise <=12°.
 *
 * Device state is infrastructure input only. It never becomes hinge geometry.
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

                val callbackClass =
                    Class.forName(
                        "android.hardware.devicestate.DeviceStateManager\$DeviceStateCallback"
                    )

                val localCallback =
                    Proxy.newProxyInstance(
                        context.classLoader,
                        arrayOf(
                            callbackClass
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

                unregister
                    ?.apply {
                        isAccessible =
                            true
                    }
                    ?.invoke(
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
    }

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

        val physicalClosed =
            physicalClosedProperty(
                rawState
            )

        val outerPrimary =
            hasNamedProperty(
                rawState,
                "PROPERTY_FOLDABLE_DISPLAY_CONFIGURATION_OUTER_PRIMARY",
            )

        val inferredFolded =
            when {
                physicalClosed != null ->
                    physicalClosed

                id in learnedFoldedStateIds ->
                    true

                previousId != null &&
                    previousId in learnedFoldedStateIds &&
                    id != previousId ->
                    false

                outerPrimary == true ->
                    true

                else ->
                    null
            }

        lastStateId =
            id

        if (
            inferredFolded != null
        ) {
            lastFolded =
                inferredFolded
        }

        val source =
            when {
                physicalClosed != null ->
                    "physical-posture"
                id in learnedFoldedStateIds ->
                    "learned-folded-id"
                previousId != null &&
                    previousId in learnedFoldedStateIds &&
                    id != previousId ->
                    "learned-opening-edge"
                outerPrimary == true ->
                    "outer-primary"
                else ->
                    "unknown"
            }

        DuoDiagnostics.event(
            "early-wake",
            "device-state previous=$previousId current=$id " +
                "folded=$inferredFolded source=$source",
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

    private fun physicalClosedProperty(
        rawState: Any?,
    ): Boolean? {
        val closed =
            hasNamedProperty(
                rawState,
                "PROPERTY_FOLDABLE_HARDWARE_CONFIGURATION_FOLD_IN_CLOSED",
            )

        val halfOpen =
            hasNamedProperty(
                rawState,
                "PROPERTY_FOLDABLE_HARDWARE_CONFIGURATION_FOLD_IN_HALF_OPEN",
            )

        val open =
            hasNamedProperty(
                rawState,
                "PROPERTY_FOLDABLE_HARDWARE_CONFIGURATION_FOLD_IN_OPEN",
            )

        return when {
            closed == true ->
                true
            halfOpen == true ||
                open == true ->
                false
            else ->
                null
        }
    }

    private fun hasNamedProperty(
        rawState: Any?,
        fieldName: String,
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
                        fieldName
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
    '''            scope = scope,
            currentHingeAngle = { hinge.lastAngle },
            onStatus = { message -> _secondaryDisplayStatus.value = message },
''',
    '''            scope = scope,
            currentHingeAngle = { hinge.lastAngle },
            frozenInnerFrame = {
                val age =
                    snapshots.ageMs(
                        true
                    )

                if (
                    age != null &&
                    age <=
                        FOLD7_FROZEN_FRAME_MAX_AGE_MS
                ) {
                    snapshots.get(
                        innerPanel = true,
                        width = 1968,
                        height = 2184,
                    )
                } else {
                    null
                }
            },
            onStatus = { message -> _secondaryDisplayStatus.value = message },
''',
    "service cached inner frame provider",
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
    '''        /** How old a panel's last picture may be and still bridge the next fold. */
        private const val SNAPSHOT_MAX_AGE_MS = 15 * 60_000L
''',
    '''        /** How old a panel's last picture may be and still bridge the next fold. */
        private const val SNAPSHOT_MAX_AGE_MS = 15 * 60_000L

        /**
         * Continuity may reuse only a snapshot taken near the current physical
         * fold. This avoids showing a minutes-old app state on the cover.
         */
        private const val FOLD7_FROZEN_FRAME_MAX_AGE_MS =
            10_000L
''',
    "frozen frame freshness bound",
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

checks = {
    GRADLE: [
        'versionCode = 34',
        'versionName = "1.3.29-zfold7-deterministic-early-wake"',
    ],
    PANEL: [
        'private fun deterministicFrozenFrameMode(): Boolean',
        '"snapshot-transition"',
        'live recapture suppressed',
    ],
    HOST: [
        'private val frozenFrameProvider: () -> Bitmap?',
        'private fun drawFrozenFrame(',
        'private fun tryBindFrozenFrame(',
        'continuity frozen frame bound',
        'falling back to live mirror',
    ],
    CTRL: [
        'fun onEarlyOpeningEdge(',
        'reason = "device-state-opening-edge"',
    ],
    COORD: [
        'private val frozenInnerFrame: () -> android.graphics.Bitmap?',
        'frozenFrameProvider = frozenInnerFrame',
        'fun onEarlyOpeningEdge(',
    ],
    FEED: [
        'fun kickPreciseBurst(',
        'precise-burst reason=$reason',
    ],
    SERVICE: [
        'Fold7DeviceStateObserver(',
        'frozenInnerFrame = {',
        'FOLD7_FROZEN_FRAME_MAX_AGE_MS',
        'kickPreciseBurst(',
        'service-lifecycle',
    ],
    TEST: [
        'fun deviceStateOpeningEdgeWakesBeforePreciseAngle()',
        'fun deviceStateOpeningEdgeIsIgnoredWhenNotNativeCover()',
    ],
    OBSERVER: [
        'PROPERTY_FOLDABLE_HARDWARE_CONFIGURATION_FOLD_IN_CLOSED',
        'PROPERTY_FOLDABLE_HARDWARE_CONFIGURATION_FOLD_IN_HALF_OPEN',
        'PROPERTY_FOLDABLE_HARDWARE_CONFIGURATION_FOLD_IN_OPEN',
        'PROPERTY_FOLDABLE_DISPLAY_CONFIGURATION_OUTER_PRIMARY',
        'learnedFoldedStateIds',
    ],
}

for path, needles in checks.items():
    text = (ROOT / path).read_text()
    for needle in needles:
        if needle not in text:
            raise SystemExit(
                f"{path}: missing postcondition {needle!r}"
            )

print("Fold7 1.3.29 Fix 2 deterministic-frame + early-wake patch complete.")
