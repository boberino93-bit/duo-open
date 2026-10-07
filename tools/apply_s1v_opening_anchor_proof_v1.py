#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

GRADLE = Path("app/build.gradle.kts")
PANEL = Path("app/src/full/java/com/duoopen/overlay/PanelEngine.kt")
SURFACE = Path("app/src/full/java/com/duoopen/overlay/FoldSurface.kt")
COMPOSER = Path("app/src/full/java/com/duoopen/overlay/Fold7RightPaneComposer.kt")
GATE = Path("app/src/full/java/com/duoopen/overlay/Fold7OpeningAnchorProofGate.kt")
GATE_TEST = Path("app/src/test/java/com/duoopen/overlay/Fold7OpeningAnchorProofGateTest.kt")

MARKER = "S1V_OPENING_ANCHOR_PROOF_V1"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    i = text.find(start)
    if i < 0:
        raise RuntimeError(f"{label}: start anchor missing")
    j = text.find(end, i + len(start))
    if j < 0:
        raise RuntimeError(f"{label}: end anchor missing")
    return text[:i] + replacement + text[j:]


def transform_gradle(text: str) -> str:
    if 'versionName = "5.1.0-beta2-zfold7-s1v-anchor"' in text:
        return text
    text = one(text, "        versionCode = 55\n", "        versionCode = 56\n", "versionCode")
    return one(
        text,
        '        versionName = "5.1.0-beta2-zfold7-s1u"\n',
        '        versionName = "5.1.0-beta2-zfold7-s1v-anchor"\n',
        "versionName",
    )


def transform_surface(text: str) -> str:
    if "copySnapshotForAnchor" in text:
        return text

    text = one(
        text,
        '''    val view = FoldOverlayView(context, bitmap, foldLine).also { it.config = config }\n    val attached: Boolean\n''',
        '''    val view = FoldOverlayView(context, bitmap, foldLine).also { it.config = config }\n    // S1V_OPENING_ANCHOR_PROOF_V1: retain the exact pixels currently owned by\n    // this surface so the opening handoff can copy them before Samsung remaps\n    // the logical display. The copy becomes independent continuity authority.\n    private var anchorSnapshot: Bitmap = bitmap\n    val attached: Boolean\n''',
        "snapshot anchor field",
    )

    text = one(
        text,
        '''    /** Swap a stale bridging picture for the fresh capture, keeping the current tilt. */\n    fun replaceSnapshot(bitmap: Bitmap) = view.setSnapshot(bitmap)\n''',
        '''    /** Swap a stale bridging picture for the fresh capture, keeping the current tilt. */\n    fun replaceSnapshot(bitmap: Bitmap) {\n        anchorSnapshot = bitmap\n        view.setSnapshot(bitmap)\n    }\n\n    /** Own a software copy that survives detaching this window during cover -> inner remap. */\n    fun copySnapshotForAnchor(): Bitmap? =\n        if (anchorSnapshot.isRecycled) {\n            null\n        } else {\n            runCatching { anchorSnapshot.copy(Bitmap.Config.ARGB_8888, false) }.getOrNull()\n        }\n''',
        "snapshot anchor copy",
    )
    return text


def transform_composer(text: str) -> str:
    if "toInnerRightPane" in text:
        return text

    text = one(
        text,
        "import android.graphics.Canvas\n",
        "import android.graphics.Canvas\nimport android.graphics.Color\n",
        "composer color import",
    )

    insert = r'''

    /**
     * S1V_OPENING_ANCHOR_PROOF_V1
     * Exact inverse registration for the physical opening proof: preserve the
     * 1080x2520 cover pixels and place them, unwarped, into the canonical
     * 936x2184 inner right pane. The unused inner area is deterministic black
     * so a physical test cannot mistake native content for the held frame.
     */
    fun toInnerRightPane(source: Bitmap): Bitmap? {
        if (source.width < COVER_WIDTH || source.height < COVER_HEIGHT) return null

        val result = Bitmap.createBitmap(
            INNER_WIDTH,
            INNER_HEIGHT,
            Bitmap.Config.ARGB_8888,
        )
        val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
        val canvas = Canvas(result)
        canvas.drawColor(Color.BLACK)
        canvas.drawBitmap(
            source,
            Rect(0, 0, COVER_WIDTH, COVER_HEIGHT),
            Rect(RIGHT_PANE_LEFT, 0, RIGHT_PANE_RIGHT, INNER_HEIGHT),
            paint,
        )
        return result
    }
'''
    i = text.rfind("\n}")
    if i < 0:
        raise RuntimeError("composer class end missing")
    return text[:i] + insert + text[i:]


