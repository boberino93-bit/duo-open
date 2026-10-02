#!/usr/bin/env python3
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "payload_alpha2"

def read(path):
    return (ROOT / path).read_text()

def write(path, text):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"ALPHA2 FAIL-CLOSED: {label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)

def between(text, start, end, replacement, label):
    i = text.find(start)
    if i < 0:
        raise SystemExit(f"ALPHA2 FAIL-CLOSED: {label}: start marker missing")
    j = text.find(end, i + len(start))
    if j < 0:
        raise SystemExit(f"ALPHA2 FAIL-CLOSED: {label}: end marker missing")
    return text[:i] + replacement + text[j:]

# 1) Exact Gen3 opening owner remains, but opening renderer delegates to the
#    already-proven Fold7 PanelEngine snapshot/shader backend.
shutil.copy2(
    PAYLOAD / "app/src/full/java/com/duoopen/overlay/Fold7Gen3VisualCoordinator.kt",
    ROOT / "app/src/full/java/com/duoopen/overlay/Fold7Gen3VisualCoordinator.kt",
)

# 2) Rewire concrete opening renderer beneath Gen3 exact owner.
path = "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"
s = read(path)
start = "    private fun reconcileContinuityCoverRendering(\n"
end = "    /** Samsung continuous angle via Shizuku + fold wallpaper, when everything lines up. */\n"
replacement = '''    private fun reconcileContinuityCoverRendering(\n        reason: String,\n    ) {\n        if (!::continuity.isInitialized) {\n            return\n        }\n\n        val privilegedReady =\n            ShizukuBridge.ready &&\n                continuity.renderOwnershipEnabled\n\n        /*\n         * Alpha2 keeps Gen3 as the semantic/exact owner, but restores the\n         * validated Fold7 snapshot/shader renderer for OPENING. The Alpha1\n         * field trace showed its LiveBlur host failing to attach on every\n         * accepted opening attempt.\n         */\n        for (engine in engines.values.toList()) {\n            engine.setContinuityCoverOwned(\n                owned =\n                    privilegedReady &&\n                        engine.isFold7CoverGeometryNow(),\n                reason = "gen3:$reason",\n            )\n        }\n\n        if (::gen3Visual.isInitialized) {\n            gen3Visual.reconcile(\n                state = continuity.state,\n                closingVisible =\n                    continuity.visualMirrorActive,\n                privilegedReady =\n                    privilegedReady,\n                reason =\n                    reason,\n            )\n        }\n\n        val openingDemand =\n            ::gen3Visual.isInitialized &&\n                gen3Visual.openingVisualDemandActive\n\n        val openingHostDisplayId =\n            if (::gen3Visual.isInitialized) {\n                gen3Visual.openingHostDisplayId\n            } else {\n                null\n            }\n\n        for (engine in engines.values.toList()) {\n            val runOpeningRenderer =\n                privilegedReady &&\n                    openingDemand &&\n                    engine.isFold7CoverGeometryNow() &&\n                    engine.display.displayId ==\n                        openingHostDisplayId\n\n            if (runOpeningRenderer) {\n                engine.beginContinuityOpeningVisual(\n                    "gen3-opening-snapshot:$reason"\n                )\n            } else {\n                engine.endContinuityOpeningVisual(\n                    "gen3-opening-not-owner:$reason"\n                )\n            }\n        }\n    }\n\n'''
s = between(s, start, end, replacement, "FoldOverlayService renderer reconciliation")
write(path, s)

