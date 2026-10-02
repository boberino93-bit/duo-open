#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path.cwd()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    require(count == 1, f"{label}: expected exactly one marker, found {count}")
    return text.replace(old, new, 1)


def replace_between(text: str, start_marker: str, end_marker: str, new_block: str, label: str) -> str:
    start = text.find(start_marker)
    require(start >= 0, f"{label}: start marker not found")
    end = text.find(end_marker, start)
    require(end >= 0, f"{label}: end marker not found")
    return text[:start] + new_block.rstrip() + "\n\n" + text[end:]


PASSIVE_WALLPAPER = r'''package com.duoopen.wallpaper

import android.graphics.Bitmap
import android.graphics.BitmapShader
import android.graphics.Color
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.Shader
import android.service.wallpaper.WallpaperService
import android.util.Log
import android.view.SurfaceHolder
import com.duoopen.fold.isInnerPanel
import com.duoopen.settings.DuoConfig
import com.duoopen.settings.DuoSettings
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.MainScope
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlin.math.max

/**
 * Passive Fold7 launcher-continuity wallpaper.
 *
 * The wallpaper owns image presentation only. It never owns hinge geometry,
 * panel power, display routing, fold semantics, or transition timing.
 *
 * Both panels sample one canonical 1968x2184 wallpaper plane. The cover maps
 * the exact canonical right pane (x=984..1920, y=0..2184) to 1080x2520.
 * This preserves visual continuity while the Gen6 overlay owns animation.
 */
class DuoWallpaperService : WallpaperService() {

    override fun onCreateEngine(): Engine = DuoEngine()

    private inner class DuoEngine : Engine() {
        private val scope = MainScope()
        private val context = this@DuoWallpaperService
        private val paint = Paint(Paint.FILTER_BITMAP_FLAG)

        private var config: DuoConfig = DuoSettings.config.value
        private var bitmap: Bitmap? = null
        private var bitmapVersion = -1L
        private var imageShader: BitmapShader? = null

        private var surfaceReady = false
        private var width = 0f
        private var height = 0f

        override fun onCreate(surfaceHolder: SurfaceHolder) {
            super.onCreate(surfaceHolder)
            setOffsetNotificationsEnabled(false)

            scope.launch {
                DuoSettings.config.collect { next ->
                    config = next
                    if (next.imageVersion != bitmapVersion) {
                        loadImage(next.imageVersion)
                    } else {
                        rebuildImageShader()
                        draw()
                    }
                }
            }
        }

        override fun onDestroy() {
            scope.cancel()
            super.onDestroy()
        }

        override fun onVisibilityChanged(visible: Boolean) {
            if (visible) draw()
        }

        override fun onSurfaceChanged(
            holder: SurfaceHolder,
            format: Int,
            w: Int,
            h: Int,
        ) {
            super.onSurfaceChanged(holder, format, w, h)
            surfaceReady = true
            width = w.toFloat()
            height = h.toFloat()
            rebuildImageShader()
            draw()
        }

        override fun onSurfaceDestroyed(holder: SurfaceHolder) {
            surfaceReady = false
            imageShader = null
            super.onSurfaceDestroyed(holder)
        }

        private fun isInner(): Boolean =
            displayContext?.display.isInnerPanel()

        private fun loadImage(version: Long) {
            bitmapVersion = version
            scope.launch {
                val loaded =
                    withContext(Dispatchers.IO) {
                        WallpaperImage.load(context, version)
                    }

                if (version != bitmapVersion) {
                    loaded?.takeIf { !it.isRecycled }?.recycle()
                    return@launch
                }

                bitmap
                    ?.takeIf { it !== loaded && !it.isRecycled }
                    ?.recycle()

                bitmap = loaded
                rebuildImageShader()
                draw()
            }
        }

        private fun rebuildImageShader() {
            val bmp = bitmap ?: return
            if (bmp.isRecycled || width <= 0f || height <= 0f) return

            val canonicalScale =
                max(
                    INNER_WIDTH / bmp.width.toFloat(),
                    INNER_HEIGHT / bmp.height.toFloat(),
                )

            val canonicalDx =
                (INNER_WIDTH - bmp.width * canonicalScale) * 0.5f
            val canonicalDy =
                (INNER_HEIGHT - bmp.height * canonicalScale) * 0.5f

            val inner = isInner()
            val canonicalViewportWidth =
                if (inner) INNER_WIDTH else RIGHT_PANE_WIDTH
            val cropLeft =
                if (inner) 0f else RIGHT_PANE_LEFT

            val viewportScale = width / canonicalViewportWidth

            imageShader =
                BitmapShader(
                    bmp,
                    Shader.TileMode.CLAMP,
                    Shader.TileMode.CLAMP,
                ).apply {
                    filterMode = BitmapShader.FILTER_MODE_LINEAR
                    setLocalMatrix(
                        Matrix().apply {
                            setScale(
                                canonicalScale * viewportScale,
                                canonicalScale * viewportScale,
                            )
                            postTranslate(
                                (canonicalDx - cropLeft) * viewportScale,
                                canonicalDy * viewportScale,
                            )
                        }
                    )
                }
        }

        private fun draw() {
            if (!surfaceReady) return

            val canvas =
                try {
                    surfaceHolder.lockHardwareCanvas()
                } catch (error: Exception) {
                    Log.w(TAG, "lockHardwareCanvas failed", error)
                    null
                } ?: return

            try {
                canvas.drawColor(Color.BLACK)
                paint.shader = imageShader
                if (imageShader != null) {
                    canvas.drawRect(0f, 0f, width, height, paint)
                }
            } finally {
                runCatching {
                    surfaceHolder.unlockCanvasAndPost(canvas)
                }
            }
        }
    }

    private companion object {
        const val TAG = "DuoWallpaper"
        const val INNER_WIDTH = 1968f
        const val INNER_HEIGHT = 2184f
        const val RIGHT_PANE_LEFT = 984f
        const val RIGHT_PANE_RIGHT = 1920f
        const val RIGHT_PANE_WIDTH = RIGHT_PANE_RIGHT - RIGHT_PANE_LEFT
    }
}
'''

