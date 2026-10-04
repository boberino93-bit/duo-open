#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

MARKER = "RUNTIME_OPTIMIZATION_CYCLE_A_V1"

SERVICE = "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"
HINGE = "app/src/main/java/com/duoopen/fold/HingeAngleSource.kt"
DIAG = "app/src/main/java/com/duoopen/debug/DuoDiagnostics.kt"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_service(text: str) -> str:
    if f"{MARKER}:SERVICE" in text:
        return text

    duplicate_start = '''        PersistentRuntimeService.ensureRunning(this)\n        instance = this\n\n        PersistentRuntimeService.ensureRunning(\n            this\n        )'''
    single_start = f'''        // {MARKER}:SERVICE — one persistent-runtime start request is sufficient.\n        PersistentRuntimeService.ensureRunning(this)\n        instance = this'''
    text = replace_once(
        text,
        duplicate_start,
        single_start,
        "duplicate PersistentRuntimeService.ensureRunning",
    )

    snapshot_count = text.count("engines.values.toList()")
    if snapshot_count < 3:
        raise RuntimeError(
            "engine iteration optimization: expected at least three values.toList() hot-loop snapshots, "
            f"found {snapshot_count}"
        )
    text = text.replace("engines.values.toList()", "engines.values")

    old_reason = '''        primeContinuityFrameIfNeeded(\n            "hinge:$angle"\n        )\n\n        reconcileContinuityCoverRendering(\n            "hinge:$angle"\n        )'''
    new_reason = f'''        // {MARKER}:REASON — reuse the identical per-drain reason string.\n        val hingeReason =\n            "hinge:$angle"\n\n        primeContinuityFrameIfNeeded(\n            hingeReason\n        )\n\n        reconcileContinuityCoverRendering(\n            hingeReason\n        )'''
    text = replace_once(text, old_reason, new_reason, "hinge reason allocation")
    return text


def transform_hinge(text: str) -> str:
    if f"{MARKER}:HINGE_SELECTOR" in text:
        return text

    old = '''    private fun choose(): Stats? {\n        val reporting = candidates.filter { it.events > 0 }\n        if (reporting.isEmpty()) return null\n        val best = reporting.minWithOrNull(compareBy<Stats> { it.resolution }.thenBy { !it.isStandard })!!\n        val current = active\n        if (current == null || best.resolution < current.resolution) {\n            if (current !== best) Log.i(TAG, "public hinge source: ${best.sensor.name} (res ${best.resolution})")\n            active = best\n            activeSensor = best.sensor\n            return best\n        }\n        return current\n    }'''

    new = f'''    private fun choose(): Stats? {{\n        // {MARKER}:HINGE_SELECTOR\n        // Preserve the exact ordering rule from filter + minWithOrNull while\n        // avoiding a temporary List and Comparator traversal on every sensor sample.\n        var best: Stats? = null\n        for (candidate in candidates) {{\n            if (candidate.events <= 0) continue\n            val incumbent = best\n            if (\n                incumbent == null ||\n                candidate.resolution < incumbent.resolution ||\n                (\n                    candidate.resolution == incumbent.resolution &&\n                        candidate.isStandard &&\n                        !incumbent.isStandard\n                    )\n            ) {{\n                best = candidate\n            }}\n        }}\n\n        val selected = best ?: return null\n        val current = active\n        if (current == null || selected.resolution < current.resolution) {{\n            if (current !== selected) {{\n                Log.i(\n                    TAG,\n                    "public hinge source: ${{selected.sensor.name}} (res ${{selected.resolution}})",\n                )\n            }}\n            active = selected\n            activeSensor = selected.sensor\n            return selected\n        }}\n        return current\n    }}'''

    return replace_once(text, old, new, "allocation-free hinge selector")


