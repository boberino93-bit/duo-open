#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

GRADLE = Path("app/build.gradle.kts")
AUTHORITY = Path("app/src/main/java/com/duoopen/fold/Fold7AngleAuthority.kt")
AUTHORITY_TEST = Path("app/src/test/java/com/duoopen/fold/Fold7AngleAuthorityTest.kt")
HINGE_SOURCE = Path("app/src/main/java/com/duoopen/fold/HingeAngleSource.kt")
COVER_READINESS = Path("app/src/full/java/com/duoopen/overlay/Fold7CoverReadiness.kt")
COORDINATOR = Path("app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt")
PRESENT_GATE = Path("app/src/full/java/com/duoopen/overlay/Fold7InnerPresentationGate.kt")
PRESENT_GATE_TEST = Path("app/src/test/java/com/duoopen/overlay/Fold7InnerPresentationGateTest.kt")
PANEL_AUTHORITY = Path("app/src/full/java/com/duoopen/shell/Fold7PanelAuthorityGen4.kt")
PANEL_AUTHORITY_TEST = Path("app/src/test/java/com/duoopen/shell/Fold7PanelAuthorityGen4Test.kt")
SHELL = Path("app/src/full/java/com/duoopen/shell/DuoShellService.kt")
PANEL = Path("app/src/full/java/com/duoopen/overlay/PanelEngine.kt")
EXPORTER = Path("app/src/main/java/com/duoopen/debug/DebugBundleExporter.kt")

MARKER = "S1S_BETA_CONVERGENCE_V1"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_gradle(text: str) -> str:
    if 'versionName = "5.1.0-beta2-zfold7-s1s"' in text:
        return text
    text = one(text, "        versionCode = 52\n", "        versionCode = 53\n", "versionCode")
    return one(
        text,
        '        versionName = "5.1.0-beta2-zfold7-s1r"\n',
        '        versionName = "5.1.0-beta2-zfold7-s1s"\n',
        "versionName",
    )


def transform_authority(text: str) -> str:
    if "suppressedCoarseMidpoint" in text:
        return text

    text = one(
        text,
        '''        val droppedSequencePrecise: Long,\n    )\n''',
        '''        val droppedSequencePrecise: Long,\n        val suppressedCoarseMidpoint: Long,\n    )\n''',
        "snapshot coarse suppression field",
    )
    text = one(
        text,
        '''    private var droppedSequencePrecise = 0L\n''',
        '''    private var droppedSequencePrecise = 0L\n    // S1S_BETA_CONVERGENCE_V1: public 0/90/180-style sensors may corroborate\n    // endpoint rest but must never impersonate continuous geometry mid-fold.\n    private var suppressedCoarseMidpoint = 0L\n''',
        "coarse suppression counter",
    )
    text = one(
        text,
        '''            droppedSequencePrecise = droppedSequencePrecise,\n        )\n''',
        '''            droppedSequencePrecise = droppedSequencePrecise,\n            suppressedCoarseMidpoint = suppressedCoarseMidpoint,\n        )\n''',
        "snapshot coarse suppression export",
    )

    old = '''        val sourceChanged = currentSource != candidate.source\n        val changed =\n            currentAngle.isNaN() ||\n                abs(candidate.angle - currentAngle) >= CHANGE_EPSILON_DEG ||\n                sourceChanged\n\n        currentAngle = candidate.angle\n        currentSource = candidate.source\n        currentObservedUptimeMs = candidate.observedUptimeMs\n        currentCoarse = candidate.coarse\n        publicCandidate = null\n'''
    new = '''        // S1S_BETA_CONVERGENCE_V1: a coarse public midpoint (typically\n        // Samsung's 90-degree stop) is classification evidence, not geometry.\n        // Do not let precise expiry manufacture a semantic 90-degree jump.\n        if (\n            candidate.coarse &&\n            candidate.angle > COARSE_ENDPOINT_MAX_DEG &&\n            candidate.angle < 180f - COARSE_ENDPOINT_MAX_DEG\n        ) {\n            suppressedCoarseMidpoint++\n            publicCandidate = null\n            return Decision(\n                accepted = false,\n                dropReason = "coarse-midpoint-suppressed",\n                sourceAgeMs = ageMs,\n            )\n        }\n\n        val promotedAngle =\n            if (candidate.coarse) {\n                if (candidate.angle <= COARSE_ENDPOINT_MAX_DEG) 0f else 180f\n            } else {\n                candidate.angle\n            }\n\n        val sourceChanged = currentSource != candidate.source\n        val changed =\n            currentAngle.isNaN() ||\n                abs(promotedAngle - currentAngle) >= CHANGE_EPSILON_DEG ||\n                sourceChanged\n\n        currentAngle = promotedAngle\n        currentSource = candidate.source\n        currentObservedUptimeMs = candidate.observedUptimeMs\n        currentCoarse = candidate.coarse\n        publicCandidate = null\n'''
    text = one(text, old, new, "coarse midpoint semantic fence")
    text = one(
        text,
        '''        const val DEFAULT_PUBLIC_MAX_AGE_MS = 3_000L\n        private const val CHANGE_EPSILON_DEG = 0.10f\n''',
        '''        const val DEFAULT_PUBLIC_MAX_AGE_MS = 3_000L\n        const val COARSE_ENDPOINT_MAX_DEG = 12f\n        private const val CHANGE_EPSILON_DEG = 0.10f\n''',
        "coarse endpoint constant",
    )
    return text


