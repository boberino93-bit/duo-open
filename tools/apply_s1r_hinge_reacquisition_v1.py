#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

GRADLE = Path("app/build.gradle.kts")
FEED = Path("app/src/full/java/com/duoopen/shell/WallpaperAngleFeed.kt")
POLICY = Path("app/src/full/java/com/duoopen/shell/Fold7AngleRecoveryPolicy.kt")
POLICY_TEST = Path("app/src/test/java/com/duoopen/shell/Fold7AngleRecoveryPolicyTest.kt")
EXPORTER = Path("app/src/main/java/com/duoopen/debug/DebugBundleExporter.kt")
MARKER = "S1R_HINGE_REACQUISITION_V1"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_gradle(text: str) -> str:
    if 'versionName = "5.1.0-beta2-zfold7-s1r"' in text:
        return text
    text = one(text, "        versionCode = 51\n", "        versionCode = 52\n", "versionCode")
    return one(
        text,
        '        versionName = "5.1.0-beta2-zfold7-s1q"\n',
        '        versionName = "5.1.0-beta2-zfold7-s1r"\n',
        "versionName",
    )


POLICY_SOURCE = r'''package com.duoopen.shell

/**
 * S1R_HINGE_REACQUISITION_V1
 *
 * Small Android-free admission gate for rebuilding Samsung's FoldInteractive
 * reader after the shell command channel remains alive but angle callbacks
 * stop returning. The field failure this protects against produced hundreds
 * of sent=true polls followed only by timeouts.
 */
internal class Fold7AngleRecoveryPolicy(
    private val softStaleMs: Long = 700L,
    private val hardStaleMs: Long = 3_500L,
    private val cooldownMs: Long = 1_200L,
) {
    enum class Trigger {
        OPENING_EDGE,
        DISPLAY_CHANGE,
        WALLPAPER_RETURN,
        WATCHDOG,
    }

    data class Decision(
        val admit: Boolean,
        val reason: String,
    )

    private var inFlight = false
    private var lastRecoveryUptimeMs: Long? = null

    fun evaluate(
        trigger: Trigger,
        nowUptimeMs: Long,
        sampleAgeMs: Long,
        foldWallpaperActive: Boolean,
    ): Decision {
        if (inFlight) return Decision(false, "recovery-in-flight")

        val last = lastRecoveryUptimeMs
        if (last != null && nowUptimeMs - last < cooldownMs) {
            return Decision(false, "cooldown")
        }

        if (trigger == Trigger.WATCHDOG && !foldWallpaperActive) {
            return Decision(false, "watchdog-no-fold-wallpaper")
        }

        val requiredAge =
            if (trigger == Trigger.WATCHDOG) hardStaleMs else softStaleMs

        if (sampleAgeMs < requiredAge) {
            return Decision(false, "reader-fresh")
        }

        inFlight = true
        lastRecoveryUptimeMs = nowUptimeMs
        return Decision(true, "stale-reader")
    }

    fun complete() {
        inFlight = false
    }

    fun reset() {
        inFlight = false
        lastRecoveryUptimeMs = null
    }
}
'''


POLICY_TEST_SOURCE = r'''package com.duoopen.shell

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7AngleRecoveryPolicyTest {
    @Test
    fun freshOpeningDoesNotRotateReader() {
        val p = Fold7AngleRecoveryPolicy()
        assertFalse(
            p.evaluate(
                Fold7AngleRecoveryPolicy.Trigger.OPENING_EDGE,
                nowUptimeMs = 10_000L,
                sampleAgeMs = 250L,
                foldWallpaperActive = false,
            ).admit,
        )
    }

    @Test
    fun staleOpeningRotatesReaderBeforeWallpaperReturns() {
        val p = Fold7AngleRecoveryPolicy()
        assertTrue(
            p.evaluate(
                Fold7AngleRecoveryPolicy.Trigger.OPENING_EDGE,
                nowUptimeMs = 10_000L,
                sampleAgeMs = 900L,
                foldWallpaperActive = false,
            ).admit,
        )
    }

    @Test
    fun inFlightAndCooldownSuppressRecoveryStorms() {
        val p = Fold7AngleRecoveryPolicy()
        assertTrue(
            p.evaluate(
                Fold7AngleRecoveryPolicy.Trigger.DISPLAY_CHANGE,
                nowUptimeMs = 10_000L,
                sampleAgeMs = 2_000L,
                foldWallpaperActive = false,
            ).admit,
        )
        assertFalse(
            p.evaluate(
                Fold7AngleRecoveryPolicy.Trigger.DISPLAY_CHANGE,
                nowUptimeMs = 10_050L,
                sampleAgeMs = 2_050L,
                foldWallpaperActive = false,
            ).admit,
        )
        p.complete()
        assertFalse(
            p.evaluate(
                Fold7AngleRecoveryPolicy.Trigger.DISPLAY_CHANGE,
                nowUptimeMs = 10_700L,
                sampleAgeMs = 2_700L,
                foldWallpaperActive = false,
            ).admit,
        )
        assertTrue(
            p.evaluate(
                Fold7AngleRecoveryPolicy.Trigger.DISPLAY_CHANGE,
                nowUptimeMs = 11_250L,
                sampleAgeMs = 3_250L,
                foldWallpaperActive = false,
            ).admit,
        )
    }

    @Test
    fun watchdogOnlyRepairsWhenFoldWallpaperIsActuallyBack() {
        val p = Fold7AngleRecoveryPolicy()
        assertFalse(
            p.evaluate(
                Fold7AngleRecoveryPolicy.Trigger.WATCHDOG,
                nowUptimeMs = 20_000L,
                sampleAgeMs = 8_000L,
                foldWallpaperActive = false,
            ).admit,
        )
        assertTrue(
            p.evaluate(
                Fold7AngleRecoveryPolicy.Trigger.WATCHDOG,
                nowUptimeMs = 20_001L,
                sampleAgeMs = 8_001L,
                foldWallpaperActive = true,
            ).admit,
        )
    }
}
'''


