#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

TARGET_VERSION_CODE = 56
TARGET_VERSION_NAME = "5.6.0-gen12-route-lane-resilience-zfold7"
MARKER = "GEN12_ROUTE_LANE_RESILIENCE"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_new(path: Path, text: str) -> None:
    if path.exists():
        existing = read(path)
        if existing != text:
            raise RuntimeError(f"new-file collision: {path}")
        return
    write(path, text)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_build_gradle(text: str) -> str:
    if TARGET_VERSION_NAME in text:
        return text
    text = replace_once(text, "versionCode = 55", f"versionCode = {TARGET_VERSION_CODE}", "versionCode")
    text = replace_once(
        text,
        'versionName = "5.5.0-gen11-product-ui-zfold7"',
        f'versionName = "{TARGET_VERSION_NAME}"',
        "versionName",
    )
    return text


def bootstrap_gate_source() -> str:
    return '''package com.duoopen.fold

/**
 * GEN12_ROUTE_LANE_RESILIENCE
 *
 * A tiny pre-dispatch gate for privileged presentation work. While Samsung's
 * cover route is still bootstrapping, only the latest visual/presentation
 * intent is retained locally. Once the route is ready, that one latest intent
 * may enter the existing Gen10.4 single-flight RPC gate.
 *
 * This gate does not infer route readiness and does not own display state.
 */
class Fold7PresentationBootstrapGate<T> {
    data class Offer<T>(
        val dispatch: T?,
        val replacedDeferred: Boolean,
        val droppedDeferred: Boolean,
    )

    private var deferred: T? = null

    fun offer(value: T, defer: Boolean): Offer<T> {
        if (defer) {
            val replaced = deferred != null
            deferred = value
            return Offer(
                dispatch = null,
                replacedDeferred = replaced,
                droppedDeferred = false,
            )
        }

        val dropped = deferred != null
        deferred = null
        return Offer(
            dispatch = value,
            replacedDeferred = false,
            droppedDeferred = dropped,
        )
    }

    fun release(): T? {
        val value = deferred
        deferred = null
        return value
    }

    fun drop(): Boolean {
        val hadDeferred = deferred != null
        deferred = null
        return hadDeferred
    }

    val hasDeferred: Boolean
        get() = deferred != null
}
'''


def bootstrap_gate_test_source() -> str:
    return '''package com.duoopen.fold

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7PresentationBootstrapGateTest {
    @Test
    fun prewarmKeepsOnlyLatestIntentUntilReleased() {
        val gate = Fold7PresentationBootstrapGate<Int>()

        val first = gate.offer(10, defer = true)
        val second = gate.offer(20, defer = true)
        val third = gate.offer(30, defer = true)

        assertNull(first.dispatch)
        assertFalse(first.replacedDeferred)
        assertTrue(second.replacedDeferred)
        assertTrue(third.replacedDeferred)
        assertTrue(gate.hasDeferred)
        assertEquals(30, gate.release())
        assertFalse(gate.hasDeferred)
    }

    @Test
    fun reversalDropsDeferredClosingIntentAndDispatchesCurrentIntent() {
        val gate = Fold7PresentationBootstrapGate<String>()
        gate.offer("closing", defer = true)

        val reversal = gate.offer("opening", defer = false)

        assertEquals("opening", reversal.dispatch)
        assertTrue(reversal.droppedDeferred)
        assertFalse(gate.hasDeferred)
    }

    @Test
    fun explicitDropNeverManufacturesAValue() {
        val gate = Fold7PresentationBootstrapGate<Int>()
        gate.offer(7, defer = true)
        assertTrue(gate.drop())
        assertFalse(gate.drop())
        assertNull(gate.release())
    }
}
'''


