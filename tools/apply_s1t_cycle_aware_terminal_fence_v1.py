#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

GRADLE = Path("app/build.gradle.kts")
AUTHORITY = Path("app/src/full/java/com/duoopen/shell/Fold7PanelAuthorityGen4.kt")
AUTHORITY_TEST = Path("app/src/test/java/com/duoopen/shell/Fold7PanelAuthorityGen4Test.kt")
SHELL = Path("app/src/full/java/com/duoopen/shell/DuoShellService.kt")

MARKER = "S1T_CYCLE_AWARE_NATIVE_COVER_V1"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_gradle(text: str) -> str:
    if 'versionName = "5.1.0-beta2-zfold7-s1t"' in text:
        return text
    text = one(text, "        versionCode = 53\n", "        versionCode = 54\n", "versionCode")
    return one(
        text,
        '        versionName = "5.1.0-beta2-zfold7-s1s"\n',
        '        versionName = "5.1.0-beta2-zfold7-s1t"\n',
        "versionName",
    )


def transform_authority(text: str) -> str:
    if MARKER in text:
        return text

    text = one(
        text,
        "        val routeReady: Boolean,\n    )\n",
        "        val routeReady: Boolean,\n        val terminalNativeCoverCloseCycleId: Long,\n    )\n",
        "snapshot terminal close-cycle field",
    )
    text = one(
        text,
        "            routeReady = routeReady,\n        )\n",
        "            routeReady = routeReady,\n            terminalNativeCoverCloseCycleId = terminalNativeCoverCloseCycleId,\n        )\n",
        "snapshot terminal close-cycle export",
    )
    text = one(
        text,
        "    private var routeReady = false\n",
        "    private var routeReady = false\n    // S1T_CYCLE_AWARE_NATIVE_COVER_V1: remember the highest close-cycle that\n    // legitimately reached native cover. A late mutation from that cycle stays\n    // fenced, while a strictly newer close cycle is allowed to prepare again.\n    private var terminalNativeCoverCloseCycleId = 0L\n",
        "terminal close-cycle state",
    )

    # New daemon/app service lifetimes restart close-cycle numbering.
    text = one(
        text,
        "        routeReady = false\n        phase = if (nativeCover) Phase.NATIVE_COVER else Phase.INNER_NATIVE\n",
        "        routeReady = false\n        terminalNativeCoverCloseCycleId = 0L\n        phase = if (nativeCover) Phase.NATIVE_COVER else Phase.INNER_NATIVE\n",
        "recovery resets terminal close-cycle",
    )
    text = one(
        text,
        "        routeReady = false\n        recoveryReady = true\n        phase = if (nativeCover) Phase.NATIVE_COVER else Phase.INNER_NATIVE\n",
        "        routeReady = false\n        terminalNativeCoverCloseCycleId = 0L\n        recoveryReady = true\n        phase = if (nativeCover) Phase.NATIVE_COVER else Phase.INNER_NATIVE\n",
        "service rollover resets terminal close-cycle",
    )

    old_fence = '''        // S1S_BETA_CONVERGENCE_V1: NATIVE_COVER is terminal for a close
        // cycle. A delayed same-service prepare must never resurrect the
        // secondary route after Samsung owns the closed cover again.
        if (phase == Phase.NATIVE_COVER) {
            return false
        }

        this.owner = owner
'''
    new_fence = '''        // S1T_CYCLE_AWARE_NATIVE_COVER_V1
        // S1S correctly fenced delayed mutations after NATIVE_COVER, but the
        // phase-only guard also blocked every later legitimate close. Fence by
        // close-cycle identity instead: completed/older cycles stay rejected;
        // a strictly newer close cycle may prepare normally.
        if (
            phase == Phase.NATIVE_COVER &&
            terminalNativeCoverCloseCycleId > 0L &&
            owner.closeCycleId <= terminalNativeCoverCloseCycleId
        ) {
            return false
        }

        this.owner = owner
'''
    text = one(text, old_fence, new_fence, "replace phase-only terminal fence")

    old_release = '''        owner = null
        physicalDisplayId = null
        logicalDisplayId = null
        physicalHeld = false
        routeReady = false
        phase = if (nativeCover) Phase.NATIVE_COVER else Phase.INNER_NATIVE
'''
    new_release = '''        val releasedOwner = owner
        owner = null
        physicalDisplayId = null
        logicalDisplayId = null
        physicalHeld = false
        routeReady = false
        if (nativeCover && releasedOwner != null) {
            terminalNativeCoverCloseCycleId =
                maxOf(terminalNativeCoverCloseCycleId, releasedOwner.closeCycleId)
        }
        phase = if (nativeCover) Phase.NATIVE_COVER else Phase.INNER_NATIVE
'''
    text = one(text, old_release, new_release, "record completed native-cover cycle")

    old_mark = '''    fun markNativeCover() {
        if (!recoveryReady) return
        owner = null
        physicalDisplayId = null
        logicalDisplayId = null
        physicalHeld = false
        routeReady = false
        phase = Phase.NATIVE_COVER
    }
'''
    new_mark = '''    fun markNativeCover() {
        if (!recoveryReady) return
        owner?.let {
            terminalNativeCoverCloseCycleId =
                maxOf(terminalNativeCoverCloseCycleId, it.closeCycleId)
        }
        owner = null
        physicalDisplayId = null
        logicalDisplayId = null
        physicalHeld = false
        routeReady = false
        phase = Phase.NATIVE_COVER
    }
'''
    text = one(text, old_mark, new_mark, "mark native cover records owner cycle")
    return text


