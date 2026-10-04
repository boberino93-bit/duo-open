#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

GRADLE = Path("app/build.gradle.kts")
PROTOCOL = Path("app/src/full/java/com/duoopen/shell/ShellProtocol.kt")
SHELL = Path("app/src/full/java/com/duoopen/shell/DuoShellService.kt")
BRIDGE = Path("app/src/full/java/com/duoopen/shell/ShizukuBridge.kt")
SERVICE = Path("app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt")
EXPORTER = Path("app/src/main/java/com/duoopen/debug/DebugBundleExporter.kt")
MARKER = "S1M_CONCURRENT_OUTER_ROUTE_PROBE_V1"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_gradle(text: str) -> str:
    if 'versionName = "5.1.0-beta2-zfold7-s1m"' in text:
        return text
    text = one(text, "        versionCode = 46\n", "        versionCode = 47\n", "versionCode")
    return one(
        text,
        '        versionName = "5.1.0-beta2-zfold7-s1l"\n',
        '        versionName = "5.1.0-beta2-zfold7-s1m"\n',
        "versionName",
    )


def transform_protocol(text: str) -> str:
    if "PROBE_CONCURRENT_OUTER_DEFAULT = 22" in text:
        return text
    return one(
        text,
        "    const val PREWAKE_INNER_PHYSICAL_ONLY = 21\n\n    const val CB_ANGLE = 1\n",
        "    const val PREWAKE_INNER_PHYSICAL_ONLY = 21\n"
        "    // S1M_CONCURRENT_OUTER_ROUTE_PROBE_V1: bounded diagnostic state-5 probe.\n"
        "    const val PROBE_CONCURRENT_OUTER_DEFAULT = 22\n\n"
        "    const val CB_ANGLE = 1\n",
        "protocol S1M code",
    )


def transform_shell(text: str) -> str:
    if MARKER in text:
        return text

    transaction = r'''            ShellProtocol.PROBE_CONCURRENT_OUTER_DEFAULT -> {
                // S1M_CONCURRENT_OUTER_ROUTE_PROBE_V1: diagnostic-only,
                // bounded CONCURRENT_OUTER_DEFAULT (state 5) request.
                val identity = clearCallingIdentity()
                val result = try {
                    probeConcurrentOuterDefault()
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
        "S1M transaction",
    )

    helper = r'''    // S1M_CONCURRENT_OUTER_ROUTE_PROBE_V1
    // The Fold7 advertises state 5 as CONCURRENT_OUTER_DEFAULT. S1L proved the
    // inner physical panel can be warm while Samsung still withholds the usable
    // 1968x2184 logical route in TENT. This probe briefly requests state 5,
    // samples route/default geometry, then *always* resets the request.
    // It never modifies Duo Open continuity state or renderer ownership.
    private fun probeConcurrentOuterDefault(): Bundle {
        data class RouteSample(
            val elapsedMs: Long,
            val state: String,
            val routes: String,
            val defaultGeometry: String,
            val innerLogicalId: Int,
            val coverLogicalId: Int,
        )

        val started = SystemClock.elapsedRealtime()

        fun compact(value: String): String =
            value
                .lineSequence()
                .map { it.trim() }
                .filter { it.isNotBlank() }
                .take(24)
                .joinToString(" | ")
                .take(6000)

        fun routeString(): String =
            runCatching {
                logicalDisplayIdsDirect()
                    .sorted()
                    .joinToString(" | ") { id ->
                        val geometry = directGeometry(id)
                        val physical = physicalDisplayIdFromLogical(id)
                        "id=$id:${geometry?.first ?: -1}x${geometry?.second ?: -1}:physical=$physical"
                    }
            }.getOrElse { error ->
                "route-error=${error.javaClass.simpleName}:${error.message}"
            }

        fun logicalFor(width: Int, height: Int): Int =
            runCatching {
                logicalDisplayIdsDirect()
                    .firstOrNull { id -> directGeometry(id) == (width to height) }
                    ?: -1
            }.getOrDefault(-1)

        fun sample(): RouteSample {
            val defaultGeometry =
                runCatching {
                    val geometry = directGeometry(Display.DEFAULT_DISPLAY)
                    "${geometry?.first ?: -1}x${geometry?.second ?: -1}"
                }.getOrDefault("-1x-1")

            return RouteSample(
                elapsedMs = SystemClock.elapsedRealtime() - started,
                state = compact(runProbe("cmd device_state state 2>/dev/null")),
                routes = routeString(),
                defaultGeometry = defaultGeometry,
                innerLogicalId = logicalFor(1968, 2184),
                coverLogicalId = logicalFor(1080, 2520),
            )
        }

        val before = sample()
        var requestOutput = ""
        var resetOutput = ""
        val during = mutableListOf<RouteSample>()
        var thrown: String? = null

        try {
            requestOutput = compact(runProbe("cmd device_state state 5 2>&1"))

            // Bounded ~260 ms probe. This is long enough for the framework's
            // display mapper to publish a route if state 5 supports concurrent
            // topology, but short enough to avoid taking over normal posture.
            val targets = longArrayOf(0L, 35L, 80L, 150L, 260L)
            for (target in targets) {
                val due = started + target
                val now = SystemClock.elapsedRealtime()
                if (due > now) Thread.sleep(due - now)
                during += sample()
            }
        } catch (error: Throwable) {
            thrown = "${error.javaClass.simpleName}: ${error.message}"
        } finally {
            resetOutput = compact(runProbe("cmd device_state state reset 2>&1"))
        }

        Thread.sleep(70L)
        val after = sample()

        val firstInner =
            during.firstOrNull { it.innerLogicalId >= 0 }

        val outerDefaultPreserved =
            during
                .filter { it.innerLogicalId >= 0 }
                .all { it.defaultGeometry == "1080x2520" }

        val routePublished = firstInner != null

        fun encode(sample: RouteSample): String =
            "t=${sample.elapsedMs}ms;default=${sample.defaultGeometry};" +
                "inner=${sample.innerLogicalId};cover=${sample.coverLogicalId};" +
                "routes=${sample.routes};state=${sample.state}"

        return Bundle().apply {
            putBoolean("ok", thrown == null)
            putBoolean("routePublished", routePublished)
            putLong("firstInnerRouteMs", firstInner?.elapsedMs ?: -1L)
            putBoolean("outerDefaultPreserved", routePublished && outerDefaultPreserved)
            putString("before", encode(before))
            putString("during", during.joinToString(" || ", transform = ::encode))
            putString("after", encode(after))
            putString("requestOutput", requestOutput)
            putString("resetOutput", resetOutput)
            putString("error", thrown)
            putString("requestedState", "5:CONCURRENT_OUTER_DEFAULT")
            putLong("probeMs", SystemClock.elapsedRealtime() - started)
        }
    }

