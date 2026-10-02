package com.duoopen.fold

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Build
import android.os.Handler
import android.os.SystemClock
import android.util.Log
import kotlin.math.abs
import kotlin.math.roundToInt

/**
 * Fold7 hinge acquisition plus the single authoritative geometry owner.
 *
 * Public/vendor sensors and Samsung FoldInteractive are producers. They never
 * arbitrate against each other directly. [Fold7AngleAuthority] owns that choice,
 * retains public on-change samples while precise geometry is healthy, and can
 * promote the retained fallback when precise geometry expires without waiting
 * for another physical movement.
 */
class HingeAngleSource(
    context: Context,
    private val onAngle: (Float) -> Unit,
    private val onAuthoritativeSample: ((AuthoritativeSample) -> Unit)? = null,
    private val callbackHandler: Handler? = null,
) : SensorEventListener {

    data class AuthoritativeSample(
        val angle: Float,
        val observedUptimeMs: Long,
        val deliveredUptimeMs: Long,
        val source: String,
        val coarse: Boolean,
        val reason: String,
    )

    private class Stats(val sensor: Sensor) {
        var events = 0
        var last = Float.NaN
        var registered = false
        val distinct = LinkedHashSet<Int>()
        val resolution: Float
            get() = sensor.resolution.takeIf { it.isFinite() && it > 0f } ?: 1f
        val isStandard: Boolean get() = sensor.type == Sensor.TYPE_HINGE_ANGLE

        fun observe(value: Float) {
            events++
            last = value
            if (distinct.size < MAX_DISTINCT) distinct += value.roundToInt()
        }

        val looksCoarse: Boolean
            get() = resolution >= COARSE_RESOLUTION ||
                (events >= COARSE_MIN_EVENTS && distinct.size <= 3 &&
                    distinct.all { v -> STOPS.any { abs(v - it) <= 2 } })
    }

    private val sensorManager = context.getSystemService(SensorManager::class.java)
    private val candidates: List<Stats> = discover().map(::Stats)
    private val authority = Fold7AngleAuthority()

    val sensors: List<Sensor> get() = candidates.map { it.sensor }
    val sensor: Sensor? get() = activeSensor ?: candidates.firstOrNull()?.sensor

    var activeSensor: Sensor? = null
        private set

    /** Latest authoritative angle, regardless of which producer supplied it. */
    var lastAngle: Float = Float.NaN
        private set

    var rateHz: Float = 0f
        private set

    val externalActive: Boolean
        get() {
            val snapshot = authority.snapshot(SystemClock.uptimeMillis())
            return snapshot.preciseLeaseRemainingMs > 0L &&
                (snapshot.source == Fold7AngleAuthority.Source.SAMSUNG_PRECISE ||
                    snapshot.source == Fold7AngleAuthority.Source.SYNTHETIC_ENDPOINT)
        }

    val isCoarse: Boolean
        get() {
            val snapshot = authority.snapshot(SystemClock.uptimeMillis())
            return when (snapshot.source) {
                Fold7AngleAuthority.Source.PUBLIC_STANDARD,
                Fold7AngleAuthority.Source.PUBLIC_VENDOR -> snapshot.coarse
                Fold7AngleAuthority.Source.SAMSUNG_PRECISE,
                Fold7AngleAuthority.Source.SYNTHETIC_ENDPOINT -> false
                Fold7AngleAuthority.Source.NONE ->
                    (active ?: candidates.firstOrNull())?.looksCoarse == true
            }
        }

    private var active: Stats? = null
    private var started = false
    private var lastEventUptime = 0L
    private var rateWindowStart = 0L
    private var rateWindowCount = 0

    private val preciseExpiryRunnable =
        Runnable {
            val now = SystemClock.uptimeMillis()
            val decision =
                authority.expirePrecise(
                    nowUptimeMs = now,
                    reason = "precise-lease-expired",
                )
            handleDecision(decision)
        }

    fun beginExternalSession(session: Long) {
        val now = SystemClock.uptimeMillis()
        callbackHandler?.removeCallbacks(preciseExpiryRunnable)
        val decision = authority.startPreciseSession(session, now)
        handleDecision(decision)
        Log.i(TAG, "precise session start=$session")
    }

    fun feedExternal(
        session: Long,
        sequence: Long,
        angle: Float,
        sourceUptimeMs: Long,
        receivedUptimeMs: Long = SystemClock.uptimeMillis(),
    ) {
        val decision =
            authority.offerPrecise(
                session = session,
                sequence = sequence,
                angle = angle,
                observedUptimeMs = sourceUptimeMs,
                receivedUptimeMs = receivedUptimeMs,
            )
        handleDecision(decision)
        if (decision.accepted) schedulePreciseExpiry(receivedUptimeMs)
    }

    fun feedSyntheticExternal(
        session: Long,
        angle: Float,
        sourceUptimeMs: Long = SystemClock.uptimeMillis(),
        reason: String,
    ) {
        val decision =
            authority.offerSyntheticEndpoint(
                session = session,
                angle = angle,
                nowUptimeMs = sourceUptimeMs,
                reason = reason,
            )
        handleDecision(decision)
        if (decision.accepted) schedulePreciseExpiry(sourceUptimeMs)
    }

    /** Expire precise authority but keep the reader session eligible to recover. */
    fun expireExternal(reason: String) {
        val decision =
            authority.expirePrecise(
                nowUptimeMs = SystemClock.uptimeMillis(),
                reason = reason,
            )
        handleDecision(decision)
    }

    /** Permanently revoke one reader session; late callbacks from it stay inert. */
    fun revokeExternalSession(
        session: Long,
        reason: String,
    ) {
        callbackHandler?.removeCallbacks(preciseExpiryRunnable)
        val decision =
            authority.revokePreciseSession(
                session = session,
                nowUptimeMs = SystemClock.uptimeMillis(),
                reason = reason,
            )
        handleDecision(decision)
    }

    /** Compatibility entrypoint for older callers; does not invalidate session identity. */
    fun clearExternal() {
        expireExternal("legacy-clear")
    }

    fun lastEventAgeMs(): Long {
        val snapshot = authority.snapshot(SystemClock.uptimeMillis())
        return snapshot.sourceAgeMs
    }

    fun statusText(): String {
        val now = SystemClock.uptimeMillis()
        val snapshot = authority.snapshot(now)
        val raw = if (snapshot.angle.isNaN()) "—" else "%.1f°".format(snapshot.angle)
        val age =
            if (snapshot.sourceAgeMs == Long.MAX_VALUE) "no sample"
            else "${snapshot.sourceAgeMs} ms old"
        val rate = if (rateHz > 0f) "%.0f Hz".format(rateHz) else "idle"
        val shadow =
            if (snapshot.publicShadowAngle.isFinite()) {
                " · public shadow %.1f°/%dms".format(
                    snapshot.publicShadowAngle,
                    snapshot.publicShadowAgeMs,
                )
            } else {
                ""
            }

        return when (snapshot.source) {
            Fold7AngleAuthority.Source.SAMSUNG_PRECISE ->
                "Authoritative Samsung precise · $rate · raw $raw · $age · lease ${snapshot.preciseLeaseRemainingMs} ms$shadow"

            Fold7AngleAuthority.Source.SYNTHETIC_ENDPOINT ->
                "Authoritative endpoint bridge · raw $raw · $age · lease ${snapshot.preciseLeaseRemainingMs} ms$shadow"

            Fold7AngleAuthority.Source.PUBLIC_STANDARD,
            Fold7AngleAuthority.Source.PUBLIC_VENDOR -> {
                val s = active ?: candidates.firstOrNull()
                val name = s?.sensor?.name?.trim() ?: "public hinge sensor"
                val coarse = if (snapshot.coarse) "coarse" else "fine"
                "Authoritative $name · $coarse · $rate · raw $raw · $age"
            }

            Fold7AngleAuthority.Source.NONE ->
                if (snapshot.angle.isFinite()) {
                    "Geometry unknown/stale · holding $raw · $age$shadow"
                } else {
                    "Geometry unknown · waiting for first authoritative sample$shadow"
                }
        }
    }

    fun report(): String = buildString {
        val snapshot = authority.snapshot(SystemClock.uptimeMillis())
        appendLine("Duo Open hinge authority report")
        appendLine("device=${Build.MANUFACTURER} ${Build.MODEL} (${Build.DEVICE}) android=${Build.VERSION.RELEASE}")
        appendLine(
            "authority=${snapshot.source} angle=${snapshot.angle} ageMs=${snapshot.sourceAgeMs} " +
                "coarse=${snapshot.coarse} preciseSession=${snapshot.preciseSession} " +
                "leaseRemainingMs=${snapshot.preciseLeaseRemainingMs}",
        )
        appendLine(
            "publicShadow=${snapshot.publicShadowAngle} shadowAgeMs=${snapshot.publicShadowAgeMs} " +
                "drops(stale/session/sequence)=${snapshot.droppedStalePrecise}/" +
                "${snapshot.droppedSessionPrecise}/${snapshot.droppedSequencePrecise}",
        )
        appendLine("public candidates:")
        if (candidates.isEmpty()) appendLine("- (none)")
        for (c in candidates) {
            val s = c.sensor
            appendLine(
                "- ${s.name} type=${s.type} (${s.stringType}) vendor=${s.vendor} wakeUp=${s.isWakeUpSensor} " +
                    "res=${s.resolution} range=${s.maximumRange} mode=${s.reportingMode} minDelay=${s.minDelay}us " +
                    "registered=${c.registered} events=${c.events} distinct=${c.distinct} last=${c.last}",
            )
        }
        val others = allSensors().filter { s -> isFoldRelated(s) && candidates.none { it.sensor == s } }
        if (others.isNotEmpty()) {
            appendLine("other fold-related sensors (not angle candidates):")
            for (s in others) {
                appendLine("- ${s.name} type=${s.type} (${s.stringType}) range=${s.maximumRange} wakeUp=${s.isWakeUpSensor}")
            }
        }
        appendLine()
        append(com.duoopen.debug.DuoDiagnostics.report())
    }

    fun start() {
        if (started) return
        started = true
        val sm = sensorManager ?: return
        if (candidates.isEmpty()) {
            Log.w(TAG, "no hinge angle sensor found")
            return
        }
        for (c in candidates) {
            c.registered = try {
                if (callbackHandler != null) {
                    sm.registerListener(this, c.sensor, SAMPLING_PERIOD_US, callbackHandler)
                } else {
                    sm.registerListener(this, c.sensor, SAMPLING_PERIOD_US)
                }
            } catch (e: SecurityException) {
                Log.w(TAG, "register denied for ${c.sensor.name}: ${e.message}")
                false
            }
            Log.i(
                TAG,
                "candidate ${c.sensor.name} type=${c.sensor.stringType} " +
                    "res=${c.sensor.resolution} wakeUp=${c.sensor.isWakeUpSensor} registered=${c.registered}",
            )
        }
    }

    fun stop() {
        if (!started) return
        started = false
        callbackHandler?.removeCallbacks(preciseExpiryRunnable)
        sensorManager?.unregisterListener(this)
        for (c in candidates) c.registered = false
    }

    override fun onSensorChanged(event: SensorEvent) {
        val value = event.values.firstOrNull() ?: return
        val stats = candidates.firstOrNull { it.sensor == event.sensor } ?: return

        if (!value.isFinite() || value < -PLAUSIBLE_SLACK || value > 180f + PLAUSIBLE_SLACK) return

        stats.observe(value)
        if (choose() !== stats) return

        val receivedUptimeMs = SystemClock.uptimeMillis()
        val elapsedNowNs = SystemClock.elapsedRealtimeNanos()
        val ageNs = (elapsedNowNs - event.timestamp).coerceAtLeast(0L)
        val observedUptimeMs =
            (receivedUptimeMs - ageNs / 1_000_000L)
                .coerceAtLeast(0L)

        val source =
            if (stats.isStandard) {
                Fold7AngleAuthority.Source.PUBLIC_STANDARD
            } else {
                Fold7AngleAuthority.Source.PUBLIC_VENDOR
            }

        val decision =
            authority.offerPublic(
                source = source,
                angle = value,
                observedUptimeMs = observedUptimeMs,
                receivedUptimeMs = receivedUptimeMs,
                coarse = stats.looksCoarse,
            )

        handleDecision(decision)
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit

    private fun handleDecision(decision: Fold7AngleAuthority.Decision) {
        if (!decision.accepted && decision.dropReason != null) {
            Log.d(
                TAG,
                "angle authority drop reason=${decision.dropReason} age=${decision.sourceAgeMs}",
            )
        }

        if (decision.output == null) {
            if (
                decision.stateChanged &&
                authority.snapshot(SystemClock.uptimeMillis()).source ==
                    Fold7AngleAuthority.Source.NONE
            ) {
                // No source currently owns geometry. Do not let downstream
                // code mistake the last precise sample for a current angle.
                lastAngle = Float.NaN
            }
            return
        }

        val output = decision.output
        val delivered = output.deliveredUptimeMs
        tickRate(delivered)
        lastEventUptime = output.observedUptimeMs
        lastAngle = output.angle

        val sample =
            AuthoritativeSample(
                angle = output.angle,
                observedUptimeMs = output.observedUptimeMs,
                deliveredUptimeMs = output.deliveredUptimeMs,
                source = output.source.name,
                coarse = output.coarse,
                reason = output.reason,
            )

        onAuthoritativeSample?.invoke(sample)
        onAngle(output.angle)
    }

    private fun schedulePreciseExpiry(nowUptimeMs: Long) {
        val h = callbackHandler ?: return
        h.removeCallbacks(preciseExpiryRunnable)
        val expiry = authority.nextPreciseExpiryUptimeMs() ?: return
        h.postDelayed(
            preciseExpiryRunnable,
            (expiry - nowUptimeMs + 1L).coerceAtLeast(1L),
        )
    }

    private fun choose(): Stats? {
        val reporting = candidates.filter { it.events > 0 }
        if (reporting.isEmpty()) return null
        val best = reporting.minWithOrNull(compareBy<Stats> { it.resolution }.thenBy { !it.isStandard })!!
        val current = active
        if (current == null || best.resolution < current.resolution) {
            if (current !== best) Log.i(TAG, "public hinge source: ${best.sensor.name} (res ${best.resolution})")
            active = best
            activeSensor = best.sensor
            return best
        }
        return current
    }

    private fun tickRate(now: Long) {
        if (rateWindowStart == 0L || now - lastEventUptime > 1_000L) {
            rateWindowStart = now
            rateWindowCount = 0
        }
        rateWindowCount++
        val elapsed = now - rateWindowStart
        if (elapsed >= 500L) {
            rateHz = rateWindowCount * 1000f / elapsed
            rateWindowStart = now
            rateWindowCount = 0
        }
    }

    private fun allSensors(): List<Sensor> =
        runCatching { sensorManager?.getSensorList(Sensor.TYPE_ALL) }.getOrNull().orEmpty()

    private fun discover(): List<Sensor> {
        val all = allSensors()
        val standard =
            all.filter { it.type == Sensor.TYPE_HINGE_ANGLE }
                .ifEmpty { listOfNotNull(sensorManager?.getDefaultSensor(Sensor.TYPE_HINGE_ANGLE)) }
                .sortedBy { it.isWakeUpSensor }
        val vendor = all.filter { it.type >= Sensor.TYPE_DEVICE_PRIVATE_BASE && isAngleCandidate(it) }
        return (standard + vendor).distinctBy { "${it.type}|${it.name}|${it.isWakeUpSensor}" }
    }

    private fun isAngleCandidate(s: Sensor): Boolean {
        if (!isFoldRelated(s)) return false
        val range = s.maximumRange
        if (!range.isFinite() || range !in 150f..360f) return false
        return s.reportingMode == Sensor.REPORTING_MODE_CONTINUOUS ||
            s.reportingMode == Sensor.REPORTING_MODE_ON_CHANGE
    }

    private fun isFoldRelated(s: Sensor): Boolean {
        val text = "${s.name} ${s.stringType}".lowercase()
        return text.contains("hinge") || text.contains("fold")
    }

    private companion object {
        const val TAG = "DuoHinge"
        const val SAMPLING_PERIOD_US = 8_000
        const val PLAUSIBLE_SLACK = 5f
        const val COARSE_RESOLUTION = 45f
        const val COARSE_MIN_EVENTS = 6
        const val MAX_DISTINCT = 8
        val STOPS = intArrayOf(0, 90, 180)
    }
}