# 3) Add wake-path causal timing without changing wake policy/thresholds.
path = "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"
s = read(path)
old = '''    private fun wakeInner(\n        generation: Long,\n    ) {\n        if (\n            !controller.isGenerationCurrent(generation) ||\n            !ShizukuBridge.ready\n        ) {\n            return\n        }\n\n        scope.launch(Dispatchers.IO) {\n            if (!controller.isGenerationCurrent(generation)) {\n                return@launch\n            }\n\n            val result =\n                runCatching {\n                    ShizukuBridge.wakeInnerDisplay()\n                }.getOrNull()\n\n            DuoDiagnostics.event(\n                "fold7-state",\n                "inner-wake generation=$generation " +\n                    "ok=${result?.getBoolean(\"ok\", false) == true} " +\n                    "physical=${result?.getLong(\"physicalDisplayId\", -1L) ?: -1L} " +\n                    "error=${result?.getString(\"error\")}",\n            )\n        }\n    }\n'''
new = '''    private fun wakeInner(\n        generation: Long,\n    ) {\n        if (\n            !controller.isGenerationCurrent(generation) ||\n            !ShizukuBridge.ready\n        ) {\n            return\n        }\n\n        val queuedAtNs =\n            SystemClock.elapsedRealtimeNanos()\n\n        scope.launch(Dispatchers.IO) {\n            val startedAtNs =\n                SystemClock.elapsedRealtimeNanos()\n\n            if (!controller.isGenerationCurrent(generation)) {\n                return@launch\n            }\n\n            val result =\n                runCatching {\n                    ShizukuBridge.wakeInnerDisplay()\n                }.getOrNull()\n\n            val completedAtNs =\n                SystemClock.elapsedRealtimeNanos()\n\n            val queueMs =\n                (startedAtNs - queuedAtNs) /\n                    1_000_000.0\n\n            val totalMs =\n                (completedAtNs - queuedAtNs) /\n                    1_000_000.0\n\n            DuoDiagnostics.event(\n                "fold7-state",\n                "inner-wake generation=$generation " +\n                    "ok=${result?.getBoolean(\"ok\", false) == true} " +\n                    "physical=${result?.getLong(\"physicalDisplayId\", -1L) ?: -1L} " +\n                    "queueMs=${\"%.3f\".format(queueMs)} " +\n                    "shellLatencyMs=${result?.getLong(\"latencyMs\", -1L) ?: -1L} " +\n                    "totalMs=${\"%.3f\".format(totalMs)} " +\n                    "error=${result?.getString(\"error\")}",\n            )\n        }\n    }\n'''
s = replace_once(s, old, new, "wake causal instrumentation")
write(path, s)

# 4) Add diagnostics upload transport source files.
for rel in [
    "app/src/main/java/com/duoopen/debug/DebugBundleUploader.kt",
    "app/src/main/java/com/duoopen/debug/DiagnosticReceiptStore.kt",
    "app/src/test/java/com/duoopen/debug/DebugBundleUploaderTest.kt",
]:
    src = PAYLOAD / rel
    dst = ROOT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

# 5) BuildConfig endpoint configuration + Alpha2 version.
path = "app/build.gradle.kts"
s = read(path)
old = '''val keystoreProps = Properties().apply {\n    val f = rootProject.file("keystore.properties")\n    if (f.exists()) f.inputStream().use { load(it) }\n}\n\nandroid {\n'''
new = '''val keystoreProps = Properties().apply {\n    val f = rootProject.file("keystore.properties")\n    if (f.exists()) f.inputStream().use { load(it) }\n}\n\nfun buildConfigString(value: String): String =\n    "\\\"" +\n        value\n            .replace("\\\\", "\\\\\\\\")\n            .replace("\\\"", "\\\\\\\"") +\n        "\\\""\n\nval diagnosticUploadUrl =\n    providers.gradleProperty("DUO_DIAGNOSTIC_UPLOAD_URL")\n        .orElse(providers.environmentVariable("DUO_DIAGNOSTIC_UPLOAD_URL"))\n        .orElse("")\n        .get()\n\nval diagnosticIngestKey =\n    providers.gradleProperty("DUO_DIAGNOSTIC_INGEST_KEY")\n        .orElse(providers.environmentVariable("DUO_DIAGNOSTIC_INGEST_KEY"))\n        .orElse("")\n        .get()\n\nandroid {\n'''
s = replace_once(s, old, new, "Gradle diagnostic configuration")
s = replace_once(s, 'versionCode = 38\n        versionName = "3.0.0-alpha1-zfold7"', 'versionCode = 39\n        versionName = "3.0.0-alpha2-zfold7"\n\n        buildConfigField("String", "DIAGNOSTIC_UPLOAD_URL", buildConfigString(diagnosticUploadUrl))\n        buildConfigField("String", "DIAGNOSTIC_INGEST_KEY", buildConfigString(diagnosticIngestKey))', "Alpha2 version/build config")
write(path, s)