def transform_authority_test(text: str) -> str:
    if "newerCloseCycleMayPrepareAfterNativeCover" in text:
        return text

    old = '''    @Test
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
    new = '''    @Test
    fun nativeCoverRejectsLatePrepareFromCompletedCycle() {
        val m = Fold7PanelAuthorityGen4()
        m.completeRecovery(nativeCover = false)
        assertTrue(m.admit(100, 1).accepted)
        assertTrue(
            m.beginPrepare(
                Fold7PanelAuthorityGen4.Owner(100, 1, 12),
                1,
            )
        )
        m.completePrepare(1, true, 222, 7, true)
        assertTrue(m.admit(100, 2).accepted)
        m.beginRelease(100, 2)
        m.completeRelease(2, success = true, nativeCover = true)
        assertEquals(1L, m.snapshot().terminalNativeCoverCloseCycleId)

        assertTrue(m.admit(100, 3).accepted)
        val accepted =
            m.beginPrepare(
                Fold7PanelAuthorityGen4.Owner(100, 1, 99),
                3,
            )
        assertFalse(accepted)
        m.completePrepare(3, true, 333, 8, true)

        assertEquals(Fold7PanelAuthorityGen4.Phase.NATIVE_COVER, m.snapshot().phase)
        assertFalse(m.snapshot().routeReady)
        assertFalse(m.snapshot().physicalHeld)
        assertEquals(null, m.snapshot().owner)
    }

    @Test
    fun newerCloseCycleMayPrepareAfterNativeCover() {
        val m = Fold7PanelAuthorityGen4()
        m.completeRecovery(nativeCover = false)
        assertTrue(m.admit(100, 1).accepted)
        assertTrue(
            m.beginPrepare(
                Fold7PanelAuthorityGen4.Owner(100, 1, 12),
                1,
            )
        )
        m.completePrepare(1, true, 222, 7, true)
        assertTrue(m.admit(100, 2).accepted)
        m.beginRelease(100, 2)
        m.completeRelease(2, success = true, nativeCover = true)

        assertTrue(m.admit(100, 3).accepted)
        val accepted =
            m.beginPrepare(
                Fold7PanelAuthorityGen4.Owner(100, 2, 20),
                3,
            )
        assertTrue(accepted)
        assertEquals(Fold7PanelAuthorityGen4.Phase.COVER_PREPARING, m.snapshot().phase)
        assertEquals(2L, m.snapshot().owner?.closeCycleId)
        assertEquals(1L, m.snapshot().terminalNativeCoverCloseCycleId)
    }
