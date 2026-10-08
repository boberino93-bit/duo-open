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

    gate = root / "app/src/full/java/com/duoopen/overlay/Fold7CoverLeaseSnapshotGate.kt"
    coordinator = root / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"
    test = root / "app/src/test/java/com/duoopen/overlay/Fold7CoverLeaseStaleReceiptTest.kt"

    replace_once(
        gate,
        '''        val routeReady: Boolean,
        val ok: Boolean,
        val ownerServiceEpoch: Long = 0L,
''',
        '''        val routeReady: Boolean,
        val ok: Boolean,
        val stale: Boolean = false,
        val ownerServiceEpoch: Long = 0L,
''',
        "snapshot stale field",
    )

    replace_once(
        gate,
        '''        if (snapshot.connectionEpoch != connectionEpoch) {
            return rejected("stale-connection-epoch")
        }
        if (snapshot.shellSession <= 0L) {
''',
        '''        if (snapshot.connectionEpoch != connectionEpoch) {
            return rejected("stale-connection-epoch")
        }
        if (snapshot.stale) {
            return rejected("shell-marked-stale")
        }
        if (snapshot.shellSession <= 0L) {
''',
        "reject stale receipt before revision adoption",
    )

    replace_once(
        coordinator,
        '''                routeReady = result.getBoolean("routeReady", false),
                ok = result.getBoolean("ok", false),
            )
''',
        '''                routeReady = result.getBoolean("routeReady", false),
                ok = result.getBoolean("ok", false),
                stale = result.getBoolean("stale", false),
            )
''',
        "map shell stale receipt bit",
    )

    test.parent.mkdir(parents=True, exist_ok=True)
    test.write_text(
        '''package com.duoopen.overlay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class Fold7CoverLeaseStaleReceiptTest {
    private fun snapshot(
        revision: Long,
        stale: Boolean,
    ) =
        Fold7CoverLeaseSnapshotGate.Snapshot(
            connectionEpoch = 7L,
            shellSession = 99L,
            shellRevision = revision,
            leaseState = "IDLE",
            leaseId = 0L,
            leaseEpoch = 0L,
            ownerGeneration = -1L,
            physicalDisplayId = -1L,
            targetLogicalId = -1,
            physicalLeaseHeld = false,
            routeReady = false,
            ok = !stale,
            stale = stale,
        )

    @Test
    fun staleShellReceiptDoesNotAdvanceAcceptedRevision() {
        val gate = Fold7CoverLeaseSnapshotGate()
        gate.onConnectionEpoch(7L)

        val first = gate.accept(snapshot(revision = 10L, stale = false))
        assertTrue(first.accepted)

        val stale = gate.accept(snapshot(revision = 11L, stale = true))
        assertFalse(stale.accepted)
        assertEquals("shell-marked-stale", stale.reason)
        assertEquals(10L, stale.snapshot?.shellRevision)

        // If revision 11 had been adopted, this valid revision 11 receipt would
        // now be rejected as duplicate. Accepting it proves stale receipts do
        // not advance app-side authority.
        val valid = gate.accept(snapshot(revision = 11L, stale = false))
        assertTrue(valid.accepted)
        assertEquals(11L, valid.snapshot?.shellRevision)
    }
}
'''
    )

    require(gate, "val stale: Boolean = false", 1)
    require(gate, 'return rejected("shell-marked-stale")', 1)
    require(coordinator, 'stale = result.getBoolean("stale", false)', 1)
    require(test, "staleShellReceiptDoesNotAdvanceAcceptedRevision", 1)

    print("GEN12.2 STALE RECEIPT GATE: PASS")


if __name__ == "__main__":
    main()
