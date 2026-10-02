#!/usr/bin/env python3
"""Apply Duo Open Gen7 Shizuku + wallpaper onboarding service pack V1.

The patch is intentionally exact-baseline and fail-closed. It only edits known
source files when the expected pre-change snippets are present. If main has
moved or another agent already modified an overlapping block, the script stops
instead of guessing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

BASELINE_MAIN_SHA = "db0810e55a411a905f3877cc2a3518881c044daf"

EXPECTED_GIT_BLOBS = {
    "app/src/full/java/com/duoopen/shell/ShizukuBridge.kt": "d276f950eb279b3af281b9930dda7a8e8c3fd6a1",
    "app/src/main/java/com/duoopen/ui/ControlSheet.kt": "4686116fac055634039fc3384f7112fbf849e803",
    "app/src/main/java/com/duoopen/ui/HomePreview.kt": "1608af1ba754174013c87be221618626926c8ada",
    "app/src/main/java/com/duoopen/ui/DuoApp.kt": "21ea9df5d9d55f4cd116ae7ce511e3bc30a4911e",
}


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


class PatchError(RuntimeError):
    pass


@dataclass(frozen=True)
class Replacement:
    label: str
    old: str
    new: str
    already_marker: str


def replace_exact(text: str, rep: Replacement) -> tuple[str, str]:
    if rep.already_marker in text:
        return text, "already-applied"
    count = text.count(rep.old)
    if count != 1:
        raise PatchError(
            f"{rep.label}: expected exactly one pre-change block, found {count}. "
            "Refusing to guess against a drifted source file."
        )
    return text.replace(rep.old, rep.new, 1), "applied"


SHIZUKU_REPLACEMENTS = [
    Replacement(
        "Shizuku imports",
        """import android.content.ComponentName
import android.content.Context
import android.content.pm.PackageManager
import android.content.ServiceConnection
import android.graphics.Bitmap
import android.os.Binder
import android.os.Bundle
import android.os.IBinder
import android.os.Parcel
import android.os.SystemClock
""",
        """import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.ServiceConnection
import android.graphics.Bitmap
import android.os.Binder
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.Parcel
import android.os.SystemClock
""",
        "import android.os.Looper",
    ),
    Replacement(
        "Shizuku explicit binding states",
        """    sealed class State(val summary: String) {
        object NotInstalled : State("Shizuku isn't installed.")
        object NotRunning : State("Shizuku is installed but not running. Start it (wireless debugging or a computer), then come back.")
        object NeedsPermission : State("Shizuku is running. Authorise Duo Open to use it.")
        object Denied : State("Shizuku access was declined. Enable Duo Open under Shizuku → Authorised applications.")
        class Ready(val uid: Int, val capture: String?) : State(
            if (capture == null || capture.startsWith("unavailable")) "Shizuku ready (uid $uid); display capture ${capture ?: "unknown"}."
            else "Shizuku ready (uid $uid); fast display capture via $capture.",
        )
    }
""",
        """    sealed class State(val summary: String) {
        object NotInstalled : State("Shizuku isn't installed.")
        object NotRunning : State("Shizuku is installed but not running. Start it (wireless debugging or a computer), then come back.")
        object NeedsPermission : State("Shizuku is running. Authorise Duo Open to use it.")
        object Denied : State("Shizuku access was declined. Open Shizuku → Authorised applications and allow Duo Open.")
        object Binding : State("Shizuku permission granted. Connecting Duo Open to its helper service…")
        class BindFailed(val reason: String) : State(
            "Shizuku permission is granted, but Duo Open couldn't connect to its helper: $reason. Retry the connection or restart Shizuku.",
        )
        class Ready(val uid: Int, val capture: String?) : State(
            if (capture == null || capture.startsWith("unavailable")) "Shizuku ready (uid $uid); display capture ${capture ?: "unknown"}."
            else "Shizuku ready (uid $uid); fast display capture via $capture.",
        )
    }
