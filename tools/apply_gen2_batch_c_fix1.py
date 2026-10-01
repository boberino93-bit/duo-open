#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source anchor in {path}, found {count}")
    path.write_text(text.replace(old, new, 1))
    print(f"patched {label}: {path}")

def require(path: Path, needle: str, label: str) -> None:
    text = path.read_text()
    if needle not in text:
        raise SystemExit(f"{label}: required text not found in {path}: {needle!r}")

hinge = ROOT / "app/src/main/java/com/duoopen/fold/HingeAngleSource.kt"
service = ROOT / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"
bridge = ROOT / "app/src/full/java/com/duoopen/shell/ShizukuBridge.kt"
shell = ROOT / "app/src/full/java/com/duoopen/shell/DuoShellService.kt"

require(bridge, "fun startAnglesSequenced(", "Batch B bridge prerequisite")
require(shell, "p.writeLong(parsedLine.pollSequence)", "Batch B shell prerequisite")
require(hinge, "private val onAngle: (Float) -> Unit,", "original constructor prerequisite")

if "duo-fold7-angle-control" in service.read_text():
    raise SystemExit("Batch C appears already integrated; refusing to patch twice.")

replace_once(
    hinge,
    "import android.os.Build\nimport android.os.SystemClock\n",
    "import android.os.Build\nimport android.os.Handler\nimport android.os.Looper\nimport android.os.SystemClock\n",
    "HingeAngleSource handler imports",
)

replace_once(
    hinge,
    '''class HingeAngleSource(
    context: Context,
    private val onAngle: (Float) -> Unit,
) : SensorEventListener {''',
    '''class HingeAngleSource(
    context: Context,
    private val onAngle: (Float) -> Unit,
    private val sensorHandler: Handler? = null,
    private val deliveryHandler: Handler? = null,
) : SensorEventListener {''',
    "HingeAngleSource source-compatible handler parameters",
)

replace_once(
    hinge,
    '''            c.registered = try {
                sm.registerListener(this, c.sensor, SAMPLING_PERIOD_US)
            } catch (e: SecurityException) {''',
    '''            c.registered = try {
                val callbackHandler = sensorHandler
                if (callbackHandler == null) {
                    sm.registerListener(
                        this,
                        c.sensor,
                        SAMPLING_PERIOD_US,
                    )
                } else {
                    sm.registerListener(
                        this,
                        c.sensor,
                        SAMPLING_PERIOD_US,
                        callbackHandler,
                    )
                }
            } catch (e: SecurityException) {''',
    "explicit SensorManager Handler overload",
)

old_sensor = '''    override fun onSensorChanged(event: SensorEvent) {
        val value = event.values.firstOrNull() ?: return
        val stats = candidates.firstOrNull { it.sensor == event.sensor } ?: return
        // An external continuous source wins while it's alive; if it goes
        // quiet the sensors take over again.
        if (externalActive) {
            if (SystemClock.uptimeMillis() - externalLastUptime < EXTERNAL_STALE_MS) return
            externalActive = false
        }

        val coarseMidpointAfterContinuousEndpoint =
            lastAngle.isFinite() &&
                value in COARSE_MIDPOINT_MIN_DEG..
                    COARSE_MIDPOINT_MAX_DEG &&
                (
                    lastAngle <=
                        CONTINUOUS_ENDPOINT_LOW_GUARD_DEG ||
                        lastAngle >=
                            CONTINUOUS_ENDPOINT_HIGH_GUARD_DEG
                    )

        if (coarseMidpointAfterContinuousEndpoint) {
            Log.d(
                TAG,
                "ignoring coarse midpoint $value after continuous endpoint $lastAngle"
            )
            return
        }

        // Not an angle in degrees (state code, radians, normalized): ignore.
        if (!value.isFinite() || value < -PLAUSIBLE_SLACK || value > 180f + PLAUSIBLE_SLACK) return
        stats.observe(value)
        if (choose() !== stats) return

        val now = SystemClock.uptimeMillis()
        tickRate(now)
        lastEventUptime = now
        lastAngle = value.coerceIn(0f, 180f)
        onAngle(lastAngle)
    }
'''