def transform_authority_test(text: str) -> str:
    if "coarseMidpointCannotTakeSemanticAuthority" in text:
        return text

    old = '''    @Test\n    fun freshPreciseOwnsWhilePublicIsRetainedThenPromoted() {\n        val a = Fold7AngleAuthority(preciseMaxAgeMs = 192L)\n        a.startPreciseSession(7L, 1_000L)\n        val p = a.offerPrecise(7L, 1L, 5f, 1_000L, 1_010L)\n        assertNotNull(p.output)\n\n        val shadow = a.offerPublic(\n            source = Fold7AngleAuthority.Source.PUBLIC_STANDARD,\n            angle = 90f,\n            observedUptimeMs = 1_050L,\n            receivedUptimeMs = 1_050L,\n            coarse = true,\n        )\n        assertNull(shadow.output)\n\n        val expired = a.expirePrecise(1_193L, "lease-expired")\n        assertEquals(90f, expired.output!!.angle)\n        assertEquals(Fold7AngleAuthority.Source.PUBLIC_STANDARD, expired.output!!.source)\n        assertTrue(expired.output!!.coarse)\n    }\n'''
    new = '''    @Test\n    fun coarseMidpointCannotTakeSemanticAuthority() {\n        val a = Fold7AngleAuthority(preciseMaxAgeMs = 192L)\n        a.startPreciseSession(7L, 1_000L)\n        assertNotNull(a.offerPrecise(7L, 1L, 5f, 1_000L, 1_010L).output)\n\n        val shadow = a.offerPublic(\n            source = Fold7AngleAuthority.Source.PUBLIC_STANDARD,\n            angle = 90f,\n            observedUptimeMs = 1_050L,\n            receivedUptimeMs = 1_050L,\n            coarse = true,\n        )\n        assertNull(shadow.output)\n\n        val expired = a.expirePrecise(1_193L, "lease-expired")\n        assertNull(expired.output)\n        assertEquals(Fold7AngleAuthority.Source.NONE, a.snapshot(1_193L).source)\n        assertEquals(1L, a.snapshot(1_193L).suppressedCoarseMidpoint)\n    }\n\n    @Test\n    fun coarseEndpointMayOnlyPromoteAsCanonicalRest() {\n        val a = Fold7AngleAuthority()\n        val d = a.offerPublic(\n            source = Fold7AngleAuthority.Source.PUBLIC_STANDARD,\n            angle = 7f,\n            observedUptimeMs = 500L,\n            receivedUptimeMs = 501L,\n            coarse = true,\n        )\n        assertEquals(0f, d.output!!.angle)\n        assertTrue(d.output!!.coarse)\n    }\n'''
    return one(text, old, new, "replace coarse midpoint promotion test")


def transform_hinge_source(text: str) -> str:
    if "coarse-suppressed" in text:
        return text
    old = '''        if (!decision.accepted && decision.dropReason != null) {\n            Log.d(\n                TAG,\n                "angle authority drop reason=${decision.dropReason} age=${decision.sourceAgeMs}",\n            )\n        }\n'''
    new = '''        if (!decision.accepted && decision.dropReason != null) {\n            Log.d(\n                TAG,\n                "angle authority drop reason=${decision.dropReason} age=${decision.sourceAgeMs}",\n            )\n            if (decision.dropReason == "coarse-midpoint-suppressed") {\n                val snapshot = authority.snapshot(SystemClock.uptimeMillis())\n                com.duoopen.debug.DuoDiagnostics.event(\n                    "angle-authority",\n                    "coarse-suppressed ageMs=${decision.sourceAgeMs} " +\n                        "shadow=${snapshot.publicShadowAngle} total=${snapshot.suppressedCoarseMidpoint}",\n                )\n            }\n        }\n'''
    text = one(text, old, new, "coarse suppression diagnostics")
    text = one(
        text,
        '''                "${snapshot.droppedSessionPrecise}/${snapshot.droppedSequencePrecise}",\n''',
        '''                "${snapshot.droppedSessionPrecise}/${snapshot.droppedSequencePrecise} " +\n                "coarseMidSuppressed=${snapshot.suppressedCoarseMidpoint}",\n''',
        "hinge report coarse suppression",
    )
    return text