""",
        "object Binding : State(\"Shizuku permission granted.",
    ),
    Replacement(
        "Shizuku bind watchdog fields",
        """    private const val TAG = "DuoShizuku"
    private const val REQUEST_CODE = 7311

    private val _state = MutableStateFlow<State>(State.NotInstalled)
    val state: StateFlow<State> = _state.asStateFlow()

    @Volatile
    var service: IBinder? = null
        private set
    private var binding = false
    private lateinit var appContext: Context

    private val captureSeq =
""",
        """    private const val TAG = "DuoShizuku"
    private const val REQUEST_CODE = 7311
    private const val BIND_TIMEOUT_MS = 8_000L

    private val _state = MutableStateFlow<State>(State.NotInstalled)
    val state: StateFlow<State> = _state.asStateFlow()

    @Volatile
    var service: IBinder? = null
        private set
    @Volatile private var binding = false
    @Volatile private var bindAttempt = 0L
    private lateinit var appContext: Context
    private val mainHandler = Handler(Looper.getMainLooper())
    private var bindTimeoutRunnable: Runnable? = null

    private val captureSeq =
""",
        "private const val BIND_TIMEOUT_MS = 8_000L",
    ),
    Replacement(
        "Shizuku connection callbacks",
        """    private val connection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName, binder: IBinder) {
            service = binder
            connectionEpoch = connectionEpochCounter.incrementAndGet()
            binding = false
            Log.i(TAG, "shell service connected")
            refresh()
        }

        override fun onServiceDisconnected(name: ComponentName) {
            service = null
            connectionEpoch = connectionEpochCounter.incrementAndGet()
            binding = false
            Log.i(TAG, "shell service disconnected")
            refresh()
        }
    }

    private val binderListener = Shizuku.OnBinderReceivedListener { refresh() }
    private val deadListener = Shizuku.OnBinderDeadListener {
        service = null
        connectionEpoch = connectionEpochCounter.incrementAndGet()
        refresh()
    }
    private val permissionListener = Shizuku.OnRequestPermissionResultListener { _, result ->
        refresh()
        if (result == PackageManager.PERMISSION_GRANTED) bind()
    }
""",
        """    private val connection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName, binder: IBinder) {
            cancelBindTimeout()
            service = binder
            connectionEpoch = connectionEpochCounter.incrementAndGet()
            binding = false
            Log.i(TAG, "shell service connected")
            refresh()
        }

        override fun onServiceDisconnected(name: ComponentName) {
            cancelBindTimeout()
            service = null
            connectionEpoch = connectionEpochCounter.incrementAndGet()
            binding = false
            Log.i(TAG, "shell service disconnected")
            refresh()
        }
    }

    private val binderListener = Shizuku.OnBinderReceivedListener {
        cancelBindTimeout()
        if (service == null) {
            binding = false
        }
        if (_state.value is State.BindFailed) {
            _state.value = State.NeedsPermission
        }
        refresh()
    }
    private val deadListener = Shizuku.OnBinderDeadListener {
        cancelBindTimeout()
        service = null
        binding = false
        connectionEpoch = connectionEpochCounter.incrementAndGet()
        refresh()
    }
    private val permissionListener = Shizuku.OnRequestPermissionResultListener { _, result ->
        if (result == PackageManager.PERMISSION_GRANTED) {
            retryBind()
        } else {
            refresh()
        }
    }