ANGLE_TEST = r'''package com.duoopen.fold

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7AngleAuthorityTest {
    @Test
    fun coarsePublicRemainsShadowOnlyAfterPreciseExpiry() {
        val a = Fold7AngleAuthority(preciseMaxAgeMs = 192L)
        a.startPreciseSession(7L, 1_000L)
        val p = a.offerPrecise(7L, 1L, 5f, 1_000L, 1_010L)
        assertNotNull(p.output)

        val shadow = a.offerPublic(
            source = Fold7AngleAuthority.Source.PUBLIC_STANDARD,
            angle = 90f,
            observedUptimeMs = 1_050L,
            receivedUptimeMs = 1_050L,
            coarse = true,
        )
        assertNull(shadow.output)

        val expired = a.expirePrecise(1_193L, "lease-expired")
        assertNull(expired.output)
        assertTrue(expired.stateChanged)
        assertEquals("coarse-public-shadow-only", expired.dropReason)
        assertEquals(Fold7AngleAuthority.Source.NONE, a.snapshot(1_193L).source)
        assertEquals(90f, a.snapshot(1_193L).publicShadowAngle)
    }

    @Test
    fun coldStartCoarsePublicNeverOwnsContinuousGeometry() {
        val a = Fold7AngleAuthority()
        val d = a.offerPublic(
            source = Fold7AngleAuthority.Source.PUBLIC_STANDARD,
            angle = 90f,
            observedUptimeMs = 500L,
            receivedUptimeMs = 501L,
            coarse = true,
        )
        assertNull(d.output)
        assertEquals("coarse-public-shadow-only", d.dropReason)
        assertEquals(Fold7AngleAuthority.Source.NONE, a.snapshot(501L).source)
        assertEquals(90f, a.snapshot(501L).publicShadowAngle)
    }

    @Test
    fun delayedPreciseCannotAcquireAuthority() {
        val a = Fold7AngleAuthority(preciseMaxAgeMs = 192L)
        a.startPreciseSession(1L, 0L)
        val d = a.offerPrecise(1L, 1L, 42f, 0L, 193L)
        assertFalse(d.accepted)
        assertEquals("stale-source-age", d.dropReason)
        assertEquals(Fold7AngleAuthority.Source.NONE, a.snapshot(193L).source)
    }

    @Test
    fun oldSessionAndDuplicateSequenceAreRejected() {
        val a = Fold7AngleAuthority()
        a.startPreciseSession(4L, 100L)
        assertTrue(a.offerPrecise(4L, 1L, 10f, 100L, 101L).accepted)
        assertFalse(a.offerPrecise(4L, 1L, 11f, 102L, 103L).accepted)
        a.revokePreciseSession(4L, 104L, "stop")
        a.startPreciseSession(6L, 105L)
        assertFalse(a.offerPrecise(4L, 2L, 12f, 106L, 107L).accepted)
    }

    @Test
    fun syntheticEndpointIsSessionScopedAndDoesNotExtendLease() {
        val a = Fold7AngleAuthority(preciseMaxAgeMs = 192L)
        a.startPreciseSession(2L, 1_000L)
        a.offerPrecise(2L, 1L, 4f, 1_000L, 1_004L)
        val before = a.nextPreciseExpiryUptimeMs()
        val synthetic = a.offerSyntheticEndpoint(2L, 0f, 1_140L, "bridge")
        assertNotNull(synthetic.output)
        assertEquals(before, a.nextPreciseExpiryUptimeMs())
        a.revokePreciseSession(2L, 1_150L, "stop")
        assertFalse(a.offerSyntheticEndpoint(2L, 180f, 1_151L, "old").accepted)
    }

    @Test
    fun finePublicStillOwnsWhenNoPreciseLeaseExists() {
        val a = Fold7AngleAuthority()
        val d = a.offerPublic(
            source = Fold7AngleAuthority.Source.PUBLIC_VENDOR,
            angle = 88f,
            observedUptimeMs = 500L,
            receivedUptimeMs = 501L,
            coarse = false,
        )
        assertEquals(88f, d.output!!.angle)
        assertEquals(Fold7AngleAuthority.Source.PUBLIC_VENDOR, d.output!!.source)
    }

    @Test
    fun preciseReacquiresImmediatelyAfterCoarseShadow() {
        val a = Fold7AngleAuthority(preciseMaxAgeMs = 192L)
        a.startPreciseSession(10L, 1_000L)
        a.offerPrecise(10L, 1L, 5f, 1_000L, 1_005L)
        a.offerPublic(
            source = Fold7AngleAuthority.Source.PUBLIC_STANDARD,
            angle = 90f,
            observedUptimeMs = 1_100L,
            receivedUptimeMs = 1_100L,
            coarse = true,
        )
        a.expirePrecise(1_193L, "lease-expired")
        val reacquired = a.offerPrecise(
            session = 10L,
            sequence = 2L,
            angle = 84f,
            observedUptimeMs = 1_194L,
            receivedUptimeMs = 1_195L,
        )
        assertEquals(84f, reacquired.output!!.angle)
        assertEquals(Fold7AngleAuthority.Source.SAMSUNG_PRECISE, reacquired.output!!.source)
    }

    @Test
    fun preciseExpiryWithoutFallbackBecomesUnknown() {
        val a = Fold7AngleAuthority(preciseMaxAgeMs = 192L)
        a.startPreciseSession(9L, 1_000L)
        a.offerPrecise(9L, 1L, 44f, 1_000L, 1_010L)
        val expired = a.expirePrecise(1_193L, "lease-expired")
        assertNull(expired.output)
        assertTrue(expired.stateChanged)
        assertEquals(Fold7AngleAuthority.Source.NONE, a.snapshot(1_193L).source)
    }
}
'''

