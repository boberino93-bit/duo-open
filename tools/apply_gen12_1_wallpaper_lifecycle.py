#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

TARGET_VERSION_CODE = 57
TARGET_VERSION_NAME = "5.6.1-gen12-1-wallpaper-lifecycle-zfold7"
MARKER = "GEN12_1_WALLPAPER_LIFECYCLE"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_new(path: Path, text: str) -> None:
    if path.exists():
        existing = read(path)
        if existing != text:
            raise RuntimeError(f"new-file collision: {path}")
        return
    write(path, text)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_build_gradle(text: str) -> str:
    if TARGET_VERSION_NAME in text:
        return text
    text = replace_once(text, "versionCode = 56", f"versionCode = {TARGET_VERSION_CODE}", "versionCode")
    text = replace_once(
        text,
        'versionName = "5.6.0-gen12-route-lane-resilience-zfold7"',
        f'versionName = "{TARGET_VERSION_NAME}"',
        "versionName",
    )
    return text


def transform_settings(text: str) -> str:
    if "GEN12_1_SETTINGS_SERIALIZATION" in text:
        return text

    text = replace_once(
        text,
        "    fun update(transform: (DuoConfig) -> DuoConfig) {\n",
        "    // GEN12_1_SETTINGS_SERIALIZATION: image metadata and visual tuning may be\n"
        "    // updated from different coroutine contexts. Serialize read/transform/write\n"
        "    // so a background wallpaper commit cannot overwrite a simultaneous UI edit.\n"
        "    @Synchronized\n"
        "    fun update(transform: (DuoConfig) -> DuoConfig) {\n",
        "serialize settings update",
    )

    anchor = '''    /** Restores the look defaults, keeping fold geometry, engine choice and the image. */
    fun resetTuning() = update {
'''
    insert = '''    /**
     * Advances wallpaper metadata only after WallpaperImage has durably committed
     * the corresponding payload. Serialized with every other settings mutation.
     */
    @Synchronized
    fun bumpImageVersionAfterPayloadCommit(): Long {
        val next = _config.value.copy(imageVersion = _config.value.imageVersion + 1L)
        _config.value = next
        prefs.edit {
            putFloat("intensity", next.intensity)
            putFloat("blurSpread", next.blurSpread)
            putFloat("darkening", next.darkening)
            putFloat("eyeDistanceMm", next.eyeDistanceMm)
            putBoolean("foldSplitsLong", next.foldSplitsLong)
            putInt("movingSide", next.movingSide)
            putBoolean("coverFrostFromRight", next.coverFrostFromRight)
            putBoolean("liveBlur", next.liveBlur)
            putBoolean("instantStart", next.instantStart)
            putBoolean("shizukuCapture", next.shizukuCapture)
            putBoolean("shizukuAngle", next.shizukuAngle)
            putLong("imageVersion", next.imageVersion)
        }
        return next.imageVersion
    }

'''
    text = replace_once(text, anchor, insert + anchor, "image version commit API")
    return text


