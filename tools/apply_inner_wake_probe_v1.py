#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

MARKER = "INNER_WAKE_PROBE_V1"
COORD = "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"
SHELL = "app/src/full/java/com/duoopen/shell/DuoShellService.kt"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def regex_once(text: str, pattern: str, replacement: str, label: str) -> str:
    out, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one regex match, found {count}")
    return out


def transform_coordinator(text: str) -> str:
    if MARKER in text:
        return text
    if "attempt: Int = 1" not in text or "MAX_INNER_WAKE_ATTEMPTS" not in text:
        raise RuntimeError("Beta2 wake-retry source shape not present")

    text = replace_once(
        text,
        '''    private val controller =
        Fold7ContinuityController(
            onTransition = ::logTransition,
        )''',
        '''    private val controller =
        Fold7ContinuityController(
            onTransition = ::logTransition,
        )

    // INNER_WAKE_PROBE_V1: semantic opening identity is intentionally separate
    // from transition generation and presentation-attempt identity.
    private val openingWakeGate =
        Fold7OpeningWakeAttemptGate(
            serviceEpoch = serviceEpoch,
        )''',
        "opening wake gate field",
    )

    wake = r'''    private fun wakeInner(
        generation: Long,
        attempt: Int = 1,
        openingKey: Fold7OpeningWakeAttemptGate.Key? = openingWakeGate.current(),
    ) {
        if (
            !ShizukuBridge.ready ||
            openingKey == null ||
            !openingWakeGate.isCurrent(openingKey)
        ) {
            return
        }

        val openingState =
            controller.state in setOf(
                Fold7ContinuityController.State.OPENING_FROM_CLOSED,
                Fold7ContinuityController.State.INNER_HANDOFF,
            )

        if (!openingState) {
            return
        }

        val queuedAtNs =
            SystemClock.elapsedRealtimeNanos()

        scope.launch(Dispatchers.IO) {
            val startedAtNs =
                SystemClock.elapsedRealtimeNanos()

            // WAKE_COMMITTED is the transaction boundary: before this point a
            // reversal/new opening/lifecycle invalidation must make old work a
            // no-op. Ordinary INNER_HANDOFF does not retire the OpeningKey.
            if (!openingWakeGate.isCurrent(openingKey)) {
                DuoDiagnostics.event(
                    "inner-wake-stage",
                    "STALE_BEFORE_COMMIT serviceEpoch=${openingKey.serviceEpoch} " +
                        "openingAttempt=${openingKey.openingAttemptSequence} retry=$attempt",
                )
                return@launch
            }

            DuoDiagnostics.event(
                "inner-wake-stage",
                "WAKE_COMMITTED serviceEpoch=${openingKey.serviceEpoch} " +
                    "openingAttempt=${openingKey.openingAttemptSequence} retry=$attempt " +
                    "acceptedGeneration=${openingKey.acceptedGeneration} currentGeneration=${controller.generation}",
            )

            val result =
                runCatching {
                    ShizukuBridge.wakeInnerDisplay()
                }.getOrNull()

            val completedAtNs =
                SystemClock.elapsedRealtimeNanos()

            val queueMs =
                (startedAtNs - queuedAtNs) /
                    1_000_000.0

            val totalMs =
                (completedAtNs - queuedAtNs) /
                    1_000_000.0

            handler.post {
                val keyStillCurrent =
                    openingWakeGate.isCurrent(openingKey)

                val topologyNow =
                    topology()

                DuoDiagnostics.event(
                    "inner-wake-stage",
                    "WAKE_RESULT serviceEpoch=${openingKey.serviceEpoch} " +
                        "openingAttempt=${openingKey.openingAttemptSequence} retry=$attempt " +
                        "keyCurrent=$keyStillCurrent ok=${result?.getBoolean("ok", false) == true} " +
                        "physical=${result?.getLong("physicalDisplayId", -1L) ?: -1L} " +
                        "physicalPowered=${result?.getBoolean("physicalPowered", false) == true} " +
                        "physicalPowerMs=${result?.getLong("physicalPowerMs", -1L) ?: -1L} " +
                        "routeProbeCount=${result?.getInt("routeProbeCount", -1) ?: -1} " +
                        "routeFirstSeenMs=${result?.getLong("routeFirstSeenMs", -1L) ?: -1L} " +
                        "innerLogical=${result?.getInt("innerLogicalId", -1) ?: -1} " +
                        "logicalEnabled=${result?.getBoolean("innerLogicalEnabled", false) == true} " +
                        "logicalEnableMs=${result?.getLong("logicalEnableMs", -1L) ?: -1L} " +
                        "logicalPowered=${result?.getBoolean("innerLogicalPowered", false) == true} " +
                        "logicalPowerMs=${result?.getLong("logicalPowerMs", -1L) ?: -1L} " +
                        "logicalReady=${result?.getBoolean("logicalReady", false) == true} " +
                        "innerActive=${topologyNow.innerActive} innerDefault=${topologyNow.innerIsDefault} " +
                        "queueMs=${"%.3f".format(queueMs)} totalMs=${"%.3f".format(totalMs)} " +
                        "error=${result?.getString("error")} logicalError=${result?.getString("logicalError")}",
                )

                if (!keyStillCurrent) {
                    return@post
                }

                if (topologyNow.innerActive) {
                    openingWakeGate.complete(openingKey)
                    DuoDiagnostics.event(
                        "inner-wake-stage",
                        "TOPOLOGY_READY serviceEpoch=${openingKey.serviceEpoch} " +
                            "openingAttempt=${openingKey.openingAttemptSequence} retry=$attempt " +
                            "innerDefault=${topologyNow.innerIsDefault}",
                    )
                    return@post
                }

                val stillOpening =
                    controller.state in setOf(
                        Fold7ContinuityController.State.OPENING_FROM_CLOSED,
                        Fold7ContinuityController.State.INNER_HANDOFF,
                    )

                if (
                    stillOpening &&
                    ShizukuBridge.ready &&
                    openingWakeGate.isCurrent(openingKey) &&
                    attempt < MAX_INNER_WAKE_ATTEMPTS
                ) {
                    handler.postDelayed(
                        {
                            if (openingWakeGate.isCurrent(openingKey)) {
                                wakeInner(
                                    generation = controller.generation,
                                    attempt = attempt + 1,
                                    openingKey = openingKey,
                                )
                            }
                        },
                        INNER_WAKE_RETRY_MS,
                    )
                } else {
                    DuoDiagnostics.event(
                        "inner-wake-stage",
                        "NOT_READY serviceEpoch=${openingKey.serviceEpoch} " +
                            "openingAttempt=${openingKey.openingAttemptSequence} retry=$attempt " +
                            "state=${controller.state}",
                    )
                }
            }
        }
    }

    private fun beginPrewarm'''

    text = regex_once(
        text,
        r'''    private fun wakeInner\(\n        generation: Long,\n        attempt: Int = 1,\n    \) \{.*?\n    \}\n\n    private fun beginPrewarm''',
        wake,
        "attempt-fenced wakeInner",
    )

    text = replace_once(
        text,
        '''    fun release(reason: String) {
        armRequested = false''',
        '''    fun release(reason: String) {
        openingWakeGate.invalidate()
        armRequested = false''',
        "release invalidation",
    )
    text = replace_once(
        text,
        '''    fun destroy() {
        destroyed = true''',
        '''    fun destroy() {
        openingWakeGate.invalidate()
        destroyed = true''',
        "destroy invalidation",
    )
    text = replace_once(
        text,
        '''    fun onPrivilegedUnavailable() {
        val previousState =''',
        '''    fun onPrivilegedUnavailable() {
        openingWakeGate.invalidate()
        val previousState =''',
        "privilege invalidation",
    )
    text = replace_once(
        text,
        '''        val result =
            controller.reset(
                angle = angle,''',
        '''        openingWakeGate.invalidate()

        val result =
            controller.reset(
                angle = angle,''',
        "arm reset invalidation",
    )

    text = replace_once(
        text,
        '''    private fun logTransition(
        transition: Fold7ContinuityController.Transition,
    ) {
        val cycleChange =''',
        '''    private fun logTransition(
        transition: Fold7ContinuityController.Transition,
    ) {
        val wakeKey =
            openingWakeGate.onTransition(
                from = transition.from,
                to = transition.to,
                generation = transition.generation,
            )

        if (
            transition.to == Fold7ContinuityController.State.OPENING_FROM_CLOSED &&
            wakeKey != null
        ) {
            DuoDiagnostics.event(
                "inner-wake-stage",
                "OPENING_ACCEPTED serviceEpoch=${wakeKey.serviceEpoch} " +
                    "openingAttempt=${wakeKey.openingAttemptSequence} " +
                    "generation=${wakeKey.acceptedGeneration} reason=${transition.reason}",
            )
        }

        val cycleChange =''',
        "transition attempt tracking",
    )
    return text


