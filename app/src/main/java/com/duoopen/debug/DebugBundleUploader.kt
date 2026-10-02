package com.duoopen.debug

import android.content.Context
import com.duoopen.BuildConfig
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/** Blocking transport; call from Dispatchers.IO / background work only. */
object DebugBundleUploader {
    class UploadException(message: String) : Exception(message)

    fun isConfigured(): Boolean =
        BuildConfig.DIAGNOSTIC_UPLOAD_URL.trim().startsWith("https://")

    fun upload(context: Context, file: File): DiagnosticReceiptStore.Receipt {
        require(file.isFile && file.length() > 0L) { "Diagnostic ZIP is empty" }

        val endpoint = BuildConfig.DIAGNOSTIC_UPLOAD_URL.trim()
        if (!endpoint.startsWith("https://")) {
            throw UploadException("Diagnostic upload endpoint is not configured")
        }

        val localSha256 = sha256(file)
        val connection = (URL(endpoint).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 12_000
            readTimeout = 25_000
            doOutput = true
            instanceFollowRedirects = false
            setFixedLengthStreamingMode(file.length())
            setRequestProperty("Content-Type", "application/zip")
            setRequestProperty("Accept", "application/json")
            setRequestProperty("X-Duo-Sha256", localSha256)
            setRequestProperty("X-Duo-Version", BuildConfig.VERSION_NAME)
            setRequestProperty("X-Duo-Version-Code", BuildConfig.VERSION_CODE.toString())
            setRequestProperty("X-Duo-Platform", "android")

            val ingestKey = BuildConfig.DIAGNOSTIC_INGEST_KEY.trim()
            if (ingestKey.isNotEmpty()) {
                setRequestProperty("Authorization", "Bearer $ingestKey")
            }
        }

        try {
            connection.outputStream.use { output ->
                file.inputStream().buffered().use { input ->
                    input.copyTo(output)
                }
            }

            val status = connection.responseCode
            val responseText =
                (if (status in 200..299) connection.inputStream else connection.errorStream)
                    ?.bufferedReader()
                    ?.use { it.readText() }
                    .orEmpty()

            if (status != HttpURLConnection.HTTP_CREATED) {
                throw UploadException("Diagnostic relay returned HTTP $status: ${responseText.take(400)}")
            }

            val json = runCatching { JSONObject(responseText) }
                .getOrElse { throw UploadException("Diagnostic relay returned an invalid receipt") }

            val received = json.optBoolean("received", false)
            val diagnosticId = json.optString("diagnosticId", "").trim()
            val remoteSha256 = json.optString("sha256", "").trim().lowercase()
            val artifactPath = json.optString("artifactPath", "").trim()
            val receivedAt = json.optString("receivedAt", "").trim()

            if (!received || diagnosticId.isEmpty() || artifactPath.isEmpty()) {
                throw UploadException("Diagnostic relay did not provide a complete receipt")
            }
            if (remoteSha256 != localSha256) {
                throw UploadException("Diagnostic receipt checksum does not match the local ZIP")
            }

            return DiagnosticReceiptStore.Receipt(
                diagnosticId = diagnosticId,
                sha256 = localSha256,
                artifactPath = artifactPath,
                receivedAt = receivedAt,
                version = BuildConfig.VERSION_NAME,
                versionCode = BuildConfig.VERSION_CODE,
            ).also { DiagnosticReceiptStore.save(context, it) }
        } finally {
            connection.disconnect()
        }
    }

    fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().buffered().use { input ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                val read = input.read(buffer)
                if (read <= 0) break
                digest.update(buffer, 0, read)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it.toInt() and 0xff) }
    }
}
