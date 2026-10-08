#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app/src/full/java/com/duoopen/debug/VisualForensics.kt"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


text = TARGET.read_text(encoding="utf-8")

text = replace_once(
    text,
    '''        val result = runCatching {
            ShizukuBridge.captureForensics(route.id, exclusions, SCALE)
        }.getOrElse { error ->
            return Record(sample, target, actual, panel, "logical-excluded", route.id, physicalId,
                route.state, exclusions.size, "CAPTURE_CALL_EXCEPTION", false,
                "${error.javaClass.simpleName}: ${error.message}", null, 0L, null, null, null, null)
        }

        val bitmap = result.bitmap
        if (!result.ok || result.secureLayers || bitmap == null) {
            bitmap?.recycle()
            return Record(sample, target, actual, panel, "logical-excluded", route.id, physicalId,
                route.state, exclusions.size, result.status, result.secureLayers, result.error,
                null, 0L, null, null, null, null)
        }
''',
    '''        /*
         * The S1H recorder was merged without the proposed captureForensics()
         * bridge transaction. Use the existing read-only logical capture path
         * instead of calling a nonexistent API. A null result can mean backend
         * unavailability or protected content; current ShellProtocol cannot
         * distinguish those causes, so the status remains explicitly ambiguous.
         */
        val bitmap = runCatching {
            ShizukuBridge.capture(route.id, exclusions, SCALE)
        }.getOrElse { error ->
            return Record(sample, target, actual, panel, "logical-excluded", route.id, physicalId,
                route.state, exclusions.size, "CAPTURE_CALL_EXCEPTION", false,
                "${error.javaClass.simpleName}: ${error.message}", null, 0L, null, null, null, null)
        }

        if (bitmap == null) {
            return Record(sample, target, actual, panel, "logical-excluded", route.id, physicalId,
                route.state, exclusions.size, "CAPTURE_UNAVAILABLE_OR_SECURE", false,
                "Current ShizukuBridge CAPTURE transaction does not expose secure/backend attribution",
                null, 0L, null, null, null, null)
        }
''',
    "logical forensic capture fallback",
)

old_physical = '''        val name = "s${sample}-${target}ms-${panel}-physical-screencap.png"
        val file = File(session, name)
        val result = runCatching { ShizukuBridge.capturePhysicalForensics(physicalId, file) }
            .getOrElse { error ->
                runCatching { file.delete() }
                return Record(sample, target, actual, panel, "physical-screencap", route?.id ?: -1, physicalId,
                    route?.state ?: Display.STATE_UNKNOWN, 0, "CAPTURE_CALL_EXCEPTION", false,
                    "${error.javaClass.simpleName}: ${error.message}", null, 0L, null, null, null, null)
            }

        if (!result.ok || !file.isFile || file.length() <= 0L) {
            runCatching { file.delete() }
            return Record(sample, target, actual, panel, "physical-screencap", route?.id ?: -1, physicalId,
                route?.state ?: Display.STATE_UNKNOWN, 0, result.status, false,
                listOfNotNull(result.error, result.commandOutput).joinToString(" | ").ifBlank { null },
                null, 0L, null, null, null, null)
        }

        val bitmap = BitmapFactory.decodeFile(file.absolutePath)
        val metric = bitmap?.let(::metrics)
        bitmap?.recycle()
        return Record(sample, target, actual, panel, "physical-screencap", route?.id ?: -1, physicalId,
            route?.state ?: Display.STATE_UNKNOWN, 0, "CAPTURED", false, result.commandOutput,
            name, file.length(), sha256(file), metric?.mean, metric?.range, metric?.dark)
'''

new_physical = '''        /*
         * capturePhysicalForensics() and its shell transaction were never
         * implemented in the current bridge/protocol. Do not invent a command
         * path or silently bypass Android capture policy. Preserve the forensic
         * record as an explicit unavailable backend until that protocol is
         * designed and reviewed.
         */
        return Record(sample, target, actual, panel, "physical-screencap", route?.id ?: -1, physicalId,
            route?.state ?: Display.STATE_UNKNOWN, 0, "PHYSICAL_BACKEND_UNAVAILABLE", false,
            "Current ShellProtocol has no physical screencap forensic transaction",
            null, 0L, null, null, null, null)
'''

text = replace_once(text, old_physical, new_physical, "physical forensic capture quarantine")

TARGET.write_text(text, encoding="utf-8")
print("Repaired baseline VisualForensics compile break without adding privileged capture behavior")
print(TARGET.relative_to(ROOT))