def transform_shell(text: str) -> str:
    if MARKER in text:
        return text
    if 'putBoolean(\n                "innerLogicalPowered"' not in text:
        raise RuntimeError("Beta2 physical+logical wake source shape not present")

    method = r'''    private fun wakeInnerPhysicalDisplay(): Bundle {
        val t0 =
            SystemClock.elapsedRealtime()

        val physicalId =
            resolveFold7InnerPhysicalDisplayId()

        val physicalStart =
            SystemClock.elapsedRealtime()

        val (powered, error) =
            setPhysicalPowerNormal(
                physicalId
            )

        val physicalPowerMs =
            SystemClock.elapsedRealtime() - physicalStart

        var logicalId = -1
        var logicalEnabled = false
        var logicalPowered = false
        var logicalError: String? = null
        var routeProbeCount = 0
        var routeFirstSeenMs = -1L
        var logicalEnableMs = -1L
        var logicalPowerMs = -1L

        if (powered && physicalId >= 0L) {
            // INNER_WAKE_PROBE_V1: preserve Beta2 behavior but expose exactly
            // when Samsung publishes the disabled 1968x2184 route.
            for (attempt in 0 until 6) {
                routeProbeCount++
                val candidate =
                    runCatching {
                        logicalDisplayIdsDirect()
                            .asSequence()
                            .firstOrNull { id ->
                                directGeometry(id) == (1968 to 2184) &&
                                    physicalDisplayIdFromLogical(id) == physicalId
                            }
                    }.getOrNull()

                if (candidate != null) {
                    logicalId = candidate
                    routeFirstSeenMs =
                        SystemClock.elapsedRealtime() - t0
                    break
                }

                if (attempt < 5) {
                    Thread.sleep(8L)
                }
            }

            if (logicalId >= 0) {
                val enableStart =
                    SystemClock.elapsedRealtime()

                runCatching {
                    if (logicalId != Display.DEFAULT_DISPLAY) {
                        enableConnectedDisplayInternal(logicalId)
                    }
                    logicalEnabled = true
                }.onFailure { routeError ->
                    logicalError =
                        "${routeError.javaClass.simpleName}: ${routeError.message}"
                }

                logicalEnableMs =
                    SystemClock.elapsedRealtime() - enableStart

                val freshLogical =
                    runCatching {
                        logicalDisplayIdsDirect()
                            .asSequence()
                            .firstOrNull { id ->
                                directGeometry(id) == (1968 to 2184) &&
                                    physicalDisplayIdFromLogical(id) == physicalId
                            }
                    }.getOrNull()

                if (freshLogical != null) {
                    logicalId = freshLogical
                    val powerStart =
                        SystemClock.elapsedRealtime()

                    logicalPowered =
                        runCatching {
                            requestDisplayPowerInternal(
                                freshLogical,
                                Display.STATE_ON,
                            )
                        }.getOrElse { routeError ->
                            logicalError =
                                listOfNotNull(
                                    logicalError,
                                    "${routeError.javaClass.simpleName}: ${routeError.message}",
                                ).joinToString(" | ")
                            false
                        }

                    logicalPowerMs =
                        SystemClock.elapsedRealtime() - powerStart
                }
            }
        }

        val logicalReady =
            powered && logicalPowered

        return Bundle().apply {
            putBoolean("ok", powered)
            putLong("physicalDisplayId", physicalId)
            putInt("targetWidth", 1968)
            putInt("targetHeight", 2184)
            putBoolean("physicalPowered", powered)
            putLong("physicalPowerMs", physicalPowerMs)
            putInt("routeProbeCount", routeProbeCount)
            putLong("routeFirstSeenMs", routeFirstSeenMs)
            putInt("innerLogicalId", logicalId)
            putBoolean("innerLogicalEnabled", logicalEnabled)
            putLong("logicalEnableMs", logicalEnableMs)
            putBoolean("innerLogicalPowered", logicalPowered)
            putLong("logicalPowerMs", logicalPowerMs)
            putBoolean("logicalReady", logicalReady)
            // Backward compatibility only. This legacy field never proves
            // FIRST_PRESENTED/FIRST_USEFUL pixels.
            putBoolean("usefulReady", logicalReady)
            putString("command", "Fold7 physical + logical inner early wake")
            if (error != null) putString("error", error)
            if (logicalError != null) putString("logicalError", logicalError)
            putLong("latencyMs", SystemClock.elapsedRealtime() - t0)
        }
    }

    private fun logicalDisplayIdsDirect'''

    return regex_once(
        text,
        r'''    private fun wakeInnerPhysicalDisplay\(\): Bundle \{.*?\n    \}\n\n    private fun logicalDisplayIdsDirect''',
        method,
        "inner wake stage telemetry",
    )