GATE_SOURCE = r'''package com.duoopen.overlay

/**
 * S1V_OPENING_ANCHOR_PROOF_V1
 *
 * App-side proof gate only. PRESENTED means the anchor window has produced a
 * draw, remains attached and laid out on Fold7 inner geometry, and Android now
 * reports the destination display STATE_ON. Physical Fold7 observation remains
 * the final authority; this gate deliberately does not claim photon-level proof.
 */
internal class Fold7OpeningAnchorProofGate(
    private val maxWaitMs: Long = 6_500L,
) {
    enum class Action { WAIT, PRESENTED, TIMEOUT }

    data class Decision(
        val action: Action,
        val elapsedMs: Long,
        val reason: String,
    )

    private var startedAtMs = Long.MIN_VALUE

    fun begin(nowMs: Long) {
        startedAtMs = nowMs
    }

    fun evaluate(
        nowMs: Long,
        drawSeen: Boolean,
        attached: Boolean,
        laidOut: Boolean,
        innerGeometry: Boolean,
        displayOn: Boolean,
    ): Decision {
        if (startedAtMs == Long.MIN_VALUE) begin(nowMs)
        val elapsed = (nowMs - startedAtMs).coerceAtLeast(0L)

        if (drawSeen && attached && laidOut && innerGeometry && displayOn) {
            return Decision(Action.PRESENTED, elapsed, "draw+attached+inner+display-on")
        }
        if (elapsed >= maxWaitMs) {
            return Decision(Action.TIMEOUT, elapsed, "anchor-proof-timeout")
        }
        return Decision(Action.WAIT, elapsed, "awaiting-presentation-evidence")
    }
}
'''


GATE_TEST_SOURCE = r'''package com.duoopen.overlay

import org.junit.Assert.assertEquals
import org.junit.Test

class Fold7OpeningAnchorProofGateTest {
    @Test
    fun internalObjectStateAloneIsNotPresentationProof() {
        val g = Fold7OpeningAnchorProofGate(maxWaitMs = 6_500L)
        g.begin(1_000L)
        assertEquals(
            Fold7OpeningAnchorProofGate.Action.WAIT,
            g.evaluate(
                nowMs = 1_100L,
                drawSeen = false,
                attached = true,
                laidOut = true,
                innerGeometry = true,
                displayOn = true,
            ).action,
        )
    }

    @Test
    fun drawWithoutPhysicalDestinationOnStillWaits() {
        val g = Fold7OpeningAnchorProofGate(maxWaitMs = 6_500L)
        g.begin(1_000L)
        assertEquals(
            Fold7OpeningAnchorProofGate.Action.WAIT,
            g.evaluate(1_200L, true, true, true, true, false).action,
        )
    }

    @Test
    fun allAppSidePresentationEvidenceAdmitsHold() {
        val g = Fold7OpeningAnchorProofGate(maxWaitMs = 6_500L)
        g.begin(1_000L)
        assertEquals(
            Fold7OpeningAnchorProofGate.Action.PRESENTED,
            g.evaluate(1_240L, true, true, true, true, true).action,
        )
    }

    @Test
    fun waitIsBoundedByObservedSamsungWindow() {
        val g = Fold7OpeningAnchorProofGate(maxWaitMs = 6_500L)
        g.begin(1_000L)
        assertEquals(
            Fold7OpeningAnchorProofGate.Action.WAIT,
            g.evaluate(7_499L, false, true, true, true, false).action,
        )
        assertEquals(
            Fold7OpeningAnchorProofGate.Action.TIMEOUT,
            g.evaluate(7_500L, false, true, true, true, false).action,
        )
    }
}
'''