'''
    return one(text, old, new, "replace S1S terminal-fence test with cycle-aware tests")


def transform_shell(text: str) -> str:
    if "gen4TerminalCloseCycleId" in text:
        return text
    return one(
        text,
        '''            putLong("gen4IntentSequence", snapshot.lastIntentSequence)

            putLong("shellSession", shellSession)
''',
        '''            putLong("gen4IntentSequence", snapshot.lastIntentSequence)
            putLong("gen4TerminalCloseCycleId", snapshot.terminalNativeCoverCloseCycleId)

            putLong("shellSession", shellSession)
''',
        "Gen4 terminal close-cycle diagnostics",
    )


def validate(gradle: str, authority: str, tests: str, shell: str) -> None:
    required = (
        (gradle, ['versionCode = 54', 'versionName = "5.1.0-beta2-zfold7-s1t"']),
        (authority, [MARKER, "terminalNativeCoverCloseCycleId", "owner.closeCycleId <= terminalNativeCoverCloseCycleId"]),
        (tests, ["nativeCoverRejectsLatePrepareFromCompletedCycle", "newerCloseCycleMayPrepareAfterNativeCover"]),
        (shell, ["gen4TerminalCloseCycleId"]),
    )
    for text, needles in required:
        for needle in needles:
            if needle not in text:
                raise RuntimeError(f"missing S1T invariant: {needle}")


def apply(repo: Path, check: bool) -> None:
    paths = [repo / GRADLE, repo / AUTHORITY, repo / AUTHORITY_TEST, repo / SHELL]
    if not all(path.exists() for path in paths):
        raise RuntimeError("required S1S materialized sources are missing")

    before = [path.read_text(encoding="utf-8") for path in paths]
    after = [
        transform_gradle(before[0]),
        transform_authority(before[1]),
        transform_authority_test(before[2]),
        transform_shell(before[3]),
    ]
    validate(*after)
    if not check:
        for path, content in zip(paths, after):
            path.write_text(content, encoding="utf-8")


def self_test() -> None:
    authority = '''    data class Snapshot(\n        val routeReady: Boolean,\n    )\n    private var routeReady = false\n    fun snapshot() = Snapshot(\n            routeReady = routeReady,\n        )\n    fun completeRecovery(nativeCover: Boolean) {\n        routeReady = false\n        phase = if (nativeCover) Phase.NATIVE_COVER else Phase.INNER_NATIVE\n    }\n    fun completeServiceRollover(nativeCover: Boolean) {\n        routeReady = false\n        recoveryReady = true\n        phase = if (nativeCover) Phase.NATIVE_COVER else Phase.INNER_NATIVE\n    }\n        // S1S_BETA_CONVERGENCE_V1: NATIVE_COVER is terminal for a close\n        // cycle. A delayed same-service prepare must never resurrect the\n        // secondary route after Samsung owns the closed cover again.\n        if (phase == Phase.NATIVE_COVER) {\n            return false\n        }\n\n        this.owner = owner\n        owner = null\n        physicalDisplayId = null\n        logicalDisplayId = null\n        physicalHeld = false\n        routeReady = false\n        phase = if (nativeCover) Phase.NATIVE_COVER else Phase.INNER_NATIVE\n    fun markNativeCover() {\n        if (!recoveryReady) return\n        owner = null\n        physicalDisplayId = null\n        logicalDisplayId = null\n        physicalHeld = false\n        routeReady = false\n        phase = Phase.NATIVE_COVER\n    }\n'''
    out = transform_authority(authority)
    assert MARKER in out
    assert "owner.closeCycleId <= terminalNativeCoverCloseCycleId" in out
    print("S1T cycle-aware terminal fence model: PASS")


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
    if args.check:
        print("S1T cycle-aware terminal fence: source shape verified")
    else:
        print("S1T cycle-aware terminal fence: applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