def apply(repo: Path, check: bool) -> None:
    coord = repo / COORD
    shell = repo / SHELL
    if not coord.exists() or not shell.exists():
        raise RuntimeError("required runtime sources missing")
    c_before = coord.read_text(encoding="utf-8")
    s_before = shell.read_text(encoding="utf-8")
    c_after = transform_coordinator(c_before)
    s_after = transform_shell(s_before)
    if MARKER not in c_after or "routeFirstSeenMs" not in s_after:
        raise RuntimeError("probe markers missing after transform")
    if not check:
        coord.write_text(c_after, encoding="utf-8")
        shell.write_text(s_after, encoding="utf-8")


def self_test() -> None:
    # Model the semantic lifetime independently of Kotlin/Android execution.
    seq = 0
    active = None
    def begin():
        nonlocal seq, active
        seq += 1
        active = seq
        return active
    first = begin()
    assert active == first  # ordinary INNER_HANDOFF preserves it
    active = None          # reversal/terminal invalidates it
    second = begin()
    assert second != first
    assert active != first # delayed retry from prior opening cannot commit
    print("inner wake probe v1 model: PASS")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=".")
    p.add_argument("--check", action="store_true")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        self_test()
        return 0
    apply(Path(a.repo).resolve(), a.check)
    print("inner wake probe v1: " + ("source shape verified" if a.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
