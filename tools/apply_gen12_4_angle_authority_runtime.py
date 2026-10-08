#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        fail(f"{label}: expected exactly one match in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_between(path: Path, start: str, end: str, replacement: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(start) != 1:
        fail(f"{label}: start marker count={text.count(start)}")
    start_i = text.index(start)
    end_i = text.find(end, start_i + len(start))
    if end_i < 0:
        fail(f"{label}: end marker missing")
    path.write_text(text[:start_i] + replacement + text[end_i:], encoding="utf-8")


def require(path: Path, needle: str, count: int | None = None) -> None:
    text = path.read_text(encoding="utf-8")
    actual = text.count(needle)
    if count is None and actual == 0:
        fail(f"{path}: missing {needle!r}")
    if count is not None and actual != count:
        fail(f"{path}: expected {count} occurrences of {needle!r}, found {actual}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    root = Path(args.repo).resolve()

    feed = root / "app/src/full/java/com/duoopen/shell/WallpaperAngleFeed.kt"
    shell = root / "app/src/full/java/com/duoopen/shell/DuoShellService.kt"
    gradle = root / "app/build.gradle.kts"
    arbiter = root / "app/src/full/java/com/duoopen/shell/Fold7AngleTargetArbiter.kt"

    if not arbiter.exists():
        fail("Gen12.4 authority model must be applied before runtime integration")

    # Replace the timeout-only reader watchdog with explicit target authority.
    replace_once(
        feed,
        '''    private val readerWatchdog =
        Fold7AngleReaderWatchdog(
            timeoutThreshold = READER_RESTART_TIMEOUTS,
            minimumRestartIntervalMs = READER_RESTART_MIN_INTERVAL_MS,
        )
''',
        '''    // GEN12_4_ANGLE_AUTHORITY: a timeout is attributed to the one
    // command target used by that poll. Reader replacement is permitted only
    // after complete target rounds fail.
    private val targetArbiter =
        Fold7AngleTargetArbiter(
            restartAfterExhaustedRounds = TARGET_RESTART_EXHAUSTED_ROUNDS,
            restartCooldownMs = TARGET_RESTART_COOLDOWN_MS,
        )
''',
        "target arbiter field",
    )

    replace_once(
        feed,
        '''    private var readerRestartCount = 0L
    private var readerRestartFailures = 0L
    private var lastWallpaperIdentity = ""
''',
        '''    private var readerRestartCount = 0L
    private var readerRestartFailures = 0L
    private var readerRestartPending = false
    private var readerRestartReason = ""

    @Volatile
    private var inFlightTargetKey: String? = null

    @Volatile
    private var candidateKeysSnapshot: List<String> = emptyList()

    private var lastWallpaperIdentity = ""
''',
        "target and restart state",
    )

    replace_once(
        feed,
        '''                            " · restart $readerRestartCount/$readerRestartFailures" +
                            " · anchors ${anchors.size}" +
                            " · drop ${droppedSessionSamples + droppedPollSamples}" +
''',
        '''                            " · restart $readerRestartCount/$readerRestartFailures" +
                            " · anchors ${anchors.size}" +
                            " · target ${targetArbiter.provenKey ?: inFlightTargetKey ?: "probing"}" +
                            " · candidates ${candidateKeysSnapshot.size}" +
                            " · rounds ${targetArbiter.exhaustedRounds}" +
                            " · failover ${targetArbiter.failovers}" +
                            " · reply vis ${b.getInt("visibleParsed")}/${b.getInt("hiddenParsed")}" +
                            " · drop ${droppedSessionSamples + droppedPollSamples}" +
''',
        "authority status telemetry",
    )

    replace_once(
        feed,
        '''                    controlHandler.post {
                        if (running) {
                            hinge.expireExternal("reader-stale")
                            maybeRestartReader(
                                expectedSession = readerSession,
                                reason = "reader-stale-age=$age",
                            )
                        }
                    }
''',
        '''                    controlHandler.post {
                        if (running) {
                            // Staleness revokes geometry authority, but does not
                            // diagnose the reader. Target-specific poll misses own
                            // recovery decisions in Gen12.4.
                            hinge.expireExternal("reader-stale")
                        }
                    }
''',
        "stale status is not reader diagnosis",
    )

    replace_once(
        feed,
        '''        readerRestartCount = 0L
        readerRestartFailures = 0L
        readerWatchdog.reset()
        lastWallpaperIdentity = ""
''',
        '''        readerRestartCount = 0L
        readerRestartFailures = 0L
        readerRestartPending = false
        readerRestartReason = ""
        inFlightTargetKey = null
        candidateKeysSnapshot = emptyList()
        targetArbiter.reset()
        lastWallpaperIdentity = ""
''',
        "authority start reset",
    )

    old_send = '''            val sent =
                runCatching {
                    val commandAnchors =
                        ensureAnchors()

                    val action =
                        "$actionPrefix:${poll.sequence}"

                    var sentAny = false
                    var lastError: Throwable? = null

                    for (commandAnchor in commandAnchors) {
                        val token =
                            commandAnchor.view.windowToken
                                ?: continue

                        runCatching {
                            WallpaperManager
                                .getInstance(commandAnchor.view.context)
                                .sendWallpaperCommand(
                                    token,
                                    action,
                                    0,
                                    0,
                                    0,
                                    null,
                                )
                        }.onSuccess {
                            sentAny = true
                        }.onFailure {
                            lastError = it
                        }
                    }

                    if (!sentAny && lastError != null) {
                        throw lastError!!
                    }

                    sentAny
                }.onFailure {
                    status =
                        "Wallpaper command failed: ${it.message}"
                }.getOrDefault(false)
'''
    new_send = '''            val sent =
                runCatching {
                    val commandAnchors =
                        ensureAnchors()

                    val candidates =
                        commandAnchors.map {
                            Fold7AngleTargetArbiter.Candidate(
                                key = it.key,
                                preferInner = it.preferInner,
                            )
                        }

                    candidateKeysSnapshot =
                        candidates.map { it.key }

                    val selected =
                        targetArbiter.select(candidates)

                    val commandAnchor =
                        selected?.let { candidate ->
                            commandAnchors.firstOrNull {
                                it.key == candidate.key
                            }
                        }

                    inFlightTargetKey =
                        commandAnchor?.key

                    if (commandAnchor == null) {
                        false
                    } else {
                        val token =
                            commandAnchor.view.windowToken
                                ?: return@runCatching false

                        val action =
                            "$actionPrefix:${poll.sequence}"

                        TransitionLab.recordIngressStage(
                            type = "angle-target-select",
                            angleSession = session,
                            pollSequence = poll.sequence,
                            reason =
                                "target=${commandAnchor.key} " +
                                    "proven=${targetArbiter.provenKey}",
                        )

                        WallpaperManager
                            .getInstance(commandAnchor.view.context)
                            .sendWallpaperCommand(
                                token,
                                action,
                                0,
                                0,
                                0,
                                null,
                            )
                        true
                    }
                }.onFailure {
                    status =
                        "Wallpaper command failed: ${it.message}"
                }.getOrDefault(false)
'''
    replace_once(feed, old_send, new_send, "single target command dispatch")

    replace_once(
        feed,
        '''                if (!sent) {
                    completePollWithoutSample(
                        session = session,
                        poll = poll,
                        reason = "command-not-sent",
                    )
                } else {
''',
        '''                if (!sent) {
                    completeTargetMissWithoutSample(
                        session = session,
                        poll = poll,
                        reason =
                            if (inFlightTargetKey == null) {
                                "no-target"
                            } else {
                                "command-not-sent"
                            },
                    )
                } else {
''',
        "attribute command miss",
    )

    # Replace timeout/watchdog/restart block with target-driven recovery and a
    # transactional reader replacement. App session ownership is committed only
    # after START_ANGLES has synchronously succeeded.
    replace_between(
        feed,
        '''    private fun onPollTimeout(
''',
        '''    private fun completePollWithoutSample(
''',
        r'''    private fun onPollTimeout(
        session: Long,
        poll: Fold7AnglePipelineGen2.PollToken,
    ) {
        if (!isCurrent(session)) return

        val current =
            pipeline.inFlightPoll

        if (
            current?.session !=
            poll.session ||
            current.sequence !=
            poll.sequence
        ) {
            return
        }

        timedOutPolls++

        val now =
            SystemClock.uptimeMillis()

        val targetKey =
            inFlightTargetKey

        val miss =
            targetArbiter.onMiss(
                targetKey = targetKey,
                candidateKeys = candidateKeysSnapshot,
                nowUptimeMs = now,
            )

        TransitionLab.recordIngressStage(
            type = "angle-target-timeout",
            angleSession = session,
            pollSequence = poll.sequence,
            reason =
                "target=$targetKey exhausted=${miss.roundExhausted} " +
                    "rounds=${miss.exhaustedRounds} restart=${miss.requestReaderRestart}",
        )

        if (miss.roundExhausted) {
            TransitionLab.recordIngressStage(
                type = "angle-target-round-exhausted",
                angleSession = session,
                pollSequence = poll.sequence,
                reason =
                    "rounds=${miss.exhaustedRounds} restart=${miss.requestReaderRestart}",
            )
        }

        inFlightTargetKey = null

        val next =
            pipeline.timeoutPoll(
                token = poll,
                timeoutUptimeMs = now,
            ) ?: return

        if (miss.requestReaderRestart) {
            restartReader(
                expectedSession = session,
                reason = "target-rounds-exhausted:${poll.sequence}",
            )
            return
        }

        schedulePoll(
            session = session,
            delayMs = next,
        )
    }

    private fun completeTargetMissWithoutSample(
        session: Long,
        poll: Fold7AnglePipelineGen2.PollToken,
        reason: String,
    ) {
        if (!isCurrent(session)) return

        val now =
            SystemClock.uptimeMillis()
        val targetKey =
            inFlightTargetKey

        val next =
            pipeline.completePoll(
                token = poll,
                completionUptimeMs = now,
            ) ?: return

        if (targetKey == null) {
            inFlightTargetKey = null
            TransitionLab.recordIngressStage(
                type = "angle-target-unavailable",
                angleSession = session,
                pollSequence = poll.sequence,
                reason = reason,
            )
            schedulePoll(
                session = session,
                delayMs = maxOf(next, NO_TARGET_RECHECK_MS),
            )
            return
        }

        val miss =
            targetArbiter.onMiss(
                targetKey = targetKey,
                candidateKeys = candidateKeysSnapshot,
                nowUptimeMs = now,
            )

        TransitionLab.recordIngressStage(
            type = "angle-target-timeout",
            angleSession = session,
            pollSequence = poll.sequence,
            reason =
                "target=$targetKey reason=$reason exhausted=${miss.roundExhausted} " +
                    "rounds=${miss.exhaustedRounds} restart=${miss.requestReaderRestart}",
        )

        inFlightTargetKey = null

        if (miss.requestReaderRestart) {
            restartReader(
                expectedSession = session,
                reason = "target-send-failure:${poll.sequence}",
            )
            return
        }

        schedulePoll(
            session = session,
            delayMs = next,
        )
    }

    private fun restartReader(
        expectedSession: Long,
        reason: String,
    ) {
        if (!isCurrent(expectedSession)) return

        readerRestartPending = true
        readerRestartReason = reason
        controlHandler.removeCallbacks(pollRunnable)
        hinge.expireExternal("reader-restart-pending:$reason")

        attemptReaderReplacement(
            expectedSession = expectedSession,
            reason = reason,
        )
    }

    private fun attemptReaderReplacement(
        expectedSession: Long,
        reason: String,
    ) {
        if (
            !isCurrent(expectedSession) ||
            !readerRestartPending
        ) {
            return
        }

        if (!ShizukuBridge.ready) {
            readerRestartFailures++
            status = "FoldInteractive reader replacement waiting for Shizuku"
            scheduleReaderRestartRetry(expectedSession, reason)
            return
        }

        val oldSession =
            readerSession
        val newSession =
            oldSession + 1L
        val newPrefix =
            "com.duoopen.angle.READ_${SystemClock.elapsedRealtime()}_$newSession"

        val started =
            ShizukuBridge.startAnglesSequenced(
                newPrefix,
            ) { angle, sourceUptime, binderArrivalTimeNs, pollSequence ->
                controlHandler.post {
                    onAngle(
                        session = newSession,
                        pollSequence = pollSequence,
                        angle = angle,
                        sourceUptime = sourceUptime,
                        binderArrivalTimeNs = binderArrivalTimeNs,
                    )
                }
            }

        TransitionLab.recordIngressStage(
            type = "angle-reader-restart",
            angleSession = newSession,
            reason = "$reason started=$started oldSession=$oldSession transactional=true",
        )

        DuoDiagnostics.event(
            "angle-source",
            "reader replacement oldSession=$oldSession candidateSession=$newSession " +
                "started=$started reason=$reason",
        )

        if (!started) {
            readerRestartFailures++
            status = "FoldInteractive reader replacement failed; retrying: $reason"
            scheduleReaderRestartRetry(expectedSession, reason)
            return
        }

        // Commit ownership only after the shell confirms START_ANGLES.
        readerSession = newSession
        actionPrefix = newPrefix
        readerRestartPending = false
        readerRestartReason = ""
        inFlightTargetKey = null

        controlHandler.removeCallbacks(pollRunnable)
        pipeline.invalidateSession()
        hinge.revokeExternalSession(
            session = oldSession,
            reason = "reader-restart:$reason",
        )

        targetArbiter.onReaderRestart()
        readerRestartCount++
        startedAt =
            SystemClock.uptimeMillis()
        lastCallbackUptime = 0L
        lastDeliveryLagMs = -1L
        lastAngleSeen = Float.NaN
        lastAngleChangeUptime = 0L
        endpointBridgeGeneration++

        hinge.beginExternalSession(newSession)
        pipeline.startSession()

        mainHandler.post {
            if (isCurrent(newSession)) {
                runCatching {
                    ensureAnchors(force = true)
                }
            }
        }

        schedulePoll(
            session = newSession,
            delayMs = 0L,
        )
    }

    private fun scheduleReaderRestartRetry(
        expectedSession: Long,
        reason: String,
    ) {
        controlHandler.postDelayed(
            {
                if (
                    isCurrent(expectedSession) &&
                    readerRestartPending
                ) {
                    attemptReaderReplacement(
                        expectedSession = expectedSession,
                        reason = readerRestartReason.ifEmpty { reason },
                    )
                }
            },
            READER_RESTART_RETRY_MS,
        )
    }

''',
        "target recovery and transactional reader replacement",
    )

    # A successfully accepted callback proves the exact one-target command path.
    replace_once(
        feed,
        '''        val now =
            SystemClock.uptimeMillis()

        endpointBridgeGeneration++
''',
        '''        val now =
            SystemClock.uptimeMillis()

        val acknowledgedTarget =
            inFlightTargetKey

        if (acknowledgedTarget != null) {
            val ack =
                targetArbiter.onAck(
                    targetKey = acknowledgedTarget,
                    nowUptimeMs = now,
                )

            TransitionLab.recordIngressStage(
                type = "angle-target-ack",
                angleSession = session,
                pollSequence = pollSequence,
                reason =
                    "target=$acknowledgedTarget promoted=${ack.promoted} failover=${ack.failover}",
            )

            if (ack.promoted) {
                TransitionLab.recordIngressStage(
                    type = "angle-target-promote",
                    angleSession = session,
                    pollSequence = pollSequence,
                    reason =
                        "from=${ack.previousProvenKey} to=${ack.provenKey} failover=${ack.failover}",
                )

                DuoDiagnostics.event(
                    "angle-source",
                    "target promoted from=${ack.previousProvenKey} " +
                        "to=${ack.provenKey} failover=${ack.failover}",
                )
            }
        }

        inFlightTargetKey = null
        endpointBridgeGeneration++
''',
        "acknowledge selected target",
    )

    # Gen12.3's reader watchdog is no longer authoritative once target probing
    # owns failure diagnosis.
    replace_once(
        feed,
        '''        readerWatchdog.onSample()

''',
        '''''',
        "remove timeout-watchdog sample reset",
    )

    replace_once(
        feed,
        '''    private data class CommandAnchor(
        val key: String,
        val displayId: Int,
        val view: View,
        val windowManager: WindowManager,
    )
''',
        '''    private data class CommandAnchor(
        val key: String,
        val displayId: Int,
        val preferInner: Boolean,
        val view: View,
        val windowManager: WindowManager,
        var lastSeenUptimeMs: Long,
    )
''',
        "retained anchor metadata",
    )

    replace_once(
        feed,
        '''        val staleKeys =
            anchors.keys.filter {
                it !in desiredKeys
            }

        for (key in staleKeys) {
            removeAnchor(key)
        }
''',
        '''        val staleKeys =
            anchors.keys.filter {
                it !in desiredKeys
            }

        val provenKey =
            targetArbiter.provenKey
        val provenAckAgeMs =
            targetArbiter.lastAckAgeMs(now)

        for (key in staleKeys) {
            val commandAnchor =
                anchors[key]
                    ?: continue

            val recentlySeen =
                now - commandAnchor.lastSeenUptimeMs <=
                    STALE_ANCHOR_RETENTION_MS

            val activelyProven =
                key == provenKey &&
                    provenAckAgeMs in
                    0L..PROVEN_ANCHOR_ACK_RETENTION_MS

            if (!recentlySeen && !activelyProven) {
                TransitionLab.recordIngressStage(
                    type = "angle-target-retire",
                    reason =
                        "target=$key lastSeenAge=${now - commandAnchor.lastSeenUptimeMs} " +
                            "provenAckAge=$provenAckAgeMs",
                )
                removeAnchor(key)
            }
        }
''',
        "anchor retention lease",
    )

    replace_once(
        feed,
        '''            if (key in anchors) {
                continue
            }

            runCatching {
''',
        '''            val existing =
                anchors[key]

            if (existing != null) {
                existing.lastSeenUptimeMs = now
                continue
            }

            runCatching {
''',
        "refresh retained anchor sighting",
    )

    replace_once(
        feed,
        '''                    CommandAnchor(
                        key = key,
                        displayId = display.displayId,
                        view = view,
                        windowManager = wm,
                    )
''',
        '''                    CommandAnchor(
                        key = key,
                        displayId = display.displayId,
                        preferInner = isFold7Inner(display),
                        view = view,
                        windowManager = wm,
                        lastSeenUptimeMs = now,
                    )
''',
        "anchor authority hints",
    )

    replace_once(
        feed,
        '''        val commandAnchor =
            anchors.remove(key)
                ?: return

        runCatching {
''',
        '''        val commandAnchor =
            anchors.remove(key)
                ?: return

        targetArbiter.forget(key)

        runCatching {
''',
        "forget retired target",
    )

    replace_once(
        feed,
        '''        const val POLL_TIMEOUT_MS =
            96L

        const val READER_RESTART_TIMEOUTS =
            3

        const val READER_RESTART_MIN_INTERVAL_MS =
            750L

        const val ANGLE_ANCHOR_REFRESH_MS =
            250L
''',
        '''        // Target attribution lets us probe alternates sooner than the old
        // global reader timeout while retaining ample margin over healthy field
        // callback latency. Physical validation may tune this value.
        const val POLL_TIMEOUT_MS =
            64L

        const val TARGET_RESTART_EXHAUSTED_ROUNDS =
            2

        const val TARGET_RESTART_COOLDOWN_MS =
            1_000L

        const val READER_RESTART_RETRY_MS =
            1_000L

        const val NO_TARGET_RECHECK_MS =
            250L

        const val STALE_ANCHOR_RETENTION_MS =
            1_500L

        const val PROVEN_ANCHOR_ACK_RETENTION_MS =
            5_000L

        const val ANGLE_ANCHOR_REFRESH_MS =
            250L
''',
        "authority timing constants",
    )

    # Reader visibility is retained as telemetry instead of being an authority
    # gate. This lets the physical trace tell us whether the proven target is a
    # hidden inner engine or a visible cover engine.
    replace_once(
        shell,
        '''        private var parsed = 0
        private var rejected = 0
        private var lastAngle = Float.NaN
''',
        '''        private var parsed = 0
        private var rejected = 0
        private var visibleParsed = 0
        private var hiddenParsed = 0
        private var lastVisible = false
        private var lastAngle = Float.NaN
''',
        "visibility counters",
    )

    replace_once(
        shell,
        '''        private data class ParsedAngle(
            val angle: Float,
            val pollSequence: Long,
        )
''',
        '''        private data class ParsedAngle(
            val angle: Float,
            val pollSequence: Long,
            val visible: Boolean,
        )
''',
        "parsed angle visibility",
    )

    replace_once(
        shell,
        '''                            parsed++
                            lastAngle = parsedLine.angle
                            lastPollSequence = parsedLine.pollSequence
''',
        '''                            parsed++
                            if (parsedLine.visible) {
                                visibleParsed++
                            } else {
                                hiddenParsed++
                            }
                            lastVisible = parsedLine.visible
                            lastAngle = parsedLine.angle
                            lastPollSequence = parsedLine.pollSequence
''',
        "count hidden and visible replies",
    )

    replace_once(
        shell,
        '''            putInt("rejected", rejected)
            putFloat("angle", lastAngle)
''',
        '''            putInt("rejected", rejected)
            putInt("visibleParsed", visibleParsed)
            putInt("hiddenParsed", hiddenParsed)
            putBoolean("lastVisible", lastVisible)
            putFloat("angle", lastAngle)
''',
        "visibility status bundle",
    )

    replace_once(
        shell,
        '''            val angleMatch = ANGLE.matcher(line)
            if (!angleMatch.find()) return null
            val value = angleMatch.group(1)?.toFloatOrNull() ?: return null
            if (value !in 0f..180f) return null

            return ParsedAngle(
                angle = value,
                pollSequence = pollSequence,
            )
''',
        '''            val angleMatch = ANGLE.matcher(line)
            if (!angleMatch.find()) return null
            val value = angleMatch.group(1)?.toFloatOrNull() ?: return null
            if (value !in 0f..180f) return null

            val visible =
                line.contains("isVisible=true") ||
                    line.contains("isVisible[true]")

            return ParsedAngle(
                angle = value,
                pollSequence = pollSequence,
                visible = visible,
            )
''',
        "parse visibility as telemetry",
    )

    replace_once(
        gradle,
        '''        versionCode = 59
        versionName = "5.6.3-gen12-3-angle-feed-resilience-zfold7"
''',
        '''        versionCode = 60
        versionName = "5.6.4-gen12-4-angle-authority-zfold7"
''',
        "Gen12.4 version",
    )

    require(feed, "Fold7AngleTargetArbiter(", 1)
    require(feed, 'type = "angle-target-select"', 1)
    require(feed, 'type = "angle-target-ack"', 1)
    require(feed, 'type = "angle-target-timeout"', 2)
    require(feed, 'type = "angle-target-promote"', 1)
    require(feed, 'type = "angle-target-round-exhausted"', 1)
    require(feed, 'type = "angle-target-retire"', 1)
    require(feed, "transactional=true", 1)
    require(feed, "const val POLL_TIMEOUT_MS =\n            64L", 1)
    require(shell, 'putInt("visibleParsed", visibleParsed)', 1)
    require(shell, 'putInt("hiddenParsed", hiddenParsed)', 1)
    require(shell, "visible = visible", 1)
    require(gradle, "versionCode = 60", 1)
    require(gradle, 'versionName = "5.6.4-gen12-4-angle-authority-zfold7"', 1)

    print("GEN12.4 ANGLE AUTHORITY RUNTIME: APPLIED")


if __name__ == "__main__":
    main()
