package com.duoopen.debug

import android.app.KeyguardManager
import android.content.Context
import android.hardware.display.DisplayManager
import android.os.Build
import android.os.PowerManager
import android.os.SystemClock
import android.util.Log
import com.duoopen.BuildConfig
import java.io.File
import java.time.Instant
import java.util.ArrayDeque
import java.util.concurrent.Executors

/**
 * Persistent, low-overhead field recorder for fold/dual-screen debugging.
 * It records technical state transitions only; it never records screen
 * pixels, notification contents, messages, passwords, or keystrokes.
 */
object DuoDiagnostics {
    private const val TAG = "DuoDiag"
    private const val FILE_NAME = "duoopen-field-debug.log"
    private const val MAX_LINES = 1200
    private const val MAX_FILE_BYTES = 1_000_000L
    private const val KEEP_BYTES = 500_000

    /**
     * Optional synchronous observation tap.
     *
     * The full-edition Transition Lab installs this in debug builds so existing
     * state-machine diagnostics can be timestamped in the same monotonic domain
     * as hinge/frame/surface events. The observer must remain fast and must not
     * call [event], which would recurse.
     */
    @Volatile
    var observer:
        ((category: String, message: String, timeNs: Long) -> Unit)? =
        null

    private val lock = Any()
    private val lines = ArrayDeque<String>(MAX_LINES)
    private val writer = Executors.newSingleThreadExecutor { r ->
        Thread(r, "DuoDiagnostics").apply { isDaemon = true }
    }

    @Volatile
    private var ready = false

    private lateinit var app: Context
    private lateinit var file: File

    fun init(context: Context) {
        if (ready) return

        synchronized(lock) {
            if (ready) return

            app = context.applicationContext
            file = File(
                app.filesDir,
                FILE_NAME,
            )

            runCatching {
                if (file.exists()) {
                    file.readLines()
                        .takeLast(MAX_LINES)
                        .forEach(::pushLocked)
                }
            }

            ready = true
        }

        event(
            "app",
            "session-start version=${BuildConfig.VERSION_NAME} code=${BuildConfig.VERSION_CODE} " +
                "manufacturer=${Build.MANUFACTURER} model=${Build.MODEL} " +
                "device=${Build.DEVICE} sdk=${Build.VERSION.SDK_INT}",
        )

        event(
            "display",
            displaySummary(),
        )
    }

    fun event(
        category: String,
        message: String,
        error: Throwable? = null,
    ) {
        if (!ready) return

        val eventTimeNs =
            System.nanoTime()

        val suffix =
            error?.let {
                " error=${it.javaClass.simpleName}:${it.message}"
            } ?: ""

        val line =
            "${Instant.now()} uptime=${SystemClock.uptimeMillis()} [$category] $message$suffix"

        observer?.let { sink ->
            runCatching {
                sink(
                    category,
                    message + suffix,
                    eventTimeNs,
                )
            }.onFailure {
                // Never recurse through event() if the observation-only tap fails.
                Log.w(
                    TAG,
                    "diagnostic observer failed",
                    it,
                )
            }
        }

        synchronized(lock) {
            pushLocked(line)
        }

        Log.i(
            TAG,
            line,
        )

        writer.execute {
            runCatching {
                rotateIfNeeded()

                file.appendText(
                    line + "\n"
                )
            }.onFailure {
                Log.w(
                    TAG,
                    "diagnostic write failed",
                    it,
                )
            }
        }
    }

    fun report(): String {
        if (!ready) {
            return "DuoDiagnostics not initialised."
        }

        val snapshot =
            synchronized(lock) {
                lines.toList()
            }

        return buildString {
            appendLine(
                "=== Duo Open field diagnostics ==="
            )
            appendLine(
                "generated=${Instant.now()}"
            )
            appendLine(
                "version=${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})"
            )
            appendLine(
                "manufacturer=${Build.MANUFACTURER}"
            )
            appendLine(
                "model=${Build.MODEL}"
            )
            appendLine(
                "device=${Build.DEVICE}"
            )
            appendLine(
                "sdk=${Build.VERSION.SDK_INT}"
            )
            appendLine(
                displaySummary()
            )
            appendLine(
                deviceStateSummary()
            )
            appendLine(
                "events=${snapshot.size}"
            )
            appendLine()

            snapshot.forEach(
                ::appendLine
            )
        }
    }

    fun clear() {
        if (!ready) return

        synchronized(lock) {
            lines.clear()
        }

        writer.execute {
            runCatching {
                file.delete()
            }
        }

        event(
            "app",
            "diagnostics-cleared",
        )
    }

    private fun pushLocked(
        line: String,
    ) {
        while (
            lines.size >= MAX_LINES
        ) {
            lines.removeFirst()
        }

        lines.addLast(line)
    }

    private fun rotateIfNeeded() {
        if (
            !file.exists() ||
            file.length() <= MAX_FILE_BYTES
        ) {
            return
        }

        val bytes =
            file.readBytes()

        val start =
            (
                bytes.size -
                    KEEP_BYTES
                )
                .coerceAtLeast(0)

        file.writeBytes(
            bytes.copyOfRange(
                start,
                bytes.size,
            )
        )
    }

    private fun deviceStateSummary(): String {
        val pm =
            app.getSystemService(
                PowerManager::class.java,
            )

        val km =
            app.getSystemService(
                KeyguardManager::class.java,
            )

        return (
            "interactive=${pm?.isInteractive} " +
                "keyguardLocked=${km?.isKeyguardLocked}"
            )
    }

    private fun displaySummary(): String {
        val dm =
            app.getSystemService(
                DisplayManager::class.java,
            )

        return (
            "displays=" +
                dm.displays.joinToString(
                    " | "
                ) { display ->

                    val mode =
                        runCatching {
                            display.mode
                        }.getOrNull()

                    if (mode == null) {
                        "id=${display.displayId} " +
                            "name=${display.name} " +
                            "state=${display.state}"
                    } else {
                        "id=${display.displayId} " +
                            "name=${display.name} " +
                            "state=${display.state} " +
                            "${mode.physicalWidth}x${mode.physicalHeight}@" +
                            "${"%.1f".format(mode.refreshRate)}Hz"
                    }
                }
            )
    }
}
