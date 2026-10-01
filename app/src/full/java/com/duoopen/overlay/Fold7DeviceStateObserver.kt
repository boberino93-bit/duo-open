package com.duoopen.overlay

import android.content.Context
import android.os.Handler
import com.duoopen.debug.DuoDiagnostics
import java.lang.reflect.Proxy
import java.util.LinkedHashSet
import java.util.concurrent.Executor

/**
 * Fold7 wake-only device-state observer.
 *
 * Samsung state identifiers remain opaque. The first choice is Android's
 * semantic physical fold posture properties:
 *
 * - FOLD_IN_CLOSED
 * - FOLD_IN_HALF_OPEN
 * - FOLD_IN_OPEN
 *
 * If those properties are unavailable, a state id is learned as "folded"
 * only from independently confirmed native-cover topology + precise <=12°.
 *
 * Device state is infrastructure input only. It never becomes hinge geometry.
 */
internal class Fold7DeviceStateObserver(
    private val context: Context,
    private val handler: Handler,
    private val onOpeningEdge: (
        previousStateId: Int,
        currentStateId: Int,
    ) -> Unit,
) {
    private var manager: Any? = null
    private var callback: Any? = null
    private var started = false

    private var lastStateId: Int? = null
    private var lastFolded: Boolean? = null

    private val learnedFoldedStateIds =
        LinkedHashSet<Int>()

    fun start() {
        if (started) return

        runCatching {
            org.lsposed.hiddenapibypass.HiddenApiBypass
                .addHiddenApiExemptions(
                    "Landroid/hardware/devicestate/"
                )
        }

        val result =
            runCatching {
                val localManager =
                    context.getSystemService(
                        DEVICE_STATE_SERVICE
                    )
                        ?: error(
                            "device_state service unavailable"
                        )

                val callbackClass =
                    Class.forName(
                        "android.hardware.devicestate.DeviceStateManager\$DeviceStateCallback"
                    )

                val localCallback =
                    Proxy.newProxyInstance(
                        context.classLoader,
                        arrayOf(
                            callbackClass
                        ),
                    ) {
                            proxy,
                            method,
                            args,
                        ->
                        when (
                            method.name
                        ) {
                            "onDeviceStateChanged",
                            "onStateChanged",
                            -> {
                                val raw =
                                    args
                                        ?.firstOrNull()

                                val id =
                                    stateIdentifier(
                                        raw
                                    )

                                if (id != null) {
                                    handleState(
                                        id = id,
                                        rawState = raw,
                                    )
                                }

                                null
                            }

                            "hashCode" ->
                                System.identityHashCode(
                                    proxy
                                )

                            "equals" ->
                                proxy ===
                                    args
                                        ?.firstOrNull()

                            "toString" ->
                                "Fold7DeviceStateObserverCallback"

                            else ->
                                null
                        }
                    }

                val register =
                    localManager
                        .javaClass
                        .methods
                        .firstOrNull {
                            it.name ==
                                "registerCallback" &&
                                it.parameterCount ==
                                    2
                        }
                        ?: error(
                            "registerCallback unavailable"
                        )

                register.isAccessible =
                    true

                val executor =
                    Executor { runnable ->
                        handler.post(
                            runnable
                        )
                    }

                register.invoke(
                    localManager,
                    executor,
                    localCallback,
                )

                manager =
                    localManager

                callback =
                    localCallback

                started =
                    true
            }

        result.onSuccess {
            DuoDiagnostics.event(
                "early-wake",
                "device-state observer registered",
            )
        }.onFailure { error ->
            DuoDiagnostics.event(
                "early-wake",
                "device-state observer unavailable " +
                    "error=${error.javaClass.simpleName}:${error.message}",
            )
        }
    }

    fun stop() {
        if (!started) return

        val localManager =
            manager

        val localCallback =
            callback

        runCatching {
            if (
                localManager != null &&
                localCallback != null
            ) {
                val unregister =
                    localManager
                        .javaClass
                        .methods
                        .firstOrNull {
                            it.name ==
                                "unregisterCallback" &&
                                it.parameterCount ==
                                    1
                        }

                unregister
                    ?.apply {
                        isAccessible =
                            true
                    }
                    ?.invoke(
                        localManager,
                        localCallback,
                    )
            }
        }

        started =
            false

        manager =
            null

        callback =
            null
    }

    fun corroborateFoldedRest(
        nativeCover: Boolean,
        preciseAngle: Float,
    ) {
        if (
            !nativeCover ||
            !preciseAngle.isFinite() ||
            preciseAngle >
                CLOSED_MAX_DEG
        ) {
            return
        }

        val id =
            lastStateId
                ?: return

        val learned =
            learnedFoldedStateIds
                .add(
                    id
                )

        lastFolded =
            true

        if (learned) {
            DuoDiagnostics.event(
                "early-wake",
                "learned folded device-state id=$id " +
                    "from native-cover precise=$preciseAngle",
            )
        }
    }

    private fun handleState(
        id: Int,
        rawState: Any?,
    ) {
        val previousId =
            lastStateId

        val previousFolded =
            lastFolded

        val physicalClosed =
            physicalClosedProperty(
                rawState
            )

        val outerPrimary =
            hasNamedProperty(
                rawState,
                "PROPERTY_FOLDABLE_DISPLAY_CONFIGURATION_OUTER_PRIMARY",
            )

        val inferredFolded =
            when {
                physicalClosed != null ->
                    physicalClosed

                id in learnedFoldedStateIds ->
                    true

                previousId != null &&
                    previousId in learnedFoldedStateIds &&
                    id != previousId ->
                    false

                outerPrimary == true ->
                    true

                else ->
                    null
            }

        lastStateId =
            id

        if (
            inferredFolded != null
        ) {
            lastFolded =
                inferredFolded
        }

        val source =
            when {
                physicalClosed != null ->
                    "physical-posture"
                id in learnedFoldedStateIds ->
                    "learned-folded-id"
                previousId != null &&
                    previousId in learnedFoldedStateIds &&
                    id != previousId ->
                    "learned-opening-edge"
                outerPrimary == true ->
                    "outer-primary"
                else ->
                    "unknown"
            }

        DuoDiagnostics.event(
            "early-wake",
            "device-state previous=$previousId current=$id " +
                "folded=$inferredFolded source=$source",
        )

        if (
            previousId != null &&
            previousFolded == true &&
            inferredFolded == false
        ) {
            onOpeningEdge(
                previousId,
                id,
            )
        }
    }

    private fun physicalClosedProperty(
        rawState: Any?,
    ): Boolean? {
        val closed =
            hasNamedProperty(
                rawState,
                "PROPERTY_FOLDABLE_HARDWARE_CONFIGURATION_FOLD_IN_CLOSED",
            )

        val halfOpen =
            hasNamedProperty(
                rawState,
                "PROPERTY_FOLDABLE_HARDWARE_CONFIGURATION_FOLD_IN_HALF_OPEN",
            )

        val open =
            hasNamedProperty(
                rawState,
                "PROPERTY_FOLDABLE_HARDWARE_CONFIGURATION_FOLD_IN_OPEN",
            )

        return when {
            closed == true ->
                true
            halfOpen == true ||
                open == true ->
                false
            else ->
                null
        }
    }

    private fun hasNamedProperty(
        rawState: Any?,
        fieldName: String,
    ): Boolean? {
        if (
            rawState == null ||
            rawState is Number
        ) {
            return null
        }

        return runCatching {
            val stateClass =
                Class.forName(
                    "android.hardware.devicestate.DeviceState"
                )

            if (
                !stateClass
                    .isInstance(
                        rawState
                    )
            ) {
                return@runCatching null
            }

            val property =
                stateClass
                    .getField(
                        fieldName
                    )
                    .getInt(
                        null
                    )

            stateClass
                .getMethod(
                    "hasProperty",
                    Integer.TYPE,
                )
                .invoke(
                    rawState,
                    property,
                ) as Boolean
        }.getOrNull()
    }

    private fun stateIdentifier(
        rawState: Any?,
    ): Int? =
        when (
            rawState
        ) {
            null ->
                null

            is Number ->
                rawState
                    .toInt()

            else ->
                runCatching {
                    (
                        rawState
                            .javaClass
                            .getMethod(
                                "getIdentifier"
                            )
                            .invoke(
                                rawState
                            ) as Number
                        )
                        .toInt()
                }.getOrNull()
        }

    private companion object {
        const val DEVICE_STATE_SERVICE =
            "device_state"

        const val CLOSED_MAX_DEG =
            12f
    }
}