PRESENT_GATE_SOURCE = r'''package com.duoopen.overlay

/**
 * S1S_BETA_CONVERGENCE_V1
 * Presentation readiness is deliberately stronger than topology existence.
 * A logical INNER route must be default + STATE_ON continuously before the
 * temporary optical bridge may be released. A bounded timeout prevents a
 * proxy from becoming permanently stranded if Samsung never reports ready.
 */
internal class Fold7InnerPresentationGate(
    private val stableMs: Long = 160L,
    private val maxHoldMs: Long = 500L,
) {
    enum class Action { WAIT, RELEASE_READY, RELEASE_TIMEOUT }

    data class Decision(
        val action: Action,
        val stableForMs: Long,
        val elapsedMs: Long,
        val reason: String,
    )

    private var startedAtMs = Long.MIN_VALUE
    private var readySinceMs = Long.MIN_VALUE

    fun begin(nowMs: Long) {
        startedAtMs = nowMs
        readySinceMs = Long.MIN_VALUE
    }

    fun evaluate(
        nowMs: Long,
        innerDefault: Boolean,
        innerPresentationReady: Boolean,
    ): Decision {
        if (startedAtMs == Long.MIN_VALUE) begin(nowMs)
        val elapsed = (nowMs - startedAtMs).coerceAtLeast(0L)

        if (!innerDefault || !innerPresentationReady) {
            readySinceMs = Long.MIN_VALUE
            if (elapsed >= maxHoldMs) {
                return Decision(Action.RELEASE_TIMEOUT, 0L, elapsed, "bounded-timeout")
            }
            return Decision(Action.WAIT, 0L, elapsed, "destination-not-ready")
        }

        if (readySinceMs == Long.MIN_VALUE) readySinceMs = nowMs
        val stable = (nowMs - readySinceMs).coerceAtLeast(0L)
        if (stable >= stableMs) {
            return Decision(Action.RELEASE_READY, stable, elapsed, "presentation-stable")
        }
        if (elapsed >= maxHoldMs) {
            return Decision(Action.RELEASE_TIMEOUT, stable, elapsed, "bounded-timeout")
        }
        return Decision(Action.WAIT, stable, elapsed, "stabilizing")
    }
}
'''


PRESENT_GATE_TEST_SOURCE = r'''package com.duoopen.overlay

import org.junit.Assert.assertEquals
import org.junit.Test

class Fold7InnerPresentationGateTest {
    @Test
    fun topologyWithoutPresentationNeverReleasesEarly() {
        val g = Fold7InnerPresentationGate(stableMs = 160L, maxHoldMs = 500L)
        g.begin(1_000L)
        assertEquals(
            Fold7InnerPresentationGate.Action.WAIT,
            g.evaluate(1_250L, innerDefault = true, innerPresentationReady = false).action,
        )
    }

    @Test
    fun readyMustRemainStableBeforeRelease() {
        val g = Fold7InnerPresentationGate(stableMs = 160L, maxHoldMs = 500L)
        g.begin(1_000L)
        assertEquals(
            Fold7InnerPresentationGate.Action.WAIT,
            g.evaluate(1_100L, true, true).action,
        )
        assertEquals(
            Fold7InnerPresentationGate.Action.WAIT,
            g.evaluate(1_240L, true, true).action,
        )
        assertEquals(
            Fold7InnerPresentationGate.Action.RELEASE_READY,
            g.evaluate(1_261L, true, true).action,
        )
    }

    @Test
    fun readinessLossResetsStableWindow() {
        val g = Fold7InnerPresentationGate(stableMs = 160L, maxHoldMs = 500L)
        g.begin(1_000L)
        g.evaluate(1_080L, true, true)
        g.evaluate(1_180L, true, false)
        assertEquals(
            Fold7InnerPresentationGate.Action.WAIT,
            g.evaluate(1_250L, true, true).action,
        )
    }

    @Test
    fun timeoutIsBounded() {
        val g = Fold7InnerPresentationGate(stableMs = 160L, maxHoldMs = 500L)
        g.begin(1_000L)
        assertEquals(
            Fold7InnerPresentationGate.Action.RELEASE_TIMEOUT,
            g.evaluate(1_501L, false, false).action,
        )
    }
}
'''


def transform_cover_readiness(text: str) -> str:
    if "coverPresentationReady" in text:
        return text
    text = one(
        text,
        '''        val coverLogicalId: Int?,\n    )\n''',
        '''        val coverLogicalId: Int?,\n        val coverPresentationReady: Boolean,\n    )\n''',
        "cover presentation topology field",
    )
    text = one(
        text,
        '''                topology.coverActive &&\n                topology.innerIsDefault &&\n''',
        '''                topology.coverActive &&\n                topology.coverPresentationReady &&\n                topology.innerIsDefault &&\n''',
        "cover presentation readiness gate",
    )
    return text