def wallpaper_source() -> str:
    return r'''package com.duoopen.wallpaper

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.ImageDecoder
import android.graphics.Paint
import android.graphics.RadialGradient
import android.graphics.Shader
import android.net.Uri
import android.os.SystemClock
import android.util.AtomicFile
import com.duoopen.debug.DuoDiagnostics
import com.duoopen.settings.DuoSettings
import java.io.File
import java.io.FileNotFoundException
import java.io.FileOutputStream
import java.io.IOException
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/**
 * GEN12_1_WALLPAPER_LIFECYCLE
 *
 * Durable wallpaper store shared by app preview + live wallpaper in one process.
 * The payload is committed atomically before imageVersion advances. The decoded
 * import becomes the cache entry for the committed version, avoiding the former
 * immediate second full-size decode and its peak-memory amplification.
 */
object WallpaperImage {
    private const val FILE_NAME = "wallpaper.jpg"
    private const val MAX_DIM = 2600
    private const val MAX_PIXELS = 5_000_000L
    private const val DEFAULT_SIZE = 2048
    private const val LOW_MEMORY_DEFAULT_SIZE = 384

    private val lock = Any()
    private var cached: Pair<Long, Bitmap>? = null

    private fun file(context: Context) = File(context.filesDir, FILE_NAME)
    private fun atomicFile(context: Context) = AtomicFile(file(context))

    /** Blocking; call off the main thread. Never throws for normal storage/decode failure. */
    fun load(context: Context, version: Long): Bitmap = synchronized(lock) {
        cached?.let { (v, bmp) ->
            if (v == version && !bmp.isRecycled) {
                return bmp
            }
        }

        val started = SystemClock.uptimeMillis()
        val atomic = atomicFile(context)
        val base = file(context)

        val payloadAvailable =
            try {
                // openRead performs AtomicFile recovery if a previous write was interrupted.
                atomic.openRead().use { }
                true
            } catch (_: FileNotFoundException) {
                false
            } catch (e: Exception) {
                DuoDiagnostics.event(
                    "wallpaper-store",
                    "rehydrate-open-failed version=$version",
                    e,
                )
                false
            }

        val (bmp, source) =
            if (payloadAvailable) {
                try {
                    decode(ImageDecoder.createSource(base)) to "persisted"
                } catch (oom: OutOfMemoryError) {
                    DuoDiagnostics.event(
                        "wallpaper-store",
                        "rehydrate-oom version=$version bytes=${base.length()}",
                        oom,
                    )
                    lowMemoryDefault() to "low-memory-default"
                } catch (e: Exception) {
                    DuoDiagnostics.event(
                        "wallpaper-store",
                        "rehydrate-corrupt version=$version bytes=${base.length()} action=delete-and-default",
                        e,
                    )
                    atomic.delete()
                    generateDefault() to "corrupt-default"
                }
            } else {
                generateDefault() to "default"
            }

        cached = version to bmp
        DuoDiagnostics.event(
            "wallpaper-store",
            "rehydrate-ok version=$version source=$source size=${bmp.width}x${bmp.height} " +
                "bytes=${base.takeIf { it.exists() }?.length() ?: 0L} " +
                "elapsedMs=${SystemClock.uptimeMillis() - started}",
        )
        bmp
    }

    /**
     * Blocking; decodes a picked image, atomically commits it to private app
     * storage, then advances imageVersion. No metadata success is emitted before
     * the payload commit has completed.
     */
    fun import(context: Context, uri: Uri) {
        val started = SystemClock.uptimeMillis()
        val bmp =
            try {
                decode(ImageDecoder.createSource(context.contentResolver, uri))
            } catch (oom: OutOfMemoryError) {
                DuoDiagnostics.event("wallpaper-store", "import-decode-oom", oom)
                throw IOException("Wallpaper image exceeded the safe decode envelope", oom)
            }

        try {
            commitDecodedBitmap(context, bmp, started)
        } catch (t: Throwable) {
            if (!bmp.isRecycled) {
                bmp.recycle()
            }
            throw t
        }
    }

    private fun commitDecodedBitmap(
        context: Context,
        bmp: Bitmap,
        startedUptimeMs: Long,
    ): Long = synchronized(lock) {
        val atomic = atomicFile(context)
        var stream: FileOutputStream? = null

        try {
            stream = atomic.startWrite()
            if (!bmp.compress(Bitmap.CompressFormat.JPEG, 95, stream)) {
                throw IOException("Bitmap.compress returned false")
            }
            stream.fd.sync()
            atomic.finishWrite(stream)
            stream = null
        } catch (t: Throwable) {
            stream?.let { runCatching { atomic.failWrite(it) } }
            DuoDiagnostics.event("wallpaper-store", "payload-commit-failed", t)
            throw t
        }

        val base = file(context)
        if (!base.exists() || base.length() <= 0L) {
            val error = IOException("Atomic wallpaper commit produced no durable payload")
            DuoDiagnostics.event("wallpaper-store", "payload-commit-missing", error)
            throw error
        }

        // Payload first, metadata second. Collectors awakened by the version bump
        // block on [lock] until the new cache entry has been published below.
        val nextVersion = DuoSettings.bumpImageVersionAfterPayloadCommit()
        cached = nextVersion to bmp

        DuoDiagnostics.event(
            "wallpaper-store",
            "payload-commit-ok version=$nextVersion size=${bmp.width}x${bmp.height} " +
                "bytes=${base.length()} elapsedMs=${SystemClock.uptimeMillis() - startedUptimeMs}",
        )
        nextVersion
    }

    fun reset(context: Context) = synchronized(lock) {
        val atomic = atomicFile(context)
        atomic.delete()
        if (file(context).exists()) {
            val error = IOException("Wallpaper payload could not be deleted")
            DuoDiagnostics.event("wallpaper-store", "reset-delete-failed", error)
            throw error
        }
        cached = null
        val version = DuoSettings.bumpImageVersionAfterPayloadCommit()
        DuoDiagnostics.event("wallpaper-store", "reset-default version=$version")
    }

    /**
     * Center-crop scale+offset mapping a [bw]x[bh] image onto a [w]x[h] surface:
     * returns (scale, dx, dy).
     */
    fun centerCrop(bw: Int, bh: Int, w: Float, h: Float): Triple<Float, Float, Float> {
        val scale = max(w / bw, h / bh)
        return Triple(scale, (w - bw * scale) * 0.5f, (h - bh * scale) * 0.5f)
    }

    internal fun decodeTargetSize(width: Int, height: Int): Pair<Int, Int> {
        require(width > 0 && height > 0)
        val longSide = max(width, height).toFloat()
        val pixels = width.toLong() * height.toLong()
        val byDimension = min(1f, MAX_DIM.toFloat() / longSide)
        val byPixels =
            if (pixels > MAX_PIXELS) {
                sqrt(MAX_PIXELS.toDouble() / pixels.toDouble()).toFloat()
            } else {
                1f
            }
        val scale = min(byDimension, byPixels)
        return
            ((width * scale).toInt().coerceAtLeast(1)) to
                ((height * scale).toInt().coerceAtLeast(1))
    }

    private fun decode(source: ImageDecoder.Source): Bitmap =
        ImageDecoder.decodeBitmap(source) { decoder, info, _ ->
            decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
            val (targetWidth, targetHeight) = decodeTargetSize(info.size.width, info.size.height)
            if (targetWidth != info.size.width || targetHeight != info.size.height) {
                decoder.setTargetSize(targetWidth, targetHeight)
            }
        }

    /** Soft color fields over deep ink plus a fine dot grid. */
    private fun generateDefault(size: Int = DEFAULT_SIZE): Bitmap {
        val bmp = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bmp)
        canvas.drawColor(0xFF0D0A1C.toInt())

        val blobs = listOf(
            Blob(0.18f, 0.22f, 0.55f, 0xFF7B5CFF.toInt()),
            Blob(0.86f, 0.20f, 0.50f, 0xFFF0564A.toInt()),
            Blob(0.50f, 0.52f, 0.42f, 0xFFC44EDD.toInt()),
            Blob(0.20f, 0.86f, 0.50f, 0xFF19C3B2.toInt()),
            Blob(0.84f, 0.84f, 0.48f, 0xFFFFB020.toInt()),
        )
        val paint = Paint(Paint.ANTI_ALIAS_FLAG)
        for (b in blobs) {
            val cx = b.x * size
            val cy = b.y * size
            val r = b.radius * size
            paint.shader = RadialGradient(
                cx,
                cy,
                r,
                intArrayOf(b.color, b.color and 0x00FFFFFF),
                floatArrayOf(0f, 1f),
                Shader.TileMode.CLAMP,
            )
            paint.alpha = 220
            canvas.drawCircle(cx, cy, r, paint)
        }

        paint.shader = null
        paint.color = 0x38FFFFFF
        val step = size / 36f
        val dot = size / 620f
        var y = step * 0.5f
        while (y < size) {
            var x = step * 0.5f
            while (x < size) {
                canvas.drawCircle(x, y, dot, paint)
                x += step
            }
            y += step
        }
        return bmp
    }

    private fun lowMemoryDefault(): Bitmap =
        try {
            generateDefault(LOW_MEMORY_DEFAULT_SIZE)
        } catch (_: OutOfMemoryError) {
            Bitmap.createBitmap(1, 1, Bitmap.Config.ARGB_8888).apply {
                eraseColor(0xFF0D0A1C.toInt())
            }
        }

    internal fun clearMemoryCacheForTesting() = synchronized(lock) {
        cached = null
    }

    internal fun importBitmapForTesting(context: Context, bitmap: Bitmap): Long =
        commitDecodedBitmap(
            context = context,
            bmp = bitmap,
            startedUptimeMs = SystemClock.uptimeMillis(),
        )

    internal fun payloadFileForTesting(context: Context): File = file(context)

    private data class Blob(val x: Float, val y: Float, val radius: Float, val color: Int)
}
'''


