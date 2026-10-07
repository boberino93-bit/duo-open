#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

TARGET_VERSION_CODE = 54
TARGET_VERSION_NAME = "5.4.7-gen10-oneui9-display-angle-zfold7"
MARKER = "GEN10_7_ONEUI9_DISPLAY_ANGLE"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one literal match, found {count}")
    return text.replace(old, new, 1)


def transform_build_gradle(text: str) -> str:
    if TARGET_VERSION_NAME in text:
        return text
    text = replace_once(text, "versionCode = 53", f"versionCode = {TARGET_VERSION_CODE}", "versionCode")
    text = replace_once(
        text,
        'versionName = "5.4.6-gen10-oneui9-android17-compat-zfold7"',
        f'versionName = "{TARGET_VERSION_NAME}"',
        "versionName",
    )
    return text


def display_inventory_source() -> str:
    return '''package com.duoopen.overlay

import android.hardware.display.DisplayManager
import android.os.Build
import android.view.Display

/**
 * GEN10_7_ONEUI9_DISPLAY_ANGLE
 *
 * Android 17's no-argument DisplayManager inventory excludes disabled logical
 * routes. One UI 9 prewarms the Fold7 cover as a disabled/hidden secondary
 * route first, so the shell can own logical display 1 while the app sees no
 * cover at all. AOSP 17 still supports getDisplays(String) with the platform
 * ALL_INCLUDING_DISABLED category. Use that inventory only on API 37+, and
 * fall back to the ordinary public inventory if an OEM rejects it.
 *
 * This does not grant visual authority by itself. Existing Gen4 shell lease,
 * cycle identity, physical-id, readiness and renderer ownership checks remain
 * authoritative.
 */
internal object Fold7DisplayInventory {
    private const val ALL_INCLUDING_DISABLED =
        "android.hardware.display.category.ALL_INCLUDING_DISABLED"

    fun all(displayManager: DisplayManager): Array<Display> {
        val ordinary = displayManager.displays
        if (Build.VERSION.SDK_INT < 37) return ordinary

        val expanded =
            runCatching {
                displayManager.getDisplays(ALL_INCLUDING_DISABLED)
            }.getOrNull()

        return expanded
            ?.takeIf { it.isNotEmpty() }
            ?: ordinary
    }
}
'''


def transform_coordinator(text: str) -> str:
    if "GEN10_7_TOPOLOGY_ANGLE_HOLD" not in text:
        text = replace_once(
            text,
            "    @Volatile private var gen4RouteRetryCount = 0\n",
            "    @Volatile private var gen4RouteRetryCount = 0\n\n"
            "    /* GEN10_7_TOPOLOGY_ANGLE_HOLD\n"
            "     * One UI 9 can switch the default display before Samsung precise\n"
            "     * geometry has produced its first sample. Never turn that topology\n"
            "     * change into a synthetic 180-degree hinge jump.\n"
            "     */\n"
            "    @Volatile private var lastObservedHingeAngle = Float.NaN\n",
            "coordinator angle hold field",
        )

        text = replace_once(
            text,
            '''    fun onHinge(
        angle: Float,
        observedUptimeMs: Long = SystemClock.uptimeMillis(),
    ) {
        if (!renderOwnershipArmed) return

        val decision =
''',
            '''    fun onHinge(
        angle: Float,
        observedUptimeMs: Long = SystemClock.uptimeMillis(),
    ) {
        if (!renderOwnershipArmed) return

        if (angle.isFinite()) {
            lastObservedHingeAngle = angle
        }

        val decision =
''',
            "coordinator onHinge latch",
        )

        text = replace_once(
            text,
            '''        if (
            decision.actions.isNotEmpty()
        ) {
            DuoDiagnostics.event(
                "early-wake",
''',
            '''        if (
            decision.actions.isNotEmpty()
        ) {
            if (!lastObservedHingeAngle.isFinite()) {
                // DeviceState opening edge is endpoint evidence, not motion
                // geometry. Seed closed and wait for a real hinge producer.
                lastObservedHingeAngle = 0f
            }

            DuoDiagnostics.event(
                "early-wake",
''',
            "early opening closed seed",
        )

        text = replace_once(
            text,
            '''        val angle =
            currentHingeAngle()
                .takeIf { it.isFinite() }
                ?: inferredRestAngle()

        val decision =
            controller.onTopology(
''',
            '''        val sensedAngle =
            currentHingeAngle()

        val angle =
            when {
                sensedAngle.isFinite() -> {
                    lastObservedHingeAngle = sensedAngle
                    sensedAngle
                }

                lastObservedHingeAngle.isFinite() ->
                    lastObservedHingeAngle

                else ->
                    inferredRestAngle()
            }

        val decision =
            controller.onTopology(
''',
            "topology angle authority",
        )

    text = text.replace(
        "for (candidate in displayManager.displays) {",
        "for (candidate in Fold7DisplayInventory.all(displayManager)) {",
        1,
    )

    if "Fold7DisplayInventory.all(displayManager)" not in text:
        raise RuntimeError("coordinator display inventory replacement failed")

    return text


