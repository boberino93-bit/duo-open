#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"ERROR: {label}: expected exactly one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def require(path: Path, needle: str, count: int | None = None) -> None:
    text = path.read_text(encoding="utf-8")
    actual = text.count(needle)
    if count is None and actual == 0:
        raise SystemExit(f"ERROR: {path}: missing {needle!r}")
    if count is not None and actual != count:
        raise SystemExit(f"ERROR: {path}: expected {count} occurrences of {needle!r}, found {actual}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    root = Path(args.repo).resolve()

    feed = root / "app/src/full/java/com/duoopen/shell/WallpaperAngleFeed.kt"
    supervisor = root / "app/src/full/java/com/duoopen/shell/Fold7AngleTransportSupervisor.kt"

    if not supervisor.exists():
        raise SystemExit("ERROR: transport supervisor model must be applied first")

    replace_once(
        feed,
        '''    private val targetArbiter =
        Fold7AngleTargetArbiter(
            restartAfterExhaustedRounds = TARGET_RESTART_EXHAUSTED_ROUNDS,
            restartCooldownMs = TARGET_RESTART_COOLDOWN_MS,
        )
''',
        '''    private val targetArbiter =
        Fold7AngleTargetArbiter(
            restartAfterExhaustedRounds = TARGET_RESTART_EXHAUSTED_ROUNDS,
            restartCooldownMs = TARGET_RESTART_COOLDOWN_MS,
        )

    // Explicit shell/log-reader health is supervised independently from target
    // health. Stale geometry alone never counts as transport failure.
    private val transportSupervisor =
        Fold7AngleTransportSupervisor()
''',
        "transport supervisor field",
    )

    replace_once(
        feed,
        '''                val b =
                    ShizukuBridge.angleStatus()

                val age =
''',
        '''                val b =
                    ShizukuBridge.angleStatus()

                val transportDecision =
                    transportSupervisor.observe(
                        connectionEpoch = ShizukuBridge.connectionEpoch,
                        readerState = b?.getString("state"),
                    )

                if (transportDecision.requestRestart) {
                    val sessionAtObservation =
                        readerSession
                    val transportReason =
                        transportDecision.reason
                            ?: "reader-transport"

                    DuoDiagnostics.event(
                        "angle-source",
                        "transport recovery requested reason=$transportReason " +
                            "state=${b?.getString("state")} " +
                            "${transportSupervisor.summary()}",
                    )

                    controlHandler.post {
                        if (isCurrent(sessionAtObservation)) {
                            restartReader(
                                expectedSession = sessionAtObservation,
                                reason = "transport:$transportReason",
                            )
                        }
                    }
                }

                val age =
''',
        "observe explicit reader transport health",
    )

    replace_once(
        feed,
        '''                            " · failover ${targetArbiter.failovers}" +
                            " · reply vis ${b.getInt("visibleParsed")}/${b.getInt("hiddenParsed")}" +
''',
        '''                            " · failover ${targetArbiter.failovers}" +
                            " · transport ${transportSupervisor.summary()}" +
                            " · reply vis ${b.getInt("visibleParsed")}/${b.getInt("hiddenParsed")}" +
''',
        "transport status telemetry",
    )

    replace_once(
        feed,
        '''        candidateKeysSnapshot = emptyList()
        targetArbiter.reset()
        lastWallpaperIdentity = ""
''',
        '''        candidateKeysSnapshot = emptyList()
        targetArbiter.reset()
        transportSupervisor.reset(
            ShizukuBridge.connectionEpoch
        )
        lastWallpaperIdentity = ""
''',
        "transport supervisor initial epoch",
    )

    replace_once(
        feed,
        '''    private fun restartReader(
        expectedSession: Long,
        reason: String,
    ) {
        if (!isCurrent(expectedSession)) return

        readerRestartPending = true
''',
        '''    private fun restartReader(
        expectedSession: Long,
        reason: String,
    ) {
        if (
            !isCurrent(expectedSession) ||
            readerRestartPending
        ) {
            return
        }

        readerRestartPending = true
''',
        "dedupe concurrent recovery requests",
    )

    replace_once(
        feed,
        '''        val now =
            SystemClock.uptimeMillis()

        val acknowledgedTarget =
''',
        '''        val now =
            SystemClock.uptimeMillis()

        // A real accepted precise sample is the only ordinary event that
        // rearms terminal-reader recovery on the same shell connection.
        transportSupervisor.onSample()

        val acknowledgedTarget =
''',
        "accepted sample rearms transport recovery",
    )

    require(feed, "Fold7AngleTransportSupervisor()", 1)
    require(feed, "transportSupervisor.observe(", 1)
    require(feed, "transportSupervisor.onSample()", 1)
    require(feed, "transportSupervisor.reset(", 1)
    require(feed, "readerRestartPending\n        )", 1)
    require(feed, 'reason = "transport:$transportReason"', 1)

    print("GEN12.4 ANGLE TRANSPORT RUNTIME: APPLIED")


if __name__ == "__main__":
    main()