# 6) INTERNET permission for explicit diagnostic upload.
path = "app/src/main/AndroidManifest.xml"
s = read(path)
old = '''<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n\n    <uses-feature\n'''
new = '''<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n\n    <uses-permission android:name="android.permission.INTERNET" />\n\n    <uses-feature\n'''
s = replace_once(s, old, new, "INTERNET permission")
write(path, s)

# 7) Add UI button + status/receipt semantics.
path = "app/src/main/java/com/duoopen/ui/ControlSheet.kt"
s = read(path)
s = replace_once(
    s,
    '''    onTestOverlay: () -> Unit,\n    onExportDebugBundle: () -> Unit,\n    onDismiss: () -> Unit,\n''',
    '''    onTestOverlay: () -> Unit,\n    onExportDebugBundle: () -> Unit,\n    onSendDebugBundle: () -> Unit,\n    diagnosticUploadEnabled: Boolean,\n    diagnosticUploadStatus: String?,\n    onDismiss: () -> Unit,\n''',
    "ControlSheet diagnostic parameters",
)
old = '''            Button(\n                onClick =\n                    onExportDebugBundle,\n                modifier =\n                    Modifier.fillMaxWidth(),\n            ) {\n                Text(\n                    "Export debug bundle"\n                )\n            }\n\n            Spacer(\n                Modifier.height(6.dp)\n            )\n\n            Hint(\n                "Creates one ZIP containing the persistent field log, an in-memory diagnostics report, and the newest Transition Lab JSONL sessions. Share or save that ZIP, then upload it to the supervisor."\n            )\n'''
new = '''            Button(\n                onClick =\n                    onExportDebugBundle,\n                modifier =\n                    Modifier.fillMaxWidth(),\n            ) {\n                Text(\n                    "Export debug bundle"\n                )\n            }\n\n            Spacer(\n                Modifier.height(6.dp)\n            )\n\n            OutlinedButton(\n                onClick =\n                    onSendDebugBundle,\n                enabled =\n                    diagnosticUploadEnabled,\n                modifier =\n                    Modifier.fillMaxWidth(),\n            ) {\n                Text(\n                    "Send diagnostic data"\n                )\n            }\n\n            Spacer(\n                Modifier.height(6.dp)\n            )\n\n            Hint(\n                diagnosticUploadStatus\n                    ?: if (diagnosticUploadEnabled) {\n                        "Sends the same privacy-limited ZIP and only reports success after the server returns a checksum-matched Artifactory receipt."\n                    } else {\n                        "Diagnostic upload is not configured in this build. Manual export still works."\n                    },\n                warn =\n                    diagnosticUploadStatus\n                        ?.startsWith("Send failed") == true,\n            )\n\n            Hint(\n                "Creates one ZIP containing the persistent field log, an in-memory diagnostics report, and the newest Transition Lab JSONL sessions. No screen pixels, messages, passwords or keystrokes are intentionally added by the exporter."\n            )\n'''
s = replace_once(s, old, new, "ControlSheet diagnostic controls")
write(path, s)

