#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source anchor in {path}, found {count}")
    path.write_text(text.replace(old, new, 1))
    print(f"patched {label}: {path}")


def require(path: Path, needle: str, label: str) -> None:
    text = path.read_text()
    if needle not in text:
        raise SystemExit(f"{label}: required text not found in {path}: {needle!r}")

bridge = ROOT / "app/src/full/java/com/duoopen/shell/ShizukuBridge.kt"
shell = ROOT / "app/src/full/java/com/duoopen/shell/DuoShellService.kt"

old_bridge = '''    /** Receives angles from the shell-side wallpaper log reader. */
    private class AngleCallback(
        private val onAngle: (Float, Long, Long) -> Unit,
    ) : Binder() {

        init {
            attachInterface(
                null,
                ShellProtocol.CALLBACK_TOKEN,
            )
        }

        override fun onTransact(
            code: Int,
            data: Parcel,
            reply: Parcel?,
            flags: Int,
        ): Boolean {
            val binderArrivalTimeNs =
                TransitionClock.nowNs()

            if (code != ShellProtocol.CB_ANGLE) {
                return super.onTransact(
                    code,
                    data,
                    reply,
                    flags,
                )
            }

            data.enforceInterface(
                ShellProtocol.CALLBACK_TOKEN,
            )

            val angle = data.readFloat()

            val sourceUptime =
                if (
                    data.dataAvail() >=
                    Long.SIZE_BYTES
                ) {
                    data.readLong()
                } else {
                    SystemClock.uptimeMillis()
                }

            onAngle(
                angle,
                sourceUptime,
                binderArrivalTimeNs,
            )

            return true
        }
    }

    private var angleCallback:
        AngleCallback? = null

    fun startAngles(
        action: String,
        onAngle: (Float, Long, Long) -> Unit,
    ): Boolean {

        val cb =
            AngleCallback(onAngle)
        angleCallback = cb
        return call(ShellProtocol.START_ANGLES) { p ->
            p.writeString(action)
            p.writeStrongBinder(cb)
        } != null
    }
'''

new_bridge = '''    /** Receives angles from the shell-side wallpaper log reader. */
    private class AngleCallback(
        private val onAngle: (Float, Long, Long, Long) -> Unit,
    ) : Binder() {

        init {
            attachInterface(
                null,
                ShellProtocol.CALLBACK_TOKEN,
            )
        }

        override fun onTransact(
            code: Int,
            data: Parcel,
            reply: Parcel?,
            flags: Int,
        ): Boolean {
            val binderArrivalTimeNs =
                TransitionClock.nowNs()

            if (code != ShellProtocol.CB_ANGLE) {
                return super.onTransact(
                    code,
                    data,
                    reply,
                    flags,
                )
            }

            data.enforceInterface(
                ShellProtocol.CALLBACK_TOKEN,
            )

            val angle = data.readFloat()

            val sourceUptime =
                if (
                    data.dataAvail() >=
                    Long.SIZE_BYTES
                ) {
                    data.readLong()
                } else {
                    SystemClock.uptimeMillis()
                }

            /*
             * Gen-2 readers append a poll sequence after source uptime. A zero
             * sequence preserves compatibility with the current production
             * feed until it is switched to per-poll action identity.
             */
            val pollSequence =
                if (
                    data.dataAvail() >=
                    Long.SIZE_BYTES
                ) {
                    data.readLong()
                } else {
                    0L
                }

            onAngle(
                angle,
                sourceUptime,
                binderArrivalTimeNs,
                pollSequence,
            )

            return true
        }
    }

    private var angleCallback:
        AngleCallback? = null

    /**
     * Compatibility entry point for the current feed. Gen-2 callers should use
     * [startAnglesSequenced] so the poll sequence survives shell -> Binder.
     */
    fun startAngles(
        action: String,
        onAngle: (Float, Long, Long) -> Unit,
    ): Boolean =
        startAnglesSequenced(
            action = action,
        ) { angle, sourceUptime, binderArrivalTimeNs, _ ->
            onAngle(
                angle,
                sourceUptime,
                binderArrivalTimeNs,
            )
        }

    fun startAnglesSequenced(
        actionPrefix: String,
        onAngle: (Float, Long, Long, Long) -> Unit,
    ): Boolean {
        val cb =
            AngleCallback(onAngle)
        angleCallback = cb
        return call(ShellProtocol.START_ANGLES) { p ->
            p.writeString(actionPrefix)
            p.writeStrongBinder(cb)
        } != null
    }
'''

replace_once(bridge, old_bridge, new_bridge, "Shizuku sequenced angle callback")

start = shell.read_text().index('    private class AngleReader(private val action: String, private val callback: IBinder) {')
end_marker = '\n    private companion object {\n        /** Shizuku asks user services to exit with this code. */'
end = shell.read_text().index(end_marker, start)
text = shell.read_text()
old_reader = text[start:end]

new_reader = r'''    private class AngleReader(
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
'''

if old_reader.count('private class AngleReader') != 1:
    raise SystemExit('DuoShellService: could not isolate exactly one AngleReader block')
shell.write_text(text[:start] + new_reader + text[end:])
print(f"patched shell reader sequence identity: {shell}")

# Postconditions: old callers still compile, new caller contract is available.
require(bridge, 'fun startAnglesSequenced(', 'bridge postcondition')
require(bridge, 'pollSequence,', 'bridge pollSequence postcondition')
require(shell, 'p.writeLong(parsedLine.pollSequence)', 'shell callback postcondition')
require(shell, 'action.startsWith("$actionPrefix:")', 'shell action correlation postcondition')
require(shell, 'putLong("pollSequence", lastPollSequence)', 'shell diagnostics postcondition')

print('Gen-2 Batch B patch complete.')