def transform_coordinator(text: str) -> str:
    if "S1S_PRESENTATION_READY_HANDOFF" in text:
        return text

    # Closing readiness: logical presence does not prove a renderable destination.
    text = one(
        text,
        '''                        coverLogicalId = t.coverLogicalId,\n                    ),\n''',
        '''                        coverLogicalId = t.coverLogicalId,\n                        coverPresentationReady =\n                            topologySnapshot().cover?.let(::isPresentationReady) == true,\n                    ),\n''',
        "cover readiness presentation flag",
    )
    text = one(
        text,
        '''                "coverLogical=${t.coverLogicalId} coverActive=${t.coverActive}",\n''',
        '''                "coverLogical=${t.coverLogicalId} coverActive=${t.coverActive} " +\n                "coverPresentationReady=${topologySnapshot().cover?.let(::isPresentationReady) == true}",\n''',
        "cover readiness presentation telemetry",
    )

    # A mirror host also needs actual presentation-ready displays, not merely a
    # topology object that exists in DOZE/SUSPEND.
    text = one(
        text,
        '''        val activeInner = snapshot.inner?.takeIf(::isActive)\n        val activeCover = snapshot.cover?.takeIf(::isActive)\n''',
        '''        val activeInner = snapshot.inner?.takeIf(::isPresentationReady)\n        val activeCover = snapshot.cover?.takeIf(::isPresentationReady)\n''',
        "mirror host presentation-ready displays",
    )

    old_release = '''                    handler.postDelayed(\n                        {\n                            scope.launch(Dispatchers.IO) {\n                                val release =\n                                    ShizukuBridge.releaseInnerPhysicalBridge(\n                                        serviceEpoch = openingKey.serviceEpoch,\n                                        openingAttemptSequence =\n                                            openingKey.openingAttemptSequence,\n                                        reason = "native-inner-settled",\n                                    )\n\n                                Fold7DisplayStatusStore.update { current ->\n                                    current.copy(\n                                        physicalPower =\n                                            if (current.physicalPower == Fold7DisplayStatus.PhysicalPower.COMMAND_ACCEPTED) {\n                                                Fold7DisplayStatus.PhysicalPower.COMMAND_ACCEPTED\n                                            } else {\n                                                current.physicalPower\n                                            },\n                                        bridge = Fold7DisplayStatus.Bridge.RELEASED,\n                                        nativeInnerActive = true,\n                                        nativeInnerDefault = topology().innerIsDefault,\n                                    )\n                                }\n\n                                DuoDiagnostics.event(\n                                    "inner-wake-stage",\n                                    "HANDOFF_RELEASED serviceEpoch=${openingKey.serviceEpoch} " +\n                                        "openingAttempt=${openingKey.openingAttemptSequence} " +\n                                        "ok=${release?.getBoolean("ok", false) == true} " +\n                                        "stale=${release?.getBoolean("stale", false) == true} " +\n                                        "active=${release?.getBoolean("active", false) == true}",\n                                )\n                            }\n                        },\n                        INNER_BRIDGE_HANDOFF_SETTLE_MS,\n                    )\n                    return@post\n'''
    new_release = '''                    // S1S_PRESENTATION_READY_HANDOFF: do not release merely because\n                    // Android published INNER topology. Hold the optical bridge until\n                    // INNER is default + STATE_ON continuously, with a bounded timeout.\n                    scheduleInnerBridgeReleaseWhenPresentationReady(\n                        openingKey = openingKey,\n                        retry = attempt,\n                    )\n                    return@post\n'''
    text = one(text, old_release, new_release, "replace fixed 80ms inner handoff")

    helper = r'''    // S1S_PRESENTATION_READY_HANDOFF
    private fun scheduleInnerBridgeReleaseWhenPresentationReady(
        openingKey: Fold7OpeningWakeAttemptGate.Key,
        retry: Int,
    ) {
        val gate = Fold7InnerPresentationGate(
            stableMs = INNER_PRESENTATION_STABLE_MS,
            maxHoldMs = INNER_PRESENTATION_MAX_HOLD_MS,
        )
        gate.begin(SystemClock.uptimeMillis())

        fun check() {
            val now = SystemClock.uptimeMillis()
            val inner = topologySnapshot().inner
            val innerDefault = inner?.displayId == Display.DEFAULT_DISPLAY
            val presentReady = inner?.let(::isPresentationReady) == true
            val decision =
                gate.evaluate(
                    nowMs = now,
                    innerDefault = innerDefault,
                    innerPresentationReady = presentReady,
                )

            DuoDiagnostics.event(
                "inner-presentation-gate",
                "attempt=${openingKey.openingAttemptSequence} retry=$retry " +
                    "action=${decision.action} reason=${decision.reason} " +
                    "stableMs=${decision.stableForMs} elapsedMs=${decision.elapsedMs} " +
                    "inner=${inner?.displayId}:${inner?.state} default=$innerDefault",
            )

            if (decision.action == Fold7InnerPresentationGate.Action.WAIT) {
                handler.postDelayed({ check() }, INNER_PRESENTATION_POLL_MS)
                return
            }

            scope.launch(Dispatchers.IO) {
                val release =
                    ShizukuBridge.releaseInnerPhysicalBridge(
                        serviceEpoch = openingKey.serviceEpoch,
                        openingAttemptSequence = openingKey.openingAttemptSequence,
                        reason =
                            if (decision.action == Fold7InnerPresentationGate.Action.RELEASE_READY) {
                                "native-inner-presentation-ready"
                            } else {
                                "native-inner-presentation-timeout"
                            },
                    )

                Fold7DisplayStatusStore.update { current ->
                    current.copy(
                        bridge =
                            if (release?.getBoolean("ok", false) == true) {
                                Fold7DisplayStatus.Bridge.RELEASED
                            } else {
                                current.bridge
                            },
                        nativeInnerActive = topology().innerActive,
                        nativeInnerDefault = topology().innerIsDefault,
                    )
                }

                DuoDiagnostics.event(
                    "inner-wake-stage",
                    "HANDOFF_RELEASED presentation=${decision.action} " +
                        "serviceEpoch=${openingKey.serviceEpoch} " +
                        "openingAttempt=${openingKey.openingAttemptSequence} " +
                        "stableMs=${decision.stableForMs} elapsedMs=${decision.elapsedMs} " +
                        "ok=${release?.getBoolean("ok", false) == true} " +
                        "stale=${release?.getBoolean("stale", false) == true} " +
                        "active=${release?.getBoolean("active", false) == true}",
                )
            }
        }

        handler.post { check() }
    }

'''
    text = one(text, "    private fun beginPrewarm(\n", helper + "    private fun beginPrewarm(\n", "presentation release helper")

    text = one(
        text,
        '''    private fun isActive(display: Display): Boolean =\n        display.state != Display.STATE_OFF &&\n            display.state != Display.STATE_UNKNOWN\n\n''',
        '''    private fun isActive(display: Display): Boolean =\n        display.state != Display.STATE_OFF &&\n            display.state != Display.STATE_UNKNOWN\n\n    /** S1S: topology presence is weaker than renderability. */\n    private fun isPresentationReady(display: Display): Boolean =\n        display.isValid &&\n            display.state == Display.STATE_ON\n\n''',
        "presentation-ready helper",
    )

    text = one(
        text,
        '''        const val INNER_BRIDGE_HANDOFF_SETTLE_MS = 80L\n''',
        '''        // S1S supersedes the fixed 80 ms topology-only handoff.\n        const val INNER_PRESENTATION_STABLE_MS = 160L\n        const val INNER_PRESENTATION_MAX_HOLD_MS = 500L\n        const val INNER_PRESENTATION_POLL_MS = 24L\n''',
        "presentation handoff constants",
    )
    return text


