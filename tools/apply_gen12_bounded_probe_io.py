#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, found {count}")
    file.write_text(text.replace(old, new, 1))
    print(f"patched {path}")


SERVICE = "app/src/full/java/com/duoopen/shell/DuoShellService.kt"

replace_once(
    SERVICE,
    '''    private fun runProbe(
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
                "timeout after 3000ms\\n" +
                    output.take(
                        PROBE_OUTPUT_LIMIT
                    )
                )
        }

        return (
            "exit=${process.exitValue()}\\n" +
                output.take(
                    PROBE_OUTPUT_LIMIT
                )
            )
    }
''',
    '''    private fun runProbe(
        command: String,
    ): String {
        val process =
            ProcessBuilder(
                "sh",
                "-c",
                "$command 2>&1",
            ).start()

        /*
         * Drain stdout concurrently with waitFor(). The old implementation did
         * readText() first, which blocks until EOF and therefore made the later
         * three-second waitFor timeout ineffective. A slow/hung dumpsys fallback
         * could consequently occupy the serialized Gen4 cover lane indefinitely.
         *
         * Keep draining after the retained prefix is full so the child cannot
         * deadlock on a full pipe. The StringBuffer gives the timeout thread a
         * safe snapshot even if the reader needs a moment to unwind after kill.
         */
        val output = StringBuffer(PROBE_OUTPUT_LIMIT)
        val reader =
            Thread(
                {
                    runCatching {
                        process.inputStream
                            .bufferedReader()
                            .use { input ->
                                val buffer = CharArray(2_048)
                                while (true) {
                                    val count = input.read(buffer)
                                    if (count < 0) break

                                    val remaining =
                                        (PROBE_OUTPUT_LIMIT - output.length)
                                            .coerceAtLeast(0)
                                    if (remaining > 0) {
                                        output.append(
                                            buffer,
                                            0,
                                            count.coerceAtMost(remaining),
                                        )
                                    }
                                }
                            }
                    }
                },
                "duo-probe-reader",
            ).apply {
                isDaemon = true
                start()
            }

        val finished =
            process.waitFor(
                PROBE_TIMEOUT_MS,
                TimeUnit.MILLISECONDS,
            )

        if (!finished) {
            process.destroyForcibly()
        }

        runCatching {
            reader.join(PROBE_READER_JOIN_MS)
        }

        val captured = output.toString()

        return if (finished) {
            "exit=${process.exitValue()}\\n$captured"
        } else {
            "timeout after ${PROBE_TIMEOUT_MS}ms\\n$captured"
        }
    }
''',
)

replace_once(
    SERVICE,
    '''        const val PROBE_OUTPUT_LIMIT =
            16_000

        val FAMILIES = listOf("android.window.ScreenCaptureInternal", "android.window.ScreenCapture")
''',
    '''        const val PROBE_OUTPUT_LIMIT =
            16_000
        const val PROBE_TIMEOUT_MS =
            3_000L
        const val PROBE_READER_JOIN_MS =
            250L

        val FAMILIES = listOf("android.window.ScreenCaptureInternal", "android.window.ScreenCapture")
''',
)

print("Gen12 bounded probe I/O patch applied successfully")
