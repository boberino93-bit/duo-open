package com.duoopen.shell

object ShellProtocol {
    const val TOKEN = "com.duoopen.shell.DuoShellService"
    const val CALLBACK_TOKEN = "com.duoopen.shell.AngleCallback"

    const val PING = 1
    const val CAPTURE = 2
    const val START_ANGLES = 3
    const val STOP_ANGLES = 4
    const val ANGLE_STATUS = 5
    const val DISPLAY_PROBE = 6
    const val ENABLE_SECONDARY_DISPLAY = 7
    const val RESET_SECONDARY_DISPLAY = 8
    const val MIRROR_DISPLAY = 9
    const val REQUEST_DISPLAY_POWER = 10
    const val RESOLVE_COVER_DISPLAY = 11
    const val WAKE_INNER_DISPLAY = 12

    // Generation-2 privileged resource ownership. Legacy codes remain for fallback.
    const val OPEN_MIRROR_SESSION = 13
    const val MIRROR_DISPLAY_V2 = 14
    const val COVER_PANEL_LEASE_V2 = 15

    const val CB_ANGLE = 1
}
