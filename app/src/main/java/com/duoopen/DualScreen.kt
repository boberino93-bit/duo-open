package com.duoopen

import android.content.Context
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.util.Log
import android.view.Gravity
import android.view.View
import android.widget.FrameLayout
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.window.area.WindowAreaCapability
import androidx.window.area.WindowAreaController
import androidx.window.area.WindowAreaInfo
import androidx.window.area.WindowAreaPresentationSessionCallback
import androidx.window.area.WindowAreaSessionPresenter
import androidx.window.core.ExperimentalWindowApi
import com.duoopen.debug.DuoDiagnostics
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

/**
 * Keeps "Both screens at once" armed across Samsung fold/unfold transitions.
 *
 * Samsung legitimately terminates the Window Area presentation when the
 * host Activity leaves the foreground. Treat that as suspension rather
 * than an error. Recovery is attempted only after the Activity is fully
 * RESUMED and has remained stable briefly.
 */
@OptIn(ExperimentalWindowApi::class)
class DualScreen(
    private val activity: ComponentActivity,
) : DefaultLifecycleObserver {

    private val controller =
        WindowAreaController.getOrCreate()

    private val prefs =
        activity.getSharedPreferences(
            PREFS_NAME,
            Context.MODE_PRIVATE,
        )

    private val _status =
        MutableStateFlow(
            "Checking…"
        )

    val status: StateFlow<String> =
        _status

    private val _active =
        MutableStateFlow(
            prefs.getBoolean(
                PREF_ENABLED,
                false,
            )
        )

    val active: StateFlow<Boolean> =
        _active

    val supported: Boolean
        get() =
            rearInfo != null

    private var desired =
        _active.value

    private var rearInfo:
        WindowAreaInfo? = null

    private var presenter:
        WindowAreaSessionPresenter? = null

    private var requestInFlight =
        false

    private var generation =
        0L

    private var retryJob:
        Job? = null

    private var timeoutJob:
        Job? = null

    private var suspended =
        false

    init {
        activity.lifecycle.addObserver(
            this
        )

        DuoDiagnostics.event(
            "dual",
            "created desired=$desired lifecycle=${activity.lifecycle.currentState}",
        )

        activity.lifecycleScope.launch {
            activity.repeatOnLifecycle(
                Lifecycle.State.STARTED
            ) {
                controller.windowAreaInfos.collect { infos ->

                    Log.i(
                        TAG,
                        "window areas: " +
                            infos.joinToString { info ->

                                val present =
                                    info.getCapability(
                                        WindowAreaCapability.Operation
                                            .OPERATION_PRESENT_ON_AREA,
                                    )?.status

                                val transfer =
                                    info.getCapability(
                                        WindowAreaCapability.Operation
                                            .OPERATION_TRANSFER_ACTIVITY_TO_AREA,
                                    )?.status

                                "${info.type} ${info.metrics.bounds} " +
                                    "present=$present transfer=$transfer"
                            }.ifEmpty {
                                "(none)"
                            },
                    )

                    rearInfo =
                        infos.firstOrNull {
                            it.type ==
                                WindowAreaInfo.Type
                                    .TYPE_REAR_FACING
                        }

                    val diagnosticCap =
                        rearInfo?.getCapability(
                            WindowAreaCapability.Operation
                                .OPERATION_PRESENT_ON_AREA,
                        )?.status

                    DuoDiagnostics.event(
                        "dual",
                        "windowAreas count=${infos.size} cap=$diagnosticCap desired=$desired " +
                            "presenter=${presenter != null} inFlight=$requestInFlight",
                    )

                    refreshStatus()

                    /*
                     * IMPORTANT:
                     *
                     * Capability updates are observational only.
                     *
                     * The previous implementation started/restarted a
                     * presentation directly from this callback. On Samsung,
                     * AVAILABLE can be reported while MainActivity is still
                     * moving through the fold/background transition.
                     *
                     * Starting here could therefore re-enter the Window Area
                     * API immediately after Samsung had deliberately ended
                     * the previous session.
                     */
                }
            }
        }
    }

    override fun onStart(
        owner: LifecycleOwner,
    ) {
        DuoDiagnostics.event(
            "dual",
            "lifecycle onStart desired=$desired",
        )

        /*
         * Do not start from STARTED.
         *
         * Wait until RESUMED, then give the Samsung display state time to
         * stabilize before making exactly one recovery request.
         */
    }

    override fun onResume(
        owner: LifecycleOwner,
    ) {
        DuoDiagnostics.event(
            "dual",
            "lifecycle onResume desired=$desired suspended=$suspended",
        )

        if (
            desired &&
            presenter == null &&
            !requestInFlight
        ) {
            scheduleRetry(
                RECOVERY_DELAY_MS,
                "stable activity resume",
            )
        }
    }

    override fun onPause(
        owner: LifecycleOwner,
    ) {
        DuoDiagnostics.event(
            "dual",
            "lifecycle onPause desired=$desired " +
                "presenter=${presenter != null} " +
                "inFlight=$requestInFlight",
        )

        /*
         * If Samsung begins taking this Activity out of the foreground,
         * prevent a delayed recovery from firing during that transition.
         */
        retryJob?.cancel()

        retryJob =
            null
    }

    override fun onStop(
        owner: LifecycleOwner,
    ) {
        DuoDiagnostics.event(
            "dual",
            "lifecycle onStop desired=$desired " +
                "presenter=${presenter != null} " +
                "inFlight=$requestInFlight",
        )
    }

    override fun onDestroy(
        owner: LifecycleOwner,
    ) {
        DuoDiagnostics.event(
            "dual",
            "lifecycle onDestroy desired=$desired",
        )

        retryJob?.cancel()
        timeoutJob?.cancel()

        generation++

        requestInFlight =
            false

        val old =
            presenter

        presenter =
            null

        runCatching {
            old?.close()
        }

        activity.lifecycle.removeObserver(
            this
        )
    }

    fun start() {
        DuoDiagnostics.event(
            "dual",
            "user enabled",
        )

        desired =
            true

        suspended =
            false

        _active.value =
            true

        prefs.edit()
            .putBoolean(
                PREF_ENABLED,
                true,
            )
            .apply()

        _status.value =
            "Both screens armed — starting when Samsung exposes the cover display."

        scheduleRetry(
            0L,
            "user enabled",
        )
    }

    fun stop() {
        DuoDiagnostics.event(
            "dual",
            "user disabled",
        )

        desired =
            false

        suspended =
            false

        _active.value =
            false

        prefs.edit()
            .putBoolean(
                PREF_ENABLED,
                false,
            )
            .apply()

        retryJob?.cancel()
        timeoutJob?.cancel()

        generation++

        requestInFlight =
            false

        val old =
            presenter

        presenter =
            null

        runCatching {
            old?.close()
        }.onFailure {
            Log.w(
                TAG,
                "closing dual-screen session failed",
                it,
            )
        }

        refreshStatus()
    }

    private fun maybeStart(
        reason: String,
    ) {
        val diagnosticCap =
            rearInfo?.getCapability(
                WindowAreaCapability.Operation
                    .OPERATION_PRESENT_ON_AREA,
            )?.status

        DuoDiagnostics.event(
            "dual",
            "maybeStart reason=$reason desired=$desired cap=$diagnosticCap " +
                "presenter=${presenter != null} " +
                "inFlight=$requestInFlight " +
                "lifecycle=${activity.lifecycle.currentState}",
        )

        if (
            !desired ||
            presenter != null ||
            requestInFlight
        ) {
            return
        }

        if (
            !activity.lifecycle.currentState
                .isAtLeast(
                    Lifecycle.State.RESUMED
                )
        ) {
            _status.value =
                "Both screens armed — waiting for Duo Open to be fully resumed."

            DuoDiagnostics.event(
                "dual",
                "start suppressed because lifecycle is ${activity.lifecycle.currentState}",
            )

            return
        }

        val info =
            rearInfo ?: run {

                _status.value =
                    "Both screens armed — waiting for Samsung's second-screen capability."

                return
            }

        val cap =
            info.getCapability(
                WindowAreaCapability.Operation
                    .OPERATION_PRESENT_ON_AREA,
            )

        when (
            cap?.status
        ) {
            WindowAreaCapability.Status
                .WINDOW_AREA_STATUS_AVAILABLE -> {
                beginSession(
                    info,
                    reason,
                )
            }

            WindowAreaCapability.Status
                .WINDOW_AREA_STATUS_ACTIVE -> {
                _status.value =
                    "Both screens armed — Samsung reports the second screen active."
            }

            WindowAreaCapability.Status
                .WINDOW_AREA_STATUS_UNAVAILABLE -> {
                _status.value =
                    "Both screens armed — temporarily unavailable while the phone changes display state."
            }

            else -> {
                _status.value =
                    "Both screens armed — waiting for a usable second-screen session."
            }
        }
    }

    private fun beginSession(
        info: WindowAreaInfo,
        reason: String,
    ) {
        if (
            !desired ||
            requestInFlight ||
            presenter != null
        ) {
            return
        }

        requestInFlight =
            true

        val myGeneration =
            ++generation

        _status.value =
            "Starting both screens…"

        Log.i(
            TAG,
            "request dual screen gen=$myGeneration reason=$reason",
        )

        DuoDiagnostics.event(
            "dual",
            "request gen=$myGeneration reason=$reason",
        )

        val callback =
            object :
                WindowAreaPresentationSessionCallback {

                override fun onSessionStarted(
                    session:
                        WindowAreaSessionPresenter,
                ) {
                    if (
                        myGeneration != generation ||
                        !desired
                    ) {
                        runCatching {
                            session.close()
                        }

                        return
                    }

                    timeoutJob?.cancel()

                    requestInFlight =
                        false

                    presenter =
                        session

                    suspended =
                        false

                    val attached =
                        runCatching {
                            session.setContentView(
                                placeholder(
                                    session.context
                                )
                            )
                        }

                    if (
                        attached.isFailure
                    ) {
                        Log.w(
                            TAG,
                            "dual-screen content attach failed",
                            attached.exceptionOrNull(),
                        )

                        presenter =
                            null

                        runCatching {
                            session.close()
                        }

                        suspended =
                            true

                        _status.value =
                            "Dual screen couldn't attach content. It will retry after the next stable resume."

                        DuoDiagnostics.event(
                            "dual",
                            "contentAttachFailed gen=$myGeneration",
                        )

                        return
                    }

                    Log.i(
                        TAG,
                        "dual-screen session started gen=$myGeneration",
                    )

                    DuoDiagnostics.event(
                        "dual",
                        "sessionStarted gen=$myGeneration",
                    )

                    _status.value =
                        "Both screens are on."
                }

                override fun onSessionEnded(
                    t: Throwable?,
                ) {
                    if (
                        myGeneration != generation
                    ) {
                        return
                    }

                    timeoutJob?.cancel()

                    requestInFlight =
                        false

                    presenter =
                        null

                    Log.i(
                        TAG,
                        "dual-screen session ended gen=$myGeneration reason=${t?.message}",
                    )

                    DuoDiagnostics.event(
                        "dual",
                        "sessionEnded gen=$myGeneration desired=$desired message=${t?.message}",
                        t,
                    )

                    if (
                        !desired
                    ) {
                        refreshStatus()
                        return
                    }

                    suspended =
                        true

                    _status.value =
                        "Dual screen paused by Samsung. It will make one recovery attempt after Duo Open is stably resumed."

                    DuoDiagnostics.event(
                        "dual",
                        "session suspended gen=$myGeneration; no immediate retry",
                    )

                    /*
                     * No immediate retry.
                     *
                     * Samsung has explicitly ended this Activity's
                     * presentation session. Recovery belongs to the next
                     * stable onResume, not to this callback.
                     */
                }

                override fun onContainerVisibilityChanged(
                    isVisible: Boolean,
                ) {
                    DuoDiagnostics.event(
                        "dual",
                        "visibility gen=$myGeneration visible=$isVisible " +
                            "currentGen=$generation " +
                            "desired=$desired " +
                            "presenter=${presenter != null}",
                    )

                    if (
                        myGeneration != generation ||
                        !desired ||
                        presenter == null
                    ) {
                        return
                    }

                    _status.value =
                        if (
                            isVisible
                        ) {
                            "Both screens are on."
                        } else {
                            "Both screens armed — cover presentation is temporarily hidden."
                        }
                }
            }

        val result =
            runCatching {
                controller.presentContentOnWindowArea(
                    info.token,
                    activity,
                    ContextCompat.getMainExecutor(
                        activity
                    ),
                    callback,
                )
            }

        if (
            result.isFailure
        ) {
            requestInFlight =
                false

            Log.w(
                TAG,
                "presentContentOnWindowArea failed",
                result.exceptionOrNull(),
            )

            DuoDiagnostics.event(
                "dual",
                "requestFailed gen=$myGeneration",
                result.exceptionOrNull(),
            )

            suspended =
                true

            _status.value =
                "Couldn't start dual screen. It will retry after the next stable resume."

            DuoDiagnostics.event(
                "dual",
                "request failure suspended gen=$myGeneration",
            )

            /*
             * Again, no loop here. A failed request remains suspended
             * until a later foreground transition.
             */
            return
        }

        timeoutJob?.cancel()

        timeoutJob =
            activity.lifecycleScope.launch {

                delay(
                    2_500L
                )

                if (
                    desired &&
                    myGeneration == generation &&
                    requestInFlight &&
                    presenter == null
                ) {
                    Log.w(
                        TAG,
                        "dual-screen request timed out gen=$myGeneration",
                    )

                    DuoDiagnostics.event(
                        "dual",
                        "requestTimeout gen=$myGeneration",
                    )

                    requestInFlight =
                        false

                    suspended =
                        true

                    _status.value =
                        "Dual-screen start timed out. It will retry after the next stable resume."

                    DuoDiagnostics.event(
                        "dual",
                        "timeout suspended gen=$myGeneration",
                    )
                }
            }
    }

    private fun scheduleRetry(
        delayMs: Long,
        reason: String,
    ) {
        DuoDiagnostics.event(
            "dual",
            "scheduleRetry delayMs=$delayMs reason=$reason desired=$desired",
        )

        if (
            !desired
        ) {
            return
        }

        retryJob?.cancel()

        retryJob =
            activity.lifecycleScope.launch {

                if (
                    delayMs > 0L
                ) {
                    delay(
                        delayMs
                    )
                }

                if (
                    !desired
                ) {
                    return@launch
                }

                if (
                    !activity.lifecycle.currentState
                        .isAtLeast(
                            Lifecycle.State.RESUMED
                        )
                ) {
                    DuoDiagnostics.event(
                        "dual",
                        "recovery cancelled reason=$reason lifecycle=${activity.lifecycle.currentState}",
                    )

                    return@launch
                }

                maybeStart(
                    reason
                )
            }
    }

    private fun refreshStatus() {
        if (
            presenter != null
        ) {
            _status.value =
                "Both screens are on."

            return
        }

        val info =
            rearInfo

        val cap =
            info?.getCapability(
                WindowAreaCapability.Operation
                    .OPERATION_PRESENT_ON_AREA,
            )

        _status.value =
            if (
                desired
            ) {
                when {
                    suspended -> {
                        "Both screens armed — paused by Samsung; waiting for a stable resume."
                    }

                    info == null -> {
                        "Both screens armed — waiting for Samsung's second-screen capability."
                    }

                    cap?.status ==
                        WindowAreaCapability.Status
                            .WINDOW_AREA_STATUS_AVAILABLE -> {
                        "Both screens armed — cover display available."
                    }

                    cap?.status ==
                        WindowAreaCapability.Status
                            .WINDOW_AREA_STATUS_ACTIVE -> {
                        "Both screens armed — Samsung reports the second screen active."
                    }

                    cap?.status ==
                        WindowAreaCapability.Status
                            .WINDOW_AREA_STATUS_UNAVAILABLE -> {
                        "Both screens armed — temporarily unavailable while the phone changes display state."
                    }

                    else -> {
                        "Both screens armed — waiting for the second display."
                    }
                }
            } else {
                when {
                    info == null -> {
                        "This phone doesn't offer its second screen to apps."
                    }

                    cap?.status ==
                        WindowAreaCapability.Status
                            .WINDOW_AREA_STATUS_ACTIVE -> {
                        "Both screens are already active."
                    }

                    cap?.status ==
                        WindowAreaCapability.Status
                            .WINDOW_AREA_STATUS_AVAILABLE -> {
                        "Available: the cover screen can be lit while the inner screen is in use."
                    }

                    cap?.status ==
                        WindowAreaCapability.Status
                            .WINDOW_AREA_STATUS_UNAVAILABLE -> {
                        "Not available right now — open the phone fully and try again."
                    }

                    else -> {
                        "This phone doesn't support lighting both screens for apps."
                    }
                }
            }
    }

    private fun placeholder(
        context: Context,
    ): View =
        FrameLayout(context).apply {

            background =
                GradientDrawable(
                    GradientDrawable.Orientation.TL_BR,
                    intArrayOf(
                        0xFF7B5CFF.toInt(),
                        0xFFC44EDD.toInt(),
                        0xFFF0564A.toInt(),
                    ),
                )

            addView(
                TextView(context).apply {
                    text =
                        "Duo Open\n\nBoth screens are on.\nFold the phone."

                    setTextColor(
                        Color.WHITE
                    )

                    textSize =
                        26f

                    gravity =
                        Gravity.CENTER
                },
                FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.MATCH_PARENT,
                    FrameLayout.LayoutParams.MATCH_PARENT,
                ),
            )
        }

    private companion object {
        const val TAG =
            "DuoDual"

        const val PREFS_NAME =
            "duo_open"

        const val PREF_ENABLED =
            "dual_screen_experimental_enabled"

        /*
         * Long enough for Samsung's display topology and Activity state
         * to settle, short enough not to feel like a manual restart.
         */
        const val RECOVERY_DELAY_MS =
            700L
    }
}