def transform_panel(text: str) -> str:
    if MARKER in text:
        return text

    text = one(
        text,
        '''    private var openingRemapHandoffSequence = 0L\n    private var openingRemapInnerSurfaceReady = false\n''',
        '''    private var openingRemapHandoffSequence = 0L\n    private var openingRemapInnerSurfaceReady = false\n\n    // S1V_OPENING_ANCHOR_PROOF_V1: animation is intentionally disabled for\n    // this candidate. A copied cover frame is the sole visual authority until\n    // it is visibly held on the inner presentation path or the proof times out.\n    private var openingAnchorProofBitmap: Bitmap? = null\n    private var openingAnchorProofGate: Fold7OpeningAnchorProofGate? = null\n    private var openingAnchorProofDrawSeen = false\n''',
        "anchor proof fields",
    )

    old_owner = '''        if (!owned) {\n            if (continuityOpeningVisual) {\n                val transferToInner =\n                    Fold7OpeningRemapHandoffPolicy.shouldTransferToInner(\n                        openingVisualActive = continuityOpeningVisual,\n                        previousCoverOwned = previousCoverOwned,\n                        coverGeometryNow = isFold7CoverGeometryNow(),\n                        innerGeometryNow = isFold7InnerGeometryNow(),\n                        privilegedCaptureReady = ShizukuBridge.ready,\n                    )\n\n                if (transferToInner) {\n                    handoffContinuityOpeningToInner(\n                        "owner-remap:$reason"\n                    )\n                } else {\n                    endContinuityOpeningVisual(\n                        "owner-released:$reason"\n                    )\n                }\n            }\n            return\n        }\n'''
    new_owner = '''        if (!owned) {\n            if (continuityOpeningVisual && previousCoverOwned) {\n                // S1V starts the handoff BEFORE requiring inner geometry. S1K\n                // required geometry to already be inner at this exact boundary,\n                // which could discard the only authoritative cover frame.\n                handoffContinuityOpeningToInner(\n                    "owner-released:$reason"\n                )\n            } else if (continuityOpeningVisual) {\n                endContinuityOpeningVisual(\n                    "owner-released-without-cover-owner:$reason"\n                )\n            }\n            return\n        }\n'''
    text = one(text, old_owner, new_owner, "owner release starts two-phase anchor")

    text = one(
        text,
        '''        openingRemapHandoffSequence++\n        openingRemapInnerSurfaceReady = false\n        continuityOpeningVisual = true\n''',
        '''        abortOpeningAnchorProof("new-opening")\n        openingRemapHandoffSequence++\n        openingRemapInnerSurfaceReady = false\n        continuityOpeningVisual = true\n''',
        "new opening aborts stale anchor",
    )

    text = between(
        text,
        "        recycleGen5OpeningBitmap()\n",
        "    fun endContinuityOpeningVisual(\n",
        '''        recycleGen5OpeningBitmap()\n        // S1V diagnostic source policy: capture the actual cover display now.\n        // Do not synthesize the opening from a cached INNER crop. If capture is\n        // late, the handoff still has the current SnapshotSurface or cover cache\n        // as explicit fallback sources.\n        startEffect(\n            afterSwap = false,\n            startTilt = COVER_OPEN_IMMEDIATE_TILT,\n        )\n        com.duoopen.debug.DuoDiagnostics.event(\n            "opening-anchor-proof",\n            "SOURCE_ARMED display=$displayId reason=$reason source=current-cover-capture animation=disabled",\n        )\n    }\n\n''',
        "opening source policy",
    )

    start = "    private fun handoffContinuityOpeningToInner(\n"
    end = "    private fun openingRemapHandoffTilt(): Float {\n"
    replacement = r'''    // S1V_OPENING_ANCHOR_PROOF_V1
    // Phase 1: copy the cover pixels while they are still authoritative.
    // Phase 2: wait for Samsung to publish inner geometry, then instantiate
    // those SAME pixels on a new inner window. No new INNER capture participates.
    private fun handoffContinuityOpeningToInner(
        reason: String,
    ) {
        val sequence = ++openingRemapHandoffSequence
        val startedUptimeMs = SystemClock.uptimeMillis()

        val liveSurfaceCopy =
            (surface as? SnapshotSurface)?.copySnapshotForAnchor()
        val ownedOpeningCopy =
            if (liveSurfaceCopy == null) {
                gen5OwnedOpeningBitmap
                    ?.takeIf { !it.isRecycled }
                    ?.let { runCatching { it.copy(Bitmap.Config.ARGB_8888, false) }.getOrNull() }
            } else {
                null
            }
        val cachedCoverCopy =
            if (liveSurfaceCopy == null && ownedOpeningCopy == null) {
                cache.get(
                    innerPanel = false,
                    width = Fold7RightPaneComposer.COVER_WIDTH,
                    height = Fold7RightPaneComposer.COVER_HEIGHT,
                )
                    ?.takeIf { !it.isRecycled }
                    ?.let { runCatching { it.copy(Bitmap.Config.ARGB_8888, false) }.getOrNull() }
            } else {
                null
            }
        val coverFrame = liveSurfaceCopy ?: ownedOpeningCopy ?: cachedCoverCopy

        val source = when {
            liveSurfaceCopy != null -> "visible-cover-surface"
            ownedOpeningCopy != null -> "owned-opening-bitmap"
            cachedCoverCopy != null -> "cover-cache"
            else -> "none"
        }

        val innerAnchor =
            coverFrame?.let(Fold7RightPaneComposer::toInnerRightPane)
        coverFrame?.let {
            if (!it.isRecycled) runCatching { it.recycle() }
        }

        if (innerAnchor == null) {
            continuityOpeningVisual = false
            stopGen5OpeningClock()
            captureGen++
            if (surface != null) removeOverlay()
            restArmed = true
            panelSwitched = false
            recycleGen5OpeningBitmap()
            com.duoopen.debug.DuoDiagnostics.event(
                "opening-anchor-proof",
                "ABORT sequence=$sequence stage=source reason=no-cover-frame source=$source trigger=$reason",
            )
            return
        }

        continuityOpeningVisual = false
        stopGen5OpeningClock()
        captureGen++
        openingRemapInnerSurfaceReady = false
        openingAnchorProofDrawSeen = false
        openingAnchorProofBitmap?.let {
            if (!it.isRecycled) runCatching { it.recycle() }
        }
        openingAnchorProofBitmap = innerAnchor
        openingAnchorProofGate =
            Fold7OpeningAnchorProofGate(ANCHOR_PROOF_MAX_WAIT_MS).also {
                it.begin(startedUptimeMs)
            }

        com.duoopen.debug.DuoDiagnostics.event(
            "opening-anchor-proof",
            "CAPTURED sequence=$sequence source=$source trigger=$reason " +
                "cover=${Fold7RightPaneComposer.COVER_WIDTH}x${Fold7RightPaneComposer.COVER_HEIGHT} " +
                "target=${Fold7RightPaneComposer.RIGHT_PANE_LEFT}..${Fold7RightPaneComposer.RIGHT_PANE_RIGHT}",
        )

        waitForOpeningAnchorInnerGeometry(
            sequence = sequence,
            startedUptimeMs = startedUptimeMs,
            reason = reason,
        )
    }

    private fun waitForOpeningAnchorInnerGeometry(
        sequence: Long,
        startedUptimeMs: Long,
        reason: String,
    ) {
        if (sequence != openingRemapHandoffSequence || openingAnchorProofBitmap == null) return

        val elapsed = SystemClock.uptimeMillis() - startedUptimeMs
        if (isFold7InnerGeometryNow()) {
            attachOpeningAnchorProof(sequence, startedUptimeMs, reason)
            return
        }

        if (elapsed >= ANCHOR_PROOF_MAX_WAIT_MS) {
            com.duoopen.debug.DuoDiagnostics.event(
                "opening-anchor-proof",
                "TIMEOUT sequence=$sequence stage=inner-geometry elapsedMs=$elapsed trigger=$reason",
            )
            releaseOpeningAnchorProof(sequence, "inner-geometry-timeout")
            return
        }

        handler.postDelayed(
            {
                waitForOpeningAnchorInnerGeometry(
                    sequence = sequence,
                    startedUptimeMs = startedUptimeMs,
                    reason = reason,
                )
            },
            ANCHOR_PROOF_POLL_MS,
        )
    }

    private fun attachOpeningAnchorProof(
        sequence: Long,
        startedUptimeMs: Long,
        reason: String,
    ) {
        if (sequence != openingRemapHandoffSequence) return
        val bitmap = openingAnchorProofBitmap ?: return

        if (surface != null) removeOverlay()
        recycleGen5OpeningBitmap()

        innerPanel = true
        restArmed = false
        panelSwitched = false
        timedResolve = true
        follower?.cancel()
        follower = null

        val config = DuoSettings.config.value
        val foldLine =
            { w: Float, h: Float, c: com.duoopen.settings.DuoConfig ->
                DuoShader.foldFor(true, w, h, c)
            }
        val created =
            SnapshotSurface(
                service,
                windowManager,
                bitmap,
                config,
                foldLine,
            )

        if (!created.attached) {
            created.detach()
            com.duoopen.debug.DuoDiagnostics.event(
                "opening-anchor-proof",
                "ABORT sequence=$sequence stage=attach trigger=$reason",
            )
            releaseOpeningAnchorProof(sequence, "attach-failed")
            return
        }

        created.tilt = 0f
        surface = created
        phase = Phase.SHOWING
        onShowingChanged()

        created.view.viewTreeObserver.addOnDrawListener(
            object : android.view.ViewTreeObserver.OnDrawListener {
                override fun onDraw() {
                    if (sequence != openingRemapHandoffSequence) return
                    if (!openingAnchorProofDrawSeen) {
                        openingAnchorProofDrawSeen = true
                        com.duoopen.debug.DuoDiagnostics.event(
                            "opening-anchor-proof",
                            "DRAW sequence=$sequence display=$displayId " +
                                "size=${created.view.width}x${created.view.height} state=${display.state}",
                        )
                    }
                }
            },
        )
        created.view.invalidate()

        com.duoopen.debug.DuoDiagnostics.event(
            "opening-anchor-proof",
            "ATTACHED sequence=$sequence elapsedMs=${SystemClock.uptimeMillis() - startedUptimeMs} " +
                "display=$displayId state=${display.state} trigger=$reason",
        )

        checkOpeningAnchorPresentation(
            sequence = sequence,
            startedUptimeMs = startedUptimeMs,
            reason = reason,
        )
    }

    private fun checkOpeningAnchorPresentation(
        sequence: Long,
        startedUptimeMs: Long,
        reason: String,
    ) {
        if (
            sequence != openingRemapHandoffSequence ||
            openingAnchorProofBitmap == null ||
            openingRemapInnerSurfaceReady
        ) {
            return
        }

        val snapshot = surface as? SnapshotSurface
        val now = SystemClock.uptimeMillis()
        val gate = openingAnchorProofGate ?: return
        val decision =
            gate.evaluate(
                nowMs = now,
                drawSeen = openingAnchorProofDrawSeen,
                attached = snapshot?.view?.isAttachedToWindow == true,
                laidOut = snapshot?.view?.width?.let { it > 0 } == true &&
                    snapshot.view.height > 0,
                innerGeometry = isFold7InnerGeometryNow(),
                displayOn = display.state == Display.STATE_ON,
            )

        if (decision.action == Fold7OpeningAnchorProofGate.Action.PRESENTED) {
            openingRemapInnerSurfaceReady = true
            com.duoopen.debug.DuoDiagnostics.event(
                "opening-anchor-proof",
                "PRESENTED sequence=$sequence evidence=${decision.reason} " +
                    "elapsedMs=${decision.elapsedMs} holdMs=$ANCHOR_PROOF_VISIBLE_HOLD_MS trigger=$reason",
            )
            handler.postDelayed(
                {
                    releaseOpeningAnchorProof(sequence, "visible-hold-complete")
                },
                ANCHOR_PROOF_VISIBLE_HOLD_MS,
            )
            return
        }

        if (decision.action == Fold7OpeningAnchorProofGate.Action.TIMEOUT) {
            com.duoopen.debug.DuoDiagnostics.event(
                "opening-anchor-proof",
                "TIMEOUT sequence=$sequence stage=presentation elapsedMs=${decision.elapsedMs} " +
                    "draw=$openingAnchorProofDrawSeen state=${display.state} trigger=$reason",
            )
            releaseOpeningAnchorProof(sequence, "presentation-timeout")
            return
        }

        handler.postDelayed(
            {
                checkOpeningAnchorPresentation(
                    sequence = sequence,
                    startedUptimeMs = startedUptimeMs,
                    reason = reason,
                )
            },
            ANCHOR_PROOF_POLL_MS,
        )
    }

    private fun releaseOpeningAnchorProof(
        sequence: Long,
        reason: String,
    ) {
        if (sequence != openingRemapHandoffSequence) return
        val bitmap = openingAnchorProofBitmap
        openingAnchorProofBitmap = null
        openingAnchorProofGate = null
        openingAnchorProofDrawSeen = false
        openingRemapInnerSurfaceReady = false

        if (surface != null) removeOverlay()
        if (bitmap != null && !bitmap.isRecycled) {
            runCatching { bitmap.recycle() }
        }
        recycleGen5OpeningBitmap()
        phase = Phase.IDLE
        restArmed = true
        panelSwitched = false

        com.duoopen.debug.DuoDiagnostics.event(
            "opening-anchor-proof",
            "RELEASE sequence=$sequence reason=$reason display=$displayId state=${display.state}",
        )
    }

    private fun abortOpeningAnchorProof(reason: String) {
        if (openingAnchorProofBitmap == null && openingAnchorProofGate == null) return
        val sequence = openingRemapHandoffSequence
        val bitmap = openingAnchorProofBitmap
        openingAnchorProofBitmap = null
        openingAnchorProofGate = null
        openingAnchorProofDrawSeen = false
        openingRemapInnerSurfaceReady = false
        if (surface != null) removeOverlay()
        if (bitmap != null && !bitmap.isRecycled) {
            runCatching { bitmap.recycle() }
        }
        recycleGen5OpeningBitmap()
        com.duoopen.debug.DuoDiagnostics.event(
            "opening-anchor-proof",
            "ABORT sequence=$sequence stage=cancel reason=$reason",
        )
    }

'''
    text = between(text, start, end, replacement, "replace S1K remap with anchor proof")

    text = one(
        text,
        '''    fun onHinge(\n        angle: Float,\n        observedUptimeMs: Long = SystemClock.uptimeMillis(),\n    ) {\n''',
        '''    fun onHinge(\n        angle: Float,\n        observedUptimeMs: Long = SystemClock.uptimeMillis(),\n    ) {\n        if (openingAnchorProofBitmap != null) {\n            lastRawHingeAngle = angle\n            lastHingeMoveMs = SystemClock.uptimeMillis()\n            return\n        }\n''',
        "freeze hinge during anchor proof",
    )

    text = one(
        text,
        '''    fun evaluate() {\n        if (demoRunning) return\n''',
        '''    fun evaluate() {\n        if (openingAnchorProofBitmap != null) return\n        if (demoRunning) return\n''',
        "freeze evaluate during anchor proof",
    )

    text = one(
        text,
        '''            startGen5OpeningFrameLoop()\n            (created as? SnapshotSurface)?.let(::requestGen5RefreshRate)\n''',
        '''            // S1V diagnostic: no hinge animation or refresh-rate lease.\n            // The cover frame must remain motionless so physical anchoring is binary.\n            com.duoopen.debug.DuoDiagnostics.event(\n                "opening-anchor-proof",\n                "COVER_STATIC display=$displayId animation=disabled",\n            )\n''',
        "disable Gen5 animation for proof build",
    )

    text = one(
        text,
        '''    fun destroy() {\n        openingRemapHandoffSequence++\n        openingRemapInnerSurfaceReady = false\n        captureGen++ // orphan any capture in flight\n''',
        '''    fun destroy() {\n        abortOpeningAnchorProof("destroy")\n        openingRemapHandoffSequence++\n        openingRemapInnerSurfaceReady = false\n        captureGen++ // orphan any capture in flight\n''',
        "destroy aborts anchor proof",
    )

    text = one(
        text,
        '''        const val OPENING_REMAP_CAPTURE_MAX_AGE_MS = 450L\n        const val GEN5_REQUESTED_HZ = 120f\n''',
        '''        const val OPENING_REMAP_CAPTURE_MAX_AGE_MS = 450L\n        const val ANCHOR_PROOF_MAX_WAIT_MS = 6_500L\n        const val ANCHOR_PROOF_POLL_MS = 24L\n        const val ANCHOR_PROOF_VISIBLE_HOLD_MS = 900L\n        const val GEN5_REQUESTED_HZ = 120f\n''',
        "anchor proof constants",
    )

    return text


