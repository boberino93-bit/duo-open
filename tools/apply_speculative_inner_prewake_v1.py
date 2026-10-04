#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

GRADLE = Path("app/build.gradle.kts")
PROTOCOL = Path("app/src/full/java/com/duoopen/shell/ShellProtocol.kt")
SHELL = Path("app/src/full/java/com/duoopen/shell/DuoShellService.kt")
BRIDGE = Path("app/src/full/java/com/duoopen/shell/ShizukuBridge.kt")
OBSERVER = Path("app/src/full/java/com/duoopen/overlay/Fold7DeviceStateObserver.kt")
SERVICE = Path("app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt")
EXPORTER = Path("app/src/main/java/com/duoopen/debug/DebugBundleExporter.kt")
MARKER = "SPECULATIVE_INNER_PREWAKE_V1"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_gradle(text: str) -> str:
    if 'versionName = "5.1.0-beta2-zfold7-s1l"' in text:
        return text
    text = one(text, "        versionCode = 45\n", "        versionCode = 46\n", "versionCode")
    return one(
        text,
        '        versionName = "5.1.0-beta2-zfold7-s1k"\n',
        '        versionName = "5.1.0-beta2-zfold7-s1l"\n',
        "versionName",
    )


def transform_protocol(text: str) -> str:
    if "PREWAKE_INNER_PHYSICAL_ONLY = 21" in text:
        return text
    return one(
        text,
        "    const val RENDER_TIMELINE_PROBE = 20\n\n    const val CB_ANGLE = 1\n",
        "    const val RENDER_TIMELINE_PROBE = 20\n"
        "    // SPECULATIVE_INNER_PREWAKE_V1: power-only, no logical route mutation.\n"
        "    const val PREWAKE_INNER_PHYSICAL_ONLY = 21\n\n"
        "    const val CB_ANGLE = 1\n",
        "protocol prewake code",
    )


def transform_shell(text: str) -> str:
    if MARKER in text:
        return text

    transaction = r'''            ShellProtocol.PREWAKE_INNER_PHYSICAL_ONLY -> {
                // SPECULATIVE_INNER_PREWAKE_V1: physical power only.
                val identity = clearCallingIdentity()
                val result = try {
                    prewakeInnerPhysicalOnly()
                } catch (error: Throwable) {
                    Bundle().apply {
                        putBoolean("ok", false)
                        putString("error", "${error.javaClass.simpleName}: ${error.message}")
                    }
                } finally {
                    restoreCallingIdentity(identity)
                }
                out.writeNoException()
                out.writeBundle(result)
            }
'''
    text = one(
        text,
        "            ShellProtocol.START_ANGLES -> {\n",
        transaction + "            ShellProtocol.START_ANGLES -> {\n",
        "prewake transaction",
    )

    helper = r'''    // SPECULATIVE_INNER_PREWAKE_V1
    // Intentionally does not discover/enable/power a logical route, request a
    // DeviceState override, or mutate continuity ownership. It only asks HWC
    // to bring the known Fold7 inner physical panel to normal power early.
    private fun prewakeInnerPhysicalOnly(): Bundle {
        val started = SystemClock.elapsedRealtime()
        val physicalId = resolveFold7InnerPhysicalDisplayId()
        val powerStarted = SystemClock.elapsedRealtime()
        val (powered, error) = setPhysicalPowerNormal(physicalId)
        val powerMs = SystemClock.elapsedRealtime() - powerStarted

        return Bundle().apply {
            putBoolean("ok", powered)
            putLong("physicalDisplayId", physicalId)
            putBoolean("physicalPowered", powered)
            putLong("physicalPowerMs", powerMs)
            putLong("totalMs", SystemClock.elapsedRealtime() - started)
            putString("mode", "PHYSICAL_ONLY_NO_ROUTE_MUTATION")
            if (error != null) putString("error", error)
        }
    }

'''
    return one(
        text,
        "    // ---- Samsung wallpaper angle reader -------------------------------------\n",
        helper + "    // ---- Samsung wallpaper angle reader -------------------------------------\n",
        "prewake helper",
    )


def transform_bridge(text: str) -> str:
    if "fun prewakeInnerPhysicalOnly()" in text:
        return text
    addition = r'''    /**
     * S1L speculative inner prewake. Blocking shell transaction; call from IO.
     * This powers only the physical inner panel and does not mutate routing.
     */
    fun prewakeInnerPhysicalOnly(): Bundle? =
        call(ShellProtocol.PREWAKE_INNER_PHYSICAL_ONLY)

'''
    return one(
        text,
        "    /** Receives angles from the shell-side wallpaper log reader. */\n",
        addition + "    /** Receives angles from the shell-side wallpaper log reader. */\n",
        "bridge prewake method",
    )