def transform_wallpaper_service(text: str) -> str:
    if "GEN12_1_WALLPAPER_SERVICE_DIAGNOSTICS" in text:
        return text

    text = replace_once(
        text,
        "import com.duoopen.fold.DuoShader\n",
        "import com.duoopen.debug.DuoDiagnostics\nimport com.duoopen.fold.DuoShader\n",
        "diagnostic import",
    )

    text = replace_once(
        text,
        '''        override fun onCreate(surfaceHolder: SurfaceHolder) {
            super.onCreate(surfaceHolder)
''',
        '''        override fun onCreate(surfaceHolder: SurfaceHolder) {
            super.onCreate(surfaceHolder)
            DuoDiagnostics.event(
                "wallpaper-lifecycle",
                "GEN12_1_WALLPAPER_SERVICE_DIAGNOSTICS engine-create display=${displayContext?.display?.displayId}",
            )
''',
        "engine create diagnostic",
    )

    text = replace_once(
        text,
        '''        override fun onDestroy() {
            hinge.stop()
''',
        '''        override fun onDestroy() {
            DuoDiagnostics.event(
                "wallpaper-lifecycle",
                "engine-destroy display=${displayContext?.display?.displayId} version=$bitmapVersion",
            )
            hinge.stop()
''',
        "engine destroy diagnostic",
    )

    text = replace_once(
        text,
        '''        override fun onVisibilityChanged(visible: Boolean) {
            if (visible) {
''',
        '''        override fun onVisibilityChanged(visible: Boolean) {
            DuoDiagnostics.event(
                "wallpaper-lifecycle",
                "visibility=$visible display=${displayContext?.display?.displayId} version=$bitmapVersion surfaceReady=$surfaceReady",
            )
            if (visible) {
''',
        "visibility diagnostic",
    )

    text = replace_once(
        text,
        '''            surfaceReady = true
            width = w.toFloat()
            height = h.toFloat()
''',
        '''            surfaceReady = true
            width = w.toFloat()
            height = h.toFloat()
            DuoDiagnostics.event(
                "wallpaper-lifecycle",
                "surface-changed display=${displayContext?.display?.displayId} size=${w}x$h version=$bitmapVersion",
            )
''',
        "surface diagnostic",
    )

    text = replace_once(
        text,
        '''        override fun onSurfaceDestroyed(holder: SurfaceHolder) {
            surfaceReady = false
''',
        '''        override fun onSurfaceDestroyed(holder: SurfaceHolder) {
            DuoDiagnostics.event(
                "wallpaper-lifecycle",
                "surface-destroyed display=${displayContext?.display?.displayId} version=$bitmapVersion",
            )
            surfaceReady = false
''',
        "surface destroy diagnostic",
    )

    old_load = '''        private fun loadImage(version: Long) {
            bitmapVersion = version
            scope.launch {
                val bmp = withContext(Dispatchers.IO) { WallpaperImage.load(context, version) }
                if (version != bitmapVersion) return@launch
                bitmap = bmp
                rebuildImageShader()
                draw()
            }
        }
'''
    new_load = '''        private fun loadImage(version: Long) {
            bitmapVersion = version
            scope.launch {
                val started = android.os.SystemClock.uptimeMillis()
                val bmp =
                    try {
                        withContext(Dispatchers.IO) {
                            WallpaperImage.load(context, version)
                        }
                    } catch (oom: OutOfMemoryError) {
                        DuoDiagnostics.event(
                            "wallpaper-lifecycle",
                            "engine-load-oom version=$version display=${displayContext?.display?.displayId}",
                            oom,
                        )
                        return@launch
                    } catch (e: Exception) {
                        DuoDiagnostics.event(
                            "wallpaper-lifecycle",
                            "engine-load-failed version=$version display=${displayContext?.display?.displayId}",
                            e,
                        )
                        return@launch
                    }

                if (version != bitmapVersion) {
                    DuoDiagnostics.event(
                        "wallpaper-lifecycle",
                        "engine-load-stale requested=$version current=$bitmapVersion",
                    )
                    return@launch
                }

                bitmap = bmp
                rebuildImageShader()
                DuoDiagnostics.event(
                    "wallpaper-lifecycle",
                    "engine-load-ok version=$version size=${bmp.width}x${bmp.height} " +
                        "display=${displayContext?.display?.displayId} elapsedMs=${android.os.SystemClock.uptimeMillis() - started}",
                )
                draw()
            }
        }
'''
    text = replace_once(text, old_load, new_load, "safe wallpaper engine load")
    return text