'''
    return one(
        text,
        "    // ---- Samsung wallpaper angle reader -------------------------------------\n",
        helper + "    // ---- Samsung wallpaper angle reader -------------------------------------\n",
        "S1M shell helper",
    )


def transform_bridge(text: str) -> str:
    if "fun probeConcurrentOuterDefault()" in text:
        return text
    addition = r'''    /**
     * S1M bounded diagnostic probe for Fold7 state 5
     * (CONCURRENT_OUTER_DEFAULT). Blocking shell transaction; call from IO.
     */
    fun probeConcurrentOuterDefault(): Bundle? =
        call(ShellProtocol.PROBE_CONCURRENT_OUTER_DEFAULT)

'''
    return one(
        text,
        "    /** Receives angles from the shell-side wallpaper log reader. */\n",
        addition + "    /** Receives angles from the shell-side wallpaper log reader. */\n",
        "S1M bridge helper",
    )


def transform_service(text: str) -> str:
    if MARKER in text:
        return text

    text = one(
        text,
        '''    private var speculativeInnerPrewakeInFlight = false
    private var speculativeInnerPrewakeSequence = 0L

    private lateinit var continuity: Fold7ContinuityCoordinator
''',
        '''    private var speculativeInnerPrewakeInFlight = false
    private var speculativeInnerPrewakeSequence = 0L

    // S1M_CONCURRENT_OUTER_ROUTE_PROBE_V1: diagnostic-only, once per service
    // lifecycle. It cannot mutate the continuity controller directly.
    private var concurrentOuterRouteProbeIssued = false
    private var concurrentOuterRouteProbeSequence = 0L

    private lateinit var continuity: Fold7ContinuityCoordinator
