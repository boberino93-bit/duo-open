package com.duoopen.overlay

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.content.ContextCompat
import com.duoopen.R
import com.duoopen.debug.DuoDiagnostics

class PersistentRuntimeService :
    Service() {

    override fun onCreate() {
        super.onCreate()

        val manager =
            getSystemService(
                NotificationManager::class.java
            )

        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID,
                "Duo Open continuity",
                NotificationManager.IMPORTANCE_LOW,
            ).apply {
                description =
                    "Keeps Fold7 display continuity ready during fold transitions."
                setShowBadge(false)
            }
        )

        val notification =
            Notification.Builder(
                this,
                CHANNEL_ID,
            )
                .setSmallIcon(
                    R.mipmap.ic_launcher
                )
                .setContentTitle(
                    "Duo Open is ready"
                )
                .setContentText(
                    "Fold7 continuity controller is running."
                )
                .setCategory(
                    Notification.CATEGORY_SERVICE
                )
                .setOngoing(true)
                .build()

        if (
            Build.VERSION.SDK_INT >=
                34
        ) {
            startForeground(
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE,
            )
        } else {
            startForeground(
                NOTIFICATION_ID,
                notification,
            )
        }

        DuoDiagnostics.event(
            "runtime",
            "foreground continuity runtime started",
        )
    }

    override fun onStartCommand(
        intent: Intent?,
        flags: Int,
        startId: Int,
    ): Int =
        START_STICKY

    override fun onBind(
        intent: Intent?,
    ): IBinder? =
        null

    override fun onDestroy() {
        DuoDiagnostics.event(
            "runtime",
            "foreground continuity runtime destroyed",
        )

        super.onDestroy()
    }

    companion object {
        private const val CHANNEL_ID =
            "duoopen_fold7_continuity"

        private const val NOTIFICATION_ID =
            1320

        fun ensureRunning(
            context: Context,
        ) {
            runCatching {
                ContextCompat.startForegroundService(
                    context,
                    Intent(
                        context,
                        PersistentRuntimeService::class.java,
                    ),
                )
            }.onFailure { error ->
                DuoDiagnostics.event(
                    "runtime",
                    "foreground start failed",
                    error,
                )
            }
        }
    }
}