def transform_application(text: str) -> str:
    if "GEN12_1_EXIT_FORENSICS" in text:
        return text

    text = replace_once(
        text,
        "import android.app.ActivityManager\n",
        "import android.app.ActivityManager\nimport android.app.ApplicationExitInfo\n",
        "exit info import",
    )

    old = '''        val previous =
            runCatching {
                manager
                    .getHistoricalProcessExitReasons(
                        packageName,
                        0,
                        3,
                    )
                    .firstOrNull()
            }.getOrNull()
                ?: return

        val ageMs =
            (
                System.currentTimeMillis() -
                    previous.timestamp
                ).coerceAtLeast(
                0L
            )

        DuoDiagnostics.event(
            "process-exit",
            "previous reason=${previous.reason} " +
                "status=${previous.status} " +
                "importance=${previous.importance} " +
                "ageMs=$ageMs " +
                "description=${previous.description ?: "(none)"}",
        )
'''
    new = '''        // GEN12_1_EXIT_FORENSICS: log several exits, not only the newest one.
        // A user/task removal can otherwise hide the crash/OOM/ANR immediately before it.
        val previous =
            runCatching {
                manager.getHistoricalProcessExitReasons(
                    packageName,
                    0,
                    5,
                )
            }.getOrNull()
                ?: return

        previous.forEachIndexed { rank, exit ->
            val ageMs =
                (
                    System.currentTimeMillis() -
                        exit.timestamp
                    ).coerceAtLeast(0L)

            DuoDiagnostics.event(
                "process-exit",
                "rank=$rank reason=${exit.reason}:${exitReasonName(exit.reason)} " +
                    "status=${exit.status} importance=${exit.importance} " +
                    "pss=${exit.pss} rss=${exit.rss} ageMs=$ageMs " +
                    "description=${exit.description ?: "(none)"}",
            )
        }
'''
    text = replace_once(text, old, new, "multi-exit forensic log")

    anchor = '''    }
}
'''
    helper = '''    private fun exitReasonName(reason: Int): String =
        when (reason) {
            ApplicationExitInfo.REASON_EXIT_SELF -> "EXIT_SELF"
            ApplicationExitInfo.REASON_SIGNALED -> "SIGNALED"
            ApplicationExitInfo.REASON_LOW_MEMORY -> "LOW_MEMORY"
            ApplicationExitInfo.REASON_CRASH -> "CRASH"
            ApplicationExitInfo.REASON_CRASH_NATIVE -> "CRASH_NATIVE"
            ApplicationExitInfo.REASON_ANR -> "ANR"
            ApplicationExitInfo.REASON_INITIALIZATION_FAILURE -> "INITIALIZATION_FAILURE"
            ApplicationExitInfo.REASON_PERMISSION_CHANGE -> "PERMISSION_CHANGE"
            ApplicationExitInfo.REASON_EXCESSIVE_RESOURCE_USAGE -> "EXCESSIVE_RESOURCE_USAGE"
            ApplicationExitInfo.REASON_USER_REQUESTED -> "USER_REQUESTED"
            ApplicationExitInfo.REASON_USER_STOPPED -> "USER_STOPPED"
            ApplicationExitInfo.REASON_DEPENDENCY_DIED -> "DEPENDENCY_DIED"
            ApplicationExitInfo.REASON_OTHER -> "OTHER"
            ApplicationExitInfo.REASON_FREEZER -> "FREEZER"
            ApplicationExitInfo.REASON_PACKAGE_STATE_CHANGE -> "PACKAGE_STATE_CHANGE"
            ApplicationExitInfo.REASON_PACKAGE_UPDATED -> "PACKAGE_UPDATED"
            else -> "UNKNOWN"
        }

'''
    text = replace_once(text, anchor, helper + anchor, "exit reason helper")
    return text