new_sensor = '''    override fun onSensorChanged(event: SensorEvent) {
        val value = event.values.firstOrNull() ?: return
        val sensor = event.sensor
        val target = deliveryHandler

        /*
         * SensorManager delivers on the dedicated Fold7 control looper when
         * configured by FoldOverlayService. SensorEvent instances are reused,
         * so copy the sensor/value before crossing loopers. This migration
         * batch deliberately preserves controller/render delivery on main.
         */
        if (
            target != null &&
            Looper.myLooper() != target.looper
        ) {
            target.post {
                handleSensorSample(
                    sensor = sensor,
                    value = value,
                )
            }
            return
        }

        handleSensorSample(
            sensor = sensor,
            value = value,
        )
    }

    private fun handleSensorSample(
        sensor: Sensor,
        value: Float,
    ) {
        if (!started) return

        val stats = candidates.firstOrNull { it.sensor == sensor } ?: return

        if (externalActive) {
            if (SystemClock.uptimeMillis() - externalLastUptime < EXTERNAL_STALE_MS) return
            externalActive = false
        }

        val coarseMidpointAfterContinuousEndpoint =
            lastAngle.isFinite() &&
                value in COARSE_MIDPOINT_MIN_DEG..
                    COARSE_MIDPOINT_MAX_DEG &&
                (
                    lastAngle <=
                        CONTINUOUS_ENDPOINT_LOW_GUARD_DEG ||
                        lastAngle >=
                            CONTINUOUS_ENDPOINT_HIGH_GUARD_DEG
                    )

        if (coarseMidpointAfterContinuousEndpoint) {
            Log.d(
                TAG,
                "ignoring coarse midpoint $value after continuous endpoint $lastAngle"
            )
            return
        }

        if (!value.isFinite() || value < -PLAUSIBLE_SLACK || value > 180f + PLAUSIBLE_SLACK) return
        stats.observe(value)
        if (choose() !== stats) return

        val now = SystemClock.uptimeMillis()
        tickRate(now)
        lastEventUptime = now
        lastAngle = value.coerceIn(0f, 180f)
        onAngle(lastAngle)
    }
'''
replace_once(
    hinge,
    old_sensor,
    new_sensor,
    "public hinge control-thread delivery bridge",
)

replace_once(
    service,
    "import android.os.Handler\nimport android.os.Looper\n",
    "import android.os.Handler\nimport android.os.HandlerThread\nimport android.os.Looper\n",
    "FoldOverlayService HandlerThread import",
)

replace_once(
    service,
    '''    private val handler = Handler(Looper.getMainLooper())
    private val scope = MainScope()
''',
    '''    private val handler = Handler(Looper.getMainLooper())
    private var angleControlThread: HandlerThread? = null
    private var angleControlHandler: Handler? = null
    private val scope = MainScope()
''',
    "FoldOverlayService control-thread fields",
)

replace_once(
    service,
    '''        displayManager.registerDisplayListener(displayListener, handler)
        hinge = HingeAngleSource(this) { onHinge(it) }
        hinge.start()
''',
    '''        displayManager.registerDisplayListener(displayListener, handler)

        val controlThread =
            HandlerThread(
                "duo-fold7-angle-control"
            ).also {
                it.start()
            }

        angleControlThread =
            controlThread

        val controlHandler =
            Handler(
                controlThread.looper
            )

        angleControlHandler =
            controlHandler

        hinge =
            HingeAngleSource(
                context = this,
                onAngle = { angle ->
                    onHinge(angle)
                },
                sensorHandler = controlHandler,
                deliveryHandler = handler,
            )
        hinge.start()
''',
    "FoldOverlayService control-thread startup",
)

replace_once(
    service,
    '''        angleFeed?.stop()
        if (receiverRegistered) unregisterReceiver(demoReceiver)
        hinge.stop()
        displayManager.unregisterDisplayListener(displayListener)
''',
    '''        angleFeed?.stop()
        if (receiverRegistered) unregisterReceiver(demoReceiver)
        hinge.stop()

        angleControlThread?.quitSafely()
        angleControlThread = null
        angleControlHandler = null

        displayManager.unregisterDisplayListener(displayListener)
''',
    "FoldOverlayService control-thread shutdown",
)

require(
    hinge,
    "private val onAngle: (Float) -> Unit,\n    private val sensorHandler: Handler? = null,",
    "original constructor ordering preserved",
)
require(
    hinge,
    "sm.registerListener(\n                        this,\n                        c.sensor,\n                        SAMPLING_PERIOD_US,\n                        callbackHandler,",
    "explicit sensor callback handler postcondition",
)
require(hinge, "Looper.myLooper() != target.looper", "delivery-looper guard postcondition")
require(hinge, "if (!started) return", "stale queued callback guard")
require(service, 'HandlerThread(\n                "duo-fold7-angle-control"', "single control-thread creation")
require(service, "onAngle = { angle ->", "named onAngle preserves constructor compatibility")
require(service, "sensorHandler = controlHandler", "control handler wired to HingeAngleSource")
require(service, "deliveryHandler = handler", "main delivery preserved")
require(service, "angleControlThread?.quitSafely()", "control-thread shutdown")

print("Gen-2 Batch C Fix 1 patch complete.")