def validate(gradle: str, panel: str, surface: str, composer: str, gate: str, gate_test: str) -> None:
    required = (
        (gradle, ['versionCode = 56', 'versionName = "5.1.0-beta2-zfold7-s1v-anchor"']),
        (surface, ["copySnapshotForAnchor", "anchorSnapshot"]),
        (composer, ["toInnerRightPane", "RIGHT_PANE_LEFT", "canvas.drawColor(Color.BLACK)"]),
        (panel, [MARKER, "openingAnchorProofBitmap", "CAPTURED sequence=", "ATTACHED sequence=", "PRESENTED sequence=", "ANCHOR_PROOF_VISIBLE_HOLD_MS = 900L", "animation=disabled"]),
        (gate, [MARKER, "draw+attached+inner+display-on", "maxWaitMs: Long = 6_500L"]),
        (gate_test, ["internalObjectStateAloneIsNotPresentationProof", "allAppSidePresentationEvidenceAdmitsHold", "waitIsBoundedByObservedSamsungWindow"]),
    )
    for text, needles in required:
        for needle in needles:
            if needle not in text:
                raise RuntimeError("missing S1V invariant: " + needle)

    if "Fold7OpeningRemapHandoffPolicy.shouldTransferToInner" in panel:
        raise RuntimeError("S1V must not require INNER geometry at the owner-release instant")
    if "startGen5OpeningFrameLoop()" in panel:
        raise RuntimeError("S1V anchor proof must not run Gen5 opening animation")