def transform_control_sheet(text: str) -> str:
    if "GEN12_1_WALLPAPER_CONFLICT_WARNING" in text:
        return text

    old = '''        SettingsCard(
            title = "Wallpaper mode",
            subtitle =
                if (wallpaperActive) {
                    "Active · the wallpaper folds while icons remain native."
                } else {
                    "Optional fallback that does not require Accessibility."
                },
        ) {
            OutlinedButton(
                onClick = onSetWallpaper,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (wallpaperActive) "Wallpaper settings" else "Set Duo wallpaper")
            }
        }
'''
    new = '''        SettingsCard(
            title = "Wallpaper mode",
            subtitle =
                if (wallpaperActive) {
                    "Active · the wallpaper folds while icons remain native."
                } else {
                    "Optional fallback that does not require Accessibility."
                },
        ) {
            OutlinedButton(
                onClick = onSetWallpaper,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (wallpaperActive) "Wallpaper settings" else "Set Duo wallpaper")
            }
            if (overlayAvailable && shizukuReady) {
                Hint(
                    "GEN12_1_WALLPAPER_CONFLICT_WARNING · Fold7 field evidence shows that when Duo wallpaper owns the active wallpaper target, Samsung Fold interactive can stop producing the temporary precise-angle feed. Full-screen continuity is the recommended Fold7 path; wallpaper mode may fall back to coarse geometry.",
                    warn = true,
                )
            }
        }
'''
    return replace_once(text, old, new, "wallpaper/angle conflict warning")