""",
        "if (_state.value is State.BindFailed)",
    ),
    Replacement(
        "Shizuku state truth + retryable binding",
        """    val installed: Boolean
        get() = runCatching { appContext.packageManager.getPackageInfo("moe.shizuku.privileged.api", 0); true }.getOrDefault(false)

    val ready: Boolean get() = state.value is State.Ready && service != null

    fun refresh() {
        val next: State = runCatching {
            when {
                !installed && !Shizuku.pingBinder() -> State.NotInstalled
                !Shizuku.pingBinder() -> State.NotRunning
                Shizuku.isPreV11() -> State.NotRunning
                Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED -> {
                    if (service == null) bind()
                    State.Ready(Shizuku.getUid(), ping()?.getString("capture"))
                }
                Shizuku.shouldShowRequestPermissionRationale() -> State.Denied
                else -> State.NeedsPermission
            }
        }.getOrElse { State.NotRunning }
        _state.value = next
    }

    fun requestPermission() {
        runCatching {
            if (Shizuku.pingBinder() && Shizuku.checkSelfPermission() != PackageManager.PERMISSION_GRANTED) {
                Shizuku.requestPermission(REQUEST_CODE)
            }
        }.onFailure { Log.w(TAG, "requestPermission", it) }
        refresh()
    }

    private fun args() = Shizuku.UserServiceArgs(ComponentName(appContext, DuoShellService::class.java))
        .daemon(true)
        .processNameSuffix("shell")
        .debuggable(BuildConfig.DEBUG)
        .version(BuildConfig.VERSION_CODE)

    fun bind() {
        if (service != null || binding) return
        binding = true
        runCatching { Shizuku.bindUserService(args(), connection) }
            .onFailure { binding = false; Log.w(TAG, "bindUserService", it) }
    }

    fun unbind() {
        runCatching { Shizuku.unbindUserService(args(), connection, true) }
        service = null
        connectionEpoch = connectionEpochCounter.incrementAndGet()
    }
