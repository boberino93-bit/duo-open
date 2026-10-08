#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

RESET_MARKER = "GEN12_1_WALLPAPER_RESET_IO"
EXIT_MARKER = "GEN12_1_EXIT_FORENSICS"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def corrected_application_source() -> str:
    return '''package com.duoopen

import android.app.ActivityManager
import android.app.Application
import android.app.ApplicationExitInfo
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

        // GEN12_1_EXIT_FORENSICS: log several exits, not only the newest one.
        // A user/task removal can otherwise hide the crash/OOM/ANR immediately before it.
        val previous =
            runCatching {
                manager.getHistoricalProcessExitReasons(
                    packageName,
                    0,
                    5,
                )
            }.getOrNull()
                ?: return

        previous.forEachIndexed { rank, exit ->
            val ageMs =
                (
                    System.currentTimeMillis() -
                        exit.timestamp
                    ).coerceAtLeast(0L)

            DuoDiagnostics.event(
                "process-exit",
                "rank=$rank reason=${exit.reason}:${exitReasonName(exit.reason)} " +
                    "status=${exit.status} importance=${exit.importance} " +
                    "pss=${exit.pss} rss=${exit.rss} ageMs=$ageMs " +
                    "description=${exit.description ?: "(none)"}",
            )
        }
    }

    private fun exitReasonName(reason: Int): String =
        when (reason) {
            ApplicationExitInfo.REASON_EXIT_SELF -> "EXIT_SELF"
            ApplicationExitInfo.REASON_SIGNALED -> "SIGNALED"
            ApplicationExitInfo.REASON_LOW_MEMORY -> "LOW_MEMORY"
            ApplicationExitInfo.REASON_CRASH -> "CRASH"
            ApplicationExitInfo.REASON_CRASH_NATIVE -> "CRASH_NATIVE"
            ApplicationExitInfo.REASON_ANR -> "ANR"
            ApplicationExitInfo.REASON_INITIALIZATION_FAILURE -> "INITIALIZATION_FAILURE"
            ApplicationExitInfo.REASON_PERMISSION_CHANGE -> "PERMISSION_CHANGE"
            ApplicationExitInfo.REASON_EXCESSIVE_RESOURCE_USAGE -> "EXCESSIVE_RESOURCE_USAGE"
            ApplicationExitInfo.REASON_USER_REQUESTED -> "USER_REQUESTED"
            ApplicationExitInfo.REASON_USER_STOPPED -> "USER_STOPPED"
            ApplicationExitInfo.REASON_DEPENDENCY_DIED -> "DEPENDENCY_DIED"
            ApplicationExitInfo.REASON_OTHER -> "OTHER"
            ApplicationExitInfo.REASON_FREEZER -> "FREEZER"
            ApplicationExitInfo.REASON_PACKAGE_STATE_CHANGE -> "PACKAGE_STATE_CHANGE"
            ApplicationExitInfo.REASON_PACKAGE_UPDATED -> "PACKAGE_UPDATED"
            else -> "UNKNOWN"
        }
}
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()

    duo_app_path = repo / "app/src/main/java/com/duoopen/ui/DuoApp.kt"
    duo_app = duo_app_path.read_text(encoding="utf-8")
    if RESET_MARKER not in duo_app:
        old = '''                onDefaultImage = {
                    WallpaperImage.reset(
                        context.applicationContext
                    )
                },
'''
        new = '''                onDefaultImage = {
                    // GEN12_1_WALLPAPER_RESET_IO
                    // Reset is now a checked durable storage transaction. Keep it
                    // off the Compose/main thread and surface failure without
                    // taking down the activity.
                    scope.launch {
                        val reset =
                            withContext(Dispatchers.IO) {
                                runCatching {
                                    WallpaperImage.reset(
                                        context.applicationContext
                                    )
                                }
                            }

                        reset.onFailure { error ->
                            Toast.makeText(
                                context,
                                "Couldn't reset the wallpaper image: ${error.message ?: error.javaClass.simpleName}",
                                Toast.LENGTH_LONG,
                            ).show()
                        }
                    }
                },
'''
        duo_app = replace_once(duo_app, old, new, "wallpaper reset IO")
        duo_app_path.write_text(duo_app, encoding="utf-8")

    # The first Gen12.1 CI pass caught that the forensic exit-reason helper was
    # generated inside logPreviousProcessExit. Replace this small app bootstrap
    # file deterministically so the helper is class-scoped.
    application_path = repo / "app/src/main/java/com/duoopen/DuoApplication.kt"
    application_path.write_text(corrected_application_source(), encoding="utf-8")

    # Kotlin treats a newline directly after `return` as a complete statement.
    # Keep the pair construction on the return expression explicitly.
    wallpaper_path = repo / "app/src/main/java/com/duoopen/wallpaper/WallpaperImage.kt"
    wallpaper = wallpaper_path.read_text(encoding="utf-8")
    bad_return = '''        return
            ((width * scale).toInt().coerceAtLeast(1)) to
                ((height * scale).toInt().coerceAtLeast(1))
'''
    good_return = '''        return Pair(
            (width * scale).toInt().coerceAtLeast(1),
            (height * scale).toInt().coerceAtLeast(1),
        )
'''
    if bad_return in wallpaper:
        wallpaper = wallpaper.replace(bad_return, good_return, 1)
        wallpaper_path.write_text(wallpaper, encoding="utf-8")

    final_app = duo_app_path.read_text(encoding="utf-8")
    final_application = application_path.read_text(encoding="utf-8")
    final_wallpaper = wallpaper_path.read_text(encoding="utf-8")

    if RESET_MARKER not in final_app or "withContext(Dispatchers.IO)" not in final_app:
        raise RuntimeError("Gen12.1 wallpaper reset IO verifier failed")
    if EXIT_MARKER not in final_application or "private fun exitReasonName" not in final_application:
        raise RuntimeError("Gen12.1 exit-forensics compile correction verifier failed")
    if "return Pair(" not in final_wallpaper:
        raise RuntimeError("Gen12.1 decode-size compile correction verifier failed")

    print("Gen12.1 wallpaper reset IO + compile corrections applied and verified")


if __name__ == "__main__":
    main()
