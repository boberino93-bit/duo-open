package com.duoopen.debug

import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import com.duoopen.BuildConfig
import java.io.File
import java.io.FileInputStream
import java.time.Instant
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/**
 * User-visible export of local diagnostic evidence.
 *
 * S1H builds deliberately include the recent visual-forensics screenshot
 * sessions requested for Fold7 field diagnosis. Secure logical frames are not
 * persisted by VisualForensics; physical screencap output remains subject to
 * Android/enterprise screenshot policy and is packaged exactly as produced by
 * the platform together with capture-policy context and per-frame manifests.
 */
object DebugBundleExporter {
    data class Result(
        val file: File,
        val transitionSessions: Int,
        val visualForensicSessions: Int,
    )

    fun create(
        context: Context,
    ): Result {
        val app =
            context.applicationContext

        val exportDirectory =
            File(
                app.cacheDir,
                "debug-exports",
            ).apply {
                mkdirs()
            }

        pruneOldExports(
            exportDirectory
        )

        val output =
            File(
                exportDirectory,
                "duoopen-debug-${System.currentTimeMillis()}.zip",
            )

        val transitionDirectory =
            File(
                app.filesDir,
                "transition-lab",
            )

        val sessions =
            transitionDirectory
                .listFiles()
                .orEmpty()
                .filter {
                    it.isFile &&
                        it.name.startsWith(
                            "transition-"
                        ) &&
                        it.name.endsWith(
                            ".jsonl"
                        )
                }
                .sortedByDescending {
                    it.lastModified()
                }
                .take(
                    MAX_TRANSITION_SESSIONS
                )
                .sortedBy {
                    it.lastModified()
                }

        val visualSessions =
            File(
                app.filesDir,
                "visual-forensics",
            ).listFiles()
                .orEmpty()
                .filter { it.isDirectory }
                .sortedByDescending { it.lastModified() }
                .take(MAX_VISUAL_FORENSIC_SESSIONS)
                .sortedBy { it.lastModified() }

        ZipOutputStream(
            output.outputStream()
                .buffered()
        ).use { zip ->
            zip.putText(
                name =
                    "export-info.txt",
                text =
                    buildString {
                        appendLine(
                            "Duo Open debug bundle"
                        )
                        appendLine(
                            "generated=${Instant.now()}"
                        )
                        appendLine(
                            "version=${BuildConfig.VERSION_NAME}"
                        )
                        appendLine(
                            "versionCode=${BuildConfig.VERSION_CODE}"
                        )
                        appendLine(
                            "applicationId=${BuildConfig.APPLICATION_ID}"
                        )
                        appendLine(
                            "transitionSessions=${sessions.size}"
                        )
                        appendLine(
                            "visualForensicSessions=${visualSessions.size}"
                        )
                        appendLine(
                            "visualForensics=ENABLED_IN_S1H_EXPERIMENTAL_BUILD"
                        )
                        appendLine(
                            "visualForensicsNote=Recent timestamped panel screenshots, raw capture outcomes, and screen-capture policy context are included when available."
                        )
                    },
            )

            /*
             * report() comes from the in-memory ring buffer, so it also covers
             * events that might not yet have reached the persistent field file.
             */
            zip.putText(
                name =
                    "field-report.txt",
                text =
                    DuoDiagnostics.report(),
            )

            zip.putFileIfPresent(
                source =
                    File(
                        app.filesDir,
                        "duoopen-field-debug.log",
                    ),
                name =
                    "duoopen-field-debug.log",
            )

            sessions.forEach { session ->
                zip.putFileIfPresent(
                    source =
                        session,
                    name =
                        "transition-lab/${session.name}",
                )
            }

            visualSessions.forEach { session ->
                zip.putDirectory(
                    directory = session,
                    prefix = "visual-forensics/${session.name}",
                )
            }
        }

        return Result(
            file = output,
            transitionSessions =
                sessions.size,
            visualForensicSessions =
                visualSessions.size,
        )
    }

    fun share(
        context: Context,
        file: File,
    ) {
        val authority =
            "${BuildConfig.APPLICATION_ID}.debug-files"

        val uri =
            FileProvider.getUriForFile(
                context,
                authority,
                file,
            )

        val send =
            Intent(
                Intent.ACTION_SEND
            ).apply {
                type =
                    "application/zip"

                putExtra(
                    Intent.EXTRA_STREAM,
                    uri,
                )

                addFlags(
                    Intent.FLAG_GRANT_READ_URI_PERMISSION
                )
            }

        context.startActivity(
            Intent.createChooser(
                send,
                "Share Duo Open debug bundle",
            )
        )
    }

    private fun pruneOldExports(
        directory: File,
    ) {
        val cutoff =
            System.currentTimeMillis() -
                EXPORT_RETENTION_MS

        directory
            .listFiles()
            .orEmpty()
            .filter {
                it.isFile &&
                    it.lastModified() <
                    cutoff
            }
            .forEach {
                runCatching {
                    it.delete()
                }
            }
    }

    private fun ZipOutputStream.putDirectory(
        directory: File,
        prefix: String,
    ) {
        directory.walkTopDown()
            .filter { it.isFile && it.length() > 0L }
            .sortedBy { it.relativeTo(directory).invariantSeparatorsPath }
            .forEach { source ->
                val relative =
                    source.relativeTo(directory)
                        .invariantSeparatorsPath
                putFileIfPresent(
                    source = source,
                    name = "$prefix/$relative",
                )
            }
    }

    private fun ZipOutputStream.putText(
        name: String,
        text: String,
    ) {
        putNextEntry(
            ZipEntry(name)
        )

        write(
            text.toByteArray(
                Charsets.UTF_8
            )
        )

        closeEntry()
    }

    private fun ZipOutputStream.putFileIfPresent(
        source: File,
        name: String,
    ) {
        if (
            !source.isFile ||
            source.length() <= 0L
        ) {
            return
        }

        putNextEntry(
            ZipEntry(name)
        )

        FileInputStream(
            source
        ).use {
            it.copyTo(this)
        }

        closeEntry()
    }

    private const val MAX_TRANSITION_SESSIONS =
        8

    private const val MAX_VISUAL_FORENSIC_SESSIONS =
        5

    private const val EXPORT_RETENTION_MS =
        7L * 24L * 60L * 60L * 1_000L
}
