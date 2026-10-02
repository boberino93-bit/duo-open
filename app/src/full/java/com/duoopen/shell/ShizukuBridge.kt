package com.duoopen.shell

import android.content.ComponentName
import android.content.Context
import android.content.pm.PackageManager
import android.content.ServiceConnection
import android.graphics.Bitmap
import android.os.Binder
import android.os.Bundle
import android.os.IBinder
import android.os.Parcel
import android.os.SystemClock
import android.util.Log
import android.view.SurfaceControl
import com.duoopen.BuildConfig
import com.duoopen.lab.TransitionClock
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import rikka.shizuku.Shizuku

/**
 * App-side handle on Shizuku and on [DuoShellService]. Optional: everything
 * degrades to the accessibility screenshot and the public hinge sensor when
 * Shizuku isn't installed, running or authorised.
 */
object ShizukuBridge {
    sealed class State(val summary: String) {
        object NotInstalled : State("Shizuku isn't installed.")
        object NotRunning : State("Shizuku is installed but not running. Start it (wireless debugging or a computer), then come back.")
        object NeedsPermission : State("Shizuku is running. Authorise Duo Open to use it.")
        object Denied : State("Shizuku access was declined. Enable Duo Open under Shizuku → Authorised applications.")
        class Ready(val uid: Int, val capture: String?) : State(
            if (capture == null || capture.startsWith("unavailable")) "Shizuku ready (uid $uid); display capture ${capture ?: "unknown"}."
            else "Shizuku ready (uid $uid); fast display capture via $capture.",
        )
    }

    private const val TAG = "DuoShizuku"
    private const val REQUEST_CODE = 7311

    private val _state = MutableStateFlow<State>(State.NotInstalled)
    val state: StateFlow<State> = _state.asStateFlow()

    @Volatile
    var service: IBinder? = null
        private set
    private var binding = false
    private lateinit var appContext: Context

    private val captureSeq =
        java.util.concurrent.atomic.AtomicLong()

    private val connectionEpochCounter =
        java.util.concurrent.atomic.AtomicLong()

    @Volatile
    var connectionEpoch: Long = 0L
        private set