def transform_gen3(text: str) -> str:
    text = replace_once(
        text,
        '''        val display =
            displayManager.getDisplay(
                hostBinding.logicalDisplayId
            ) ?: return
''',
        '''        val display =
            currentCoverDisplay()
                ?.takeIf {
                    it.displayId ==
                        hostBinding.logicalDisplayId
                }
                ?: return
''',
        "Gen3 direct hidden-display reuse",
    )

    text = replace_once(
        text,
        '''    private fun currentCoverDisplay(): Display? =
        displayManager.displays
            .firstOrNull { display ->
''',
        '''    private fun currentCoverDisplay(): Display? =
        Fold7DisplayInventory
            .all(displayManager)
            .firstOrNull { display ->
''',
        "Gen3 all-including-disabled inventory",
    )
    return text


def transform_angle_authority(text: str) -> str:
    if "coarsePublicMaxAgeMs" not in text:
        text = replace_once(
            text,
            '''internal class Fold7AngleAuthority(
    private val preciseMaxAgeMs: Long = DEFAULT_PRECISE_MAX_AGE_MS,
    private val publicMaxAgeMs: Long = DEFAULT_PUBLIC_MAX_AGE_MS,
) {''',
            '''internal class Fold7AngleAuthority(
    private val preciseMaxAgeMs: Long = DEFAULT_PRECISE_MAX_AGE_MS,
    private val publicMaxAgeMs: Long = DEFAULT_PUBLIC_MAX_AGE_MS,
    private val coarsePublicMaxAgeMs: Long = DEFAULT_COARSE_PUBLIC_MAX_AGE_MS,
) {''',
            "angle authority constructor",
        )

        text = replace_once(
            text,
            '''        val ageMs = receivedUptimeMs - observedUptimeMs
        if (ageMs < 0L || ageMs > publicMaxAgeMs) {
            return Decision(
                accepted = false,
                dropReason = "stale-public-sample",
                sourceAgeMs = ageMs,
            )
        }

        val next = angle.coerceIn(0f, 180f)
''',
            '''        val ageMs = receivedUptimeMs - observedUptimeMs
        val maxAgeMs =
            if (coarse) coarsePublicMaxAgeMs else publicMaxAgeMs

        if (ageMs < 0L || ageMs > maxAgeMs) {
            return Decision(
                accepted = false,
                dropReason =
                    if (coarse) {
                        "stale-coarse-public-sample"
                    } else {
                        "stale-public-sample"
                    },
                sourceAgeMs = ageMs,
            )
        }

        val next = angle.coerceIn(0f, 180f)
''',
            "public ingress age budget",
        )

        text = replace_once(
            text,
            '''        val ageMs = nowUptimeMs - candidate.observedUptimeMs
        if (ageMs < 0L || ageMs > publicMaxAgeMs) {
            publicCandidate = null
            return Decision(
                accepted = false,
                dropReason = "public-shadow-stale",
                sourceAgeMs = ageMs,
            )
        }

        val sourceChanged = currentSource != candidate.source
''',
            '''        val ageMs = nowUptimeMs - candidate.observedUptimeMs
        val maxAgeMs =
            if (candidate.coarse) {
                coarsePublicMaxAgeMs
            } else {
                publicMaxAgeMs
            }

        if (ageMs < 0L || ageMs > maxAgeMs) {
            publicCandidate = null
            return Decision(
                accepted = false,
                dropReason =
                    if (candidate.coarse) {
                        "coarse-public-shadow-stale"
                    } else {
                        "public-shadow-stale"
                    },
                sourceAgeMs = ageMs,
            )
        }

        val sourceChanged = currentSource != candidate.source
''',
            "public shadow promotion budget",
        )

        text = replace_once(
            text,
            '''        const val DEFAULT_PRECISE_MAX_AGE_MS = 192L
        const val DEFAULT_PUBLIC_MAX_AGE_MS = 3_000L
        private const val CHANGE_EPSILON_DEG = 0.10f
''',
            '''        const val DEFAULT_PRECISE_MAX_AGE_MS = 192L
        const val DEFAULT_PUBLIC_MAX_AGE_MS = 3_000L

        /* GEN10_7_ONEUI9_DISPLAY_ANGLE
         * Field evidence on One UI 9 showed endpoint-only PUBLIC_STANDARD
         * shadows being promoted 174..1976 ms after observation and reversing
         * active precise motion. 160 ms preserves the prior 143 ms fresh-shadow
         * test case while rejecting every observed stale reversal in the bundle.
         */
        const val DEFAULT_COARSE_PUBLIC_MAX_AGE_MS = 160L

        private const val CHANGE_EPSILON_DEG = 0.10f
''',
            "coarse public age constant",
        )

    return text