def transform_panel_authority(text: str) -> str:
    if "terminal-native-cover-fence" in text:
        return text
    old = '''    fun beginPrepare(\n        owner: Owner,\n        intentSequence: Long,\n    ) {\n        require(recoveryReady)\n        require(owner.serviceEpoch == activeServiceEpoch)\n        require(intentSequence == lastIntentSequence)\n        this.owner = owner\n        physicalDisplayId = null\n        logicalDisplayId = null\n        physicalHeld = false\n        routeReady = false\n        phase = Phase.COVER_PREPARING\n    }\n'''
    new = '''    fun beginPrepare(\n        owner: Owner,\n        intentSequence: Long,\n    ): Boolean {\n        require(recoveryReady)\n        require(owner.serviceEpoch == activeServiceEpoch)\n        require(intentSequence == lastIntentSequence)\n\n        // S1S_BETA_CONVERGENCE_V1: NATIVE_COVER is terminal for a close\n        // cycle. A delayed same-service prepare must never resurrect the\n        // secondary route after Samsung owns the closed cover again.\n        if (phase == Phase.NATIVE_COVER) {\n            return false\n        }\n\n        this.owner = owner\n        physicalDisplayId = null\n        logicalDisplayId = null\n        physicalHeld = false\n        routeReady = false\n        phase = Phase.COVER_PREPARING\n        return true\n    }\n'''
    text = one(text, old, new, "terminal prepare fence")
    text = one(
        text,
        '''        if (intentSequence != lastIntentSequence) return\n        this.physicalDisplayId = physicalDisplayId?.takeIf { it >= 0L }\n''',
        '''        if (intentSequence != lastIntentSequence || phase != Phase.COVER_PREPARING) return\n        this.physicalDisplayId = physicalDisplayId?.takeIf { it >= 0L }\n''',
        "complete prepare phase fence",
    )
    return text


def transform_panel_authority_test(text: str) -> str:
    if "nativeCoverRejectsLatePrepareMutation" in text:
        return text
    test = r'''

    @Test
    fun nativeCoverRejectsLatePrepareMutation() {
        val m = Fold7PanelAuthorityGen4()
        m.completeRecovery(nativeCover = false)
        assertTrue(m.admit(100, 1).accepted)
        m.markNativeCover()
        assertTrue(m.admit(100, 2).accepted)

        val accepted =
            m.beginPrepare(
                Fold7PanelAuthorityGen4.Owner(100, 9, 12),
                2,
            )
        assertFalse(accepted)
        m.completePrepare(2, true, 222, 7, true)

        assertEquals(Fold7PanelAuthorityGen4.Phase.NATIVE_COVER, m.snapshot().phase)
        assertFalse(m.snapshot().routeReady)
        assertFalse(m.snapshot().physicalHeld)
        assertEquals(null, m.snapshot().owner)
    }
'''
    i = text.rfind("\n}")
    if i < 0:
        raise RuntimeError("panel authority test class end not found")
    return text[:i] + test + text[i:]