path = "app/src/main/java/com/duoopen/ui/DuoApp.kt"
s = read(path)
s = replace_once(
    s,
    'import com.duoopen.debug.DebugBundleExporter\n',
    'import com.duoopen.debug.DebugBundleExporter\nimport com.duoopen.debug.DebugBundleUploader\nimport com.duoopen.debug.DiagnosticReceiptStore\n',
    "DuoApp diagnostic imports",
)
s = replace_once(
    s,
    '''    var showSheet by\n        remember {\n            mutableStateOf(false)\n        }\n\n    Box(\n''',
    '''    var showSheet by\n        remember {\n            mutableStateOf(false)\n        }\n\n    var diagnosticUploadStatus by\n        remember(context) {\n            mutableStateOf(\n                DiagnosticReceiptStore\n                    .last(context)\n                    ?.let { receipt ->\n                        "Last received: ${receipt.diagnosticId} · ${receipt.sha256.take(12)}…"\n                    }\n            )\n        }\n\n    Box(\n''',
    "DuoApp diagnostic status state",
)
needle = '''                onExportDebugBundle = {\n                    scope.launch {\n                        val result =\n                            withContext(\n                                Dispatchers.IO\n                            ) {\n                                /*\n                                 * Flush FULL_LAB first so the exported JSONL\n                                 * includes everything queued before the tap.\n                                 */\n                                OverlayFeature\n                                    .flushDebugLogs()\n\n                                DebugBundleExporter\n                                    .create(\n                                        context.applicationContext\n                                    )\n                            }\n\n                        runCatching {\n                            DebugBundleExporter\n                                .share(\n                                    context,\n                                    result.file,\n                                )\n                        }.onFailure {\n                            Toast.makeText(\n                                context,\n                                "Couldn't share debug bundle",\n                                Toast.LENGTH_LONG,\n                            ).show()\n                        }\n                    }\n                },\n                onDismiss = {\n'''
replacement = '''                onExportDebugBundle = {\n                    scope.launch {\n                        val result =\n                            withContext(\n                                Dispatchers.IO\n                            ) {\n                                /*\n                                 * Flush FULL_LAB first so the exported JSONL\n                                 * includes everything queued before the tap.\n                                 */\n                                OverlayFeature\n                                    .flushDebugLogs()\n\n                                DebugBundleExporter\n                                    .create(\n                                        context.applicationContext\n                                    )\n                            }\n\n                        runCatching {\n                            DebugBundleExporter\n                                .share(\n                                    context,\n                                    result.file,\n                                )\n                        }.onFailure {\n                            Toast.makeText(\n                                context,\n                                "Couldn't share debug bundle",\n                                Toast.LENGTH_LONG,\n                            ).show()\n                        }\n                    }\n                },\n                onSendDebugBundle = {\n                    diagnosticUploadStatus =\n                        "Sending diagnostic data…"\n\n                    scope.launch {\n                        val upload =\n                            withContext(\n                                Dispatchers.IO\n                            ) {\n                                runCatching {\n                                    OverlayFeature\n                                        .flushDebugLogs()\n\n                                    val bundle =\n                                        DebugBundleExporter\n                                            .create(\n                                                context.applicationContext\n                                            )\n\n                                    DebugBundleUploader\n                                        .upload(\n                                            context.applicationContext,\n                                            bundle.file,\n                                        )\n                                }\n                            }\n\n                        upload\n                            .onSuccess { receipt ->\n                                diagnosticUploadStatus =\n                                    "Diagnostic received: ${receipt.diagnosticId} · ${receipt.sha256.take(12)}…"\n                            }\n                            .onFailure { error ->\n                                diagnosticUploadStatus =\n                                    "Send failed: ${error.message ?: error.javaClass.simpleName}"\n                            }\n                    }\n                },\n                diagnosticUploadEnabled =\n                    DebugBundleUploader\n                        .isConfigured(),\n                diagnosticUploadStatus =\n                    diagnosticUploadStatus,\n                onDismiss = {\n'''
s = replace_once(s, needle, replacement, "DuoApp send-diagnostic callback")
write(path, s)

print("GEN3 ALPHA2 PATCH: APPLIED")