def transform_angle_test(text: str) -> str:
    if "delayedCoarseShadowCannotReversePreciseMotion" in text:
        return text

    anchor = '''    @Test
    fun preciseExpiryWithoutFallbackBecomesUnknown() {
'''
    test = '''    @Test
    fun delayedCoarseShadowCannotReversePreciseMotion() {
        val a =
            Fold7AngleAuthority(
                preciseMaxAgeMs = 192L,
                coarsePublicMaxAgeMs = 160L,
            )

        a.startPreciseSession(11L, 1_000L)
        a.offerPrecise(11L, 1L, 131f, 1_000L, 1_001L)

        // One UI 9 can retain an endpoint-only 180-degree public shadow while
        // Samsung precise geometry continues to own the real closing motion.
        val shadow =
            a.offerPublic(
                source = Fold7AngleAuthority.Source.PUBLIC_STANDARD,
                angle = 180f,
                observedUptimeMs = 1_010L,
                receivedUptimeMs = 1_010L,
                coarse = true,
            )
        assertNull(shadow.output)

        val expired =
            a.expirePrecise(
                1_193L,
                "precise-lease-expired",
            )

        assertNull(expired.output)
        assertEquals(
            Fold7AngleAuthority.Source.NONE,
            a.snapshot(1_193L).source,
        )
        assertEquals(131f, a.snapshot(1_193L).angle)
    }

'''
    return replace_once(text, anchor, test + anchor, "coarse public regression test")


def verify(repo: Path) -> None:
    build = read(repo / "app/build.gradle.kts")
    inventory = read(repo / "app/src/full/java/com/duoopen/overlay/Fold7DisplayInventory.kt")
    coordinator = read(repo / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt")
    gen3 = read(repo / "app/src/full/java/com/duoopen/overlay/Fold7Gen3VisualCoordinator.kt")
    angle = read(repo / "app/src/main/java/com/duoopen/fold/Fold7AngleAuthority.kt")
    angle_test = read(repo / "app/src/test/java/com/duoopen/fold/Fold7AngleAuthorityTest.kt")
    panel = read(repo / "app/src/full/java/com/duoopen/overlay/PanelEngine.kt")
    shell = read(repo / "app/src/full/java/com/duoopen/shell/DuoShellService.kt")

    required = {
        "version": TARGET_VERSION_NAME in build and f"versionCode = {TARGET_VERSION_CODE}" in build,
        "compile37": "compileSdk = 37" in build and "targetSdk = 35" in build,
        "inventory-marker": MARKER in inventory,
        "inventory-category": "android.hardware.display.category.ALL_INCLUDING_DISABLED" in inventory,
        "coordinator-inventory": "for (candidate in Fold7DisplayInventory.all(displayManager))" in coordinator,
        "angle-hold": "GEN10_7_TOPOLOGY_ANGLE_HOLD" in coordinator and "lastObservedHingeAngle" in coordinator,
        "gen3-inventory": "Fold7DisplayInventory\n            .all(displayManager)" in gen3,
        "gen3-no-refetch": "currentCoverDisplay()\n                ?.takeIf" in gen3,
        "coarse-budget": "DEFAULT_COARSE_PUBLIC_MAX_AGE_MS = 160L" in angle,
        "coarse-test": "delayedCoarseShadowCannotReversePreciseMotion" in angle_test,
        "secure-fail-open": "capture-protected-or-black" in panel,
        "api37-private-contract": "GEN10_6_API37_PRIVATE_API_LINT_CONTRACT" in shell,
    }

    missing = [name for name, ok in required.items() if not ok]
    if missing:
        raise RuntimeError(f"Gen10.7 verification failed: {missing}")

    if 'targetSdk = 37' in build:
        raise RuntimeError("Gen10.7 must retain targetSdk 35 for the One UI 9 bridge")

    print("Gen10.7 One UI 9 display inventory + angle authority applied and verified")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()

    build = repo / "app/build.gradle.kts"
    coordinator = repo / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"
    gen3 = repo / "app/src/full/java/com/duoopen/overlay/Fold7Gen3VisualCoordinator.kt"
    angle = repo / "app/src/main/java/com/duoopen/fold/Fold7AngleAuthority.kt"
    angle_test = repo / "app/src/test/java/com/duoopen/fold/Fold7AngleAuthorityTest.kt"

    write(build, transform_build_gradle(read(build)))
    write(
        repo / "app/src/full/java/com/duoopen/overlay/Fold7DisplayInventory.kt",
        display_inventory_source(),
    )
    write(coordinator, transform_coordinator(read(coordinator)))
    write(gen3, transform_gen3(read(gen3)))
    write(angle, transform_angle_authority(read(angle)))
    write(angle_test, transform_angle_test(read(angle_test)))

    verify(repo)


if __name__ == "__main__":
    main()
