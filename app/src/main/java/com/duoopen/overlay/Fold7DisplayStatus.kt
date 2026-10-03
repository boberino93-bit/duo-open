package com.duoopen.overlay

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Product-visible Fold7 display pipeline state.
 *
 * This intentionally separates "we asked SurfaceFlinger to power the panel"
 * from "Android has a logical route" and "native INNER composition is live".
 * A successful privileged power call is not presented as proof that pixels are
 * already visible on the glass.
 */
data class Fold7DisplayStatus(
    val openingSource: String = "idle",
    val wakeCommand: WakeCommand = WakeCommand.IDLE,
    val physicalPower: PhysicalPower = PhysicalPower.UNKNOWN,
    val bridge: Bridge = Bridge.IDLE,
    val logicalInnerAvailable: Boolean = false,
    val nativeInnerActive: Boolean = false,
    val nativeInnerDefault: Boolean = false,
    val openingAttempt: Long = 0L,
    val lastError: String? = null,
) {
    enum class WakeCommand {
        IDLE,
        REQUESTED,
        ACCEPTED,
        FAILED,
    }

    enum class PhysicalPower {
        UNKNOWN,
        COMMAND_ACCEPTED,
        CONFIRMED_ON,
        FAILED,
    }

    enum class Bridge {
        IDLE,
        PRESENTING,
        HANDOFF_ARMED,
        RELEASED,
        FAILED,
    }

    val summary: String
        get() =
            when {
                nativeInnerDefault -> "INNER: NATIVE DEFAULT"
                nativeInnerActive -> "INNER: NATIVE ACTIVE"
                bridge == Bridge.HANDOFF_ARMED -> "INNER: HANDOFF SETTLING"
                bridge == Bridge.PRESENTING -> "INNER: BRIDGE ACTIVE"
                logicalInnerAvailable -> "INNER: LOGICAL AVAILABLE"
                physicalPower == PhysicalPower.CONFIRMED_ON -> "INNER: PHYSICAL ON"
                physicalPower == PhysicalPower.COMMAND_ACCEPTED -> "INNER: POWER COMMAND ACCEPTED"
                physicalPower == PhysicalPower.FAILED || wakeCommand == WakeCommand.FAILED -> "INNER: WAKE FAILED"
                wakeCommand == WakeCommand.REQUESTED -> "INNER: WAKE REQUESTED"
                else -> "INNER: IDLE / UNKNOWN"
            }

    val detail: String
        get() = buildString {
            append("source=")
            append(openingSource)
            append(" · wake=")
            append(wakeCommand.name)
            append(" · physical=")
            append(physicalPower.name)
            append(" · bridge=")
            append(bridge.name)
            append(" · logical=")
            append(if (logicalInnerAvailable) "YES" else "NO")
            append(" · native=")
            append(
                when {
                    nativeInnerDefault -> "DEFAULT"
                    nativeInnerActive -> "ACTIVE"
                    else -> "NO"
                }
            )
            if (openingAttempt > 0L) {
                append(" · attempt=")
                append(openingAttempt)
            }
            lastError?.takeIf { it.isNotBlank() }?.let {
                append(" · error=")
                append(it)
            }
        }
}

object Fold7DisplayStatusStore {
    private val _status = MutableStateFlow(Fold7DisplayStatus())
    val status: StateFlow<Fold7DisplayStatus> = _status.asStateFlow()

    fun update(transform: (Fold7DisplayStatus) -> Fold7DisplayStatus) {
        _status.value = transform(_status.value)
    }

    fun reset(reason: String = "idle") {
        _status.value = Fold7DisplayStatus(openingSource = reason)
    }
}