""",
        """    val installed: Boolean
        get() =
            ::appContext.isInitialized &&
                runCatching {
                    appContext.packageManager.getPackageInfo("moe.shizuku.privileged.api", 0)
                    true
                }.getOrDefault(false)

    /** Ready means permission + a live helper Binder + a successful shell ping. */
    val ready: Boolean
        get() = state.value is State.Ready && service?.isBinderAlive == true

    fun refresh() {
        if (!::appContext.isInitialized) return

        val next: State =
            runCatching {
                when {
                    !installed -> {
                        clearConnectionForManagerLoss()
                        State.NotInstalled
                    }

                    !Shizuku.pingBinder() -> {
                        clearConnectionForManagerLoss()
                        State.NotRunning
                    }

                    Shizuku.isPreV11() -> State.NotRunning

                    Shizuku.checkSelfPermission() != PackageManager.PERMISSION_GRANTED -> {
                        cancelBindTimeout()
                        binding = false
                        if (Shizuku.shouldShowRequestPermissionRationale()) {
                            State.Denied
                        } else {
                            State.NeedsPermission
                        }
                    }

                    service?.isBinderAlive == true -> {
                        val shell = ping()
                        if (shell != null) {
                            State.Ready(
                                Shizuku.getUid(),
                                shell.getString("capture"),
                            )
                        } else {
                            service = null
                            binding = false
                            cancelBindTimeout()
                            startBinding()
                        }
                    }

                    binding -> State.Binding
                    _state.value is State.BindFailed -> _state.value
                    else -> startBinding()
                }
            }.getOrElse { error ->
                Log.w(TAG, "refresh", error)
                State.BindFailed(error.message ?: error.javaClass.simpleName)
            }

        _state.value = next
    }

    /**
     * User-facing action. If permission already exists this becomes a real
     * helper reconnect instead of a no-op "Authorise" tap.
     */
    fun requestPermission() {
        if (!::appContext.isInitialized) return

        runCatching {
            when {
                !installed -> _state.value = State.NotInstalled
                !Shizuku.pingBinder() -> _state.value = State.NotRunning
                Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED -> retryBind()
                Shizuku.shouldShowRequestPermissionRationale() -> {
                    _state.value = State.Denied
                    openShizukuManager()
                }
                else -> {
                    _state.value = State.NeedsPermission
                    Shizuku.requestPermission(REQUEST_CODE)
                }
            }
        }.onFailure { error ->
            Log.w(TAG, "requestPermission", error)
            _state.value = State.BindFailed(error.message ?: error.javaClass.simpleName)
        }

        refresh()
    }

    private fun openShizukuManager(): Boolean {
        val launch =
            appContext.packageManager.getLaunchIntentForPackage(
                "moe.shizuku.privileged.api"
            ) ?: return false

        launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return runCatching {
            appContext.startActivity(launch)
            true
        }.getOrDefault(false)
    }

    private fun args() = Shizuku.UserServiceArgs(ComponentName(appContext, DuoShellService::class.java))
        .daemon(true)
        .processNameSuffix("shell")
        .debuggable(BuildConfig.DEBUG)
        .version(BuildConfig.VERSION_CODE)

    private fun startBinding(): State {
        if (service?.isBinderAlive == true) {
            return _state.value
        }
        if (binding) {
            return State.Binding
        }

        binding = true
        val attempt = ++bindAttempt

        val result =
            runCatching {
                Shizuku.bindUserService(args(), connection)
            }

        return result.fold(
            onSuccess = {
                scheduleBindTimeout(attempt)
                State.Binding
            },
            onFailure = { error ->
                binding = false
                cancelBindTimeout()
                Log.w(TAG, "bindUserService", error)
                State.BindFailed(error.message ?: error.javaClass.simpleName)
            },
        )
    }

    private fun scheduleBindTimeout(attempt: Long) {
        cancelBindTimeout()
        val timeout =
            Runnable {
                if (
                    binding &&
                    service == null &&
                    bindAttempt == attempt
                ) {
                    binding = false
                    runCatching {
                        Shizuku.unbindUserService(args(), connection, true)
                    }
                    connectionEpoch = connectionEpochCounter.incrementAndGet()
                    _state.value = State.BindFailed("connection timed out after 8 seconds")
                    Log.w(TAG, "shell service bind timed out attempt=$attempt")
                }
            }
        bindTimeoutRunnable = timeout
        mainHandler.postDelayed(timeout, BIND_TIMEOUT_MS)
    }

    private fun cancelBindTimeout() {
        bindTimeoutRunnable?.let(mainHandler::removeCallbacks)
        bindTimeoutRunnable = null
    }

    private fun clearConnectionForManagerLoss() {
        cancelBindTimeout()
        binding = false
        if (service != null) {
            connectionEpoch = connectionEpochCounter.incrementAndGet()
        }
        service = null
    }

    fun retryBind() {
        if (!::appContext.isInitialized) return

        cancelBindTimeout()
        binding = false
        runCatching {
            Shizuku.unbindUserService(args(), connection, true)
        }
        service = null
        connectionEpoch = connectionEpochCounter.incrementAndGet()

        val next =
            runCatching {
                when {
                    !installed -> State.NotInstalled
                    !Shizuku.pingBinder() -> State.NotRunning
                    Shizuku.checkSelfPermission() != PackageManager.PERMISSION_GRANTED -> {
                        if (Shizuku.shouldShowRequestPermissionRationale()) {
                            State.Denied
                        } else {
                            State.NeedsPermission
                        }
                    }
                    else -> startBinding()
                }
            }.getOrElse { error ->
                State.BindFailed(error.message ?: error.javaClass.simpleName)
            }

        _state.value = next
    }

    fun bind() {
        if (!::appContext.isInitialized) return
        if (service?.isBinderAlive == true || binding) return

        val next =
            runCatching {
                when {
                    !installed -> State.NotInstalled
                    !Shizuku.pingBinder() -> State.NotRunning
                    Shizuku.checkSelfPermission() != PackageManager.PERMISSION_GRANTED -> State.NeedsPermission
                    else -> startBinding()
                }
            }.getOrElse { error ->
                State.BindFailed(error.message ?: error.javaClass.simpleName)
            }
        _state.value = next
    }

    fun unbind() {
        cancelBindTimeout()
        binding = false
        runCatching { Shizuku.unbindUserService(args(), connection, true) }
        service = null
        connectionEpoch = connectionEpochCounter.incrementAndGet()
    }
""",
        "connection timed out after 8 seconds",
    ),
]

CONTROL_SHEET_REPLACEMENTS = [
    Replacement(
        "ControlSheet Shizuku UI state helpers",
        """    val clipboard =
        LocalClipboardManager.current

    val hasSensor =
""",
        """    val clipboard =
        LocalClipboardManager.current

    val shizukuConnecting =
        shizukuStatus.startsWith(
            "Shizuku permission granted. Connecting"
        )
    val shizukuBindFailed =
        shizukuStatus.startsWith(
            "Shizuku permission is granted, but Duo Open couldn't connect"
        )
    val shizukuNotRunning =
        shizukuStatus.startsWith(
            "Shizuku is installed but not running"
        )
    val shizukuDenied =
        shizukuStatus.startsWith(
            "Shizuku access was declined"
        )

    val hasSensor =
