#!/usr/bin/env python3
"""Apply Gen10.4 Fold7 IO coalescing + mirror construction fence after Gen10.3.

Field evidence from Gen10.2 showed obsolete cover-presentation commands completing
hundreds of milliseconds late and out of hinge order while route reassert/mirror
attach work was also pending. The client launched one Dispatchers.IO mutation per
policy update, while the shell serializes cover mutations. Sequence rejection
prevents stale state from winning, but does not keep stale work out of the queue.

Gen10.4 bounds that pressure with a latest-value-wins gate: at most one cover
presentation RPC may be in flight and only the newest pending command survives.
It also fences re-entrant mirror-host construction, which field logs showed could
create duplicate hosts/presentation attempts during Samsung display callbacks.
"""

from __future__ import annotations

import argparse
from pathlib import Path

TARGET_VERSION_CODE = 51
TARGET_VERSION_NAME = "5.4.4-gen10-io-coalescing-zfold7"
MARKER = "GEN10_4_IO_COALESCING"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def write_new(path: Path, content: str) -> None:
    if path.exists():
        existing = path.read_text()
        if existing != content:
            raise RuntimeError(f"new-file collision: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def apply(repo: Path) -> None:
    build = repo / "app/build.gradle.kts"
    text = build.read_text()
    text = replace_once(text, "versionCode = 50", f"versionCode = {TARGET_VERSION_CODE}", "versionCode")
    text = replace_once(
        text,
        'versionName = "5.4.3-gen10-hybrid-animation-zfold7"',
        f'versionName = "{TARGET_VERSION_NAME}"',
        "versionName",
    )
    build.write_text(text)

    gate_file = repo / "app/src/main/java/com/duoopen/fold/Fold7LatestOnlyGate.kt"
    gate_content = '''package com.duoopen.fold

/**
 * Single-flight latest-value-wins gate.
 *
 * The first offered value is dispatched immediately. While it is in flight,
 * only the newest pending value is retained. Completing an in-flight value
 * either returns that newest pending value (while remaining busy) or returns
 * null and becomes idle.
 */
class Fold7LatestOnlyGate<T> {
    data class Offer<T>(
        val dispatch: T?,
        val replacedPending: Boolean,
    )

    private var busy = false
    private var pending: T? = null

    fun offer(value: T): Offer<T> {
        if (!busy) {
            busy = true
            return Offer(
                dispatch = value,
                replacedPending = false,
            )
        }

        val replaced = pending != null
        pending = value
        return Offer(
            dispatch = null,
            replacedPending = replaced,
        )
    }

    fun complete(): T? {
        val next = pending
        pending = null
        if (next == null) {
            busy = false
        }
        return next
    }

    fun reset() {
        busy = false
        pending = null
    }

    val inFlight: Boolean
        get() = busy

    val hasPending: Boolean
        get() = pending != null
}
'''
    write_new(gate_file, gate_content)

    test_file = repo / "app/src/test/java/com/duoopen/fold/Fold7LatestOnlyGateTest.kt"
    test_content = '''package com.duoopen.fold

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7LatestOnlyGateTest {
    @Test
    fun firstValueDispatchesImmediately() {
        val gate = Fold7LatestOnlyGate<Int>()
        val offer = gate.offer(1)
        assertEquals(1, offer.dispatch)
        assertFalse(offer.replacedPending)
        assertTrue(gate.inFlight)
        assertFalse(gate.hasPending)
    }

    @Test
    fun busyGateKeepsOnlyNewestPendingValue() {
        val gate = Fold7LatestOnlyGate<Int>()
        gate.offer(1)
        val second = gate.offer(2)
        val third = gate.offer(3)

        assertNull(second.dispatch)
        assertFalse(second.replacedPending)
        assertNull(third.dispatch)
        assertTrue(third.replacedPending)
        assertEquals(3, gate.complete())
        assertTrue(gate.inFlight)
        assertFalse(gate.hasPending)
        assertNull(gate.complete())
        assertFalse(gate.inFlight)
    }

    @Test
    fun resetDropsPendingAndReturnsIdle() {
        val gate = Fold7LatestOnlyGate<Int>()
        gate.offer(1)
        gate.offer(2)
        gate.reset()
        assertFalse(gate.inFlight)
        assertFalse(gate.hasPending)
        assertNull(gate.complete())
    }
}
'''
    write_new(test_file, test_content)

    service = repo / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"
    text = service.read_text()

    text = replace_once(
        text,
        '''import com.duoopen.fold.HingeAngleSource
''',
        '''import com.duoopen.fold.HingeAngleSource
import com.duoopen.fold.Fold7LatestOnlyGate
''',
        "latest-only gate import",
    )

    text = replace_once(
        text,
        '''    private var nativeCoverBrightnessReassertGeneration = -1L

    private var angleFeed: WallpaperAngleFeed? = null
''',
        '''    private var nativeCoverBrightnessReassertGeneration = -1L

    /*
     * GEN10_4_IO_COALESCING
     * Keep cover power/brightness traffic single-flight. Samsung's shell-side
     * display mutation path is serialized; queueing every 40 ms hinge update
     * behind it delayed route reassert and mirror attachment in field traces.
     */
    private data class CoverPresentationRequest(
        val angle: Float,
        val direction: Fold7CoverPresentationPolicy.Direction,
        val command: Fold7CoverPresentationPolicy.Command,
        val generation: Long,
        val innerReference: Float,
    )

    private val coverPresentationGate =
        Fold7LatestOnlyGate<CoverPresentationRequest>()

    private var coverPresentationCoalesced = 0L

    private var angleFeed: WallpaperAngleFeed? = null
''',
        "cover presentation coalescing state",
    )

    old_dispatch = '''        val sequence =
            coverPresentationSequence.incrementAndGet()

        val generation =
            continuity.generation

        scope.launch(Dispatchers.IO) {
            val result =
                ShizukuBridge.setCoverPresentationV1(
                    serviceEpoch = serviceEpoch,
                    transitionGeneration = generation,
                    sequence = sequence,
                    powerOn = command.powerOn,
                    brightness = command.brightness,
                    reason = command.reason,
                )

            DuoDiagnostics.event(
                "cover-presentation",
                "angle=$angle direction=$direction " +
                    "power=${command.powerOn} " +
                    "target=${command.brightness} " +
                    "innerReference=$innerBrightnessReference " +
                    "sequence=$sequence generation=$generation " +
                    "ok=${result?.getBoolean("ok", false) == true} " +
                    "stale=${result?.getBoolean("stale", false) == true} " +
                    "physical=${result?.getLong("physicalDisplayId", -1L) ?: -1L} " +
                    "powerError=${result?.getString("powerError")} " +
                    "brightnessError=${result?.getString("brightnessError")}",
            )
        }
'''

    new_dispatch = '''        val request =
            CoverPresentationRequest(
                angle = angle,
                direction = direction,
                command = command,
                generation = continuity.generation,
                innerReference = innerBrightnessReference,
            )

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
                        "latestAngle=$angle direction=$direction",
                )
            }
        }

        offered.dispatch
            ?.let(::dispatchCoverPresentation)
'''
    text = replace_once(text, old_dispatch, new_dispatch, "coalesce cover presentation dispatch")

    dispatch_method = '''    private fun dispatchCoverPresentation(
        request: CoverPresentationRequest,
    ) {
        val sequence =
            coverPresentationSequence.incrementAndGet()

        scope.launch(Dispatchers.IO) {
            val queuedAt =
                SystemClock.uptimeMillis()

            val result =
                ShizukuBridge.setCoverPresentationV1(
                    serviceEpoch = serviceEpoch,
                    transitionGeneration = request.generation,
                    sequence = sequence,
                    powerOn = request.command.powerOn,
                    brightness = request.command.brightness,
                    reason = request.command.reason,
                )

            val completedAt =
                SystemClock.uptimeMillis()

            handler.post {
                DuoDiagnostics.event(
                    "cover-presentation",
                    "angle=${request.angle} direction=${request.direction} " +
                        "power=${request.command.powerOn} " +
                        "target=${request.command.brightness} " +
                        "innerReference=${request.innerReference} " +
                        "sequence=$sequence generation=${request.generation} " +
                        "rpcMs=${(completedAt - queuedAt).coerceAtLeast(0L)} " +
                        "ok=${result?.getBoolean("ok", false) == true} " +
                        "stale=${result?.getBoolean("stale", false) == true} " +
                        "physical=${result?.getLong("physicalDisplayId", -1L) ?: -1L} " +
                        "powerError=${result?.getString("powerError")} " +
                        "brightnessError=${result?.getString("brightnessError")}",
                )

                val next =
                    coverPresentationGate.complete()

                if (next != null) {
                    if (
                        ShizukuBridge.ready &&
                        ::continuity.isInitialized &&
                        continuity.renderOwnershipEnabled
                    ) {
                        dispatchCoverPresentation(
                            next
                        )
                    } else {
                        coverPresentationGate.reset()
                        DuoDiagnostics.event(
                            "gen10-4-io",
                            "pending cover presentation dropped after authority loss",
                        )
                    }
                }
            }
        }
    }

'''
    text = replace_once(
        text,
        '''    /** Starts engines for panels that lit up, stops those that went dark, then lets each re-evaluate. */
''',
        dispatch_method + '''    /** Starts engines for panels that lit up, stops those that went dark, then lets each re-evaluate. */
''',
        "cover presentation dispatcher",
    )

    text = replace_once(
        text,
        '''                    coverPresentationPolicy.reset()

                    setEarlyOpeningVisualLatched(
''',
        '''                    coverPresentationPolicy.reset()
                    coverPresentationGate.reset()

                    setEarlyOpeningVisualLatched(
''',
        "reset coalescer on privilege loss",
    )

    service.write_text(text)

    coordinator = repo / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"
    text = coordinator.read_text()

    text = replace_once(
        text,
        '''    private var mirrorHost: DisplayMirrorHost? = null
''',
        '''    private var mirrorHost: DisplayMirrorHost? = null

    /* GEN10_4_IO_COALESCING
     * addView()/display callbacks can re-enter syncMirrorHost before the first
     * host is published. Fence that construction window to one host.
     */
    private var mirrorHostConstructing = false
''',
        "mirror construction fence state",
    )

    text = replace_once(
        text,
        '''        runCatching {
            current?.detach()
        }
        mirrorHost = null

        // Samsung may invalidate/remap the Display between lookup and context
''',
        '''        if (mirrorHostConstructing) {
            DuoDiagnostics.event(
                "gen10-4-io",
                "mirror construction coalesced reason=$reason generation=$generation " +
                    "cover=${activeCover.displayId}",
            )
            return
        }

        mirrorHostConstructing = true

        runCatching {
            current?.detach()
        }
        mirrorHost = null

        // Samsung may invalidate/remap the Display between lookup and context
''',
        "mirror construction fence entry",
    )

    text = replace_once(
        text,
        '''            }.getOrNull()
                ?: return
''',
        '''            }.getOrNull()
                ?: run {
                    mirrorHostConstructing = false
                    return
                }
''',
        "clear fence on constructor failure",
    )

    # Gen10.1 adds three post-construction guards. Clear the fence on each
    # early return and after successful publication.
    text = replace_once(
        text,
        '''        ) {
            runCatching { created.detach() }
            return
        }

        /*
         * Re-resolve immediately before attach.''',
        '''        ) {
            runCatching { created.detach() }
            mirrorHostConstructing = false
            return
        }

        /*
         * Re-resolve immediately before attach.''',
        "clear fence on pre-attach state change",
    )

    text = replace_once(
        text,
        '''        ) {
            runCatching { created.detach() }
            DuoDiagnostics.event(
                "gen10-handoff-guard",
                "mirror attach blocked reason=$reason generation=$generation " +
                    "planned=${activeCover.displayId} current=${attachCover?.displayId}",
            )
            return
        }

        val attached =''',
        '''        ) {
            runCatching { created.detach() }
            mirrorHostConstructing = false
            DuoDiagnostics.event(
                "gen10-handoff-guard",
                "mirror attach blocked reason=$reason generation=$generation " +
                    "planned=${activeCover.displayId} current=${attachCover?.displayId}",
            )
            return
        }

        val attached =''',
        "clear fence on attach topology block",
    )

    text = replace_once(
        text,
        '''        if (!attached) {
            runCatching { created.detach() }
            return
        }
''',
        '''        if (!attached) {
            runCatching { created.detach() }
            mirrorHostConstructing = false
            return
        }
''',
        "clear fence on attach failure",
    )

    text = replace_once(
        text,
        '''        ) {
            runCatching { created.detach() }
            return
        }

        val publishedSnapshot = topologySnapshot()''',
        '''        ) {
            runCatching { created.detach() }
            mirrorHostConstructing = false
            return
        }

        val publishedSnapshot = topologySnapshot()''',
        "clear fence on post-attach state change",
    )

    text = replace_once(
        text,
        '''        ) {
            runCatching { created.detach() }
            DuoDiagnostics.event(
                "gen10-handoff-guard",
                "mirror publish blocked reason=$reason generation=$generation " +
                    "planned=${activeCover.displayId} current=${publishedCover?.displayId}",
            )
            return
        }

        mirrorHost = created
''',
        '''        ) {
            runCatching { created.detach() }
            mirrorHostConstructing = false
            DuoDiagnostics.event(
                "gen10-handoff-guard",
                "mirror publish blocked reason=$reason generation=$generation " +
                    "planned=${activeCover.displayId} current=${publishedCover?.displayId}",
            )
            return
        }

        mirrorHost = created
        mirrorHostConstructing = false
''',
        "clear fence on publish path",
    )

    coordinator.write_text(text)


def verify(repo: Path) -> None:
    build = (repo / "app/build.gradle.kts").read_text()
    service = (repo / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt").read_text()
    coordinator = (repo / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt").read_text()
    gen3 = (repo / "app/src/full/java/com/duoopen/overlay/Fold7Gen3VisualCoordinator.kt").read_text()
    panel = (repo / "app/src/full/java/com/duoopen/overlay/PanelEngine.kt").read_text()
    mirror = (repo / "app/src/full/java/com/duoopen/overlay/DisplayMirrorHost.kt").read_text()
    gate = (repo / "app/src/main/java/com/duoopen/fold/Fold7LatestOnlyGate.kt").read_text()
    test = (repo / "app/src/test/java/com/duoopen/fold/Fold7LatestOnlyGateTest.kt").read_text()

    required = [
        f"versionCode = {TARGET_VERSION_CODE}",
        f'versionName = "{TARGET_VERSION_NAME}"',
        MARKER,
        "Fold7LatestOnlyGate<CoverPresentationRequest>()",
        "coverPresentationGate.offer(",
        "dispatchCoverPresentation(",
        '"cover presentation coalesced count=$coverPresentationCoalesced "',
        '"rpcMs=${(completedAt - queuedAt).coerceAtLeast(0L)} "',
        "mirrorHostConstructing",
        '"mirror construction coalesced reason=$reason generation=$generation "',
        'type = "gen10-3-hybrid-animation"',
        '"capture-protected-or-black"',
        '"Protected/uncapturable content: native display passthrough."',
        "class Fold7LatestOnlyGate<T>",
        "busyGateKeepsOnlyNewestPendingValue",
    ]
    joined = "\n".join([build, service, coordinator, gen3, panel, mirror, gate, test])
    missing = [needle for needle in required if needle not in joined]
    if missing:
        raise RuntimeError(f"Gen10.4 verification failed; missing: {missing}")

    # The old unbounded one-coroutine-per-policy-update block must be gone from
    # updateCoverPresentation. Only dispatchCoverPresentation may call the RPC.
    if service.count("ShizukuBridge.setCoverPresentationV1(") != 2:
        # One call is the coalesced dispatcher, one is Gen10.1 native-cover
        # brightness reassert. Any additional call reintroduces unbounded work.
        raise RuntimeError(
            "Gen10.4 verification failed: unexpected cover presentation RPC call count"
        )

    if service.count("coverPresentationGate.offer(") != 1:
        raise RuntimeError("Gen10.4 verification failed: presentation gate admission is not singular")

    # Preserve Gen10.2 secure proof ordering.
    proof_index = mirror.index("val captureProof =")
    start_index = mirror.index("ShizukuBridge.startDisplayMirrorV2(")
    if proof_index >= start_index:
        raise RuntimeError("Gen10.4 verification failed: secure proof no longer gates live mirror")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    apply(repo)
    verify(repo)
    print("Gen10.4 IO coalescing + mirror construction fence applied and verified")


if __name__ == "__main__":
    main()
