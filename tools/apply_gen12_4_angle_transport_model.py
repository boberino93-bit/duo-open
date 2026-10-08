#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def write_new(path: Path, content: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise RuntimeError(f"new-file collision: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    root = Path(args.repo).resolve()

    supervisor = root / "app/src/full/java/com/duoopen/shell/Fold7AngleTransportSupervisor.kt"
    test = root / "app/src/test/java/com/duoopen/shell/Fold7AngleTransportSupervisorTest.kt"

    write_new(
        supervisor,
        '''package com.duoopen.shell

/**
 * GEN12_4_ANGLE_TRANSPORT_AUTHORITY
 *
 * Separates explicit shell/log-reader failure from wallpaper-target failure.
 * Geometry age alone is never transport-failure evidence.
 *
 * A connection-epoch change is hard evidence that the previously started
 * reader belongs to an obsolete shell service. A terminal reader state is also
 * direct evidence, but only one restart request is emitted until a valid sample
 * arrives or a new shell connection epoch appears. This prevents transport
 * recovery itself from becoming a restart loop.
 */
internal class Fold7AngleTransportSupervisor {
    data class Decision(
        val requestRestart: Boolean,
        val reason: String? = null,
        val connectionChanged: Boolean = false,
        val terminalState: Boolean = false,
    )

    private var observedConnectionEpoch = -1L
    private var terminalRecoveryLatched = false
    private var restartRequests = 0L

    @get:Synchronized
    val recoveryLatched: Boolean
        get() = terminalRecoveryLatched

    @get:Synchronized
    val restartsRequested: Long
        get() = restartRequests

    @Synchronized
    fun reset(
        connectionEpoch: Long,
    ) {
        observedConnectionEpoch = connectionEpoch
        terminalRecoveryLatched = false
        restartRequests = 0L
    }

    @Synchronized
    fun onSample() {
        terminalRecoveryLatched = false
    }

    @Synchronized
    fun observe(
        connectionEpoch: Long,
        readerState: String?,
    ): Decision {
        if (
            connectionEpoch > 0L &&
            observedConnectionEpoch >= 0L &&
            connectionEpoch != observedConnectionEpoch
        ) {
            val previous = observedConnectionEpoch
            observedConnectionEpoch = connectionEpoch
            terminalRecoveryLatched = false
            restartRequests++
            return Decision(
                requestRestart = true,
                reason = "shell-connection-epoch:$previous->$connectionEpoch",
                connectionChanged = true,
            )
        }

        if (
            connectionEpoch > 0L &&
            observedConnectionEpoch < 0L
        ) {
            observedConnectionEpoch = connectionEpoch
        }

        val normalized =
            readerState
                ?.trim()
                ?.lowercase()
                .orEmpty()

        val terminal =
            normalized == "not started" ||
                normalized == "stopped" ||
                normalized.startsWith("reader error") ||
                normalized.startsWith("log reader ended") ||
                normalized.startsWith("callback gone")

        if (!terminal || terminalRecoveryLatched) {
            return Decision(
                requestRestart = false,
                terminalState = terminal,
            )
        }

        terminalRecoveryLatched = true
        restartRequests++
        return Decision(
            requestRestart = true,
            reason = "reader-terminal:${readerState ?: "unknown"}",
            terminalState = true,
        )
    }

    @Synchronized
    fun summary(): String =
        "epoch=$observedConnectionEpoch " +
            "terminalRecovery=${if (terminalRecoveryLatched) "latched" else "armed"} " +
            "requests=$restartRequests"
}
''',
    )

    write_new(
        test,
        '''package com.duoopen.shell

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7AngleTransportSupervisorTest {
    @Test
    fun healthyReaderStatesDoNotRequestRecovery() {
        val supervisor = Fold7AngleTransportSupervisor()
        supervisor.reset(10L)

        assertFalse(supervisor.observe(10L, "starting").requestRestart)
        assertFalse(supervisor.observe(10L, "listening").requestRestart)
        assertFalse(supervisor.observe(10L, "receiving").requestRestart)
        assertFalse(supervisor.observe(10L, null).requestRestart)
    }

    @Test
    fun stalenessIsNotRepresentedAsTransportFailure() {
        val supervisor = Fold7AngleTransportSupervisor()
        supervisor.reset(10L)

        repeat(20) {
            assertFalse(supervisor.observe(10L, "receiving").requestRestart)
        }
        assertFalse(supervisor.recoveryLatched)
    }

    @Test
    fun terminalReaderStateGetsOneRecoveryAttempt() {
        val supervisor = Fold7AngleTransportSupervisor()
        supervisor.reset(10L)

        val first = supervisor.observe(10L, "reader error: logcat unavailable")
        assertTrue(first.requestRestart)
        assertTrue(first.terminalState)
        assertTrue(supervisor.recoveryLatched)

        repeat(5) {
            assertFalse(
                supervisor.observe(
                    10L,
                    "reader error: logcat unavailable",
                ).requestRestart,
            )
        }
    }

    @Test
    fun validSampleRearmsTerminalRecovery() {
        val supervisor = Fold7AngleTransportSupervisor()
        supervisor.reset(10L)

        assertTrue(supervisor.observe(10L, "log reader ended").requestRestart)
        supervisor.onSample()
        assertFalse(supervisor.recoveryLatched)
        assertTrue(supervisor.observe(10L, "log reader ended").requestRestart)
    }

    @Test
    fun shellConnectionEpochChangeAlwaysInvalidatesOldReader() {
        val supervisor = Fold7AngleTransportSupervisor()
        supervisor.reset(10L)

        val decision = supervisor.observe(11L, "not started")
        assertTrue(decision.requestRestart)
        assertTrue(decision.connectionChanged)
        // The same observation must not immediately generate a second request.
        assertFalse(supervisor.observe(11L, "listening").requestRestart)
    }

    @Test
    fun newConnectionEpochRearmsAPreviouslyLatchedTerminalFailure() {
        val supervisor = Fold7AngleTransportSupervisor()
        supervisor.reset(10L)

        assertTrue(supervisor.observe(10L, "reader error: x").requestRestart)
        assertTrue(supervisor.recoveryLatched)

        val connection = supervisor.observe(11L, "not started")
        assertTrue(connection.requestRestart)
        assertTrue(connection.connectionChanged)
        assertFalse(supervisor.recoveryLatched)

        // If the reader on the fresh shell epoch itself terminates, allow one
        // evidence-based terminal recovery attempt, then latch again.
        assertTrue(supervisor.observe(11L, "reader error: y").requestRestart)
        assertTrue(supervisor.recoveryLatched)
        assertFalse(supervisor.observe(11L, "reader error: y").requestRestart)
    }
}
''',
    )

    print("GEN12.4 ANGLE TRANSPORT SUPERVISOR MODEL: APPLIED")


if __name__ == "__main__":
    main()