""",
        "val shizukuConnecting =",
    ),
    Replacement(
        "Wallpaper-only onboarding truth",
        """                    Hint(
                        when {
                            wallpaperActive ->
                                "Active. The home and lock screen wallpaper folds; icons stay sharp."

                            overlayAvailable ->
                                "Alternative that needs no accessibility service. Only the wallpaper folds."

                            else ->
                                "This edition folds the home and lock screen wallpaper; icons and apps stay sharp."
                        }
                    )
""",
        """                    Hint(
                        when {
                            wallpaperActive ->
                                "Verified active. Duo Open is the current live wallpaper; the home and lock screen wallpaper folds while icons stay sharp."

                            overlayAvailable ->
                                "Optional wallpaper-only mode. Set opens Android's live-wallpaper confirmation; confirm it there, then return. Duo Open verifies activation automatically."

                            else ->
                                "Set opens Android's live-wallpaper confirmation. Confirm it there, then return; Duo Open verifies activation automatically."
                        }
                    )
""",
        "Optional wallpaper-only mode. Set opens Android's live-wallpaper confirmation",
    ),
    Replacement(
        "Wallpaper button wording",
        """                        if (wallpaperActive) {
                            "Change"
                        } else {
                            "Set"
                        }
""",
        """                        if (wallpaperActive) {
                            "Open picker"
                        } else {
                            "Set in Android"
                        }
""",
        '"Set in Android"',
    ),
    Replacement(
        "Wallpaper image scope clarification",
        """            Section(
                "Wallpaper image",
                "Only used by the wallpaper mode and this preview. The whole-screen fold uses whatever is on screen.",
            )
""",
        """            Section(
                "Wallpaper image",
                "Only used by Duo Open's wallpaper-only mode and this preview. It does not select Samsung's Fold Interactive hinge-source wallpaper. The whole-screen fold uses whatever is on screen.",
            )
""",
        "It does not select Samsung's Fold Interactive hinge-source wallpaper",
    ),
    Replacement(
        "Shizuku setup explanation",
        """                Section(
                    "Shizuku mode (optional)",
                    "Shizuku gives apps ADB-level helpers without root. With it, Duo Open captures the screen with no rate limit and keeps the picture under the frost live, and on Samsung foldables reads the real hinge angle instead of just 0° / 90° / 180°.",
                )
""",
        """                Section(
                    "Shizuku mode (optional)",
                    "Shizuku runs Duo Open's privileged helper without root. Permission alone is not treated as ready: Duo Open also verifies that its helper Binder is connected. On current Fold7 builds, precise hinge input additionally depends on Samsung's Fold Interactive live wallpaper.",
                )
""",
        "Permission alone is not treated as ready",
    ),
    Replacement(
        "Shizuku action feedback",
        """                Row(
                    horizontalArrangement =
                        Arrangement.spacedBy(
                            12.dp
                        )
                ) {
                    if (!shizukuReady) {
                        Button(
                            onClick =
                                onShizukuAuthorize,
                            modifier =
                                Modifier.weight(1f),
                            enabled =
                                shizukuInstalled,
                        ) {
                            Text("Authorise")
                        }
                    }

                    OutlinedButton(
                        onClick =
                            onOpenShizuku,
                        modifier =
                            Modifier.weight(1f),
                    ) {
                        Text(
                            if (
                                shizukuInstalled
                            ) {
                                "Open Shizuku"
                            } else {
                                "Get Shizuku"
                            }
                        )
                    }
                }