NEW_PROMOTE_PUBLIC = r'''    private fun promotePublic(
        nowUptimeMs: Long,
        reason: String,
    ): Decision {
        val candidate = publicCandidate
            ?: return Decision(accepted = true)

        val ageMs = nowUptimeMs - candidate.observedUptimeMs
        if (ageMs < 0L || ageMs > publicMaxAgeMs) {
            publicCandidate = null
            return Decision(
                accepted = false,
                dropReason = "public-shadow-stale",
                sourceAgeMs = ageMs,
            )
        }

        if (candidate.coarse) {
            val changed = currentSource != Source.NONE
            currentSource = Source.NONE
            currentCoarse = false

            return Decision(
                output = null,
                accepted = true,
                stateChanged = changed,
                dropReason = "coarse-public-shadow-only",
                sourceAgeMs = ageMs,
            )
        }

        val sourceChanged = currentSource != candidate.source
        val changed =
            currentAngle.isNaN() ||
                abs(candidate.angle - currentAngle) >= CHANGE_EPSILON_DEG ||
                sourceChanged

        currentAngle = candidate.angle
        currentSource = candidate.source
        currentObservedUptimeMs = candidate.observedUptimeMs
        currentCoarse = false
        publicCandidate = null

        return Decision(
            output =
                if (changed) {
                    Output(
                        angle = currentAngle,
                        observedUptimeMs = currentObservedUptimeMs,
                        deliveredUptimeMs = nowUptimeMs,
                        source = currentSource,
                        coarse = false,
                        reason = reason,
                    )
                } else {
                    null
                },
            accepted = true,
            stateChanged = sourceChanged,
            sourceAgeMs = ageMs,
        )
    }'''