def transform_diagnostics(text: str) -> str:
    if f"{MARKER}:DIAGNOSTIC_BATCH" in text:
        return text

    fields_old = '''    private val writer = Executors.newSingleThreadExecutor { r ->\n        Thread(r, "DuoDiagnostics").apply { isDaemon = true }\n    }\n\n    @Volatile\n    private var ready = false'''
    fields_new = f'''    private val writer = Executors.newSingleThreadExecutor {{ r ->\n        Thread(r, "DuoDiagnostics").apply {{ isDaemon = true }}\n    }}\n\n    // {MARKER}:DIAGNOSTIC_BATCH\n    // Event capture remains synchronous and lossless in-memory. File persistence\n    // drains through one queued writer task in bounded batches instead of one\n    // executor task + append syscall per event.\n    private val pendingFileLines = ArrayDeque<String>()\n    private var fileFlushScheduled = false\n\n    @Volatile\n    private var ready = false'''
    text = replace_once(text, fields_old, fields_new, "diagnostic batching fields")

    old_write = '''        synchronized(lock) {\n            pushLocked(line)\n        }\n\n        Log.i(\n            TAG,\n            line,\n        )\n\n        writer.execute {\n            runCatching {\n                rotateIfNeeded()\n\n                file.appendText(\n                    line + "\\n"\n                )\n            }.onFailure {\n                Log.w(\n                    TAG,\n                    "diagnostic write failed",\n                    it,\n                )\n            }\n        }'''
    new_write = '''        val scheduleFlush =\n            synchronized(lock) {\n                pushLocked(line)\n                pendingFileLines.addLast(line)\n                if (fileFlushScheduled) {\n                    false\n                } else {\n                    fileFlushScheduled = true\n                    true\n                }\n            }\n\n        Log.i(\n            TAG,\n            line,\n        )\n\n        if (scheduleFlush) {\n            writer.execute(::flushPendingFileLines)\n        }'''
    text = replace_once(text, old_write, new_write, "per-event diagnostic file write")

    old_clear = '''        synchronized(lock) {\n            lines.clear()\n        }\n\n        writer.execute {'''
    new_clear = '''        synchronized(lock) {\n            lines.clear()\n            pendingFileLines.clear()\n        }\n\n        writer.execute {'''
    text = replace_once(text, old_clear, new_clear, "diagnostic clear pending queue")

    anchor = '''    private fun pushLocked(\n        line: String,\n    ) {'''
    helper = '''    private fun flushPendingFileLines() {\n        while (true) {\n            val batch =\n                synchronized(lock) {\n                    if (pendingFileLines.isEmpty()) {\n                        fileFlushScheduled = false\n                        return\n                    }\n\n                    buildString {\n                        var count = 0\n                        while (\n                            pendingFileLines.isNotEmpty() &&\n                            count < FILE_WRITE_BATCH_LINES\n                        ) {\n                            append(pendingFileLines.removeFirst())\n                            append('\\n')\n                            count++\n                        }\n                    }\n                }\n\n            runCatching {\n                rotateIfNeeded()\n                file.appendText(batch)\n            }.onFailure {\n                Log.w(\n                    TAG,\n                    "diagnostic write failed",\n                    it,\n                )\n            }\n        }\n    }\n\n    private fun pushLocked(\n        line: String,\n    ) {'''
    text = replace_once(text, anchor, helper, "diagnostic batch flush helper")

    const_anchor = '''    private const val KEEP_BYTES = 500_000'''
    const_new = '''    private const val KEEP_BYTES = 500_000\n    private const val FILE_WRITE_BATCH_LINES = 64'''
    text = replace_once(text, const_anchor, const_new, "diagnostic batch size")
    return text


def apply(repo: Path, check_only: bool) -> None:
    transforms = {
        SERVICE: transform_service,
        HINGE: transform_hinge,
        DIAG: transform_diagnostics,
    }
    for rel, transform in transforms.items():
        path = repo / rel
        if not path.exists():
            raise RuntimeError(f"missing source file: {rel}")
        before = path.read_text(encoding="utf-8")
        after = transform(before)
        if MARKER not in after:
            raise RuntimeError(f"{rel}: optimization marker missing after transform")
        if not check_only and after != before:
            path.write_text(after, encoding="utf-8")


def self_test() -> None:
    service_fixture = '''        PersistentRuntimeService.ensureRunning(this)\n        instance = this\n\n        PersistentRuntimeService.ensureRunning(\n            this\n        )\nengines.values.toList()\nengines.values.toList()\nengines.values.toList()\n        primeContinuityFrameIfNeeded(\n            "hinge:$angle"\n        )\n\n        reconcileContinuityCoverRendering(\n            "hinge:$angle"\n        )'''
    transformed = transform_service(service_fixture)
    assert transformed.count("PersistentRuntimeService.ensureRunning") == 1
    assert "values.toList()" not in transformed
    assert transformed.count('"hinge:$angle"') == 1

    hinge_fixture = '''    private fun choose(): Stats? {\n        val reporting = candidates.filter { it.events > 0 }\n        if (reporting.isEmpty()) return null\n        val best = reporting.minWithOrNull(compareBy<Stats> { it.resolution }.thenBy { !it.isStandard })!!\n        val current = active\n        if (current == null || best.resolution < current.resolution) {\n            if (current !== best) Log.i(TAG, "public hinge source: ${best.sensor.name} (res ${best.resolution})")\n            active = best\n            activeSensor = best.sensor\n            return best\n        }\n        return current\n    }'''
    assert "candidates.filter" not in transform_hinge(hinge_fixture)

    print("runtime optimization cycle A self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    apply(Path(args.repo).resolve(), check_only=args.check)
    print(
        "runtime optimization cycle A: " +
        ("source shape verified" if args.check else "applied")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
