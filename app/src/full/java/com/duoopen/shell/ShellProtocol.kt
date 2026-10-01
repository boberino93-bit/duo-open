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

    const val CB_ANGLE = 1
}