def transform_shell(text: str) -> str:
    if "terminal-native-cover-fence" in text:
        return text
    old = '''        gen4PanelAuthority.beginPrepare(\n            owner = owner,\n            intentSequence = intentSequence,\n        )\n\n        val physicalId = resolveFold7CoverPhysicalDisplayId(-1)\n'''
    new = '''        if (\n            !gen4PanelAuthority.beginPrepare(\n                owner = owner,\n                intentSequence = intentSequence,\n            )\n        ) {\n            return gen4PanelBundle(\n                operation = "prepare:$reason",\n                ok = false,\n                stale = true,\n                decision = "terminal-native-cover-fence",\n                error = "late secondary-route prepare rejected after NATIVE_COVER",\n            )\n        }\n\n        val physicalId = resolveFold7CoverPhysicalDisplayId(-1)\n'''
    return one(text, old, new, "shell terminal prepare fence")


def transform_panel(text: str) -> str:
    if "S1S_REFRESH_LEASE_V1" in text:
        return text

    text = one(
        text,
        '''    private var gen5FrameIntervalNs = 8_333_333L\n    private var gen5RefreshRoot: SurfaceControl? = null\n''',
        '''    private var gen5FrameIntervalNs = 8_333_333L\n    // S1S_REFRESH_LEASE_V1: SurfaceControl hint + WindowManager preference are\n    // scoped to the active visual attempt and measured from real vsync cadence.\n    private var gen5RefreshRoot: SurfaceControl? = null\n    private var gen5PreviousPreferredRefreshRate: Float? = null\n    private var gen5CadenceFrames = 0L\n''',
        "refresh lease fields",
    )

    text = one(
        text,
        '''                gen5LastChoreographerFrameNs = frameTimeNanos\n\n                val nowNs = frameTimeNanos + gen5FrameClockOffsetNs\n''',
        '''                gen5LastChoreographerFrameNs = frameTimeNanos\n                gen5CadenceFrames++\n\n                val nowNs = frameTimeNanos + gen5FrameClockOffsetNs\n''',
        "cadence counter",
    )
    text = one(
        text,
        '''                            "frameIntervalNs=$gen5FrameIntervalNs clock=vsync-calibrated " +\n                            "requestedHz=$GEN5_REQUESTED_HZ effectiveHz=$effectiveHz",\n''',
        '''                            "frameIntervalNs=$gen5FrameIntervalNs clock=vsync-calibrated " +\n                            "cadenceHz=${"%.1f".format(1_000_000_000.0 / gen5FrameIntervalNs)} " +\n                            "lease=${refreshLeaseClassification()} " +\n                            "requestedHz=$GEN5_REQUESTED_HZ effectiveHz=$effectiveHz",\n''',
        "refresh cadence telemetry",
    )
    text = one(
        text,
        '''        gen5FrameIntervalNs = 8_333_333L\n        clearGen5RefreshRate()\n''',
        '''        gen5FrameIntervalNs = 8_333_333L\n        gen5CadenceFrames = 0L\n        clearGen5RefreshRate()\n''',
        "clear cadence reset",
    )

    old_request = '''            runCatching {\n                SurfaceControl.Transaction()\n                    .setFrameRate(\n                        root,\n                        GEN5_REQUESTED_HZ,\n                        Surface.FRAME_RATE_COMPATIBILITY_DEFAULT,\n                        Surface.CHANGE_FRAME_RATE_ONLY_IF_SEAMLESS,\n                    )\n                    .apply()\n                gen5RefreshRoot = root\n            }.onSuccess {\n                com.duoopen.debug.DuoDiagnostics.event(\n                    "gen5-refresh",\n                    "requested=$GEN5_REQUESTED_HZ seamlessOnly=true " +\n                        "effective=${display.mode.refreshRate} supported=[$supported]",\n                )\n            }.onFailure {\n'''
    new_request = '''            runCatching {\n                val lp = snapshot.view.layoutParams as? WindowManager.LayoutParams\n                if (lp != null) {\n                    if (gen5PreviousPreferredRefreshRate == null) {\n                        gen5PreviousPreferredRefreshRate = lp.preferredRefreshRate\n                    }\n                    lp.preferredRefreshRate = GEN5_REQUESTED_HZ\n                    windowManager.updateViewLayout(snapshot.view, lp)\n                }\n\n                SurfaceControl.Transaction()\n                    .setFrameRate(\n                        root,\n                        GEN5_REQUESTED_HZ,\n                        Surface.FRAME_RATE_COMPATIBILITY_DEFAULT,\n                        Surface.CHANGE_FRAME_RATE_ONLY_IF_SEAMLESS,\n                    )\n                    .apply()\n                gen5RefreshRoot = root\n            }.onSuccess {\n                com.duoopen.debug.DuoDiagnostics.event(\n                    "gen5-refresh",\n                    "requested=$GEN5_REQUESTED_HZ seamlessOnly=true windowPreferred=true " +\n                        "effective=${display.mode.refreshRate} supported=[$supported]",\n                )\n            }.onFailure {\n'''
    text = one(text, old_request, new_request, "refresh dual lease")

    old_clear = '''    private fun clearGen5RefreshRate() {\n        val root = gen5RefreshRoot ?: return\n        gen5RefreshRoot = null\n        runCatching {\n            SurfaceControl.Transaction()\n                .setFrameRate(\n                    root,\n                    0f,\n                    Surface.FRAME_RATE_COMPATIBILITY_DEFAULT,\n                    Surface.CHANGE_FRAME_RATE_ONLY_IF_SEAMLESS,\n                )\n                .apply()\n        }\n        com.duoopen.debug.DuoDiagnostics.event(\n            "gen5-refresh",\n            "cleared requestedHz=$GEN5_REQUESTED_HZ effective=${runCatching { display.mode.refreshRate }.getOrNull()}",\n        )\n    }\n'''
    new_clear = '''    private fun refreshLeaseClassification(): String {\n        val cadenceHz = 1_000_000_000.0 / gen5FrameIntervalNs.coerceAtLeast(1L)\n        return when {\n            cadenceHz >= 100.0 -> "HONORED_HIGH"\n            cadenceHz >= 75.0 -> "INTERMEDIATE"\n            else -> "FALLBACK_60_CLASS"\n        }\n    }\n\n    private fun clearGen5RefreshRate() {\n        val root = gen5RefreshRoot\n        gen5RefreshRoot = null\n        if (root != null) {\n            runCatching {\n                SurfaceControl.Transaction()\n                    .setFrameRate(\n                        root,\n                        0f,\n                        Surface.FRAME_RATE_COMPATIBILITY_DEFAULT,\n                        Surface.CHANGE_FRAME_RATE_ONLY_IF_SEAMLESS,\n                    )\n                    .apply()\n            }\n        }\n\n        val previous = gen5PreviousPreferredRefreshRate\n        gen5PreviousPreferredRefreshRate = null\n        val snapshotView = (surface as? SnapshotSurface)?.view\n        if (previous != null && snapshotView != null) {\n            runCatching {\n                val lp = snapshotView.layoutParams as? WindowManager.LayoutParams\n                if (lp != null) {\n                    lp.preferredRefreshRate = previous\n                    windowManager.updateViewLayout(snapshotView, lp)\n                }\n            }\n        }\n\n        com.duoopen.debug.DuoDiagnostics.event(\n            "gen5-refresh",\n            "cleared requestedHz=$GEN5_REQUESTED_HZ cadenceFrames=$gen5CadenceFrames " +\n                "classification=${refreshLeaseClassification()} " +\n                "effective=${runCatching { display.mode.refreshRate }.getOrNull()}",\n        )\n    }\n'''
    text = one(text, old_clear, new_clear, "refresh lease clear and classify")
    return text