def transform_feed(text: str) -> str:
    if MARKER in text:
        return text

    text = one(
        text,
        '''    private var lastWallpaperIdentity = ""
    private var lastFreshState: Boolean? = null
    private var startedAt = 0L
    private var scheduledPollSession = -1L
''',
        f'''    @Volatile
    private var lastWallpaperIdentity = ""
    private var lastFreshState: Boolean? = null
    private var startedAt = 0L
    private var scheduledPollSession = -1L

    // {MARKER}: field evidence showed the reader could remain logically alive
    // while every wallpaper command timed out after a cover/native transition.
    // Rotate the complete reader session/token/anchor rather than polling a
    // permanently dead FoldInteractive callback forever.
    private val recoveryPolicy = Fold7AngleRecoveryPolicy()
    private var recoveryCount = 0L
    private var recoveryAwaitingFirstSample = false
    private var recoveryStartedUptime = 0L
''',
        "recovery fields",
    )

    old_wallpaper_change = '''                if (wallpaper != lastWallpaperIdentity) {
                    DuoDiagnostics.event(
                        "angle-source",
                        "wallpaper changed from=" +
                            "${lastWallpaperIdentity.ifEmpty { "(initial)" }} " +
                            "to=$wallpaper readerFresh=$fresh ageMs=$age",
                    )

                    lastWallpaperIdentity = wallpaper
                }
'''
    new_wallpaper_change = '''                if (wallpaper != lastWallpaperIdentity) {
                    DuoDiagnostics.event(
                        "angle-source",
                        "wallpaper changed from=" +
                            "${lastWallpaperIdentity.ifEmpty { "(initial)" }} " +
                            "to=$wallpaper readerFresh=$fresh ageMs=$age",
                    )

                    lastWallpaperIdentity = wallpaper

                    if (!fresh && wallpaper.contains("FoldInteractive")) {
                        requestRecovery(
                            trigger = Fold7AngleRecoveryPolicy.Trigger.WALLPAPER_RETURN,
                            reason = "fold-wallpaper-return:$wallpaper",
                            foldWallpaperActive = true,
                        )
                    }
                }
'''
    text = one(text, old_wallpaper_change, new_wallpaper_change, "wallpaper return recovery")

    old_stale = '''                    controlHandler.post {
                        if (running) {
                            hinge.expireExternal("reader-stale")
                        }
                    }
                }
'''
    new_stale = '''                    controlHandler.post {
                        if (running) {
                            hinge.expireExternal("reader-stale")
                        }
                    }

                    requestRecovery(
                        trigger = Fold7AngleRecoveryPolicy.Trigger.WATCHDOG,
                        reason = "stale-watchdog:$wallpaper",
                        foldWallpaperActive = wallpaper.contains("FoldInteractive"),
                    )
                }
'''
    text = one(text, old_stale, new_stale, "stale watchdog recovery")

    text = one(
        text,
        '''                            " · drop ${droppedSessionSamples + droppedPollSamples}" +
                            " · dup $duplicateAngles" +
                            " · source ${if (fresh) "live" else "stale"}" +
''',
        '''                            " · drop ${droppedSessionSamples + droppedPollSamples}" +
                            " · dup $duplicateAngles" +
                            " · recover $recoveryCount" +
                            " · source ${if (fresh) "live" else "stale"}" +
''',
        "status recovery count",
    )

    text = one(
        text,
        '''        lastWallpaperIdentity = ""
        lastFreshState = null

        status = "Starting Fold7 Gen-2 Samsung hinge reader"
''',
        '''        lastWallpaperIdentity = ""
        lastFreshState = null
        recoveryPolicy.reset()
        recoveryCount = 0L
        recoveryAwaitingFirstSample = false
        recoveryStartedUptime = 0L

        status = "Starting Fold7 Gen-2 Samsung hinge reader"
''',
        "start recovery reset",
    )

    text = one(
        text,
        '''        controlHandler.removeCallbacks(
            pollRunnable
        )

        controlHandler.post {
''',
        '''        controlHandler.removeCallbacks(
            pollRunnable
        )

        recoveryPolicy.reset()
        recoveryAwaitingFirstSample = false

        controlHandler.post {
''',
        "stop recovery reset",
    )

    old_kick = '''        controlHandler.post {
            if (!isCurrent(session)) return@post

            TransitionLab.recordIngressStage(
                type = "poll-kick",
                angleSession = session,
                reason = reason,
            )

            if (pipeline.inFlightPoll == null) {
                schedulePoll(
                    session = session,
                    delayMs = 0L,
                )
            }
        }
'''
    new_kick = '''        controlHandler.post {
            if (!isCurrent(session)) return@post

            TransitionLab.recordIngressStage(
                type = "poll-kick",
                angleSession = session,
                reason = reason,
            )

            if (
                requestRecoveryFromControl(
                    trigger = Fold7AngleRecoveryPolicy.Trigger.OPENING_EDGE,
                    reason = "opening-kick:$reason",
                    foldWallpaperActive = lastWallpaperIdentity.contains("FoldInteractive"),
                )
            ) {
                return@post
            }

            if (pipeline.inFlightPoll == null) {
                schedulePoll(
                    session = session,
                    delayMs = 0L,
                )
            }
        }
'''
    text = one(text, old_kick, new_kick, "opening kick recovery")

    old_display = '''        mainHandler.post {
            if (running) {
                runCatching {
                    ensureAnchor()
                }.onFailure {
                    status =
                        "Anchor failed: ${it.message}"
                }
            }
        }
    }

    private fun startPoll(
'''
    new_display = '''        mainHandler.post {
            if (running) {
                runCatching {
                    ensureAnchor()
                }.onFailure {
                    status =
                        "Anchor failed: ${it.message}"
                }

                requestRecovery(
                    trigger = Fold7AngleRecoveryPolicy.Trigger.DISPLAY_CHANGE,
                    reason = "default-display-change:$anchorKey",
                    foldWallpaperActive = lastWallpaperIdentity.contains("FoldInteractive"),
                )
            }
        }
    }

    private fun readerSampleAgeMs(
        nowUptimeMs: Long = SystemClock.uptimeMillis(),
    ): Long =
        if (lastCallbackUptime == 0L) {
            (nowUptimeMs - startedAt).coerceAtLeast(0L)
        } else {
            (nowUptimeMs - lastCallbackUptime).coerceAtLeast(0L)
        }

    private fun requestRecovery(
        trigger: Fold7AngleRecoveryPolicy.Trigger,
        reason: String,
        foldWallpaperActive: Boolean,
    ) {
        controlHandler.post {
            requestRecoveryFromControl(
                trigger = trigger,
                reason = reason,
                foldWallpaperActive = foldWallpaperActive,
            )
        }
    }

    private fun requestRecoveryFromControl(
        trigger: Fold7AngleRecoveryPolicy.Trigger,
        reason: String,
        foldWallpaperActive: Boolean,
    ): Boolean {
        if (!running) return false

        val now = SystemClock.uptimeMillis()
        val age = readerSampleAgeMs(now)
        val decision =
            recoveryPolicy.evaluate(
                trigger = trigger,
                nowUptimeMs = now,
                sampleAgeMs = age,
                foldWallpaperActive = foldWallpaperActive,
            )

        if (!decision.admit) {
            if (decision.reason != "reader-fresh") {
                DuoDiagnostics.event(
                    "angle-recovery",
                    "SKIP trigger=$trigger reason=$reason ageMs=$age " +
                        "policy=${decision.reason} session=$readerSession",
                )
            }
            return false
        }

        val oldSession = readerSession

        DuoDiagnostics.event(
            "angle-recovery",
            "START trigger=$trigger reason=$reason ageMs=$age " +
                "oldSession=$oldSession anchor=$anchorKey wallpaper=$lastWallpaperIdentity",
        )
        TransitionLab.recordIngressStage(
            type = "angle-recovery-start",
            angleSession = oldSession,
            reason = "$trigger:$reason ageMs=$age",
        )

        // Drop the old token on main before creating the replacement reader.
        // A recreated 1x1 FLAG_SHOW_WALLPAPER anchor guarantees a fresh window
        // token even when the default display ID/geometry did not change.
        mainHandler.post {
            if (!isCurrent(oldSession)) {
                controlHandler.post {
                    recoveryPolicy.complete()
                }
                return@post
            }

            removeAnchor()

            controlHandler.post {
                restartReaderAfterAnchorDrop(
                    oldSession = oldSession,
                    trigger = trigger,
                    reason = reason,
                    staleAgeMs = age,
                )
            }
        }

        return true
    }

    private fun restartReaderAfterAnchorDrop(
        oldSession: Long,
        trigger: Fold7AngleRecoveryPolicy.Trigger,
        reason: String,
        staleAgeMs: Long,
    ) {
        if (!isCurrent(oldSession)) {
            recoveryPolicy.complete()
            return
        }

        controlHandler.removeCallbacks(pollRunnable)
        pipeline.invalidateSession()
        hinge.revokeExternalSession(
            session = oldSession,
            reason = "reader-recovery:$trigger:$reason",
        )
        ShizukuBridge.stopAngles()

        val newSession = oldSession + 1L
        readerSession = newSession
        actionPrefix =
            "com.duoopen.angle.READ_${SystemClock.elapsedRealtime()}_$newSession"
        val prefix = actionPrefix
        val restartUptime = SystemClock.uptimeMillis()

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

        startedAt = restartUptime
        lastCallbackUptime = 0L
        lastDeliveryLagMs = -1L
        lastAngleSeen = Float.NaN
        lastAngleChangeUptime = 0L
        scheduledPollSession = -1L

        if (!started) {
            status = "Angle reader recovery failed to bind"
            recoveryPolicy.complete()
            DuoDiagnostics.event(
                "angle-recovery",
                "FAILED trigger=$trigger reason=$reason oldSession=$oldSession " +
                    "newSession=$newSession staleAgeMs=$staleAgeMs",
            )
            TransitionLab.recordIngressStage(
                type = "angle-recovery-failed",
                angleSession = newSession,
                reason = "$trigger:$reason",
            )
            return
        }

        pipeline.startSession()
        hinge.beginExternalSession(newSession)
        recoveryCount++
        recoveryAwaitingFirstSample = true
        recoveryStartedUptime = restartUptime
        recoveryPolicy.complete()

        mainHandler.post {
            if (isCurrent(newSession)) {
                runCatching {
                    ensureAnchor()
                }.onFailure {
                    status = "Recovery anchor failed: ${it.message}"
                }
            }
        }

        TransitionLab.recordIngressStage(
            type = "angle-recovery-reader-ready",
            angleSession = newSession,
            reason = "$trigger:$reason staleAgeMs=$staleAgeMs",
        )
        DuoDiagnostics.event(
            "angle-recovery",
            "READER_READY trigger=$trigger oldSession=$oldSession newSession=$newSession " +
                "staleAgeMs=$staleAgeMs prefix=$prefix",
        )

        schedulePoll(
            session = newSession,
            delayMs = 0L,
        )
    }

    private fun startPoll(
'''
    text = one(text, old_display, new_display, "display-change and recovery helpers")

    old_now = '''        val now =
            SystemClock.uptimeMillis()

        endpointBridgeGeneration++
'''
    new_now = '''        val now =
            SystemClock.uptimeMillis()

        if (recoveryAwaitingFirstSample) {
            recoveryAwaitingFirstSample = false
            val recoveryLatencyMs =
                (now - recoveryStartedUptime).coerceAtLeast(0L)
            DuoDiagnostics.event(
                "angle-recovery",
                "FIRST_SAMPLE session=$session poll=$pollSequence angle=$angle " +
                    "latencyMs=$recoveryLatencyMs sourceLagMs=${(now - sourceUptime).coerceAtLeast(0L)}",
            )
            TransitionLab.recordIngressStage(
                type = "angle-recovery-first-sample",
                angleSession = session,
                pollSequence = pollSequence,
                valueFloat = angle,
                valueNs = recoveryLatencyMs * TransitionClock.NS_PER_MS,
            )
        }

        endpointBridgeGeneration++
'''
    text = one(text, old_now, new_now, "first recovered sample telemetry")

    return text


