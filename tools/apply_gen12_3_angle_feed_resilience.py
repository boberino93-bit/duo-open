#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        fail(f"{label}: expected exactly one anchor in {path}, found {count}")
    path.write_text(text.replace(old, new, 1))


def replace_between(path: Path, start: str, end: str, replacement: str, label: str) -> None:
    text = path.read_text()
    if text.count(start) != 1:
        fail(f"{label}: start marker count={text.count(start)} in {path}")
    start_i = text.index(start)
    end_i = text.find(end, start_i + len(start))
    if end_i < 0:
        fail(f"{label}: end marker missing in {path}")
    path.write_text(text[:start_i] + replacement + text[end_i:])


def require(path: Path, needle: str, count: int | None = None) -> None:
    text = path.read_text()
    actual = text.count(needle)
    if count is None:
        if actual == 0:
            fail(f"{path}: missing required text {needle!r}")
    elif actual != count:
        fail(f"{path}: expected {count} occurrences of {needle!r}, found {actual}")


def forbid(path: Path, needle: str) -> None:
    if needle in path.read_text():
        fail(f"{path}: forbidden text survived: {needle!r}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    root = Path(args.repo).resolve()

    feed = root / "app/src/full/java/com/duoopen/shell/WallpaperAngleFeed.kt"
    shell = root / "app/src/full/java/com/duoopen/shell/DuoShellService.kt"
    watchdog = root / "app/src/full/java/com/duoopen/shell/Fold7AngleReaderWatchdog.kt"
    watchdog_test = root / "app/src/test/java/com/duoopen/shell/Fold7AngleReaderWatchdogTest.kt"
    gradle = root / "app/build.gradle.kts"

    watchdog.parent.mkdir(parents=True, exist_ok=True)
    watchdog.write_text(
        '''package com.duoopen.shell

/**
 * GEN12_3_ANGLE_FEED_RESILIENCE
 *
 * Pure liveness gate for Samsung FoldInteractive acquisition. Isolated poll
 * misses are normal, but a consecutive timeout streak means the app is still
 * issuing wallpaper commands while no fresh reader callback is making forward
 * progress. A bounded restart replaces that reader/session instead of polling a
 * dead path forever.
 */
internal class Fold7AngleReaderWatchdog(
    private val timeoutThreshold: Int,
    private val minimumRestartIntervalMs: Long,
) {
    init {
        require(timeoutThreshold > 0)
        require(minimumRestartIntervalMs >= 0L)
    }

    private var consecutiveTimeouts = 0
    private var lastRestartUptimeMs = Long.MIN_VALUE

    fun reset() {
        consecutiveTimeouts = 0
        lastRestartUptimeMs = Long.MIN_VALUE
    }

    fun onSample() {
        consecutiveTimeouts = 0
    }

    fun onTimeout(nowUptimeMs: Long): Boolean {
        consecutiveTimeouts += 1
        if (consecutiveTimeouts < timeoutThreshold) return false
        return grantRestart(nowUptimeMs)
    }

    fun onStale(nowUptimeMs: Long): Boolean =
        grantRestart(nowUptimeMs)

    val timeoutStreak: Int
        get() = consecutiveTimeouts

    private fun grantRestart(nowUptimeMs: Long): Boolean {
        if (
            lastRestartUptimeMs != Long.MIN_VALUE &&
            nowUptimeMs - lastRestartUptimeMs < minimumRestartIntervalMs
        ) {
            return false
        }

        lastRestartUptimeMs = nowUptimeMs
        consecutiveTimeouts = 0
        return true
    }
}
'''
    )

    watchdog_test.parent.mkdir(parents=True, exist_ok=True)
    watchdog_test.write_text(
        '''package com.duoopen.shell

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7AngleReaderWatchdogTest {
    @Test
    fun threeConsecutiveTimeoutsReplaceReader() {
        val watchdog = Fold7AngleReaderWatchdog(3, 750L)

        assertFalse(watchdog.onTimeout(100L))
        assertFalse(watchdog.onTimeout(200L))
        assertTrue(watchdog.onTimeout(300L))
    }

    @Test
    fun successfulSampleBreaksTimeoutStreak() {
        val watchdog = Fold7AngleReaderWatchdog(3, 750L)

        assertFalse(watchdog.onTimeout(100L))
        assertFalse(watchdog.onTimeout(200L))
        watchdog.onSample()
        assertFalse(watchdog.onTimeout(300L))
        assertFalse(watchdog.onTimeout(400L))
        assertTrue(watchdog.onTimeout(500L))
    }

    @Test
    fun restartCooldownPreventsStorm() {
        val watchdog = Fold7AngleReaderWatchdog(1, 750L)

        assertTrue(watchdog.onTimeout(1_000L))
        assertFalse(watchdog.onTimeout(1_200L))
        assertTrue(watchdog.onStale(1_750L))
    }

    @Test
    fun staleStatusCanRecoverReaderEvenWithoutTimeoutProgress() {
        val watchdog = Fold7AngleReaderWatchdog(3, 750L)

        assertTrue(watchdog.onStale(2_500L))
        assertFalse(watchdog.onStale(3_000L))
        assertTrue(watchdog.onStale(3_250L))
    }
}
'''
    )

    replace_once(
        feed,
        '''    // Main-thread-owned window state.
    private var anchor: View? = null
    private var anchorWm: WindowManager? = null
    private var anchorKey = ""
''',
        '''    // Main-thread-owned Fold7 command anchors. We retain one token per
    // available built-in panel so a default-display swap cannot silently move
    // commands away from Samsung's hidden FoldInteractive producer.
    private val anchors = LinkedHashMap<String, CommandAnchor>()
    private var lastAnchorRefreshUptime = 0L
''',
        "replace single default-display angle anchor",
    )

    replace_once(
        feed,
        '''    private val pipeline =
        Fold7AnglePipelineGen2(
            targetPeriodMs = INTERACTIVE_POLL_MS,
            minimumYieldMs = MINIMUM_YIELD_MS,
        )
''',
        '''    private val pipeline =
        Fold7AnglePipelineGen2(
            targetPeriodMs = INTERACTIVE_POLL_MS,
            minimumYieldMs = MINIMUM_YIELD_MS,
        )

    private val readerWatchdog =
        Fold7AngleReaderWatchdog(
            timeoutThreshold = READER_RESTART_TIMEOUTS,
            minimumRestartIntervalMs = READER_RESTART_MIN_INTERVAL_MS,
        )
''',
        "reader watchdog field",
    )

    replace_once(
        feed,
        '''    private var timedOutPolls = 0L
    private var lastWallpaperIdentity = ""
''',
        '''    private var timedOutPolls = 0L
    private var readerRestartCount = 0L
    private var readerRestartFailures = 0L
    private var lastWallpaperIdentity = ""
''',
        "reader restart counters",
    )

    replace_once(
        feed,
        '''                            " · timeout $timedOutPolls" +
                            " · drop ${droppedSessionSamples + droppedPollSamples}" +
''',
        '''                            " · timeout $timedOutPolls" +
                            " · restart $readerRestartCount/$readerRestartFailures" +
                            " · anchors ${anchors.size}" +
                            " · drop ${droppedSessionSamples + droppedPollSamples}" +
''',
        "angle status liveness telemetry",
    )

    replace_once(
        feed,
        '''                    controlHandler.post {
                        if (running) {
                            hinge.expireExternal("reader-stale")
                        }
                    }
''',
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
        "stale reader recovery",
    )

    replace_once(
        feed,
        '''        timedOutPolls = 0L
        lastWallpaperIdentity = ""
        lastFreshState = null
''',
        '''        timedOutPolls = 0L
        readerRestartCount = 0L
        readerRestartFailures = 0L
        readerWatchdog.reset()
        lastWallpaperIdentity = ""
        lastFreshState = null
''',
        "start reader watchdog reset",
    )

    # Startup and topology callbacks rebuild the full panel anchor set. The hot
    # poll path uses the cached set and refreshes it only at a bounded cadence.
    feed_text = feed.read_text()
    if feed_text.count("ensureAnchor()") != 3:
        fail(f"expected three ensureAnchor calls, found {feed_text.count('ensureAnchor()')}")
    feed_text = feed_text.replace("ensureAnchor()", "ensureAnchors(force = true)", 2)
    feed_text = feed_text.replace("ensureAnchor()", "ensureAnchors()", 1)
    if feed_text.count("removeAnchor()") != 1:
        fail(f"expected one removeAnchor call, found {feed_text.count('removeAnchor()')}")
    feed_text = feed_text.replace("removeAnchor()", "removeAnchors()", 1)
    feed.write_text(feed_text)

    replace_once(
        feed,
        '''            val sent =
                runCatching {
                    ensureAnchors()

                    val a =
                        anchor

                    if (
                        a == null ||
                        a.windowToken == null
                    ) {
                        false
                    } else {
                        val action =
                            "$actionPrefix:${poll.sequence}"

                        WallpaperManager
                            .getInstance(a.context)
                            .sendWallpaperCommand(
                                a.windowToken,
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
''',
        '''            val sent =
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
''',
        "fan out FoldInteractive command across panel anchors",
    )

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

        TransitionLab.recordIngressStage(
            type = "poll-timeout",
            angleSession = session,
            pollSequence = poll.sequence,
        )

        val now =
            SystemClock.uptimeMillis()

        if (readerWatchdog.onTimeout(now)) {
            restartReader(
                expectedSession = session,
                reason = "poll-timeout-streak:${poll.sequence}",
            )
            return
        }

        val next =
            pipeline.timeoutPoll(
                token = poll,
                timeoutUptimeMs = now,
            ) ?: return

        schedulePoll(
            session = session,
            delayMs = next,
        )
    }

    private fun maybeRestartReader(
        expectedSession: Long,
        reason: String,
    ) {
        if (
            !isCurrent(expectedSession) ||
            !ShizukuBridge.ready ||
            !readerWatchdog.onStale(SystemClock.uptimeMillis())
        ) {
            return
        }

        restartReader(
            expectedSession = expectedSession,
            reason = reason,
        )
    }

    private fun restartReader(
        expectedSession: Long,
        reason: String,
    ) {
        if (
            !isCurrent(expectedSession) ||
            !ShizukuBridge.ready
        ) {
            return
        }

        val oldSession =
            readerSession

        val newSession =
            oldSession + 1L

        readerSession = newSession
        actionPrefix =
            "com.duoopen.angle.READ_${SystemClock.elapsedRealtime()}_$newSession"

        val prefix =
            actionPrefix

        controlHandler.removeCallbacks(
            pollRunnable
        )

        pipeline.invalidateSession()
        hinge.revokeExternalSession(
            session = oldSession,
            reason = "reader-restart:$reason",
        )

        val started =
            ShizukuBridge.startAnglesSequenced(
                prefix,
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
            reason = "$reason started=$started oldSession=$oldSession",
        )

        DuoDiagnostics.event(
            "angle-source",
            "reader restart oldSession=$oldSession newSession=$newSession " +
                "started=$started reason=$reason",
        )

        if (!started) {
            readerRestartFailures++
            status =
                "FoldInteractive reader restart failed: $reason"
            return
        }

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

''',
        "replace timeout-only loop with bounded reader replacement",
    )

    replace_once(
        feed,
        '''        lastCallbackUptime =
            now

        lastDeliveryLagMs =
''',
        '''        lastCallbackUptime =
            now

        readerWatchdog.onSample()

        lastDeliveryLagMs =
''',
        "successful sample resets liveness streak",
    )

    replace_between(
        feed,
        '''    private fun displayKey(
''',
        '''    companion object {
''',
        r'''    private data class CommandAnchor(
        val key: String,
        val displayId: Int,
        val view: View,
        val windowManager: WindowManager,
    )

    private fun displayKey(
        display: Display,
    ): String {
        val mode =
            runCatching {
                display.mode
            }.getOrNull()
                ?: return "${display.displayId}"

        return (
            "${display.displayId}:" +
                "${mode.physicalWidth}x${mode.physicalHeight}"
            )
    }

    private fun isFold7Panel(
        display: Display,
    ): Boolean {
        val mode =
            runCatching {
                display.mode
            }.getOrNull()
                ?: return false

        return (
            mode.physicalWidth == 1968 &&
                mode.physicalHeight == 2184
            ) ||
            (
                mode.physicalWidth == 1080 &&
                    mode.physicalHeight == 2520
                )
    }

    private fun isFold7Inner(
        display: Display,
    ): Boolean {
        val mode =
            runCatching {
                display.mode
            }.getOrNull()
                ?: return false

        return mode.physicalWidth == 1968 &&
            mode.physicalHeight == 2184
    }

    private fun commandDisplays(
        dm: DisplayManager,
    ): List<Display> {
        val expanded =
            runCatching {
                dm.getDisplays(
                    ALL_INCLUDING_DISABLED
                ).toList()
            }.getOrDefault(
                emptyList()
            )

        val ordinary =
            dm.displays.toList()

        val defaultDisplay =
            dm.getDisplay(
                Display.DEFAULT_DISPLAY
            )

        val all =
            (expanded +
                ordinary +
                listOfNotNull(defaultDisplay))
                .distinctBy {
                    it.displayId
                }

        val fold7 =
            all.filter(::isFold7Panel)
                .sortedWith(
                    compareBy<Display> {
                        if (isFold7Inner(it)) 0 else 1
                    }.thenBy {
                        it.displayId
                    }
                )

        return if (fold7.isNotEmpty()) {
            fold7
        } else {
            listOfNotNull(defaultDisplay) +
                ordinary.filter {
                    it.displayId != defaultDisplay?.displayId
                }
        }
    }

    /**
     * Main-thread-only command anchors.
     *
     * One UI 9 can remap logical display 0 from 1968x2184 inner to 1080x2520
     * cover while FoldInteractive remains the hidden inner-side angle producer.
     * Keep tokens on every available Fold7 panel and send the uniquely tagged
     * command to each; the shell reader deduplicates same-poll replies.
     */
    private fun ensureAnchors(
        force: Boolean = false,
    ): List<CommandAnchor> {
        val now =
            SystemClock.uptimeMillis()

        if (
            !force &&
            anchors.isNotEmpty() &&
            now - lastAnchorRefreshUptime <
                ANGLE_ANCHOR_REFRESH_MS
        ) {
            return anchors.values.toList()
        }

        lastAnchorRefreshUptime = now

        val dm =
            context.getSystemService(
                DisplayManager::class.java,
            )

        val displays =
            commandDisplays(dm)

        val desiredKeys =
            displays.map(::displayKey)
                .toSet()

        val staleKeys =
            anchors.keys.filter {
                it !in desiredKeys
            }

        for (key in staleKeys) {
            removeAnchor(key)
        }

        for (display in displays) {
            val key =
                displayKey(display)

            if (key in anchors) {
                continue
            }

            runCatching {
                val c =
                    context
                        .createDisplayContext(display)
                        .createWindowContext(
                            WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                            null,
                        )

                val wm =
                    c.getSystemService(
                        WindowManager::class.java,
                    )

                val view =
                    View(c)

                val params =
                    WindowManager.LayoutParams(
                        1,
                        1,
                        WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                        WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                            WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                            WindowManager.LayoutParams.FLAG_SHOW_WALLPAPER,
                        PixelFormat.TRANSLUCENT,
                    ).apply {
                        gravity =
                            Gravity.TOP or
                                Gravity.START
                        title =
                            "DuoOpenAngleAnchor:${display.displayId}"
                    }

                wm.addView(
                    view,
                    params,
                )

                anchors[key] =
                    CommandAnchor(
                        key = key,
                        displayId = display.displayId,
                        view = view,
                        windowManager = wm,
                    )

                DuoDiagnostics.event(
                    "angle-source",
                    "anchor add key=$key inner=${isFold7Inner(display)}",
                )
            }.onFailure {
                DuoDiagnostics.event(
                    "angle-source",
                    "anchor add failed key=$key error=${it.javaClass.simpleName}:${it.message}",
                )
            }
        }

        return anchors.values.toList()
    }

    private fun removeAnchor(
        key: String,
    ) {
        val commandAnchor =
            anchors.remove(key)
                ?: return

        runCatching {
            commandAnchor.windowManager
                .removeViewImmediate(
                    commandAnchor.view
                )
        }

        DuoDiagnostics.event(
            "angle-source",
            "anchor remove key=$key display=${commandAnchor.displayId}",
        )
    }

    private fun removeAnchors() {
        val keys =
            anchors.keys.toList()

        for (key in keys) {
            removeAnchor(key)
        }

        lastAnchorRefreshUptime = 0L
    }

''',
        "replace default-only command anchor with Fold7 multi-panel anchors",
    )

    replace_once(
        feed,
        '''        const val POLL_TIMEOUT_MS =
            96L

        const val STATUS_TICK_MS =
''',
        '''        const val POLL_TIMEOUT_MS =
            96L

        const val READER_RESTART_TIMEOUTS =
            3

        const val READER_RESTART_MIN_INTERVAL_MS =
            750L

        const val ANGLE_ANCHOR_REFRESH_MS =
            250L

        private const val ALL_INCLUDING_DISABLED =
            "android.hardware.display.category.ALL_INCLUDING_DISABLED"

        const val STATUS_TICK_MS =
''',
        "reader watchdog and anchor refresh constants",
    )

    # Hidden/off inner wallpaper commands are safe to parse because actionPrefix
    # and pollSequence are unique, and epoch freshness is already checked before
    # any callback is accepted. Visibility was the wrong authority boundary.
    replace_once(
        shell,
        '''            if (!line.contains("SprWallpaper|FoldInteractive") || !line.contains("onCommand:")) return null
            if (!(line.contains("isVisible=true") || line.contains("isVisible[true]"))) return null

            val actionMatch = ACTION.matcher(line)
''',
        '''            if (!line.contains("SprWallpaper|FoldInteractive") || !line.contains("onCommand:")) return null

            // GEN12_3_ANGLE_FEED_RESILIENCE: the FoldInteractive producer may
            // be hidden on the inner panel while the native cover is default.
            // Exact action identity + fresh epoch + poll sequence are the
            // authority checks; isVisible is diagnostic, not a validity gate.
            val actionMatch = ACTION.matcher(line)
''',
        "accept hidden FoldInteractive command replies",
    )

    replace_once(
        shell,
        '''                            if (age < -100 || age > 1500) {
                                rejected++
                                continue
                            }
                            parsed++
''',
        '''                            if (age < -100 || age > 1500) {
                                rejected++
                                continue
                            }
                            if (
                                parsedLine.pollSequence > 0L &&
                                parsedLine.pollSequence == lastPollSequence
                            ) {
                                rejected++
                                continue
                            }
                            parsed++
''',
        "dedupe multi-anchor same-poll reader replies",
    )

    replace_once(
        gradle,
        '''        versionCode = 58
        versionName = "5.6.2-gen12-2-route-retention-fence-zfold7"
''',
        '''        versionCode = 59
        versionName = "5.6.3-gen12-3-angle-feed-resilience-zfold7"
''',
        "Gen12.3 version",
    )

    require(feed, "Fold7AngleReaderWatchdog(", 1)
    require(feed, "READER_RESTART_TIMEOUTS =\n            3", 1)
    require(feed, "reader restart oldSession=", 1)
    require(feed, "angle-reader-restart", 1)
    require(feed, "ALL_INCLUDING_DISABLED", 2)
    require(feed, "DuoOpenAngleAnchor:${display.displayId}", 1)
    require(feed, "for (commandAnchor in commandAnchors)", 1)
    require(feed, "maybeRestartReader(", 2)
    forbid(feed, "private var anchor: View?")
    require(shell, "GEN12_3_ANGLE_FEED_RESILIENCE", 1)
    forbid(shell, 'line.contains("isVisible=true")')
    require(watchdog_test, "threeConsecutiveTimeoutsReplaceReader", 1)
    require(watchdog_test, "staleStatusCanRecoverReaderEvenWithoutTimeoutProgress", 1)
    require(gradle, "versionCode = 59", 1)
    require(gradle, 'versionName = "5.6.3-gen12-3-angle-feed-resilience-zfold7"', 1)

    print("GEN12.3 ANGLE FEED RESILIENCE: PASS")


if __name__ == "__main__":
    main()