    private val connection = object : ServiceConnection {
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

    fun init(context: Context) {
        if (::appContext.isInitialized) return
        appContext = context.applicationContext
        runCatching {
            Shizuku.addBinderReceivedListenerSticky(binderListener)
            Shizuku.addBinderDeadListener(deadListener)
            Shizuku.addRequestPermissionResultListener(permissionListener)
        }.onFailure { Log.w(TAG, "Shizuku listeners", it) }
        refresh()
    }

    val installed: Boolean
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

    private fun call(code: Int, write: (Parcel) -> Unit = {}): Bundle? {
        val binder = service ?: return null
        val p = Parcel.obtain()
        val r = Parcel.obtain()
        return try {
            p.writeInterfaceToken(ShellProtocol.TOKEN)
            write(p)
            if (!binder.transact(code, p, r, 0)) return null
            r.readException()
            if (r.dataAvail() > 0) r.readBundle(ShizukuBridge::class.java.classLoader) else Bundle()
        } catch (e: Exception) {
            Log.w(TAG, "shell call $code failed: $e")
            null
        } finally {
            p.recycle()
            r.recycle()
        }
    }

    fun ping(): Bundle? = call(ShellProtocol.PING)

    /** Blocking; call off the main thread. Null if unavailable or the frame had secure content. */
    fun capture(displayId: Int, excluded: List<SurfaceControl>, scale: Float): Bitmap? {
        val b = call(ShellProtocol.CAPTURE) { p ->
            p.writeInt(displayId)
            p.writeInt(excluded.size)
            excluded.forEach { p.writeTypedObject(it, 0) }
            p.writeFloat(scale)
        } ?: return null
        if (!b.getBoolean("ok")) {
            Log.w(
                TAG,
                "shell capture failed: ${b.getString("error")}",
            )
            return null
        }

        val seq =
            captureSeq.incrementAndGet()

        val captureMs =
            b.getLong("ms")

        if (
            seq == 1L ||
            seq % 20L == 0L
        ) {
            Log.i(
                TAG,
                "capture display=$displayId " +
                    "scale=$scale ${captureMs}ms",
            )
        }

        if (b.getBoolean("secure")) {
            return null
        }
        @Suppress("DEPRECATION")
        return b.getParcelable("bitmap")
    }

    /** Receives angles from the shell-side wallpaper log reader. */
    private class AngleCallback(
        private val onAngle: (Float, Long, Long, Long) -> Unit,
    ) : Binder() {

        init {
            attachInterface(
                null,
                ShellProtocol.CALLBACK_TOKEN,
            )
        }

        override fun onTransact(
            code: Int,
            data: Parcel,
            reply: Parcel?,
            flags: Int,
        ): Boolean {
            val binderArrivalTimeNs =
                TransitionClock.nowNs()

            if (code != ShellProtocol.CB_ANGLE) {
                return super.onTransact(
                    code,
                    data,
                    reply,
                    flags,
                )
            }

            data.enforceInterface(
                ShellProtocol.CALLBACK_TOKEN,
            )

            val angle = data.readFloat()

            val sourceUptime =
                if (
                    data.dataAvail() >=
                    Long.SIZE_BYTES
                ) {
                    data.readLong()
                } else {
                    SystemClock.uptimeMillis()
                }

            /*
             * Gen-2 readers append a poll sequence after source uptime. A zero
             * sequence preserves compatibility with the current production
             * feed until it is switched to per-poll action identity.
             */
            val pollSequence =
                if (
                    data.dataAvail() >=
                    Long.SIZE_BYTES
                ) {
                    data.readLong()
                } else {
                    0L
                }

            onAngle(
                angle,
                sourceUptime,
                binderArrivalTimeNs,
                pollSequence,
            )

            return true
        }
    }

    private var angleCallback:
        AngleCallback? = null

    /**
     * Compatibility entry point for the current feed. Gen-2 callers should use
     * [startAnglesSequenced] so the poll sequence survives shell -> Binder.
     */
    fun startAngles(
        action: String,
        onAngle: (Float, Long, Long) -> Unit,
    ): Boolean =
        startAnglesSequenced(
            actionPrefix = action,
        ) { angle, sourceUptime, binderArrivalTimeNs, _ ->
            onAngle(
                angle,
                sourceUptime,
                binderArrivalTimeNs,
            )
        }

    fun startAnglesSequenced(
        actionPrefix: String,
        onAngle: (Float, Long, Long, Long) -> Unit,
    ): Boolean {
        val cb =
            AngleCallback(onAngle)
        angleCallback = cb
        return call(ShellProtocol.START_ANGLES) { p ->
            p.writeString(actionPrefix)
            p.writeStrongBinder(cb)
        } != null
    }

    fun stopAngles() {
        call(ShellProtocol.STOP_ANGLES)
        angleCallback = null
    }

    fun angleStatus(): Bundle? = call(ShellProtocol.ANGLE_STATUS)

    /**
     * Executes the read-only display probe as Shizuku's shell user.
     * This is blocking and must be called off the main thread.
     */
    fun displayProbe(): Bundle? =
        call(
            ShellProtocol.DISPLAY_PROBE
        )

    /** Blocking; call off the main thread. */
    fun resolveCoverDisplay(): Bundle? =
        call(
            ShellProtocol.RESOLVE_COVER_DISPLAY
        )

    /** Wake the stable physical 1968x2184 Fold7 inner panel. Blocking; call off main. */
    fun wakeInnerDisplay(): Bundle? =
        call(
            ShellProtocol.WAKE_INNER_DISPLAY
        )

    /** Blocking; call off the main thread. */
    fun enableSecondaryDisplay(
        displayIdHint: Int,
    ): Bundle? =
        call(
            ShellProtocol.ENABLE_SECONDARY_DISPLAY
        ) { parcel ->
            parcel.writeInt(
                displayIdHint
            )
        }

    /** Blocking; call off the main thread. */
    fun resetSecondaryDisplay(
        displayIdHint: Int,
    ): Bundle? =
        call(
            ShellProtocol.RESET_SECONDARY_DISPLAY
        ) { parcel ->
            parcel.writeInt(
                displayIdHint
            )
        }

    fun startDisplayMirror(
        sourceDisplayId: Int,
    ): Bundle? =
        call(
            ShellProtocol.MIRROR_DISPLAY
        ) { parcel ->
            parcel.writeInt(1)
            parcel.writeInt(
                sourceDisplayId
            )
        }

    fun stopDisplayMirror(): Bundle? =
        call(
            ShellProtocol.MIRROR_DISPLAY
        ) { parcel ->
            parcel.writeInt(0)
        }

    fun openDisplayMirrorSession(): Bundle? =
        call(ShellProtocol.OPEN_MIRROR_SESSION)

    fun startDisplayMirrorV2(
        session: Long,
        sequence: Long,
        leaseId: Long,
        sourceDisplayId: Int,
    ): Bundle? =
        call(ShellProtocol.MIRROR_DISPLAY_V2) { parcel ->
            parcel.writeInt(1)
            parcel.writeLong(session)
            parcel.writeLong(sequence)
            parcel.writeLong(leaseId)
            parcel.writeInt(sourceDisplayId)
        }

    fun stopDisplayMirrorV2(
        session: Long,
        sequence: Long,
        leaseId: Long,
    ): Bundle? =
        call(ShellProtocol.MIRROR_DISPLAY_V2) { parcel ->
            parcel.writeInt(0)
            parcel.writeLong(session)
            parcel.writeLong(sequence)
            parcel.writeLong(leaseId)
        }

    fun forceStopDisplayMirrorV2(
        session: Long,
        sequence: Long,
    ): Bundle? =
        call(ShellProtocol.MIRROR_DISPLAY_V2) { parcel ->
            parcel.writeInt(2)
            parcel.writeLong(session)
            parcel.writeLong(sequence)
            parcel.writeLong(0L)
        }

    fun prewarmSecondaryDisplayV2(
        ownerGeneration: Long,
    ): Bundle? =
        call(ShellProtocol.COVER_PANEL_LEASE_V2) { parcel ->
            parcel.writeInt(1)
            parcel.writeLong(ownerGeneration)
            parcel.writeString("prewarm")
        }

    fun releaseSecondaryDisplayV2(
        ownerGeneration: Long,
        reason: String,
    ): Bundle? =
        call(ShellProtocol.COVER_PANEL_LEASE_V2) { parcel ->
            parcel.writeInt(2)
            parcel.writeLong(ownerGeneration)
            parcel.writeString(reason)
        }

    fun reconcileSecondaryDisplayLeaseV2(
        reason: String,
    ): Bundle? =
        call(ShellProtocol.COVER_PANEL_LEASE_V2) { parcel ->
            parcel.writeInt(3)
            parcel.writeLong(-1L)
            parcel.writeString(reason)
        }

    fun secondaryDisplayLeaseStatusV2(): Bundle? =
        call(ShellProtocol.COVER_PANEL_LEASE_V2) { parcel ->
            parcel.writeInt(4)
            parcel.writeLong(-1L)
            parcel.writeString("status")
        }

    /**
     * Reassert an already-owned Fold7 cover lease without changing ownership.
     */
    fun ensureSecondaryDisplayHeldV2(
        ownerGeneration: Long,
        reason: String,
    ): Bundle? =
        call(ShellProtocol.COVER_PANEL_LEASE_V2) { parcel ->
            parcel.writeInt(5)
            parcel.writeLong(ownerGeneration)
            parcel.writeString(reason)
        }

    fun prewarmSecondaryDisplayV3(
        ownerGeneration: Long,
        reason: String = "prewarm",
    ): Bundle? =
        call(ShellProtocol.COVER_PANEL_LEASE_V3) { parcel ->
            parcel.writeInt(1)
            parcel.writeLong(0L)
            parcel.writeLong(0L)
            parcel.writeLong(0L)
            parcel.writeLong(ownerGeneration)
            parcel.writeString(reason)
        }

    internal fun prewarmSecondaryDisplayV4(
        ownerServiceEpoch: Long,
        ownerCloseCycleId: Long,
        ownerGeneration: Long,
        expectedToken: com.duoopen.overlay.Fold7CoverLeaseSnapshotGate.LeaseToken?,
        reason: String = "prewarm-v4",
    ): Bundle? =
        call(ShellProtocol.COVER_PANEL_LEASE_V4) { parcel ->
            parcel.writeInt(1)
            parcel.writeLong(expectedToken?.shellSession ?: 0L)
            parcel.writeLong(expectedToken?.leaseId ?: 0L)
            parcel.writeLong(expectedToken?.leaseEpoch ?: 0L)
            parcel.writeLong(expectedToken?.ownerServiceEpoch ?: -1L)
            parcel.writeLong(expectedToken?.ownerCloseCycleId ?: -1L)
            parcel.writeLong(expectedToken?.ownerGeneration ?: -1L)
            parcel.writeLong(ownerServiceEpoch)
            parcel.writeLong(ownerCloseCycleId)
            parcel.writeLong(ownerGeneration)
            parcel.writeString(reason)
        }

    internal fun ensureSecondaryDisplayHeldV3(
        token: com.duoopen.overlay.Fold7CoverLeaseSnapshotGate.LeaseToken,
        reason: String,
    ): Bundle? =
        call(ShellProtocol.COVER_PANEL_LEASE_V3) { parcel ->
            parcel.writeInt(5)
            parcel.writeLong(token.shellSession)
            parcel.writeLong(token.leaseId)
            parcel.writeLong(token.leaseEpoch)
            parcel.writeLong(token.ownerGeneration)
            parcel.writeString(reason)
        }

    internal fun releaseSecondaryDisplayV3(
        token: com.duoopen.overlay.Fold7CoverLeaseSnapshotGate.LeaseToken,
        reason: String,
    ): Bundle? =
        call(ShellProtocol.COVER_PANEL_LEASE_V3) { parcel ->
            parcel.writeInt(2)
            parcel.writeLong(token.shellSession)
            parcel.writeLong(token.leaseId)
            parcel.writeLong(token.leaseEpoch)
            parcel.writeLong(token.ownerGeneration)
            parcel.writeString(reason)
        }

    fun reconcileSecondaryDisplayLeaseV3(
        shellSession: Long,
        reason: String,
    ): Bundle? =
        call(ShellProtocol.COVER_PANEL_LEASE_V3) { parcel ->
            parcel.writeInt(3)
            parcel.writeLong(shellSession)
            parcel.writeLong(0L)
            parcel.writeLong(0L)
            parcel.writeLong(-1L)
            parcel.writeString(reason)
        }

    fun secondaryDisplayLeaseStatusV3(
        shellSession: Long,
    ): Bundle? =
        call(ShellProtocol.COVER_PANEL_LEASE_V3) { parcel ->
            parcel.writeInt(4)
            parcel.writeLong(shellSession)
            parcel.writeLong(0L)
            parcel.writeLong(0L)
            parcel.writeLong(-1L)
            parcel.writeString("status")
        }

    private fun coverPanelGen4(
        operation: Int,
        serviceEpoch: Long,
        closeCycleId: Long,
        transitionGeneration: Long,
        intentSequence: Long,
        reason: String,
    ): Bundle? =
        call(ShellProtocol.COVER_PANEL_GEN4) { parcel ->
            parcel.writeInt(operation)
            parcel.writeLong(serviceEpoch)
            parcel.writeLong(closeCycleId)
            parcel.writeLong(transitionGeneration)
            parcel.writeLong(intentSequence)
            parcel.writeString(reason)
        }

    internal fun coverPanelStatusGen4(
        serviceEpoch: Long,
        intentSequence: Long,
        reason: String,
    ): Bundle? =
        coverPanelGen4(
            operation = 1,
            serviceEpoch = serviceEpoch,
            closeCycleId = 0L,
            transitionGeneration = -1L,
            intentSequence = intentSequence,
            reason = reason,
        )

    internal fun prepareCoverPanelGen4(
        serviceEpoch: Long,
        closeCycleId: Long,
        transitionGeneration: Long,
        intentSequence: Long,
        reason: String,
    ): Bundle? =
        coverPanelGen4(
            operation = 2,
            serviceEpoch = serviceEpoch,
            closeCycleId = closeCycleId,
            transitionGeneration = transitionGeneration,
            intentSequence = intentSequence,
            reason = reason,
        )

    internal fun reassertCoverPanelGen4(
        serviceEpoch: Long,
        closeCycleId: Long,
        transitionGeneration: Long,
        intentSequence: Long,
        reason: String,
    ): Bundle? =
        coverPanelGen4(
            operation = 3,
            serviceEpoch = serviceEpoch,
            closeCycleId = closeCycleId,
            transitionGeneration = transitionGeneration,
            intentSequence = intentSequence,
            reason = reason,
        )

    internal fun returnCoverPanelGen4(
        serviceEpoch: Long,
        intentSequence: Long,
        reason: String,
    ): Bundle? =
        coverPanelGen4(
            operation = 4,
            serviceEpoch = serviceEpoch,
            closeCycleId = 0L,
            transitionGeneration = -1L,
            intentSequence = intentSequence,
            reason = reason,
        )

    internal fun reconcileCoverPanelGen4(
        serviceEpoch: Long,
        intentSequence: Long,
        reason: String,
    ): Bundle? =
        coverPanelGen4(
            operation = 5,
            serviceEpoch = serviceEpoch,
            closeCycleId = 0L,
            transitionGeneration = -1L,
            intentSequence = intentSequence,
            reason = reason,
        )

    fun requestDisplayPower(
        displayId: Int,
        requestedState: Int,
    ): Bundle? =
        call(
            ShellProtocol.REQUEST_DISPLAY_POWER
        ) { parcel ->
            parcel.writeInt(
                displayId
            )
            parcel.writeInt(
                requestedState
            )
        }
}