def transform_exporter(text: str) -> str:
    if "hingeReacquisition=S1R_HINGE_REACQUISITION_V1" in text:
        return text

    anchor = '''                        appendLine(
                            "proxyRegistration=CANONICAL_RIGHT_PANE_984_0_1920_2184"
                        )
'''
    addition = anchor + '''                        appendLine(
                            "hingeReacquisition=S1R_HINGE_REACQUISITION_V1"
                        )
                        appendLine(
                            "hingeReacquisitionSoftStaleMs=700"
                        )
                        appendLine(
                            "hingeReacquisitionHardStaleMs=3500"
                        )
                        appendLine(
                            "hingeReacquisitionCooldownMs=1200"
                        )
                        appendLine(
                            "hingeReacquisitionTriggers=OPENING_EDGE,DISPLAY_CHANGE,WALLPAPER_RETURN,WATCHDOG"
                        )
'''
    return one(text, anchor, addition, "S1R exporter identity")


def validate(g: str, f: str, p: str, pt: str, e: str) -> None:
    required = (
        (g, ['versionCode = 52', 'versionName = "5.1.0-beta2-zfold7-s1r"']),
        (
            f,
            [
                MARKER,
                "requestRecoveryFromControl",
                "restartReaderAfterAnchorDrop",
                "angle-recovery-first-sample",
                "Fold7AngleRecoveryPolicy.Trigger.OPENING_EDGE",
                "Fold7AngleRecoveryPolicy.Trigger.DISPLAY_CHANGE",
                "Fold7AngleRecoveryPolicy.Trigger.WALLPAPER_RETURN",
                "Fold7AngleRecoveryPolicy.Trigger.WATCHDOG",
                "ShizukuBridge.stopAngles()",
                "hinge.revokeExternalSession(",
                "hinge.beginExternalSession(newSession)",
                "removeAnchor()",
            ],
        ),
        (p, [MARKER, "softStaleMs: Long = 700L", "hardStaleMs: Long = 3_500L", "cooldownMs: Long = 1_200L"]),
        (pt, ["staleOpeningRotatesReaderBeforeWallpaperReturns", "inFlightAndCooldownSuppressRecoveryStorms", "watchdogOnlyRepairsWhenFoldWallpaperIsActuallyBack"]),
        (e, ["hingeReacquisition=S1R_HINGE_REACQUISITION_V1", "hingeReacquisitionSoftStaleMs=700"]),
    )
    for text, needles in required:
        for needle in needles:
            if needle not in text:
                raise RuntimeError("missing S1R invariant: " + needle)

    combined = "\n".join((f, p, e))
    for prohibited in (
        "cmd device_state state 5",
        "scheduleConcurrentOuterRouteProbe",
        "PROBE_CONCURRENT_OUTER_DEFAULT",
    ):
        if prohibited in combined:
            raise RuntimeError("S1R must not reintroduce unsafe route override: " + prohibited)