def transform_exporter(text: str) -> str:
    if "betaConvergence=S1S_BETA_CONVERGENCE_V1" in text:
        return text
    anchor = '''                        appendLine(\n                            "hingeReacquisitionTriggers=OPENING_EDGE,DISPLAY_CHANGE,WALLPAPER_RETURN,WATCHDOG"\n                        )\n'''
    addition = anchor + '''                        appendLine(\n                            "betaConvergence=S1S_BETA_CONVERGENCE_V1"\n                        )\n                        appendLine(\n                            "coarseAnglePolicy=ENDPOINT_ONLY_MIDPOINT_SUPPRESSED"\n                        )\n                        appendLine(\n                            "innerHandoff=DEFAULT_PLUS_STATE_ON_STABLE_160MS_MAX_500MS"\n                        )\n                        appendLine(\n                            "terminalCoverFence=DAEMON_NATIVE_COVER_PREPARE_REJECT"\n                        )\n                        appendLine(\n                            "refreshLease=SURFACECONTROL_SEAMLESS_PLUS_WINDOW_PREFERRED_MEASURED"\n                        )\n                        appendLine(\n                            "diagnosticArtifactTruth=FINAL_APK_DEX_VERIFIER"\n                        )\n'''
    return one(text, anchor, addition, "S1S exporter markers")