def transform_home_preview(text: str) -> str:
    if "GEN12_1_WALLPAPER_ACTIVE_WARNING" in text:
        return text

    anchor = '''                ReadinessRow(
                    title = "Hinge telemetry",
                    detail =
                        when {
                            hingeAngle.isNaN() -> "Waiting for geometry"
                            paneTilt < 0.05f -> "Geometry available · visual flat"
                            else -> "Tracking · visual active"
                        },
                    active = !hingeAngle.isNaN(),
                )
'''
    replacement = anchor + '''                if (wallpaperActive && shizukuReady) {
                    ReadinessRow(
                        title = "Wallpaper compatibility",
                        detail = "GEN12_1_WALLPAPER_ACTIVE_WARNING · Duo wallpaper may displace Samsung's temporary precise-angle source",
                        active = false,
                    )
                }
'''
    return replace_once(text, anchor, replacement, "home wallpaper compatibility warning")


def sizing_test_source() -> str:
    return '''package com.duoopen.wallpaper

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class WallpaperImageSizingTest {
    @Test
    fun nativeFold7ScaleStaysNative() {
        assertEquals(1968 to 2184, WallpaperImage.decodeTargetSize(1968, 2184))
    }

    @Test
    fun squarePhotosAreBoundedByPixelBudget() {
        val (w, h) = WallpaperImage.decodeTargetSize(4000, 4000)
        assertTrue(w <= 2600)
        assertTrue(h <= 2600)
        assertTrue(w.toLong() * h.toLong() <= 5_000_000L)
    }

    @Test
    fun extremePanoramaIsBoundedByLongSide() {
        val (w, h) = WallpaperImage.decodeTargetSize(8000, 1000)
        assertTrue(w <= 2600)
        assertTrue(h > 0)
        assertTrue(w.toLong() * h.toLong() <= 5_000_000L)
    }
}
'''