def transform_observer(text: str) -> str:
    if "onPreOpeningEdge" in text:
        return text

    text = one(
        text,
        '''internal class Fold7DeviceStateObserver(
    private val context: Context,
    private val handler: Handler,
    private val onOpeningEdge: (
        previousStateId: Int,
        currentStateId: Int,
    ) -> Unit,
) {''',
        '''internal class Fold7DeviceStateObserver(
    private val context: Context,
    private val handler: Handler,
    // SPECULATIVE_INNER_PREWAKE_V1: CLOSED -> TENT on Fold7 remains marked
    // physically folded by Samsung, but is the earliest repeatable signal that
    // the user has started opening. This callback is power-prewarm only.
    private val onPreOpeningEdge: (
        previousStateId: Int,
        currentStateId: Int,
    ) -> Unit = { _, _ -> },
    private val onOpeningEdge: (
        previousStateId: Int,
        currentStateId: Int,
    ) -> Unit,
) {''',
        "observer callback",
    )

    anchor = '''        DuoDiagnostics.event(
            "early-wake",
            "device-state previous=$previousId current=$id " +
                "folded=$inferredFolded source=$source",
        )

        if (
            previousId != null &&
            previousFolded == true &&
            inferredFolded == false
        ) {'''
    replacement = '''        DuoDiagnostics.event(
            "early-wake",
            "device-state previous=$previousId current=$id " +
                "folded=$inferredFolded source=$source",
        )

        val speculativePreOpeningEdge =
            previousId != null &&
                previousFolded == true &&
                inferredFolded == true &&
                previousId != id &&
                previousId in learnedFoldedStateIds

        if (speculativePreOpeningEdge) {
            DuoDiagnostics.event(
                "early-wake",
                "speculative-preopening-edge previous=$previousId current=$id source=$source",
            )
            onPreOpeningEdge(previousId, id)
        }

        if (
            previousId != null &&
            previousFolded == true &&
            inferredFolded == false
        ) {'''
    return one(text, anchor, replacement, "observer speculative edge")


def transform_service(text: str) -> str:
    if "SPECULATIVE_INNER_PREWAKE_V1" in text:
        return text

    text = one(
        text,
        '''    private var deviceStateObserver:
        Fold7DeviceStateObserver? =
        null

    private lateinit var continuity: Fold7ContinuityCoordinator
''',
        '''    private var deviceStateObserver:
        Fold7DeviceStateObserver? =
        null

    // SPECULATIVE_INNER_PREWAKE_V1: this is intentionally outside the
    // continuity controller. It cannot advance an opening generation.
    private var speculativeInnerPrewakeInFlight = false
    private var speculativeInnerPrewakeSequence = 0L

    private lateinit var continuity: Fold7ContinuityCoordinator
''',
        "service prewake fields",
    )

    helper = r'''    private fun speculativePrewakeInnerPhysical(
        reason: String,
    ) {
        if (
            !ShizukuBridge.ready ||
            speculativeInnerPrewakeInFlight ||
            !::continuity.isInitialized ||
            continuity.state != Fold7ContinuityController.State.NATIVE_COVER
        ) {
            DuoDiagnostics.event(
                "speculative-inner-prewake",
                "SKIP reason=$reason ready=${ShizukuBridge.ready} " +
                    "inFlight=$speculativeInnerPrewakeInFlight " +
                    "state=${if (::continuity.isInitialized) continuity.state else null}",
            )
            return
        }

        speculativeInnerPrewakeInFlight = true
        val sequence = ++speculativeInnerPrewakeSequence
        val started = SystemClock.elapsedRealtime()

        DuoDiagnostics.event(
            "speculative-inner-prewake",
            "START sequence=$sequence reason=$reason state=${continuity.state} hinge=${hinge.lastAngle}",
        )

        scope.launch(Dispatchers.IO) {
            val result =
                runCatching {
                    ShizukuBridge.prewakeInnerPhysicalOnly()
                }.getOrNull()
            val totalMs = SystemClock.elapsedRealtime() - started

            handler.post {
                if (sequence == speculativeInnerPrewakeSequence) {
                    speculativeInnerPrewakeInFlight = false
                }
                DuoDiagnostics.event(
                    "speculative-inner-prewake",
                    "RESULT sequence=$sequence reason=$reason " +
                        "ok=${result?.getBoolean("ok", false) == true} " +
                        "physical=${result?.getLong("physicalDisplayId", -1L) ?: -1L} " +
                        "powered=${result?.getBoolean("physicalPowered", false) == true} " +
                        "physicalPowerMs=${result?.getLong("physicalPowerMs", -1L) ?: -1L} " +
                        "shellTotalMs=${result?.getLong("totalMs", -1L) ?: -1L} " +
                        "wallMs=$totalMs error=${result?.getString("error")}",
                )
            }
        }
    }

'''
    text = one(
        text,
        "    // HALL_OPEN_LATCH_V3\n    private fun startLidEventsIfNeeded() {\n",
        helper + "    // HALL_OPEN_LATCH_V3\n    private fun startLidEventsIfNeeded() {\n",
        "service prewake helper",
    )

    old_ctor = '''        deviceStateObserver =
            Fold7DeviceStateObserver(
                context = this,
                handler = handler,
            ) {
                    previousStateId,
                    currentStateId,
                ->'''
    new_ctor = '''        deviceStateObserver =
            Fold7DeviceStateObserver(
                context = this,
                handler = handler,
                onPreOpeningEdge = {
                        previousStateId,
                        currentStateId,
                    ->
                    val reason =
                        "device-state-preopen:$previousStateId->$currentStateId"

                    angleFeed
                        ?.kickPreciseBurst(
                            reason
                        )

                    speculativePrewakeInnerPhysical(
                        reason
                    )
                },
            ) {
                    previousStateId,
                    currentStateId,
                ->'''
    text = one(text, old_ctor, new_ctor, "service observer prewake callback")

    return text


