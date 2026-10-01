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

# Require tested Batch B as the base before changing acquisition threading.
require(bridge, "fun startAnglesSequenced(", "Batch B bridge prerequisite")
require(shell, "p.writeLong(parsedLine.pollSequence)", "Batch B shell prerequisite")

replace_once(
    hinge,
    "import android.os.Build\nimport android.os.SystemClock\n",
    "import android.os.Build\nimport android.os.Handler\nimport android.os.Looper\nimport android.os.SystemClock\n",
    "HingeAngleSource handler imports",
)

replace_once(
    hinge,
    '''class HingeAngleSource(\n    context: Context,\n    private val onAngle: (Float) -> Unit,\n) : SensorEventListener {''',
    '''class HingeAngleSource(\n    context: Context,\n    private val sensorHandler: Handler? = null,\n    private val deliveryHandler: Handler? = null,\n    private val onAngle: (Float) -> Unit,\n) : SensorEventListener {''',
    "HingeAngleSource explicit callback handlers",
)

replace_once(
    hinge,
    '''            c.registered = try {\n                sm.registerListener(this, c.sensor, SAMPLING_PERIOD_US)\n            } catch (e: SecurityException) {''',
    '''            c.registered = try {\n                val callbackHandler = sensorHandler\n                if (callbackHandler == null) {\n                    sm.registerListener(\n                        this,\n                        c.sensor,\n                        SAMPLING_PERIOD_US,\n                    )\n                } else {\n                    sm.registerListener(\n                        this,\n                        c.sensor,\n                        SAMPLING_PERIOD_US,\n                        callbackHandler,\n                    )\n                }\n            } catch (e: SecurityException) {''',
    "explicit SensorManager Handler overload",
)

old_sensor = '''    override fun onSensorChanged(event: SensorEvent) {\n        val value = event.values.firstOrNull() ?: return\n        val stats = candidates.firstOrNull { it.sensor == event.sensor } ?: return\n        // An external continuous source wins while it's alive; if it goes\n        // quiet the sensors take over again.\n        if (externalActive) {\n            if (SystemClock.uptimeMillis() - externalLastUptime < EXTERNAL_STALE_MS) return\n            externalActive = false\n        }\n\n        val coarseMidpointAfterContinuousEndpoint =\n            lastAngle.isFinite() &&\n                value in COARSE_MIDPOINT_MIN_DEG..\n                    COARSE_MIDPOINT_MAX_DEG &&\n                (\n                    lastAngle <=\n                        CONTINUOUS_ENDPOINT_LOW_GUARD_DEG ||\n                        lastAngle >=\n                            CONTINUOUS_ENDPOINT_HIGH_GUARD_DEG\n                    )\n\n        if (coarseMidpointAfterContinuousEndpoint) {\n            Log.d(\n                TAG,\n                "ignoring coarse midpoint $value after continuous endpoint $lastAngle"\n            )\n            return\n        }\n\n        // Not an angle in degrees (state code, radians, normalized): ignore.\n        if (!value.isFinite() || value < -PLAUSIBLE_SLACK || value > 180f + PLAUSIBLE_SLACK) return\n        stats.observe(value)\n        if (choose() !== stats) return\n\n        val now = SystemClock.uptimeMillis()\n        tickRate(now)\n        lastEventUptime = now\n        lastAngle = value.coerceIn(0f, 180f)\n        onAngle(lastAngle)\n    }\n'''