def persistence_test_source() -> str:
    return '''package com.duoopen.wallpaper

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Color
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.duoopen.settings.DuoSettings
import java.io.File
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class WallpaperImagePersistenceTest {
    private lateinit var context: Context

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        DuoSettings.init(context)
        runCatching { WallpaperImage.reset(context) }
        WallpaperImage.clearMemoryCacheForTesting()
    }

    @After
    fun tearDown() {
        runCatching { WallpaperImage.reset(context) }
        WallpaperImage.clearMemoryCacheForTesting()
    }

    @Test
    fun twoReplacementsSurviveMemoryAndSettingsRehydrate() {
        val first = solidBitmap(Color.RED)
        val version1 = WallpaperImage.importBitmapForTesting(context, first)

        WallpaperImage.clearMemoryCacheForTesting()
        DuoSettings.init(context)
        assertEquals(version1, DuoSettings.config.value.imageVersion)
        val firstReloaded = WallpaperImage.load(context, version1)
        assertDominant(firstReloaded, Color.RED)

        val second = solidBitmap(Color.BLUE)
        val version2 = WallpaperImage.importBitmapForTesting(context, second)
        assertTrue(version2 > version1)

        WallpaperImage.clearMemoryCacheForTesting()
        DuoSettings.init(context)
        assertEquals(version2, DuoSettings.config.value.imageVersion)
        val secondReloaded = WallpaperImage.load(context, version2)
        assertDominant(secondReloaded, Color.BLUE)
    }

    @Test
    fun corruptPersistedPayloadFailsSafeAndIsQuarantined() {
        val version = WallpaperImage.importBitmapForTesting(context, solidBitmap(Color.GREEN))
        val payload = WallpaperImage.payloadFileForTesting(context)
        payload.writeBytes(byteArrayOf(1, 2, 3, 4, 5, 6, 7))
        WallpaperImage.clearMemoryCacheForTesting()

        val fallback = WallpaperImage.load(context, version)

        assertTrue(fallback.width > 0)
        assertTrue(fallback.height > 0)
        assertFalse(payload.exists())
        assertEquals(version, DuoSettings.config.value.imageVersion)
    }

    private fun solidBitmap(color: Int): Bitmap =
        Bitmap.createBitmap(96, 128, Bitmap.Config.ARGB_8888).apply {
            eraseColor(color)
        }

    private fun assertDominant(bitmap: Bitmap, expected: Int) {
        val actual = bitmap.getPixel(bitmap.width / 2, bitmap.height / 2)
        when (expected) {
            Color.RED -> assertTrue(Color.red(actual) > Color.blue(actual) + 80)
            Color.BLUE -> assertTrue(Color.blue(actual) > Color.red(actual) + 80)
            Color.GREEN -> assertTrue(Color.green(actual) > Color.red(actual) + 80)
        }
    }
}
'''