NEW_WAKE_BLOCK = r'''    private fun wakeInnerPhysicalDisplay(): Bundle {
        val t0 = SystemClock.elapsedRealtime()
        val physicalId = resolveFold7InnerPhysicalDisplayId()
        val (physicalPowered, physicalError) = setPhysicalPowerNormal(physicalId)

        val activation =
            if (physicalPowered) {
                activateInnerRouteAfterPhysicalWake(physicalId)
            } else {
                InnerWakeActivation(
                    logicalId = -1,
                    physicalId = physicalId,
                    routeEnabled = false,
                    logicalPowered = false,
                    stillInner = false,
                    error = physicalError ?: "physical inner wake failed",
                )
            }

        return Bundle().apply {
            putBoolean("ok", physicalPowered)
            putLong("physicalDisplayId", physicalId)
            putInt("targetDisplayId", if (activation.stillInner) activation.logicalId else -1)
            putInt("targetWidth", 1968)
            putInt("targetHeight", 2184)
            putBoolean("physicalPowered", physicalPowered)
            putBoolean("routeEnabled", activation.routeEnabled)
            putBoolean("logicalPowered", activation.logicalPowered)
            putBoolean("routeStillInner", activation.stillInner)
            putBoolean("logicalWakeRequested", activation.logicalPowered || activation.routeEnabled)
            putString("command", "Fold7 physical+logical inner early wake")
            putString("error", activation.error ?: physicalError)
            putLong("latencyMs", SystemClock.elapsedRealtime() - t0)
        }
    }

    private data class InnerWakeActivation(
        val logicalId: Int,
        val physicalId: Long,
        val routeEnabled: Boolean,
        val logicalPowered: Boolean,
        val stillInner: Boolean,
        val error: String?,
    )

    private fun directInnerRoute(ownedPhysicalId: Long): Pair<Int, Long>? {
        val directIds = runCatching { logicalDisplayIdsDirect().toList() }.getOrDefault(emptyList())
        val candidates = directIds.mapNotNull { id ->
            if (directGeometry(id) != (1968 to 2184)) return@mapNotNull null
            val physical = physicalDisplayIdFromLogicalGeometry(id, 1968, 2184)
            id to physical
        }
        candidates.firstOrNull { (_, physical) -> ownedPhysicalId >= 0L && physical == ownedPhysicalId }?.let { return it }
        return candidates.firstOrNull()
    }

    private fun activateInnerRouteAfterPhysicalWake(ownedPhysicalId: Long): InnerWakeActivation {
        if (ownedPhysicalId < 0L) {
            return InnerWakeActivation(-1, ownedPhysicalId, false, false, false, "owned physical inner id unavailable")
        }

        var route: Pair<Int, Long>? = null
        for (attempt in 0 until 8) {
            val candidate = runCatching { directInnerRoute(ownedPhysicalId) }.getOrNull()
            if (candidate != null && candidate.second == ownedPhysicalId) {
                route = candidate
                break
            }
            if (attempt < 7) Thread.sleep(8L)
        }

        val resolved = route ?: return InnerWakeActivation(
            -1,
            ownedPhysicalId,
            false,
            false,
            false,
            "physical inner woke but no matching 1968x2184 logical route appeared",
        )

        val logicalId = resolved.first
        var routeEnabled = logicalId == Display.DEFAULT_DISPLAY
        var routeError: String? = null

        if (logicalId != Display.DEFAULT_DISPLAY) {
            runCatching {
                enableConnectedDisplayInternal(logicalId)
                routeEnabled = true
            }.onFailure { error ->
                routeError = "${error.javaClass.simpleName}: ${error.message}"
            }
        }

        val stillInner =
            directGeometry(logicalId) == (1968 to 2184) &&
                physicalDisplayIdFromLogicalGeometry(logicalId, 1968, 2184) == ownedPhysicalId

        val logicalPowered =
            if (stillInner) {
                runCatching {
                    requestDisplayPowerInternal(logicalId, Display.STATE_ON)
                }.getOrElse { error ->
                    routeError = listOfNotNull(routeError, "${error.javaClass.simpleName}: ${error.message}").joinToString(" | ")
                    false
                }
            } else {
                false
            }

        return InnerWakeActivation(
            logicalId = logicalId,
            physicalId = ownedPhysicalId,
            routeEnabled = routeEnabled,
            logicalPowered = logicalPowered,
            stillInner = stillInner,
            error = if (!stillInner) "inner logical route remapped before STATE_ON" else routeError,
        )
    }'''