new_sensor = '''    override fun onSensorChanged(event: SensorEvent) {\n        val value = event.values.firstOrNull() ?: return\n        val sensor = event.sensor\n        val target = deliveryHandler\n\n        /*\n         * SensorManager delivers on the dedicated Fold7 control looper when\n         * configured by FoldOverlayService. Keep all existing source\n         * arbitration/controller/render state on the established delivery\n         * looper for this migration batch. SensorEvent instances are reused by\n         * Android, so copy the only values we need before posting.\n         */\n        if (\n            target != null &&\n            Looper.myLooper() != target.looper\n        ) {\n            target.post {\n                handleSensorSample(\n                    sensor = sensor,\n                    value = value,\n                )\n            }\n            return\n        }\n\n        handleSensorSample(\n            sensor = sensor,\n            value = value,\n        )\n    }\n\n    private fun handleSensorSample(\n        sensor: Sensor,\n        value: Float,\n    ) {\n        // A callback queued before stop() must not mutate a dead service.\n        if (!started) return\n\n        val stats = candidates.firstOrNull { it.sensor == sensor } ?: return\n        // An external continuous source wins while it's alive; if it goes\n        // quiet the sensors take over again.\n        if (externalActive) {\n            if (SystemClock.uptimeMillis() - externalLastUptime < EXTERNAL_STALE_MS) return\n            externalActive = false\n        }\n\n        val coarseMidpointAfterContinuousEndpoint =\n            lastAngle.isFinite() &&\n                value in COARSE_MIDPOINT_MIN_DEG..\n                    COARSE_MIDPOINT_MAX_DEG &&\n                (\n                    lastAngle <=\n                        CONTINUOUS_ENDPOINT_LOW_GUARD_DEG ||\n                        lastAngle >=\n                            CONTINUOUS_ENDPOINT_HIGH_GUARD_DEG\n                    )\n\n        if (coarseMidpointAfterContinuousEndpoint) {\n            Log.d(\n                TAG,\n                "ignoring coarse midpoint $value after continuous endpoint $lastAngle"\n            )\n            return\n        }\n\n        // Not an angle in degrees (state code, radians, normalized): ignore.\n        if (!value.isFinite() || value < -PLAUSIBLE_SLACK || value > 180f + PLAUSIBLE_SLACK) return\n        stats.observe(value)\n        if (choose() !== stats) return\n\n        val now = SystemClock.uptimeMillis()\n        tickRate(now)\n        lastEventUptime = now\n        lastAngle = value.coerceIn(0f, 180f)\n        onAngle(lastAngle)\n    }\n'''
replace_once(hinge, old_sensor, new_sensor, "public hinge control-thread delivery bridge")

replace_once(
    service,
    "import android.os.Handler\nimport android.os.Looper\n",
    "import android.os.Handler\nimport android.os.HandlerThread\nimport android.os.Looper\n",
    "FoldOverlayService HandlerThread import",
)

replace_once(
    service,
    '''    private val handler = Handler(Looper.getMainLooper())\n    private val scope = MainScope()\n''',
    '''    private val handler = Handler(Looper.getMainLooper())\n    private var angleControlThread: HandlerThread? = null\n    private var angleControlHandler: Handler? = null\n    private val scope = MainScope()\n''',
    "FoldOverlayService control-thread fields",
)

replace_once(
    service,
    '''        displayManager.registerDisplayListener(displayListener, handler)\n        hinge = HingeAngleSource(this) { onHinge(it) }\n        hinge.start()\n''',
    '''        displayManager.registerDisplayListener(displayListener, handler)\n\n        val controlThread =\n            HandlerThread(\n                "duo-fold7-angle-control"\n            ).also {\n                it.start()\n            }\n\n        angleControlThread =\n            controlThread\n\n        val controlHandler =\n            Handler(\n                controlThread.looper\n            )\n\n        angleControlHandler =\n            controlHandler\n\n        hinge =\n            HingeAngleSource(\n                context = this,\n                sensorHandler = controlHandler,\n                deliveryHandler = handler,\n            ) { angle ->\n                onHinge(angle)\n            }\n        hinge.start()\n''',
    "FoldOverlayService control-thread startup",
)

replace_once(
    service,
    '''        angleFeed?.stop()\n        if (receiverRegistered) unregisterReceiver(demoReceiver)\n        hinge.stop()\n        displayManager.unregisterDisplayListener(displayListener)\n''',
    '''        angleFeed?.stop()\n        if (receiverRegistered) unregisterReceiver(demoReceiver)\n        hinge.stop()\n\n        angleControlThread?.quitSafely()\n        angleControlThread = null\n        angleControlHandler = null\n\n        displayManager.unregisterDisplayListener(displayListener)\n''',
    "FoldOverlayService control-thread shutdown",
)

require(hinge, "sm.registerListener(\n                        this,\n                        c.sensor,\n                        SAMPLING_PERIOD_US,\n                        callbackHandler,", "explicit sensor callback handler postcondition")
require(hinge, "Looper.myLooper() != target.looper", "delivery-looper guard postcondition")
require(hinge, "if (!started) return", "stale queued callback guard")
require(service, 'HandlerThread(\n                "duo-fold7-angle-control"', "single control-thread creation")
require(service, "sensorHandler = controlHandler", "control handler wired to HingeAngleSource")
require(service, "deliveryHandler = handler", "main delivery preserved")
require(service, "angleControlThread?.quitSafely()", "control-thread shutdown")

print("Gen-2 Batch C patch complete.")
