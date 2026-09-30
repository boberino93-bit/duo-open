package com.duoopen.shell

/** Binder protocol between the app and [DuoShellService] (runs with Shizuku's ADB privileges). */
object ShellProtocol {
    const val TOKEN = "com.duoopen.shell.DuoShellService"
    const val CALLBACK_TOKEN = "com.duoopen.shell.AngleCallback"

    /** → Bundle{uid, pid, version} */
    const val PING = 1
    /** in: displayId, n, SurfaceControl×n (excluded), scale → Bundle{ok, bitmap, width, height, error, secure} */
    const val CAPTURE = 2
    /** in: action, callback IBinder → starts the Samsung wallpaper angle reader */
    const val START_ANGLES = 3
    const val STOP_ANGLES = 4
    /** → Bundle{state, lines, parsed, rejected, last, angle} */
    const val ANGLE_STATUS = 5

    /**
     * Read-only shell-side display investigation.
     * No display state is changed by this transaction.
     */
    const val DISPLAY_PROBE = 6

    /** One-shot Fold7 service-owned secondary-panel experiment. */
    const val ENABLE_SECONDARY_DISPLAY = 7
    const val RESET_SECONDARY_DISPLAY = 8

    /**
     * in:
     *   boolean enable
     *   if enable: int sourceDisplayId
     *
     * out:
     *   Bundle{ok, error, sourceDisplayId, mirrorSurface}
     *
     * The shell process is privileged enough to ask WindowManagerService
     * for the display mirror. The normal app process receives that
     * SurfaceControl handle and reparents it to its own window root.
     */
    const val MIRROR_DISPLAY = 9

    /**
     * Request an explicit power state for the current logical route
     * to a physical display. Kept behind the Shizuku shell service
     * because MANAGE_DISPLAYS is privileged.
     */
    const val REQUEST_DISPLAY_POWER = 10

    /** callback: float angle, long uptimeMs */
    const val CB_ANGLE = 1
}