def transform_service(text: str) -> str:
    if MARKER in text:
        return text

    text = replace_once(
        text,
        "import com.duoopen.fold.Fold7LatestOnlyGate\n",
        "import com.duoopen.fold.Fold7LatestOnlyGate\nimport com.duoopen.fold.Fold7PresentationBootstrapGate\n",
        "bootstrap gate import",
    )

    text = replace_once(
        text,
        '''    private var coverPresentationCoalesced = 0L

    private var angleFeed: WallpaperAngleFeed? = null
''',
        '''    private var coverPresentationCoalesced = 0L

    /*
     * GEN12_ROUTE_LANE_RESILIENCE
     *
     * Physical One UI 9 evidence (5.5.0 / API 37) captured a close where the
     * initial Gen4 cover prewarm and an immediately concurrent presentation
     * mutation both returned only after ~1.046 s. The hinge had already moved
     * from 175 deg to ~62 deg and the cycle never reached COVER_VISUAL.
     *
     * Presentation/brightness is not useful while the Gen4 route is still
     * hidden. Keep only its latest intent locally until route bootstrap exits
     * PREWARMING, rather than putting another mutation into Samsung's critical
     * display lane. Gen4 remains the sole route/panel authority.
     */
    private val coverPresentationBootstrapGate =
        Fold7PresentationBootstrapGate<CoverPresentationRequest>()

    private var coverPresentationDeferredSinceUptime = 0L
    private var coverPresentationDeferredCount = 0L

    private val coverPresentationRouteFlushRunnable =
        Runnable {
            flushDeferredCoverPresentation("timer")
        }

    private var angleFeed: WallpaperAngleFeed? = null
''',
        "bootstrap presentation state",
    )

    old_offer = '''        val offered =
            coverPresentationGate.offer(
                request
            )

        if (offered.replacedPending) {
            coverPresentationCoalesced++
            if (
                coverPresentationCoalesced == 1L ||
                coverPresentationCoalesced % 8L == 0L
            ) {
                DuoDiagnostics.event(
                    "gen10-4-io",
                    "cover presentation coalesced count=$coverPresentationCoalesced " +
                        "latestAngle=$angle direction=$direction",
                )
            }
        }

        offered.dispatch
            ?.let(::dispatchCoverPresentation)
'''

    new_offer = '''        val deferForRouteBootstrap =
            request.direction == Fold7CoverPresentationPolicy.Direction.CLOSING &&
                continuity.state in
                    setOf(
                        Fold7ContinuityController.State.CLOSING_INTENT,
                        Fold7ContinuityController.State.COVER_PREWARMING,
                    )

        val bootstrapOffer =
            coverPresentationBootstrapGate.offer(
                value = request,
                defer = deferForRouteBootstrap,
            )

        if (bootstrapOffer.droppedDeferred) {
            coverPresentationDeferredSinceUptime = 0L
            handler.removeCallbacks(coverPresentationRouteFlushRunnable)
            DuoDiagnostics.event(
                "gen12-route-lane",
                "deferred closing presentation dropped by current direction/state " +
                    "angle=$angle direction=$direction state=${continuity.state}",
            )
        }

        if (bootstrapOffer.dispatch == null) {
            if (coverPresentationDeferredSinceUptime == 0L) {
                coverPresentationDeferredSinceUptime = SystemClock.uptimeMillis()
            }
            coverPresentationDeferredCount++
            if (
                coverPresentationDeferredCount == 1L ||
                coverPresentationDeferredCount % 8L == 0L
            ) {
                DuoDiagnostics.event(
                    "gen12-route-lane",
                    "presentation deferred count=$coverPresentationDeferredCount " +
                        "latestAngle=$angle state=${continuity.state}",
                )
            }
            scheduleDeferredCoverPresentationFlush()
            return
        }

        enqueueCoverPresentationDispatch(bootstrapOffer.dispatch)
'''
    text = replace_once(text, old_offer, new_offer, "route-bootstrap deferral")

    helper_anchor = '''    private fun dispatchCoverPresentation(
        request: CoverPresentationRequest,
    ) {
'''

    helpers = '''    private fun enqueueCoverPresentationDispatch(
        request: CoverPresentationRequest,
    ) {
        val offered =
            coverPresentationGate.offer(
                request
            )

        if (offered.replacedPending) {
            coverPresentationCoalesced++
            if (
                coverPresentationCoalesced == 1L ||
                coverPresentationCoalesced % 8L == 0L
            ) {
                DuoDiagnostics.event(
                    "gen10-4-io",
                    "cover presentation coalesced count=$coverPresentationCoalesced " +
                        "latestAngle=${request.angle} direction=${request.direction}",
                )
            }
        }

        offered.dispatch
            ?.let(::dispatchCoverPresentation)
    }

    private fun scheduleDeferredCoverPresentationFlush() {
        handler.removeCallbacks(coverPresentationRouteFlushRunnable)
        handler.postDelayed(
            coverPresentationRouteFlushRunnable,
            GEN12_ROUTE_LANE_RECHECK_MS,
        )
    }

    private fun flushDeferredCoverPresentation(
        reason: String,
    ) {
        if (!coverPresentationBootstrapGate.hasDeferred) {
            coverPresentationDeferredSinceUptime = 0L
            handler.removeCallbacks(coverPresentationRouteFlushRunnable)
            return
        }

        val now = SystemClock.uptimeMillis()
        val deferredForMs =
            if (coverPresentationDeferredSinceUptime > 0L) {
                (now - coverPresentationDeferredSinceUptime).coerceAtLeast(0L)
            } else {
                0L
            }

        when (continuity.state) {
            Fold7ContinuityController.State.CLOSING_INTENT,
            Fold7ContinuityController.State.COVER_PREWARMING -> {
                if (deferredForMs >= GEN12_ROUTE_LANE_MAX_DEFER_MS) {
                    val dropped = coverPresentationBootstrapGate.drop()
                    coverPresentationDeferredSinceUptime = 0L
                    if (dropped) {
                        DuoDiagnostics.event(
                            "gen12-route-lane",
                            "deferred presentation dropped after timeout " +
                                "waitMs=$deferredForMs reason=$reason state=${continuity.state}",
                        )
                    }
                } else {
                    scheduleDeferredCoverPresentationFlush()
                }
            }

            Fold7ContinuityController.State.COVER_READY_HIDDEN,
            Fold7ContinuityController.State.COVER_VISUAL -> {
                val next = coverPresentationBootstrapGate.release()
                coverPresentationDeferredSinceUptime = 0L
                handler.removeCallbacks(coverPresentationRouteFlushRunnable)
                if (next != null) {
                    DuoDiagnostics.event(
                        "gen12-route-lane",
                        "deferred presentation released waitMs=$deferredForMs " +
                            "reason=$reason angle=${next.angle} state=${continuity.state}",
                    )
                    enqueueCoverPresentationDispatch(next)
                }
            }

            else -> {
                val dropped = coverPresentationBootstrapGate.drop()
                coverPresentationDeferredSinceUptime = 0L
                handler.removeCallbacks(coverPresentationRouteFlushRunnable)
                if (dropped) {
                    DuoDiagnostics.event(
                        "gen12-route-lane",
                        "deferred presentation invalidated waitMs=$deferredForMs " +
                            "reason=$reason state=${continuity.state}",
                    )
                }
            }
        }
    }

'''
    text = replace_once(text, helper_anchor, helpers + helper_anchor, "route-lane helpers")

    text = replace_once(
        text,
        '''                    coverPresentationPolicy.reset()
                    coverPresentationGate.reset()

                    setEarlyOpeningVisualLatched(
''',
        '''                    coverPresentationPolicy.reset()
                    coverPresentationGate.reset()
                    coverPresentationBootstrapGate.drop()
                    coverPresentationDeferredSinceUptime = 0L
                    handler.removeCallbacks(coverPresentationRouteFlushRunnable)

                    setEarlyOpeningVisualLatched(
''',
        "reset bootstrap gate on privilege loss",
    )

    text = replace_once(
        text,
        '''        handler.removeCallbacks(
            displaySyncRunnable
        )

        angleFeed?.stop()
''',
        '''        handler.removeCallbacks(
            displaySyncRunnable
        )

        handler.removeCallbacks(
            coverPresentationRouteFlushRunnable
        )
        coverPresentationBootstrapGate.drop()
        coverPresentationDeferredSinceUptime = 0L

        angleFeed?.stop()
''',
        "destroy route-lane cleanup",
    )

    text = replace_once(
        text,
        '''        val privilegedReady =
            ShizukuBridge.ready &&
                continuity.renderOwnershipEnabled
''',
        '''        flushDeferredCoverPresentation(
            "reconcile:$reason"
        )

        val privilegedReady =
            ShizukuBridge.ready &&
                continuity.renderOwnershipEnabled
''',
        "flush on continuity reconciliation",
    )

    text = replace_once(
        text,
        '''        private const val DISPLAY_SYNC_DEBOUNCE_MS =
            24L
''',
        '''        private const val DISPLAY_SYNC_DEBOUNCE_MS =
            24L

        private const val GEN12_ROUTE_LANE_RECHECK_MS =
            24L

        private const val GEN12_ROUTE_LANE_MAX_DEFER_MS =
            1_500L
''',
        "route-lane constants",
    )

    return text


