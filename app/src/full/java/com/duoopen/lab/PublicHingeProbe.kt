package com.duoopen.lab

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.util.Log

/**
 * Observation-only public hinge probe.
 *
 * It deliberately does not participate in production source arbitration.
 * Transition Lab registers its own listener so SensorEvent.timestamp can be
 * measured without changing HingeAngleSource behavior.
 */
internal class PublicHingeProbe(
    context: Context,
    private val sink: (Sample) -> Unit,
) : SensorEventListener {
    data class Sample(
        val angleDegrees: Float,
        /** Sensor HAL timestamp in elapsedRealtimeNanos() domain. */
        val sensorTimestampNs: Long,
        /** Listener callback arrival in Transition Lab's monotonic domain. */
        val callbackArrivalTimeNs: Long,
        val sensorName: String,
        val sensorType: Int,
        val resolutionDegrees: Float,
        val coarse: Boolean,
    )

    private val sensorManager =
        context.applicationContext.getSystemService(
            SensorManager::class.java
        )

    private val candidates =
        discover()

    private var started =
        false

    fun start() {
        if (started) return

        started = true

        for (sensor in candidates) {
            val registered =
                try {
                    sensorManager?.registerListener(
                        this,
                        sensor,
                        SAMPLING_PERIOD_US,
                    ) == true
                } catch (error: SecurityException) {
                    Log.d(
                        TAG,
                        "observation denied for ${sensor.name}: ${error.message}",
                    )
                    false
                }

            Log.d(
                TAG,
                "candidate ${sensor.name} " +
                    "type=${sensor.type} " +
                    "resolution=${sensor.resolution} " +
                    "registered=$registered",
            )
        }
    }

    fun stop() {
        if (!started) return

        started = false
        sensorManager?.unregisterListener(this)
    }

    override fun onSensorChanged(
        event: SensorEvent,
    ) {
        val value =
            event.values.firstOrNull()
                ?: return

        if (
            !value.isFinite() ||
            value < -PLAUSIBLE_SLACK ||
            value > 180f + PLAUSIBLE_SLACK
        ) {
            return
        }

        val resolution =
            event.sensor.resolution
                .takeIf {
                    it.isFinite() &&
                        it > 0f
                }
                ?: 1f

        sink(
            Sample(
                angleDegrees =
                    value.coerceIn(
                        0f,
                        180f,
                    ),
                sensorTimestampNs =
                    event.timestamp,
                callbackArrivalTimeNs =
                    TransitionClock.nowNs(),
                sensorName =
                    event.sensor.name,
                sensorType =
                    event.sensor.type,
                resolutionDegrees =
                    resolution,
                coarse =
                    resolution >=
                        COARSE_RESOLUTION,
            )
        )
    }

    override fun onAccuracyChanged(
        sensor: Sensor?,
        accuracy: Int,
    ) = Unit

    private fun discover(): List<Sensor> {
        val manager =
            sensorManager
                ?: return emptyList()

        val all =
            runCatching {
                manager.getSensorList(
                    Sensor.TYPE_ALL
                )
            }.getOrNull()
                .orEmpty()

        val standard =
            all.filter {
                it.type ==
                    Sensor.TYPE_HINGE_ANGLE
            }.ifEmpty {
                listOfNotNull(
                    manager.getDefaultSensor(
                        Sensor.TYPE_HINGE_ANGLE
                    )
                )
            }

        val vendor =
            all.filter { sensor ->
                sensor.type >=
                    Sensor.TYPE_DEVICE_PRIVATE_BASE &&
                    isAngleCandidate(sensor)
            }

        return (
            standard +
                vendor
            ).distinctBy {
                "${it.type}|${it.name}|${it.isWakeUpSensor}"
            }
    }

    private fun isAngleCandidate(
        sensor: Sensor,
    ): Boolean {
        val text =
            "${sensor.name} ${sensor.stringType}"
                .lowercase()

        if (
            !text.contains("hinge") &&
            !text.contains("fold")
        ) {
            return false
        }

        val range =
            sensor.maximumRange

        if (
            !range.isFinite() ||
            range !in 150f..360f
        ) {
            return false
        }

        return (
            sensor.reportingMode ==
                Sensor.REPORTING_MODE_CONTINUOUS ||
                sensor.reportingMode ==
                    Sensor.REPORTING_MODE_ON_CHANGE
            )
    }

    private companion object {
        const val TAG =
            "DuoTransitionLab"

        const val SAMPLING_PERIOD_US =
            8_000

        const val PLAUSIBLE_SLACK =
            5f

        const val COARSE_RESOLUTION =
            45f
    }
}