GENERIC_PHYSICAL = r'''    private fun physicalDisplayIdFromLogical(
        logicalDisplayId: Int,
    ): Long =
        physicalDisplayIdFromLogicalGeometry(
            logicalDisplayId = logicalDisplayId,
            width = 1080,
            height = 2520,
        )

    private fun physicalDisplayIdFromLogicalGeometry(
        logicalDisplayId: Int,
        width: Int,
        height: Int,
    ): Long {
        val info = displayInfoForLogicalId(logicalDisplayId) ?: return -1L
        val logicalWidth = runCatching { info.javaClass.getField("logicalWidth").getInt(info) }.getOrDefault(-1)
        val logicalHeight = runCatching { info.javaClass.getField("logicalHeight").getInt(info) }.getOrDefault(-1)
        if (logicalWidth != width || logicalHeight != height) return -1L
        val address = runCatching { info.javaClass.getField("address").get(info) }.getOrNull() ?: return -1L
        return runCatching {
            address.javaClass.getMethod("getPhysicalDisplayId").invoke(address) as Long
        }.getOrElse { -1L }
    }'''


def patch_build(text: str) -> str:
    text = replace_once(text, 'versionCode = 43', 'versionCode = 44', 'versionCode')
    text = replace_once(text, 'versionName = "6.0.0-alpha1-zfold7"', 'versionName = "6.0.0-alpha2-zfold7"', 'versionName')
    return text


