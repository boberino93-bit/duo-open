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
 * No screen pixels, notification contents, messages, passwords or keystrokes
 * are added here. This packages the diagnostic files Duo Open already records.
 */
object DebugBundleExporter {
    data class Result(
        val file: File,
        val transitionSessions: Int,
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
        }

        return Result(
            file = output,
            transitionSessions =
                sessions.size,
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

    private const val EXPORT_RETENTION_MS =
        7L * 24L * 60L * 60L * 1_000L
}