''',
        "S1M service fields",
    )

    helper = r'''    private fun scheduleConcurrentOuterRouteProbe(
        reason: String,
    ) {
        if (
            concurrentOuterRouteProbeIssued ||
            !ShizukuBridge.ready ||
            !::continuity.isInitialized ||
            continuity.state != Fold7ContinuityController.State.NATIVE_COVER
        ) {
            DuoDiagnostics.event(
                "concurrent-outer-route-probe",
                "SKIP reason=$reason issued=$concurrentOuterRouteProbeIssued " +
                    "ready=${ShizukuBridge.ready} " +
                    "state=${if (::continuity.isInitialized) continuity.state else null}",
            )
            return
        }

        concurrentOuterRouteProbeIssued = true
        val sequence = ++concurrentOuterRouteProbeSequence

        // Let S1L's physical prewake complete first. The field median is
        // ~158 ms, so 230 ms preserves a clean separation between power and
        // Samsung logical-route publication.
        handler.postDelayed(
            {
                if (
                    sequence != concurrentOuterRouteProbeSequence ||
                    !ShizukuBridge.ready ||
                    !::continuity.isInitialized ||
                    continuity.state != Fold7ContinuityController.State.NATIVE_COVER
                ) {
                    DuoDiagnostics.event(
                        "concurrent-outer-route-probe",
                        "ABORT sequence=$sequence reason=$reason " +
                            "state=${if (::continuity.isInitialized) continuity.state else null}",
                    )
                    return@postDelayed
                }

                DuoDiagnostics.event(
                    "concurrent-outer-route-probe",
                    "START sequence=$sequence reason=$reason hinge=${hinge.lastAngle}",
                )

                scope.launch(Dispatchers.IO) {
                    val started = SystemClock.elapsedRealtime()
                    val result =
                        runCatching {
                            ShizukuBridge.probeConcurrentOuterDefault()
                        }.getOrNull()
                    val wallMs = SystemClock.elapsedRealtime() - started

                    handler.post {
                        DuoDiagnostics.event(
                            "concurrent-outer-route-probe",
                            "RESULT sequence=$sequence reason=$reason " +
                                "ok=${result?.getBoolean("ok", false) == true} " +
                                "routePublished=${result?.getBoolean("routePublished", false) == true} " +
                                "firstInnerRouteMs=${result?.getLong("firstInnerRouteMs", -1L) ?: -1L} " +
                                "outerDefaultPreserved=${result?.getBoolean("outerDefaultPreserved", false) == true} " +
                                "probeMs=${result?.getLong("probeMs", -1L) ?: -1L} wallMs=$wallMs " +
                                "request=${result?.getString("requestOutput")} " +
                                "before=${result?.getString("before")} " +
                                "during=${result?.getString("during")} " +
                                "after=${result?.getString("after")} " +
                                "reset=${result?.getString("resetOutput")} " +
                                "error=${result?.getString("error")}",
                        )
                    }
                }
            },
            230L,
        )
    }

'''
    text = one(
        text,
        "    private fun speculativePrewakeInnerPhysical(\n",
        helper + "    private fun speculativePrewakeInnerPhysical(\n",
        "S1M service helper",
    )

    old = '''                    speculativePrewakeInnerPhysical(
                        reason
                    )
                },
'''
    new = '''                    speculativePrewakeInnerPhysical(
                        reason
                    )

                    scheduleConcurrentOuterRouteProbe(
                        reason
                    )
                },
'''
    return one(text, old, new, "S1M preopen trigger")


def transform_exporter(text: str) -> str:
    if "concurrentOuterRouteProbe=S1M_CONCURRENT_OUTER_ROUTE_PROBE_V1" in text:
        return text
    old = '''                        appendLine(
                            "speculativeInnerPrewakePolicy=PHYSICAL_ONLY_NO_ROUTE_OR_CONTINUITY_MUTATION"
                        )
'''
    new = old + '''                        appendLine(
                            "concurrentOuterRouteProbe=S1M_CONCURRENT_OUTER_ROUTE_PROBE_V1"
                        )
                        appendLine(
                            "concurrentOuterRouteProbePolicy=ONE_SHOT_BOUNDED_STATE5_REQUEST_ALWAYS_RESET"
                        )
'''
    return one(text, old, new, "S1M export identity")


def validate(g: str, p: str, s: str, b: str, f: str, e: str) -> None:
    required = (
        (g, ['versionCode = 47', 'versionName = "5.1.0-beta2-zfold7-s1m"']),
        (p, ["PROBE_CONCURRENT_OUTER_DEFAULT = 22"]),
        (s, [MARKER, "probeConcurrentOuterDefault", "cmd device_state state 5", "cmd device_state state reset", "outerDefaultPreserved"]),
        (b, ["fun probeConcurrentOuterDefault()", "PROBE_CONCURRENT_OUTER_DEFAULT"]),
        (f, [MARKER, "scheduleConcurrentOuterRouteProbe", "concurrent-outer-route-probe", "230L"]),
        (e, ["concurrentOuterRouteProbe=S1M_CONCURRENT_OUTER_ROUTE_PROBE_V1"]),
    )
    for text, needles in required:
        for needle in needles:
            if needle not in text:
                raise RuntimeError("missing S1M invariant: " + needle)


def apply(repo: Path, check: bool) -> None:
    paths = (GRADLE, PROTOCOL, SHELL, BRIDGE, SERVICE, EXPORTER)
    for path in paths:
        if not (repo / path).exists():
            raise RuntimeError("missing " + str(path))

    values = [
        transform_gradle((repo / GRADLE).read_text()),
        transform_protocol((repo / PROTOCOL).read_text()),
        transform_shell((repo / SHELL).read_text()),
        transform_bridge((repo / BRIDGE).read_text()),
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
        sample = '        versionCode = 46\n        versionName = "5.1.0-beta2-zfold7-s1l"\n'
        out = transform_gradle(sample)
        assert "versionCode = 47" in out
        assert "zfold7-s1m" in out
        print("S1M concurrent outer route probe transformer self-test: PASS")
        if not args.check:
            return 0

    apply(Path(args.repo).resolve(), args.check)
    print("S1M concurrent outer route probe: " + ("source shape verified" if args.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
