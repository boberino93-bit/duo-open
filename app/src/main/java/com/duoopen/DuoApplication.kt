package com.duoopen

import android.app.ActivityManager
import android.app.Application
import com.duoopen.debug.DuoDiagnostics
import com.duoopen.settings.DuoSettings

class DuoApplication : Application() {
    override fun onCreate() {
        super.onCreate()

        DuoDiagnostics.init(this)
        logPreviousProcessExit()
        DuoSettings.init(this)
        com.duoopen.overlay.OverlayFeature.initProcess(this)
    }

    private fun logPreviousProcessExit() {
        val manager =
            getSystemService(
                ActivityManager::class.java
            ) ?: return

        val previous =
            runCatching {
                manager
                    .getHistoricalProcessExitReasons(
                        packageName,
                        0,
                        3,
                    )
                    .firstOrNull()
            }.getOrNull()
                ?: return

        val ageMs =
            (
                System.currentTimeMillis() -
                    previous.timestamp
                ).coerceAtLeast(
                0L
            )

        DuoDiagnostics.event(
            "process-exit",
            "previous reason=${previous.reason} " +
                "status=${previous.status} " +
                "importance=${previous.importance} " +
                "ageMs=$ageMs " +
                "description=${previous.description ?: "(none)"}",
        )
    }
}
