package com.duoopen.overlay

import android.content.Context
import android.content.pm.LauncherApps
import android.os.Process
import android.os.UserManager

/** Best-effort managed-profile package detector; failures degrade to unknown. */
internal object Fold7WorkProfileDetector {
    fun packageExistsInManagedProfile(
        context: Context,
        packageName: String,
    ): Boolean {
        if (packageName.isBlank()) return false

        val launcherApps =
            context.getSystemService(LauncherApps::class.java)
                ?: return false

        val userManager =
            context.getSystemService(UserManager::class.java)
                ?: return false

        return launcherApps.profiles.any { profile ->
            if (profile == Process.myUserHandle()) {
                false
            } else {
                val managed =
                    runCatching {
                        val method =
                            UserManager::class.java.getMethod(
                                "isManagedProfile",
                                Integer.TYPE,
                            )

                        method.invoke(
                            userManager,
                            profile.identifier,
                        ) as Boolean
                    }.getOrDefault(false)

                managed &&
                    runCatching {
                        launcherApps
                            .getActivityList(
                                packageName,
                                profile,
                            )
                            .isNotEmpty()
                    }.getOrDefault(false)
            }
        }
    }
}
