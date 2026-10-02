package com.duoopen.debug

import android.content.Context
import org.json.JSONObject

object DiagnosticReceiptStore {
    data class Receipt(
        val diagnosticId: String,
        val sha256: String,
        val artifactPath: String,
        val receivedAt: String,
        val version: String,
        val versionCode: Int,
    )

    private const val PREFS = "duoopen-diagnostic-receipts"
    private const val KEY_LAST = "last-receipt"

    fun save(context: Context, receipt: Receipt) {
        val value = JSONObject()
            .put("diagnosticId", receipt.diagnosticId)
            .put("sha256", receipt.sha256)
            .put("artifactPath", receipt.artifactPath)
            .put("receivedAt", receipt.receivedAt)
            .put("version", receipt.version)
            .put("versionCode", receipt.versionCode)
            .toString()

        context.applicationContext
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_LAST, value)
            .apply()
    }

    fun last(context: Context): Receipt? {
        val raw = context.applicationContext
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_LAST, null)
            ?: return null

        return runCatching {
            val json = JSONObject(raw)
            Receipt(
                diagnosticId = json.getString("diagnosticId"),
                sha256 = json.getString("sha256"),
                artifactPath = json.getString("artifactPath"),
                receivedAt = json.getString("receivedAt"),
                version = json.getString("version"),
                versionCode = json.getInt("versionCode"),
            )
        }.getOrNull()
    }
}