def patch_angle_authority(text: str) -> str:
    return replace_between(text, '    private fun promotePublic(', '    companion object {', NEW_PROMOTE_PUBLIC, 'coarse public authority fence')


def patch_angle_test(_: str) -> str:
    return ANGLE_TEST


def patch_hinge_source(text: str) -> str:
    old = r'''    override fun onSensorChanged(event: SensorEvent) {
        val value = event.values.firstOrNull() ?: return
        val stats = candidates.firstOrNull { it.sensor == event.sensor } ?: return

        if (!value.isFinite() || value < -PLAUSIBLE_SLACK || value > 180f + PLAUSIBLE_SLACK) return

        stats.observe(value)
        if (choose() !== stats) return

        val receivedUptimeMs = SystemClock.uptimeMillis()
        val elapsedNowNs = SystemClock.elapsedRealtimeNanos()
        val ageNs = (elapsedNowNs - event.timestamp).coerceAtLeast(0L)
        val observedUptimeMs =
            (receivedUptimeMs - ageNs / 1_000_000L)
                .coerceAtLeast(0L)

        val source =
            if (stats.isStandard) {
                Fold7AngleAuthority.Source.PUBLIC_STANDARD
            } else {
                Fold7AngleAuthority.Source.PUBLIC_VENDOR
            }

        val decision =
            authority.offerPublic(
                source = source,
                angle = value,
                observedUptimeMs = observedUptimeMs,
                receivedUptimeMs = receivedUptimeMs,
                coarse = stats.looksCoarse,
            )

        handleDecision(decision)
    }
'''
    new = r'''    override fun onSensorChanged(event: SensorEvent) {
        val value = event.values.firstOrNull() ?: return
        val stats = candidates.firstOrNull { it.sensor == event.sensor } ?: return

        if (!value.isFinite() || value < -PLAUSIBLE_SLACK || value > 180f + PLAUSIBLE_SLACK) return

        stats.observe(value)
        if (choose() !== stats) return

        val receivedUptimeMs = SystemClock.uptimeMillis()
        val elapsedNowNs = SystemClock.elapsedRealtimeNanos()
        val ageNs = (elapsedNowNs - event.timestamp).coerceAtLeast(0L)
        val observedUptimeMs =
            (receivedUptimeMs - ageNs / 1_000_000L)
                .coerceAtLeast(0L)

        val source =
            if (stats.isStandard) {
                Fold7AngleAuthority.Source.PUBLIC_STANDARD
            } else {
                Fold7AngleAuthority.Source.PUBLIC_VENDOR
            }

        val decision =
            authority.offerPublic(
                source = source,
                angle = value,
                observedUptimeMs = observedUptimeMs,
                receivedUptimeMs = receivedUptimeMs,
                coarse = stats.looksCoarse,
            )

        com.duoopen.debug.DuoDiagnostics.event(
            "hinge-authority-decision",
            "raw=$value source=${source.name} coarse=${stats.looksCoarse} " +
                "resolution=${stats.resolution} accepted=${decision.accepted} " +
                "output=${decision.output?.angle} outputSource=${decision.output?.source} " +
                "stateChanged=${decision.stateChanged} sourceAgeMs=${decision.sourceAgeMs} " +
                "reason=${decision.dropReason ?: decision.output?.reason ?: "shadow-retained"}",
        )

        handleDecision(decision)
    }
'''
    return replace_once(text, old, new, 'public hinge authority decision telemetry')