def verify(repo: Path) -> None:
    build = read(repo / "app/build.gradle.kts")
    service = read(repo / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt")
    gate = read(repo / "app/src/main/java/com/duoopen/fold/Fold7PresentationBootstrapGate.kt")
    gate_test = read(repo / "app/src/test/java/com/duoopen/fold/Fold7PresentationBootstrapGateTest.kt")
    shader = read(repo / "app/src/main/java/com/duoopen/fold/DuoShader.kt")
    overlay = read(repo / "app/src/full/java/com/duoopen/overlay/FoldOverlayView.kt")
    panel = read(repo / "app/src/full/java/com/duoopen/overlay/PanelEngine.kt")
    coordinator = read(repo / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt")
    home = read(repo / "app/src/main/java/com/duoopen/ui/HomePreview.kt")

    required = {
        "version": TARGET_VERSION_NAME in build and f"versionCode = {TARGET_VERSION_CODE}" in build,
        "compile37-target35": "compileSdk = 37" in build and "targetSdk = 35" in build,
        "service-marker": MARKER in service,
        "bootstrap-gate": "Fold7PresentationBootstrapGate<CoverPresentationRequest>" in service,
        "defer-state": "COVER_PREWARMING" in service and "presentation deferred count=" in service,
        "defer-release": "deferred presentation released" in service,
        "defer-timeout": "GEN12_ROUTE_LANE_MAX_DEFER_MS" in service,
        "gate-source": MARKER in gate and "fun offer(value: T, defer: Boolean)" in gate,
        "gate-tests": "prewarmKeepsOnlyLatestIntentUntilReleased" in gate_test and "reversalDropsDeferredClosingIntentAndDispatchesCurrentIntent" in gate_test,
        "gen11-ui": "GEN11_PRODUCT_UI" in home and "Continuity Console" in home,
        "gen10-7-angle": "GEN10_7_TOPOLOGY_ANGLE_HOLD" in coordinator,
        "secure-fail-open": "capture-protected-or-black" in panel,
        "renderer-domain-preserved": "const val MAX_TILT = 60f" in shader,
        "renderer-filter-preserved": "setFilterMode(BitmapShader.FILTER_MODE_LINEAR)" in overlay,
    }

    missing = [name for name, ok in required.items() if not ok]
    if missing:
        raise RuntimeError(f"Gen12 verification failed: {missing}")

    if "targetSdk = 37" in build:
        raise RuntimeError("Gen12 must preserve targetSdk 35 compatibility bridge")

    if service.count("ShizukuBridge.setCoverPresentationV1(") != 2:
        raise RuntimeError("Gen12 must not add another privileged cover-presentation RPC source")

    print("Gen12 route-lane resilience applied and verified")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()

    write_new(
        repo / "app/src/main/java/com/duoopen/fold/Fold7PresentationBootstrapGate.kt",
        bootstrap_gate_source(),
    )
    write_new(
        repo / "app/src/test/java/com/duoopen/fold/Fold7PresentationBootstrapGateTest.kt",
        bootstrap_gate_test_source(),
    )

    build = repo / "app/build.gradle.kts"
    write(build, transform_build_gradle(read(build)))

    service = repo / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"
    write(service, transform_service(read(service)))

    verify(repo)


if __name__ == "__main__":
    main()