def apply(repo: Path, check: bool) -> None:
    for rel in (GRADLE, FEED, EXPORTER):
        if not (repo / rel).exists():
            raise RuntimeError("missing " + str(rel))

    g = transform_gradle((repo / GRADLE).read_text(encoding="utf-8"))
    f = transform_feed((repo / FEED).read_text(encoding="utf-8"))
    e = transform_exporter((repo / EXPORTER).read_text(encoding="utf-8"))
    p = POLICY_SOURCE
    pt = POLICY_TEST_SOURCE
    validate(g, f, p, pt, e)

    if not check:
        (repo / GRADLE).write_text(g, encoding="utf-8")
        (repo / FEED).write_text(f, encoding="utf-8")
        (repo / POLICY).write_text(p, encoding="utf-8")
        (repo / POLICY_TEST).write_text(pt, encoding="utf-8")
        (repo / EXPORTER).write_text(e, encoding="utf-8")


def self_test() -> None:
    sample = '        versionCode = 51\n        versionName = "5.1.0-beta2-zfold7-s1q"\n'
    out = transform_gradle(sample)
    assert "versionCode = 52" in out
    assert "zfold7-s1r" in out
    assert "watchdog-no-fold-wallpaper" in POLICY_SOURCE
    assert "cooldown" in POLICY_SOURCE
    print("S1R hinge reacquisition transformer self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        if not args.check:
            return 0

    apply(Path(args.repo).resolve(), args.check)
    print("S1R hinge reacquisition: " + ("source shape verified" if args.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