""",
        """                Row(
                    horizontalArrangement =
                        Arrangement.spacedBy(
                            12.dp
                        )
                ) {
                    if (
                        !shizukuReady &&
                        shizukuInstalled &&
                        !shizukuNotRunning
                    ) {
                        Button(
                            onClick =
                                onShizukuAuthorize,
                            modifier =
                                Modifier.weight(1f),
                            enabled =
                                !shizukuConnecting,
                        ) {
                            Text(
                                when {
                                    shizukuConnecting -> "Connecting…"
                                    shizukuBindFailed -> "Retry connection"
                                    shizukuDenied -> "Open permissions"
                                    else -> "Authorise"
                                }
                            )
                        }
                    }

                    OutlinedButton(
                        onClick =
                            onOpenShizuku,
                        modifier =
                            Modifier.weight(1f),
                    ) {
                        Text(
                            if (
                                shizukuInstalled
                            ) {
                                "Open Shizuku"
                            } else {
                                "Get Shizuku"
                            }
                        )
                    }
                }

                when {
                    shizukuNotRunning ->
                        Hint(
                            "Start Shizuku first, then return to Duo Open. The status refreshes automatically.",
                            warn = true,
                        )

                    shizukuConnecting ->
                        Hint(
                            "Permission is already granted. Duo Open is connecting to its helper service; this attempt times out instead of waiting forever.",
                        )

                    shizukuBindFailed ->
                        Hint(
                            "Permission is granted, but the helper connection failed. Retry the connection or restart Shizuku.",
                            warn = true,
                        )
                }
""",
        '"Retry connection"',
    ),
    Replacement(
        "Samsung precise-angle wallpaper onboarding",
        """                    Hint(
                        if (foldWallpaperActive) {
                            angleFeedStatus()
                        } else {
                            "Samsung Fold interactive wallpaper is still the temporary precise-angle fallback. Set it as the home wallpaper, then return here. " +
                                angleFeedStatus()
                        },
                        warn = !foldWallpaperActive,
                    )

                    if (!foldWallpaperActive) {
                        TextButton(
                            onClick = onOpenWallpaperSettings
                        ) {
                            Text("Open wallpaper settings")
                        }
                    }
""",
        """                    Hint(
                        if (foldWallpaperActive) {
                            "Precise hinge source verified. " + angleFeedStatus()
                        } else {
                            "Precise hinge source is not verified. On current Samsung Fold7 builds, select Samsung's Fold Interactive live wallpaper as the HOME wallpaper. Android/Samsung requires confirmation in its own picker; Duo Open cannot silently apply it. Return here after confirming and Duo Open will verify it. " +
                                angleFeedStatus()
                        },
                        warn = !foldWallpaperActive,
                    )

                    if (!foldWallpaperActive) {
                        TextButton(
                            onClick = onOpenWallpaperSettings
                        ) {
                            Text("Open Samsung wallpaper setup")
                        }
                    }
""",
        "Precise hinge source is not verified",
    ),
]

HOME_PREVIEW_REPLACEMENTS = [
    Replacement(
        "HomePreview imports",
        """import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
""",
        """import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
""",
        "import androidx.compose.runtime.getValue",
    ),
    Replacement(
        "HomePreview lifecycle + overlay imports",
        """import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.roundToInt
""",
        """import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.duoopen.overlay.OverlayFeature
import kotlin.math.roundToInt
""",
        "import com.duoopen.overlay.OverlayFeature",
    ),
    Replacement(
        "HomePreview truthful Shizuku status",
        """    val ready = overlayEnabled && shizukuReady
    val status = when {
        !overlayEnabled -> "Setup needed"
        !shizukuReady -> "Shizuku needed"
        hingeAngle.isNaN() -> "Waiting for hinge"
        else -> "Ready"
    }
    val detail = when {
        !overlayEnabled -> "Turn on Duo Open accessibility to enable full-screen continuity."
        !shizukuReady -> "Start or authorize Shizuku for Fold7 panel control and precise hinge data."
        hingeAngle.isNaN() -> "The service is running; waiting for a hinge sample."
        simulated -> "Simulation active · ${hingeAngle.roundToInt()}°"
        else -> "Fold7 continuity active · hinge ${hingeAngle.roundToInt()}°"
    }
