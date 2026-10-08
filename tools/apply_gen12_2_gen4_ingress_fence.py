#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

TARGET_VERSION_CODE = 58
TARGET_VERSION_NAME = "5.6.2-gen12-2-gen4-ingress-fence-zfold7"
MARKER = "GEN12_2_GEN4_INGRESS_FENCE"
SUPERSEDED = "gen4-intent-superseded-before-route-mutation"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        fail(f"{label}: expected exactly one anchor in {path}, found {count}")
    path.write_text(text.replace(old, new, 1))


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

    shell = root / "app/src/full/java/com/duoopen/shell/DuoShellService.kt"
    fence = root / "app/src/full/java/com/duoopen/shell/Fold7Gen4IngressFence.kt"
    fence_test = root / "app/src/test/java/com/duoopen/shell/Fold7Gen4IngressFenceTest.kt"
    gradle = root / "app/build.gradle.kts"

    if not shell.is_file():
        fail(f"missing reconstructed shell: {shell}")

    fence.parent.mkdir(parents=True, exist_ok=True)
    fence.write_text(
        '''package com.duoopen.shell

/**
 * GEN12_2_GEN4_INGRESS_FENCE
 *
 * Binder ingress is allowed to observe a newer semantic panel intent before
 * that intent reaches the single-threaded hardware mutation executor. This
 * closes the queueing hole where an older release could still look current
 * simply because it was ahead of the newer prepare in that executor.
 *
 * Ordering is lexicographic by service epoch then intent sequence. A new app
 * service lifetime therefore supersedes every queued intent from the previous
 * lifetime even though its local intent sequence restarts from one.
 */
internal class Fold7Gen4IngressFence {
    data class Ticket(
        val serviceEpoch: Long,
        val intentSequence: Long,
    )

    private var latestServiceEpoch = 0L
    private var latestIntentSequence = 0L

    @Synchronized
    fun observe(
        serviceEpoch: Long,
        intentSequence: Long,
    ): Ticket {
        if (serviceEpoch <= 0L || intentSequence <= 0L) {
            return Ticket(serviceEpoch, intentSequence)
        }

        when {
            serviceEpoch > latestServiceEpoch -> {
                latestServiceEpoch = serviceEpoch
                latestIntentSequence = intentSequence
            }

            serviceEpoch == latestServiceEpoch &&
                intentSequence > latestIntentSequence -> {
                latestIntentSequence = intentSequence
            }
        }

        return Ticket(serviceEpoch, intentSequence)
    }

    @Synchronized
    fun isCurrent(
        serviceEpoch: Long,
        intentSequence: Long,
    ): Boolean =
        serviceEpoch > 0L &&
            intentSequence > 0L &&
            serviceEpoch == latestServiceEpoch &&
            intentSequence == latestIntentSequence

    @Synchronized
    fun snapshot(): Ticket =
        Ticket(
            serviceEpoch = latestServiceEpoch,
            intentSequence = latestIntentSequence,
        )
}
'''
    )

    fence_test.parent.mkdir(parents=True, exist_ok=True)
    fence_test.write_text(
        '''package com.duoopen.shell

import org.junit.Assert.assertFalse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7Gen4IngressFenceTest {
    @Test
    fun newerIntentInvalidatesOlderQueuedMutationBeforeExecution() {
        val fence = Fold7Gen4IngressFence()

        fence.observe(serviceEpoch = 10L, intentSequence = 66L)
        assertTrue(fence.isCurrent(10L, 66L))

        // Representative field race: close generation arrives while an older
        // release is still waiting to execute in the daemon mutation lane.
        fence.observe(serviceEpoch = 10L, intentSequence = 71L)

        assertFalse(fence.isCurrent(10L, 66L))
        assertTrue(fence.isCurrent(10L, 71L))
    }

    @Test
    fun lateOlderIngressCannotMoveWatermarkBackward() {
        val fence = Fold7Gen4IngressFence()
        fence.observe(3L, 12L)
        fence.observe(3L, 9L)

        assertTrue(fence.isCurrent(3L, 12L))
        assertFalse(fence.isCurrent(3L, 9L))
    }

    @Test
    fun newServiceEpochSupersedesOldServiceEvenWhenSequenceRestarts() {
        val fence = Fold7Gen4IngressFence()
        fence.observe(100L, 900L)
        fence.observe(101L, 1L)

        assertFalse(fence.isCurrent(100L, 900L))
        assertTrue(fence.isCurrent(101L, 1L))
        assertEquals(
            Fold7Gen4IngressFence.Ticket(101L, 1L),
            fence.snapshot(),
        )
    }

    @Test
    fun olderServiceCannotSupersedeCurrentService() {
        val fence = Fold7Gen4IngressFence()
        fence.observe(5L, 4L)
        fence.observe(4L, 500L)

        assertTrue(fence.isCurrent(5L, 4L))
        assertFalse(fence.isCurrent(4L, 500L))
    }
}
'''
    )

    replace_once(
        shell,
        '''    private val gen4PanelAuthority =
        Fold7PanelAuthorityGen4()

    private val shellSession =
''',
        '''    private val gen4PanelAuthority =
        Fold7PanelAuthorityGen4()

    /*
     * GEN12_2_GEN4_INGRESS_FENCE
     * Observe semantic Gen4 intent ordering before work enters the serialized
     * hardware lane. Daemon authority remains single-writer; only stale queued
     * work is rejected earlier.
     */
    private val gen4IngressFence =
        Fold7Gen4IngressFence()

    private val shellSession =
''',
        "Gen4 ingress fence field",
    )

    old_handler = '''            ShellProtocol.COVER_PANEL_GEN4 -> {
                val operation = data.readInt()
                val serviceEpoch = data.readLong()
                val closeCycleId = data.readLong()
                val transitionGeneration = data.readLong()
                val intentSequence = data.readLong()
                val reason = data.readString() ?: "unspecified"
                val identity = clearCallingIdentity()

                val result =
                    try {
                        runCoverMutation {
                            handleGen4PanelCommand(
                                operation = operation,
                                serviceEpoch = serviceEpoch,
                                closeCycleId = closeCycleId,
                                transitionGeneration = transitionGeneration,
                                intentSequence = intentSequence,
                                reason = reason,
                            )
                        }
                    } catch (t: Throwable) {
                        failureBundle("cover-panel-gen4", t)
                    } finally {
                        restoreCallingIdentity(identity)
                    }

                out.writeNoException()
                out.writeBundle(result)
            }
'''

    new_handler = '''            ShellProtocol.COVER_PANEL_GEN4 -> {
                val operation = data.readInt()
                val serviceEpoch = data.readLong()
                val closeCycleId = data.readLong()
                val transitionGeneration = data.readLong()
                val intentSequence = data.readLong()
                val reason = data.readString() ?: "unspecified"

                // GEN12_2_GEN4_INGRESS_FENCE: this happens on Binder ingress,
                // before an older request ahead of us can enter hardware work.
                gen4IngressFence.observe(
                    serviceEpoch = serviceEpoch,
                    intentSequence = intentSequence,
                )

                val identity = clearCallingIdentity()

                val result =
                    try {
                        runCoverMutation {
                            if (
                                !gen4IngressFence.isCurrent(
                                    serviceEpoch = serviceEpoch,
                                    intentSequence = intentSequence,
                                )
                            ) {
                                gen4PanelBundle(
                                    operation = "ingress-superseded:$reason",
                                    ok = false,
                                    stale = true,
                                    decision = "superseded-before-execution",
                                    error = GEN4_INGRESS_SUPERSEDED,
                                )
                            } else {
                                handleGen4PanelCommand(
                                    operation = operation,
                                    serviceEpoch = serviceEpoch,
                                    closeCycleId = closeCycleId,
                                    transitionGeneration = transitionGeneration,
                                    intentSequence = intentSequence,
                                    reason = reason,
                                )
                            }
                        }
                    } catch (t: Throwable) {
                        failureBundle("cover-panel-gen4", t)
                    } finally {
                        restoreCallingIdentity(identity)
                    }

                out.writeNoException()
                out.writeBundle(result)
            }
'''
    replace_once(shell, old_handler, new_handler, "Gen4 Binder ingress fence")

    old_normalize_sig = '''    private fun normalizeGen4SecondaryRoute(
        reason: String,
    ): Gen4CleanupResult {
        var lastError: String? = null

        repeat(GEN4_RECOVERY_ATTEMPTS) { attempt ->
            val topology = coverLeaseTopology()
'''

    new_normalize_sig = '''    private fun normalizeGen4SecondaryRoute(
        reason: String,
        expectedServiceEpoch: Long? = null,
        expectedIntentSequence: Long? = null,
    ): Gen4CleanupResult {
        var lastError: String? = null

        fun superseded(): Boolean =
            expectedServiceEpoch != null &&
                expectedIntentSequence != null &&
                !gen4IngressFence.isCurrent(
                    serviceEpoch = expectedServiceEpoch,
                    intentSequence = expectedIntentSequence,
                )

        repeat(GEN4_RECOVERY_ATTEMPTS) { attempt ->
            if (superseded()) {
                return Gen4CleanupResult(
                    ok = false,
                    nativeCover = false,
                    error = GEN4_INGRESS_SUPERSEDED,
                )
            }

            val topology = coverLeaseTopology()
'''
    replace_once(shell, old_normalize_sig, new_normalize_sig, "guard route normalization loop")

    replace_once(
        shell,
        '''                val reset = secondaryDisplayCommand(false, logicalId)
                if (reset.getBoolean("ok", false)) {
''',
        '''                if (superseded()) {
                    return Gen4CleanupResult(
                        ok = false,
                        nativeCover = false,
                        error = GEN4_INGRESS_SUPERSEDED,
                    )
                }

                val reset = secondaryDisplayCommand(false, logicalId)
                if (reset.getBoolean("ok", false)) {
''',
        "guard immediately before destructive secondary reset",
    )

    old_return = '''    private fun returnCoverPanelGen4(
        serviceEpoch: Long,
        intentSequence: Long,
        reason: String,
    ): Bundle {
        gen4PanelAuthority.beginRelease(
            serviceEpoch = serviceEpoch,
            intentSequence = intentSequence,
        )

        val cleanup =
            normalizeGen4SecondaryRoute(
                "return:$reason"
            )

        gen4PanelAuthority.completeRelease(
            intentSequence = intentSequence,
            success = cleanup.ok,
            nativeCover = cleanup.nativeCover,
        )

        return gen4PanelBundle(
            operation = "return:$reason",
            ok = cleanup.ok,
            decision = if (cleanup.ok) "native-authority-restored" else "release-pending",
            error = cleanup.error,
        )
    }
'''

    new_return = '''    private fun returnCoverPanelGen4(
        serviceEpoch: Long,
        intentSequence: Long,
        reason: String,
    ): Bundle {
        if (
            !gen4IngressFence.isCurrent(
                serviceEpoch = serviceEpoch,
                intentSequence = intentSequence,
            )
        ) {
            return gen4PanelBundle(
                operation = "return-superseded:$reason",
                ok = false,
                stale = true,
                decision = "superseded-before-release",
                error = GEN4_INGRESS_SUPERSEDED,
            )
        }

        gen4PanelAuthority.beginRelease(
            serviceEpoch = serviceEpoch,
            intentSequence = intentSequence,
        )

        if (
            !gen4IngressFence.isCurrent(
                serviceEpoch = serviceEpoch,
                intentSequence = intentSequence,
            )
        ) {
            return gen4PanelBundle(
                operation = "return-superseded:$reason",
                ok = false,
                stale = true,
                decision = "superseded-before-cleanup",
                error = GEN4_INGRESS_SUPERSEDED,
            )
        }

        val cleanup =
            normalizeGen4SecondaryRoute(
                reason = "return:$reason",
                expectedServiceEpoch = serviceEpoch,
                expectedIntentSequence = intentSequence,
            )

        if (cleanup.error == GEN4_INGRESS_SUPERSEDED) {
            return gen4PanelBundle(
                operation = "return-superseded:$reason",
                ok = false,
                stale = true,
                decision = "superseded-during-cleanup",
                error = cleanup.error,
            )
        }

        gen4PanelAuthority.completeRelease(
            intentSequence = intentSequence,
            success = cleanup.ok,
            nativeCover = cleanup.nativeCover,
        )

        return gen4PanelBundle(
            operation = "return:$reason",
            ok = cleanup.ok,
            decision = if (cleanup.ok) "native-authority-restored" else "release-pending",
            error = cleanup.error,
        )
    }
'''
    replace_once(shell, old_return, new_return, "generation-fence Gen4 release")

    replace_once(
        shell,
        '''        const val GEN4_RECOVERY_ATTEMPTS = 4
        const val GEN4_RECOVERY_RETRY_MS = 50L
''',
        '''        const val GEN4_RECOVERY_ATTEMPTS = 4
        const val GEN4_RECOVERY_RETRY_MS = 50L
        const val GEN4_INGRESS_SUPERSEDED =
            "gen4-intent-superseded-before-route-mutation"
''',
        "Gen4 ingress superseded marker",
    )

    replace_once(
        gradle,
        '''        versionCode = 57
        versionName = "5.6.1-gen12-1-wallpaper-lifecycle-zfold7"
''',
        f'''        versionCode = {TARGET_VERSION_CODE}
        versionName = "{TARGET_VERSION_NAME}"
''',
        "Gen12.2 version",
    )

    require(shell, MARKER, 2)
    require(shell, "gen4IngressFence.observe(", 1)
    require(shell, "superseded-before-execution", 1)
    require(shell, "superseded-before-release", 1)
    require(shell, "superseded-before-cleanup", 1)
    require(shell, "superseded-during-cleanup", 1)
    require(shell, "expectedIntentSequence: Long? = null", 1)
    require(shell, "GEN4_INGRESS_SUPERSEDED", 7)
    require(fence, "class Fold7Gen4IngressFence", 1)
    require(fence_test, "newerIntentInvalidatesOlderQueuedMutationBeforeExecution", 1)
    require(gradle, f"versionCode = {TARGET_VERSION_CODE}", 1)
    require(gradle, f'versionName = "{TARGET_VERSION_NAME}"', 1)

    print("GEN12.2 GEN4 INGRESS FENCE: PASS")


if __name__ == "__main__":
    main()