def transform_exporter(text: str) -> str:
    if "speculativeInnerPrewake=SPECULATIVE_INNER_PREWAKE_V1" in text:
        return text
    old = '''                        appendLine(
                            "automaticVisualForensics=SUPPRESSED_FOR_S1K_BEHAVIOR_VALIDATION"
                        )
'''
    new = old + '''                        appendLine(
                            "speculativeInnerPrewake=SPECULATIVE_INNER_PREWAKE_V1"
                        )
                        appendLine(
                            "speculativeInnerPrewakePolicy=PHYSICAL_ONLY_NO_ROUTE_OR_CONTINUITY_MUTATION"
                        )
'''
    return one(text, old, new, "export S1L identity")


def validate(g: str, p: str, s: str, b: str, o: str, f: str, e: str) -> None:
    required = (
        (g, ['versionCode = 46', 'versionName = "5.1.0-beta2-zfold7-s1l"']),
        (p, ["PREWAKE_INNER_PHYSICAL_ONLY = 21"]),
        (s, [MARKER, "prewakeInnerPhysicalOnly", "PHYSICAL_ONLY_NO_ROUTE_MUTATION"]),
        (b, ["fun prewakeInnerPhysicalOnly()", "PREWAKE_INNER_PHYSICAL_ONLY"]),
        (o, ["onPreOpeningEdge", "speculative-preopening-edge", "previousId in learnedFoldedStateIds"]),
        (f, [MARKER, "speculativePrewakeInnerPhysical", "device-state-preopen:", "speculative-inner-prewake"]),
        (e, ["speculativeInnerPrewake=SPECULATIVE_INNER_PREWAKE_V1"]),
    )
    for text, needles in required:
        for needle in needles:
            if needle not in text:
                raise RuntimeError("missing S1L invariant: " + needle)


def apply(repo: Path, check: bool) -> None:
    paths = (GRADLE, PROTOCOL, SHELL, BRIDGE, OBSERVER, SERVICE, EXPORTER)
    for path in paths:
        if not (repo / path).exists():
            raise RuntimeError("missing " + str(path))

    values = [
        transform_gradle((repo / GRADLE).read_text()),
        transform_protocol((repo / PROTOCOL).read_text()),
        transform_shell((repo / SHELL).read_text()),
        transform_bridge((repo / BRIDGE).read_text()),
        transform_observer((repo / OBSERVER).read_text()),
        transform_service((repo / SERVICE).read_text()),
        transform_exporter((repo / EXPORTER).read_text()),
    ]
    validate(*values)

    if not check:
        for path, value in zip(paths, values):
            (repo / path).write_text(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        sample = '        versionCode = 45\n        versionName = "5.1.0-beta2-zfold7-s1k"\n'
        out = transform_gradle(sample)
        assert "versionCode = 46" in out
        assert "zfold7-s1l" in out
        print("speculative inner prewake v1 transformer self-test: PASS")
        if not args.check:
            return 0

    apply(Path(args.repo).resolve(), args.check)
    print("speculative inner prewake v1: " + ("source shape verified" if args.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