""",
        """    val shizukuStatusText by
        OverlayFeature.shizukuStatus.collectAsStateWithLifecycle()

    val ready = overlayEnabled && shizukuReady
    val status = when {
        !overlayEnabled -> "Setup needed"
        !shizukuReady -> "Shizuku setup"
        hingeAngle.isNaN() -> "Waiting for hinge"
        else -> "Ready"
    }
    val detail = when {
        !overlayEnabled -> "Turn on Duo Open accessibility to enable full-screen continuity."
        !shizukuReady -> shizukuStatusText
        hingeAngle.isNaN() -> "The service is running; waiting for a hinge sample."
        simulated -> "Simulation active · ${hingeAngle.roundToInt()}°"
        else -> "Fold7 continuity active · hinge ${hingeAngle.roundToInt()}°"
    }
""",
        "OverlayFeature.shizukuStatus.collectAsStateWithLifecycle()",
    ),
    Replacement(
        "HomePreview status summary",
        '"Shizuku ${if (shizukuReady) "READY" else "OFF"}  ·  " +',
        '"Shizuku ${if (shizukuReady) "READY" else "SETUP"}  ·  " +',
        '"SETUP"}  ·  " +',
    ),
    Replacement(
        "HomePreview wallpaper action wording",
        'Text(if (wallpaperActive) "Wallpaper settings" else "Set Duo wallpaper")',
        'Text(if (wallpaperActive) "Wallpaper settings" else "Set wallpaper in Android")',
        '"Set wallpaper in Android"',
    ),
]

DUO_APP_REPLACEMENTS = [
    Replacement(
        "Duo wallpaper confirmation guidance",
        """    val setWallpaper = {
        openWallpaperPicker(
            context
        )
    }
""",
        """    val setWallpaper = {
        Toast.makeText(
            context,
            "Android will ask you to confirm Duo Open as the live wallpaper. Confirm it there, then return to Duo Open.",
            Toast.LENGTH_LONG,
        ).show()
        openWallpaperPicker(
            context
        )
    }
""",
        "Android will ask you to confirm Duo Open as the live wallpaper",
    ),
    Replacement(
        "Samsung FoldInteractive setup guidance",
        """                onOpenWallpaperSettings = {
                    openWallpaperSettings(
                        context
                    )
                },
""",
        """                onOpenWallpaperSettings = {
                    Toast.makeText(
                        context,
                        "Choose Samsung's Fold Interactive live wallpaper for the Home screen, confirm it, then return to Duo Open.",
                        Toast.LENGTH_LONG,
                    ).show()
                    openWallpaperSettings(
                        context
                    )
                },