def validate(g, a, at, hs, cr, co, pg, pgt, pa, pat, sh, p, e):
    required = (
        (g, ['versionCode = 53', 'versionName = "5.1.0-beta2-zfold7-s1s"']),
        (a, ["suppressedCoarseMidpoint", "coarse-midpoint-suppressed", "COARSE_ENDPOINT_MAX_DEG = 12f"]),
        (at, ["coarseMidpointCannotTakeSemanticAuthority", "coarseEndpointMayOnlyPromoteAsCanonicalRest"]),
        (hs, ["coarse-suppressed", "coarseMidSuppressed="]),
        (cr, ["coverPresentationReady"]),
        (co, ["S1S_PRESENTATION_READY_HANDOFF", "isPresentationReady", "INNER_PRESENTATION_STABLE_MS = 160L"]),
        (pg, [MARKER, "RELEASE_READY", "RELEASE_TIMEOUT"]),
        (pgt, ["readyMustRemainStableBeforeRelease", "timeoutIsBounded"]),
        (pa, ["terminal-native-cover-fence", "phase != Phase.COVER_PREPARING"]),
        (pat, ["nativeCoverRejectsLatePrepareMutation"]),
        (sh, ["terminal-native-cover-fence", "late secondary-route prepare rejected"]),
        (p, ["S1S_REFRESH_LEASE_V1", "preferredRefreshRate = GEN5_REQUESTED_HZ", "refreshLeaseClassification"]),
        (e, ["betaConvergence=S1S_BETA_CONVERGENCE_V1", "FINAL_APK_DEX_VERIFIER"]),
    )
    for text, needles in required:
        for needle in needles:
            if needle not in text:
                raise RuntimeError("missing S1S invariant: " + needle)

    combined = "\n".join((a, co, pa, sh, p, e))
    for prohibited in (
        "cmd device_state state 5",
        "scheduleConcurrentOuterRouteProbe",
        "PROBE_CONCURRENT_OUTER_DEFAULT",
    ):
        if prohibited in combined:
            raise RuntimeError("S1S must not reintroduce unsafe DeviceState route override: " + prohibited)


def apply(repo: Path, check: bool) -> None:
    existing = (
        GRADLE, AUTHORITY, AUTHORITY_TEST, HINGE_SOURCE, COVER_READINESS,
        COORDINATOR, PANEL_AUTHORITY, PANEL_AUTHORITY_TEST, SHELL, PANEL, EXPORTER,
    )
    for rel in existing:
        if not (repo / rel).exists():
            raise RuntimeError("missing " + str(rel))

    g = transform_gradle((repo / GRADLE).read_text(encoding="utf-8"))
    a = transform_authority((repo / AUTHORITY).read_text(encoding="utf-8"))
    at = transform_authority_test((repo / AUTHORITY_TEST).read_text(encoding="utf-8"))
    hs = transform_hinge_source((repo / HINGE_SOURCE).read_text(encoding="utf-8"))
    cr = transform_cover_readiness((repo / COVER_READINESS).read_text(encoding="utf-8"))
    co = transform_coordinator((repo / COORDINATOR).read_text(encoding="utf-8"))
    pa = transform_panel_authority((repo / PANEL_AUTHORITY).read_text(encoding="utf-8"))
    pat = transform_panel_authority_test((repo / PANEL_AUTHORITY_TEST).read_text(encoding="utf-8"))
    sh = transform_shell((repo / SHELL).read_text(encoding="utf-8"))
    p = transform_panel((repo / PANEL).read_text(encoding="utf-8"))
    e = transform_exporter((repo / EXPORTER).read_text(encoding="utf-8"))
    pg = PRESENT_GATE_SOURCE
    pgt = PRESENT_GATE_TEST_SOURCE

    validate(g, a, at, hs, cr, co, pg, pgt, pa, pat, sh, p, e)

    if not check:
        for rel, output in (
            (GRADLE, g), (AUTHORITY, a), (AUTHORITY_TEST, at), (HINGE_SOURCE, hs),
            (COVER_READINESS, cr), (COORDINATOR, co), (PANEL_AUTHORITY, pa),
            (PANEL_AUTHORITY_TEST, pat), (SHELL, sh), (PANEL, p), (EXPORTER, e),
            (PRESENT_GATE, pg), (PRESENT_GATE_TEST, pgt),
        ):
            rel_path = repo / rel
            rel_path.parent.mkdir(parents=True, exist_ok=True)
            rel_path.write_text(output, encoding="utf-8")


def self_test() -> None:
    sample = '        versionCode = 52\n        versionName = "5.1.0-beta2-zfold7-s1r"\n'
    out = transform_gradle(sample)
    assert "versionCode = 53" in out
    assert "zfold7-s1s" in out
    assert "RELEASE_TIMEOUT" in PRESENT_GATE_SOURCE
    assert "coarse-midpoint-suppressed" in transform_authority(
        ("data class Snapshot(\n        val droppedSequencePrecise: Long,\n    )\n"
         "    private var droppedSequencePrecise = 0L\n"
         "            droppedSequencePrecise = droppedSequencePrecise,\n        )\n"
         "        val sourceChanged = currentSource != candidate.source\n"
         "        val changed =\n            currentAngle.isNaN() ||\n                abs(candidate.angle - currentAngle) >= CHANGE_EPSILON_DEG ||\n                sourceChanged\n\n"
         "        currentAngle = candidate.angle\n        currentSource = candidate.source\n        currentObservedUptimeMs = candidate.observedUptimeMs\n        currentCoarse = candidate.coarse\n        publicCandidate = null\n"
         "        const val DEFAULT_PUBLIC_MAX_AGE_MS = 3_000L\n        private const val CHANGE_EPSILON_DEG = 0.10f\n")
    )
    print("S1S beta convergence transformer self-test: PASS")


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
    print("S1S beta convergence: " + ("source shape verified" if args.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