def apply(repo: Path, check: bool) -> None:
    paths = [repo / GRADLE, repo / PANEL, repo / SURFACE, repo / COMPOSER]
    if not all(path.exists() for path in paths):
        raise RuntimeError("required S1U materialized sources are missing")

    gradle = transform_gradle((repo / GRADLE).read_text(encoding="utf-8"))
    surface = transform_surface((repo / SURFACE).read_text(encoding="utf-8"))
    composer = transform_composer((repo / COMPOSER).read_text(encoding="utf-8"))
    panel = transform_panel((repo / PANEL).read_text(encoding="utf-8"))
    gate = GATE_SOURCE
    gate_test = GATE_TEST_SOURCE

    validate(gradle, panel, surface, composer, gate, gate_test)

    if not check:
        (repo / GRADLE).write_text(gradle, encoding="utf-8")
        (repo / SURFACE).write_text(surface, encoding="utf-8")
        (repo / COMPOSER).write_text(composer, encoding="utf-8")
        (repo / PANEL).write_text(panel, encoding="utf-8")
        (repo / GATE).write_text(gate, encoding="utf-8")
        (repo / GATE_TEST).write_text(gate_test, encoding="utf-8")


def self_test() -> None:
    max_wait = 6_500

    def evaluate(elapsed: int, draw: bool, attached: bool, laid_out: bool, inner: bool, on: bool) -> str:
        if draw and attached and laid_out and inner and on:
            return "PRESENTED"
        if elapsed >= max_wait:
            return "TIMEOUT"
        return "WAIT"

    assert evaluate(100, False, True, True, True, True) == "WAIT"
    assert evaluate(100, True, True, True, True, False) == "WAIT"
    assert evaluate(100, True, True, True, True, True) == "PRESENTED"
    assert evaluate(6_499, False, True, True, True, False) == "WAIT"
    assert evaluate(6_500, False, True, True, True, False) == "TIMEOUT"
    print("S1V opening anchor-proof model: PASS")


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
    print("S1V opening anchor proof: " + ("source shape verified" if args.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