def verify(repo: Path) -> None:
    build = read(repo / "app/build.gradle.kts")
    settings = read(repo / "app/src/main/java/com/duoopen/settings/DuoSettings.kt")
    image = read(repo / "app/src/main/java/com/duoopen/wallpaper/WallpaperImage.kt")
    service = read(repo / "app/src/main/java/com/duoopen/wallpaper/DuoWallpaperService.kt")
    application = read(repo / "app/src/main/java/com/duoopen/DuoApplication.kt")
    controls = read(repo / "app/src/main/java/com/duoopen/ui/ControlSheet.kt")
    home = read(repo / "app/src/main/java/com/duoopen/ui/HomePreview.kt")
    route_service = read(repo / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt")
    coordinator = read(repo / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt")
    panel = read(repo / "app/src/full/java/com/duoopen/overlay/PanelEngine.kt")

    required = {
        "version": TARGET_VERSION_NAME in build and f"versionCode = {TARGET_VERSION_CODE}" in build,
        "api37-target35": "compileSdk = 37" in build and "targetSdk = 35" in build,
        "atomic-store": "AtomicFile" in image and MARKER in image,
        "payload-before-version": image.find("atomic.finishWrite") < image.find("bumpImageVersionAfterPayloadCommit"),
        "cache-imported-bitmap": "cached = nextVersion to bmp" in image,
        "pixel-budget": "MAX_PIXELS = 5_000_000L" in image,
        "corrupt-fail-safe": "rehydrate-corrupt" in image and "atomic.delete()" in image,
        "serialized-settings": "GEN12_1_SETTINGS_SERIALIZATION" in settings,
        "wallpaper-service-diagnostics": "GEN12_1_WALLPAPER_SERVICE_DIAGNOSTICS" in service,
        "exit-forensics": "GEN12_1_EXIT_FORENSICS" in application and "rank=$rank" in application,
        "conflict-warning": "GEN12_1_WALLPAPER_CONFLICT_WARNING" in controls,
        "home-warning": "GEN12_1_WALLPAPER_ACTIVE_WARNING" in home,
        "gen12-route-lane": "GEN12_ROUTE_LANE_RESILIENCE" in route_service,
        "gen10-7-angle": "GEN10_7_TOPOLOGY_ANGLE_HOLD" in coordinator,
        "secure-fail-open": "capture-protected-or-black" in panel,
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        raise RuntimeError(f"Gen12.1 verification failed: {missing}")

    if "renameTo(" in image:
        raise RuntimeError("Gen12.1 must not use unchecked File.renameTo for wallpaper commit")
    if "targetSdk = 37" in build:
        raise RuntimeError("Gen12.1 must preserve targetSdk 35 compatibility bridge")

    print("Gen12.1 wallpaper lifecycle hardening applied and verified")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()

    build = repo / "app/build.gradle.kts"
    write(build, transform_build_gradle(read(build)))

    settings = repo / "app/src/main/java/com/duoopen/settings/DuoSettings.kt"
    write(settings, transform_settings(read(settings)))

    image = repo / "app/src/main/java/com/duoopen/wallpaper/WallpaperImage.kt"
    write(image, wallpaper_source())

    service = repo / "app/src/main/java/com/duoopen/wallpaper/DuoWallpaperService.kt"
    write(service, transform_wallpaper_service(read(service)))

    application = repo / "app/src/main/java/com/duoopen/DuoApplication.kt"
    write(application, transform_application(read(application)))

    controls = repo / "app/src/main/java/com/duoopen/ui/ControlSheet.kt"
    write(controls, transform_control_sheet(read(controls)))

    home = repo / "app/src/main/java/com/duoopen/ui/HomePreview.kt"
    write(home, transform_home_preview(read(home)))

    write_new(
        repo / "app/src/test/java/com/duoopen/wallpaper/WallpaperImageSizingTest.kt",
        sizing_test_source(),
    )
    write_new(
        repo / "app/src/androidTest/java/com/duoopen/wallpaper/WallpaperImagePersistenceTest.kt",
        persistence_test_source(),
    )

    verify(repo)


if __name__ == "__main__":
    main()