""",
        "Choose Samsung's Fold Interactive live wallpaper for the Home screen",
    ),
    Replacement(
        "Direct Samsung FoldInteractive picker",
        """private fun openWallpaperSettings(
    context: Context,
) {
    val intent =
        Intent(
            Intent.ACTION_SET_WALLPAPER
        ).addFlags(
            Intent.FLAG_ACTIVITY_NEW_TASK
        )

    if (
        runCatching {
            context.startActivity(
                intent
            )
        }.isFailure
    ) {
        Toast.makeText(
            context,
            "Couldn't open wallpaper settings",
            Toast.LENGTH_SHORT,
        ).show()
    }
}
""",
        """private fun openWallpaperSettings(
    context: Context,
) {
    val samsungFoldInteractive =
        ComponentName(
            "com.samsung.android.wallpaper.live",
            "com.samsung.android.wallpaper.live.fold.FoldInteractive",
        )

    val direct =
        Intent(
            WallpaperManager.ACTION_CHANGE_LIVE_WALLPAPER
        ).putExtra(
            WallpaperManager.EXTRA_LIVE_WALLPAPER_COMPONENT,
            samsungFoldInteractive,
        ).addFlags(
            Intent.FLAG_ACTIVITY_NEW_TASK
        )

    val fallback =
        Intent(
            Intent.ACTION_SET_WALLPAPER
        ).addFlags(
            Intent.FLAG_ACTIVITY_NEW_TASK
        )

    for (intent in listOf(direct, fallback)) {
        if (
            runCatching {
                context.startActivity(intent)
            }.isSuccess
        ) {
            return
        }
    }

    Toast.makeText(
        context,
        "Couldn't open wallpaper settings",
        Toast.LENGTH_SHORT,
    ).show()
}
""",
        "val samsungFoldInteractive =",
    ),
]

PATCHES = {
    "app/src/full/java/com/duoopen/shell/ShizukuBridge.kt": SHIZUKU_REPLACEMENTS,
    "app/src/main/java/com/duoopen/ui/ControlSheet.kt": CONTROL_SHEET_REPLACEMENTS,
    "app/src/main/java/com/duoopen/ui/HomePreview.kt": HOME_PREVIEW_REPLACEMENTS,
    "app/src/main/java/com/duoopen/ui/DuoApp.kt": DUO_APP_REPLACEMENTS,
}

POSTCONDITIONS = {
    "app/src/full/java/com/duoopen/shell/ShizukuBridge.kt": [
        "object Binding : State",
        "class BindFailed",
        "BIND_TIMEOUT_MS = 8_000L",
        "service?.isBinderAlive == true",
        "fun retryBind()",
        "binding = false\n        runCatching { Shizuku.unbindUserService",
        "connection timed out after 8 seconds",
    ],
    "app/src/main/java/com/duoopen/ui/ControlSheet.kt": [
        "Retry connection",
        "Permission alone is not treated as ready",
        "Open Samsung wallpaper setup",
        "Duo Open cannot silently apply it",
    ],
    "app/src/main/java/com/duoopen/ui/HomePreview.kt": [
        "OverlayFeature.shizukuStatus.collectAsStateWithLifecycle()",
        '"Shizuku setup"',
        '"Set wallpaper in Android"',
    ],
    "app/src/main/java/com/duoopen/ui/DuoApp.kt": [
        "Android will ask you to confirm Duo Open as the live wallpaper",
        "samsungFoldInteractive",
        "WallpaperManager.ACTION_CHANGE_LIVE_WALLPAPER",
    ],
}


def apply(repo: Path, check_only: bool = False, enforce_blob_guard: bool = True) -> list[dict]:
    repo = repo.resolve()
    results = []
    for rel, replacements in PATCHES.items():
        path = repo / rel
        if not path.is_file():
            raise PatchError(f"missing target file: {rel}")

        raw = path.read_bytes()
        current_blob = git_blob_sha(raw)
        expected_blob = EXPECTED_GIT_BLOBS[rel]
        already_applied = all(marker in raw.decode("utf-8") for marker in POSTCONDITIONS[rel])
        if enforce_blob_guard and current_blob != expected_blob and not already_applied:
            raise PatchError(
                f"{rel}: baseline blob drift. expected {expected_blob}, found {current_blob}. "
                "Rebase this service pack instead of applying blind."
            )

        text = raw.decode("utf-8")
        statuses = []
        for rep in replacements:
            text, status = replace_exact(text, rep)
            statuses.append({"label": rep.label, "status": status})

        for marker in POSTCONDITIONS[rel]:
            if marker not in text:
                raise PatchError(f"{rel}: missing postcondition marker: {marker!r}")

        after = text.encode("utf-8")
        if not check_only and after != raw:
            path.write_bytes(after)

        results.append(
            {
                "path": rel,
                "before_git_blob": current_blob,
                "after_git_blob": git_blob_sha(after),
                "changed": after != raw,
                "replacements": statuses,
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", type=Path, help="Path to duo-open checkout")
    parser.add_argument("--check", action="store_true", help="Validate applicability without writing")
    parser.add_argument(
        "--allow-drift",
        action="store_true",
        help="Disable exact Git-blob guard; snippet guards still remain. Use only during a reviewed rebase.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable results")
    args = parser.parse_args()

    try:
        results = apply(
            args.repo,
            check_only=args.check,
            enforce_blob_guard=not args.allow_drift,
        )
    except PatchError as error:
        print(f"SERVICE_PACK_V1_FAIL: {error}")
        return 2

    payload = {
        "service_pack": "DUO_OPEN_GEN7_SERVICE_PACK_SHIZUKU_ONBOARDING_V1",
        "baseline_main_sha": BASELINE_MAIN_SHA,
        "mode": "check" if args.check else "apply",
        "results": results,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("SERVICE_PACK_V1_OK")
        for result in results:
            state = "changed" if result["changed"] else "unchanged"
            print(f"- {result['path']}: {state} -> {result['after_git_blob']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
