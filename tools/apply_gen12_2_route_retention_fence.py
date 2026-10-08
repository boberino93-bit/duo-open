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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    root = Path(args.repo).resolve()

    coordinator = root / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"
    helper = root / "app/src/full/java/com/duoopen/overlay/Fold7RouteReleaseFence.kt"
    helper_test = root / "app/src/test/java/com/duoopen/overlay/Fold7RouteReleaseFenceTest.kt"
    gradle = root / "app/build.gradle.kts"

    if not coordinator.is_file():
        fail(f"missing reconstructed coordinator: {coordinator}")

    helper.parent.mkdir(parents=True, exist_ok=True)
    helper.write_text(
        '''package com.duoopen.overlay

/**
 * Gen12.2 cancellation fence for destructive Fold7 cover-route return.
 *
 * A route that is already prepared is intentionally retained for a short grace
 * window after opening. A new close generation, Shizuku reconnection, or an
 * explicit cancellation invalidates the old ticket before it can reset the
 * secondary route. This is deliberately pure so the race can be unit tested
 * without Android or Shizuku.
 */
internal class Fold7RouteReleaseFence(
    private val retentionMs: Long,
) {
    init {
        require(retentionMs >= 0L)
    }

    data class Ticket(
        val serial: Long,
        val connectionEpoch: Long,
        val generation: Long,
        val dueUptimeMs: Long,
    )

    private var serial = 0L

    @Synchronized
    fun schedule(
        nowUptimeMs: Long,
        connectionEpoch: Long,
        generation: Long,
    ): Ticket {
        val next = ++serial
        return Ticket(
            serial = next,
            connectionEpoch = connectionEpoch,
            generation = generation,
            dueUptimeMs = nowUptimeMs + retentionMs,
        )
    }

    @Synchronized
    fun cancel(): Long = ++serial

    @Synchronized
    fun isCurrent(
        ticket: Ticket,
        nowUptimeMs: Long,
        connectionEpoch: Long,
        generation: Long,
    ): Boolean =
        ticket.serial == serial &&
            nowUptimeMs >= ticket.dueUptimeMs &&
            connectionEpoch == ticket.connectionEpoch &&
            generation == ticket.generation
}
'''
    )

    helper_test.parent.mkdir(parents=True, exist_ok=True)
    helper_test.write_text(
        '''package com.duoopen.overlay

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7RouteReleaseFenceTest {
    @Test
    fun stableOpenBecomesEligibleOnlyAfterRetentionWindow() {
        val fence = Fold7RouteReleaseFence(retentionMs = 750L)
        val ticket = fence.schedule(
            nowUptimeMs = 1_000L,
            connectionEpoch = 7L,
            generation = 66L,
        )

        assertFalse(fence.isCurrent(ticket, 1_749L, 7L, 66L))
        assertTrue(fence.isCurrent(ticket, 1_750L, 7L, 66L))
    }

    @Test
    fun rapidCloseReversalCancelsOldOpeningRelease() {
        val fence = Fold7RouteReleaseFence(retentionMs = 750L)
        val oldOpening = fence.schedule(
            nowUptimeMs = 0L,
            connectionEpoch = 1L,
            generation = 66L,
        )

        // Forensic replay: a new close/prewarm arrives before the grace expires.
        fence.cancel()

        assertFalse(fence.isCurrent(oldOpening, 800L, 1L, 71L))
        assertFalse(fence.isCurrent(oldOpening, 800L, 1L, 66L))
    }

    @Test
    fun generationAdvanceRejectsReleaseEvenWithoutExplicitCancel() {
        val fence = Fold7RouteReleaseFence(retentionMs = 750L)
        val ticket = fence.schedule(0L, connectionEpoch = 3L, generation = 100L)

        assertFalse(fence.isCurrent(ticket, 900L, 3L, 101L))
    }

    @Test
    fun binderReconnectionRejectsReleaseFromOldConnection() {
        val fence = Fold7RouteReleaseFence(retentionMs = 750L)
        val ticket = fence.schedule(0L, connectionEpoch = 9L, generation = 42L)

        assertFalse(fence.isCurrent(ticket, 900L, 10L, 42L))
    }

    @Test
    fun newerReleaseSupersedesOlderReleaseTicket() {
        val fence = Fold7RouteReleaseFence(retentionMs = 750L)
        val first = fence.schedule(0L, 1L, 55L)
        val second = fence.schedule(100L, 1L, 55L)

        assertFalse(fence.isCurrent(first, 900L, 1L, 55L))
        assertTrue(fence.isCurrent(second, 900L, 1L, 55L))
    }
}
'''
    )

    replace_once(
        coordinator,
        '''    private val panelIntentSequence = AtomicLong(0L)
''',
        '''    private val panelIntentSequence = AtomicLong(0L)
    private val coverReleaseFence =
        Fold7RouteReleaseFence(COVER_ROUTE_RETENTION_MS)
''',
        "route release fence field",
    )

    replace_once(
        coordinator,
        '''    private fun beginPrewarm(
        generation: Long,
    ) {
        if (!controller.isGenerationCurrent(generation)) return

        val cycle = gen2.activeCycle
''',
        '''    private fun beginPrewarm(
        generation: Long,
    ) {
        if (!controller.isGenerationCurrent(generation)) return

        // GEN12_2_ROUTE_RETENTION_FENCE: a new close owns the already-warm route.
        // Invalidate any delayed OPENING teardown before issuing privileged I/O.
        cancelPendingCoverRelease("prewarm:generation=$generation")

        val cycle = gen2.activeCycle
''',
        "cancel retained release on prewarm",
    )

    release_start = '''    private fun releaseCoverLease(
'''
    release_end = '''    private fun reconcileCoverLease(
'''
    release_impl = r'''    private fun cancelPendingCoverRelease(
        reason: String,
    ) {
        val serial = coverReleaseFence.cancel()
        DuoDiagnostics.event(
            "gen12.2-route-retention",
            "cancel serial=$serial reason=$reason generation=${controller.generation}",
        )
    }

    private fun releaseCoverLease(
        reason: String,
    ) {
        if (!ShizukuBridge.ready) return

        /*
         * The forensic Gen12.1 capture proved that secondary-release calls can
         * take hundreds of milliseconds and then tear down a newer close route.
         * Ordinary OPENING teardown is therefore delayed. Explicit service
         * release/disarm paths remain immediate and fail-closed.
         */
        if (!reason.startsWith("secondary-release:")) {
            cancelPendingCoverRelease("immediate:$reason")
            performCoverRelease(
                reason = reason,
                expectedConnectionEpoch = ShizukuBridge.connectionEpoch,
            )
            return
        }

        val requestConnectionEpoch = ShizukuBridge.connectionEpoch
        val requestGeneration = controller.generation
        val ticket =
            coverReleaseFence.schedule(
                nowUptimeMs = SystemClock.uptimeMillis(),
                connectionEpoch = requestConnectionEpoch,
                generation = requestGeneration,
            )

        DuoDiagnostics.event(
            "gen12.2-route-retention",
            "retain serial=${ticket.serial} generation=$requestGeneration " +
                "connection=$requestConnectionEpoch delayMs=$COVER_ROUTE_RETENTION_MS reason=$reason",
        )

        handler.postDelayed(
            Runnable {
                val now = SystemClock.uptimeMillis()
                val current =
                    !destroyed &&
                        ShizukuBridge.ready &&
                        coverReleaseFence.isCurrent(
                            ticket = ticket,
                            nowUptimeMs = now,
                            connectionEpoch = ShizukuBridge.connectionEpoch,
                            generation = controller.generation,
                        )

                if (!current) {
                    DuoDiagnostics.event(
                        "gen12.2-route-retention",
                        "drop serial=${ticket.serial} requestedGeneration=$requestGeneration " +
                            "currentGeneration=${controller.generation} reason=$reason",
                    )
                } else {
                    DuoDiagnostics.event(
                        "gen12.2-route-retention",
                        "release serial=${ticket.serial} generation=$requestGeneration reason=$reason",
                    )
                    performCoverRelease(
                        reason = "$reason:retention-expired",
                        expectedConnectionEpoch = requestConnectionEpoch,
                    )
                }
            },
            COVER_ROUTE_RETENTION_MS,
        )
    }

    private fun performCoverRelease(
        reason: String,
        expectedConnectionEpoch: Long,
    ) {
        if (
            !ShizukuBridge.ready ||
            expectedConnectionEpoch != ShizukuBridge.connectionEpoch
        ) {
            return
        }

        val intentSequence = panelIntentSequence.incrementAndGet()

        scope.launch(Dispatchers.IO) {
            val result =
                ShizukuBridge.returnCoverPanelGen4(
                    serviceEpoch = serviceEpoch,
                    intentSequence = intentSequence,
                    reason = reason,
                )

            handler.post {
                if (expectedConnectionEpoch != ShizukuBridge.connectionEpoch) {
                    return@post
                }

                val acceptance =
                    acceptCoverLeaseSnapshot(
                        result = result,
                        connectionEpoch = expectedConnectionEpoch,
                        reason = "gen4-return:$reason",
                    )

                val pending =
                    acceptance.accepted &&
                        acceptance.snapshot?.leaseState == "RELEASE_PENDING"

                if (pending && gen4ReleaseRetryCount < MAX_GEN4_RELEASE_RETRIES) {
                    gen4ReleaseRetryCount += 1
                    handler.postDelayed(
                        {
                            reconcileCoverLease(
                                "release-retry-$gen4ReleaseRetryCount:$reason"
                            )
                        },
                        GEN4_RELEASE_RETRY_MS,
                    )
                } else if (!pending) {
                    gen4ReleaseRetryCount = 0
                }
            }
        }
    }

'''
    replace_between(
        coordinator,
        release_start,
        release_end,
        release_impl,
        "replace destructive transition release with retained release",
    )

    replace_once(
        coordinator,
        '''        const val MAX_GEN4_ROUTE_RETRIES = 3
''',
        '''        const val MAX_GEN4_ROUTE_RETRIES = 3
        // Measured Gen12.1 OPENING route/presentation tail reached ~622 ms in
        // the supplied Fold7 trace; 750 ms covers that reversal window while
        // bounding the hidden-route power cost.
        const val COVER_ROUTE_RETENTION_MS = 750L
''',
        "route retention constant",
    )

    replace_once(
        gradle,
        '''        versionCode = 57
        versionName = "5.6.1-gen12-1-wallpaper-lifecycle-zfold7"
''',
        '''        versionCode = 58
        versionName = "5.6.2-gen12-2-route-retention-fence-zfold7"
''',
        "Gen12.2 version",
    )

    require(coordinator, "GEN12_2_ROUTE_RETENTION_FENCE", 1)
    require(coordinator, "Fold7RouteReleaseFence(COVER_ROUTE_RETENTION_MS)", 1)
    require(coordinator, 'reason.startsWith("secondary-release:")', 1)
    require(coordinator, "cancelPendingCoverRelease(\"prewarm:generation=$generation\")", 1)
    require(coordinator, "const val COVER_ROUTE_RETENTION_MS = 750L", 1)
    require(coordinator, "performCoverRelease(", 3)
    require(helper, "generation == ticket.generation", 1)
    require(helper_test, "rapidCloseReversalCancelsOldOpeningRelease", 1)
    require(gradle, "versionCode = 58", 1)
    require(gradle, 'versionName = "5.6.2-gen12-2-route-retention-fence-zfold7"', 1)

    print("GEN12.2 ROUTE RETENTION FENCE: PASS")


if __name__ == "__main__":
    main()