def patch_shell(text: str) -> str:
    text = replace_between(
        text,
        '    private fun wakeInnerPhysicalDisplay(): Bundle {',
        '    private fun logicalDisplayIdsDirect(): IntArray {',
        NEW_WAKE_BLOCK,
        'physical+logical inner wake',
    )
    text = replace_between(
        text,
        '    private fun physicalDisplayIdFromLogical(',
        '    private fun physicalDisplayIdForGeometry(',
        GENERIC_PHYSICAL,
        'generic logical->physical resolver',
    )

    text = replace_once(
        text,
        '''        val owner =
            Fold7PanelAuthorityGen4.Owner(''',
        '''        if (directGeometry(Display.DEFAULT_DISPLAY) == (1080 to 2520)) {
            gen4PanelAuthority.markNativeCover()
            return gen4PanelBundle(
                operation = "prepare:$reason",
                ok = true,
                stale = true,
                decision = "native-cover-terminal-fence",
            )
        }

        val owner =
            Fold7PanelAuthorityGen4.Owner(''',
        'prepare terminal cover fence',
    )

    text = replace_once(
        text,
        '''        val before = gen4PanelAuthority.snapshot()
        val expectedOwner =''',
        '''        if (directGeometry(Display.DEFAULT_DISPLAY) == (1080 to 2520)) {
            gen4PanelAuthority.markNativeCover()
            return gen4PanelBundle(
                operation = "reassert:$reason",
                ok = true,
                stale = true,
                decision = "native-cover-terminal-fence",
            )
        }

        val before = gen4PanelAuthority.snapshot()
        val expectedOwner =''',
        'reassert terminal cover fence',
    )
    return text


def patch_coordinator(text: str) -> str:
    return replace_once(
        text,
        '''        if (
            controller.state !in setOf(''',
        '''        if (topology().nativeCover) {
            DuoDiagnostics.event(
                "gen4-authority",
                "route reassert fenced before shell mutation reason=$reason state=${controller.state}",
            )
            return
        }

        if (
            controller.state !in setOf(''',
        'app-side terminal route fence',
    )


def patch_wallpaper(_: str) -> str:
    return PASSIVE_WALLPAPER


def self_test() -> None:
    source = Path(__file__).read_text(encoding='utf-8')
    require('coarse-public-shadow-only' in source, 'coarse fence marker')
    require('physical+logical inner early wake' in source, 'inner wake marker')
    require('native-cover-terminal-fence' in source, 'terminal fence marker')
    require('HingeAngleSource' not in PASSIVE_WALLPAPER, 'wallpaper must not own hinge')
    require('DuoShader' not in PASSIVE_WALLPAPER, 'wallpaper must not own fold shader')
    require('RIGHT_PANE_LEFT = 984f' in PASSIVE_WALLPAPER, 'canonical right pane')
    print('GEN6 BETA HOTFIX V1 SELF-TEST: PASS')


def main() -> None:
    if '--self-test' in sys.argv:
        self_test()
        return

    require((ROOT / '.git').exists(), 'run from repository root after Gen6 V2 patcher')

    transforms = {
        'app/build.gradle.kts': patch_build,
        'app/src/main/java/com/duoopen/fold/Fold7AngleAuthority.kt': patch_angle_authority,
        'app/src/test/java/com/duoopen/fold/Fold7AngleAuthorityTest.kt': patch_angle_test,
        'app/src/main/java/com/duoopen/fold/HingeAngleSource.kt': patch_hinge_source,
        'app/src/full/java/com/duoopen/shell/DuoShellService.kt': patch_shell,
        'app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt': patch_coordinator,
        'app/src/main/java/com/duoopen/wallpaper/DuoWallpaperService.kt': patch_wallpaper,
    }

    for rel, transform in transforms.items():
        path = ROOT / rel
        require(path.exists(), f'missing source file {rel}')
        before = path.read_text(encoding='utf-8')
        after = transform(before)
        require(after != before, f'no change produced for {rel}')
        path.write_text(after, encoding='utf-8')
        print(f'Hotfixed {rel}')

    print('GEN6 BETA HOTFIX V1 APPLY: PASS')
    print('Next: git diff --check && ./gradlew testFullDebugUnitTest assembleFullDebug --stacktrace')


if __name__ == '__main__':
    main()
