#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

GRADLE = Path("app/build.gradle.kts")
SHELL = Path("app/src/full/java/com/duoopen/shell/DuoShellService.kt")
COORDINATOR = Path("app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt")
EXPORTER = Path("app/src/main/java/com/duoopen/debug/DebugBundleExporter.kt")
MARKER = "S1P_HALL_OPTICAL_PROXY_V1"
PRIVATE_STACK = "0x445550"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_gradle(text: str) -> str:
    if 'versionName = "5.1.0-beta2-zfold7-s1p"' in text:
        return text
    text = one(text, "        versionCode = 49\n", "        versionCode = 50\n", "versionCode")
    return one(
        text,
        '        versionName = "5.1.0-beta2-zfold7-s1o"\n',
        '        versionName = "5.1.0-beta2-zfold7-s1p"\n',
        "versionName",
    )


def transform_shell(text: str) -> str:
    if MARKER in text:
        return text

    text = one(
        text,
        '''    // INNER_PHYSICAL_BRIDGE_V2: keep the temporary privacy layer on Samsung's native
    // INNER layer stack. This removes the private-stack/native-stack ownership race.
    private val innerPhysicalBridgeLayerStack = 0
''',
        f'''    // {MARKER}: while Samsung remains in TENT, INNER is physically awake but
    // has no native logical composition. Put a live mirror of the still-authoritative
    // cover display on an isolated stack owned only by the inner physical panel.
    // Native stack 0 is restored atomically when the proxy is released.
    private val innerPhysicalBridgeLayerStack = {PRIVATE_STACK}
    private var innerPhysicalBridgeOpticalProxy = false
''',
        "private optical stack fields",
    )

    text = one(
        text,
        '''    private data class InnerPhysicalBridgeResult(
        val ok: Boolean,
        val active: Boolean,
        val reused: Boolean,
        val layerStack: Int,
        val error: String? = null,
    )
''',
        '''    private data class InnerPhysicalBridgeResult(
        val ok: Boolean,
        val active: Boolean,
        val reused: Boolean,
        val layerStack: Int,
        val opticalProxy: Boolean = false,
        val error: String? = null,
    )
''',
        "bridge result optical flag",
    )

    text = one(
        text,
        '''                    reused = true,
                    layerStack = innerPhysicalBridgeLayerStack,
                )
''',
        '''                    reused = true,
                    layerStack = innerPhysicalBridgeLayerStack,
                    opticalProxy = innerPhysicalBridgeOpticalProxy,
                )
''',
        "reused bridge optical flag",
    )

    text = one(
        text,
        '''            if (
                physicalId < 0L ||
                serviceEpoch < 0L ||
                openingAttempt < 0L
            ) {
''',
        '''            if (
                physicalId < 0L ||
                serviceEpoch < 0L ||
                openingAttempt < 0L
            ) {
''',
        "identity gate anchor",
    )

    identity_tail = '''                )
            }

            runCatching {
                org.lsposed.hiddenapibypass.HiddenApiBypass
'''
    identity_new = '''                )
            }

            // The optical proxy is admitted only while the default logical display is
            // still the Fold7 cover. If Samsung has already promoted INNER, native
            // composition should win and no private-stack proxy is necessary.
            if (directGeometry(Display.DEFAULT_DISPLAY) != (1080 to 2520)) {
                return@synchronized InnerPhysicalBridgeResult(
                    ok = true,
                    active = false,
                    reused = false,
                    layerStack = innerPhysicalBridgeLayerStack,
                    opticalProxy = false,
                )
            }

            runCatching {
                org.lsposed.hiddenapibypass.HiddenApiBypass
'''
    text = one(text, identity_tail, identity_new, "cover-only optical admission")

    old_layer = '''                val builder =
                    SurfaceControl.Builder()
                        .setName("DuoInnerPhysicalBridge")
                builder.javaClass
                    .getDeclaredMethod("setColorLayer")
                    .apply { isAccessible = true }
                    .invoke(builder)
                val layer = builder.build()

                val tx = SurfaceControl.Transaction()
                val txClass = tx.javaClass

                txClass.getDeclaredMethod(
                    "setLayerStack",
                    SurfaceControl::class.java,
                    Integer.TYPE,
                ).apply { isAccessible = true }
                    .invoke(tx, layer, innerPhysicalBridgeLayerStack)

                txClass.getDeclaredMethod(
                    "setColor",
                    SurfaceControl::class.java,
                    FloatArray::class.java,
                ).apply { isAccessible = true }
                    .invoke(
                        tx,
                        layer,
                        // INNER_PHYSICAL_BRIDGE_V4_NON_OCCLUDING: color is inert because
                        // alpha is forced to zero; this layer is transport/wake plumbing only.
                        floatArrayOf(0.012f, 0.012f, 0.016f),
                    )

                txClass.getDeclaredMethod(
                    "setWindowCrop",
                    SurfaceControl::class.java,
                    Rect::class.java,
                ).apply { isAccessible = true }
                    .invoke(
                        tx,
                        layer,
                        Rect(0, 0, 1968, 2184),
                    )

                // INNER_PHYSICAL_BRIDGE_V4_NON_OCCLUDING
                // Preserve the native-stack routing/projection side effect that wakes INNER,
                // but never cover Samsung/native composition while waiting for handoff.
                tx.setLayer(layer, Int.MIN_VALUE + 64)
                tx.setAlpha(layer, 0.0f)
                txClass.getDeclaredMethod(
                    "show",
                    SurfaceControl::class.java,
                ).apply { isAccessible = true }
                    .invoke(tx, layer)

                txClass.getDeclaredMethod(
                    "setDisplayLayerStack",
                    IBinder::class.java,
                    Integer.TYPE,
                ).apply { isAccessible = true }
                    .invoke(
                        tx,
                        token,
                        innerPhysicalBridgeLayerStack,
                    )

                txClass.getDeclaredMethod(
                    "setDisplayProjection",
                    IBinder::class.java,
                    Integer.TYPE,
                    Rect::class.java,
                    Rect::class.java,
                ).apply { isAccessible = true }
                    .invoke(
                        tx,
                        token,
                        0,
                        Rect(0, 0, 1968, 2184),
                        Rect(0, 0, 1968, 2184),
                    )

                tx.apply()
'''
    new_layer = f'''                // {MARKER}: mirror the still-authoritative cover display instead of
                // creating an inert transparent color layer. The proxy lives on a private
                // layer stack so it cannot recurse into the cover source display.
                val layer =
                    createMirrorCandidate(Display.DEFAULT_DISPLAY)

                val tx = SurfaceControl.Transaction()
                val txClass = tx.javaClass

                txClass.getDeclaredMethod(
                    "setLayerStack",
                    SurfaceControl::class.java,
                    Integer.TYPE,
                ).apply {{ isAccessible = true }}
                    .invoke(tx, layer, innerPhysicalBridgeLayerStack)

                txClass.getDeclaredMethod(
                    "setWindowCrop",
                    SurfaceControl::class.java,
                    Rect::class.java,
                ).apply {{ isAccessible = true }}
                    .invoke(
                        tx,
                        layer,
                        Rect(0, 0, 1080, 2520),
                    )

                // Full-panel optical proof: scale the live cover composition into INNER.
                // This intentionally prioritizes eliminating the black TENT interval. Once
                // field-proven, geometry can be refined independently without changing the
                // early optical-ownership mechanism.
                tx.setLayer(layer, Int.MAX_VALUE - 64)
                tx.setAlpha(layer, 1.0f)
                txClass.getDeclaredMethod(
                    "show",
                    SurfaceControl::class.java,
                ).apply {{ isAccessible = true }}
                    .invoke(tx, layer)

                txClass.getDeclaredMethod(
                    "setDisplayLayerStack",
                    IBinder::class.java,
                    Integer.TYPE,
                ).apply {{ isAccessible = true }}
                    .invoke(
                        tx,
                        token,
                        innerPhysicalBridgeLayerStack,
                    )

                txClass.getDeclaredMethod(
                    "setDisplayProjection",
                    IBinder::class.java,
                    Integer.TYPE,
                    Rect::class.java,
                    Rect::class.java,
                ).apply {{ isAccessible = true }}
                    .invoke(
                        tx,
                        token,
                        0,
                        Rect(0, 0, 1080, 2520),
                        Rect(0, 0, 1968, 2184),
                    )

                tx.apply()
'''
    text = one(text, old_layer, new_layer, "replace transparent bridge with optical proxy")

    text = one(
        text,
        '''                innerPhysicalBridgeOwnerServiceEpoch = serviceEpoch
                innerPhysicalBridgeOwnerAttempt = openingAttempt

                InnerPhysicalBridgeResult(
                    ok = true,
                    active = true,
                    reused = false,
                    layerStack = innerPhysicalBridgeLayerStack,
                )
''',
        '''                innerPhysicalBridgeOwnerServiceEpoch = serviceEpoch
                innerPhysicalBridgeOwnerAttempt = openingAttempt
                innerPhysicalBridgeOpticalProxy = true

                InnerPhysicalBridgeResult(
                    ok = true,
                    active = true,
                    reused = false,
                    layerStack = innerPhysicalBridgeLayerStack,
                    opticalProxy = true,
                )
''',
        "mark optical proxy active",
    )

    text = one(
        text,
        '''                innerPhysicalBridgeOwnerAttempt = -1L
                InnerPhysicalBridgeResult(
''',
        '''                innerPhysicalBridgeOwnerAttempt = -1L
                innerPhysicalBridgeOpticalProxy = false
                InnerPhysicalBridgeResult(
''',
        "clear optical flag on creation failure",
    )

    # Restore native stack AND native inner projection on every release/reversal.
    old_restore = '''                        if (token != null) {
                            tx.javaClass
                                .getDeclaredMethod(
                                    "setDisplayLayerStack",
                                    IBinder::class.java,
                                    Integer.TYPE,
                                )
                                .apply { isAccessible = true }
                                .invoke(tx, token, 0)
                        }
'''
    new_restore = '''                        if (token != null) {
                            tx.javaClass
                                .getDeclaredMethod(
                                    "setDisplayLayerStack",
                                    IBinder::class.java,
                                    Integer.TYPE,
                                )
                                .apply { isAccessible = true }
                                .invoke(tx, token, 0)
                            tx.javaClass
                                .getDeclaredMethod(
                                    "setDisplayProjection",
                                    IBinder::class.java,
                                    Integer.TYPE,
                                    Rect::class.java,
                                    Rect::class.java,
                                )
                                .apply { isAccessible = true }
                                .invoke(
                                    tx,
                                    token,
                                    0,
                                    Rect(0, 0, 1968, 2184),
                                    Rect(0, 0, 1968, 2184),
                                )
                        }
'''
    text = one(text, old_restore, new_restore, "restore native stack and projection")

    text = one(
        text,
        '''            innerPhysicalBridgeOwnerAttempt = -1L

            Bundle().apply {
''',
        '''            innerPhysicalBridgeOwnerAttempt = -1L
            innerPhysicalBridgeOpticalProxy = false

            Bundle().apply {
''',
        "clear optical flag on release",
    )

    text = one(
        text,
        '''            putBoolean("physicalBridgeReused", bridge.reused)
            putInt("physicalBridgeLayerStack", bridge.layerStack)
''',
        '''            putBoolean("physicalBridgeReused", bridge.reused)
            putInt("physicalBridgeLayerStack", bridge.layerStack)
            putBoolean("physicalBridgeOpticalProxy", bridge.opticalProxy)
''',
        "export optical bridge wake field",
    )

    return text


def transform_coordinator(text: str) -> str:
    if "S1P_OPTICAL_PROXY_STATUS" in text:
        return text
    text = one(
        text,
        '''                                // INNER_PHYSICAL_BRIDGE_V4_STATUS: bridge existence is not optical proof.
                                bridgeActive -> Fold7DisplayStatus.Bridge.HANDOFF_ARMED
''',
        '''                                // S1P_OPTICAL_PROXY_STATUS: the bridge is now a real live-display
                                // mirror on INNER's private physical layer stack, not an inert layer.
                                bridgeActive && result?.getBoolean("physicalBridgeOpticalProxy", false) == true ->
                                    Fold7DisplayStatus.Bridge.PRESENTING
                                bridgeActive -> Fold7DisplayStatus.Bridge.HANDOFF_ARMED
''',
        "optical bridge display status",
    )

    text = one(
        text,
        '''                        "physicalPowerMs=${result?.getLong("physicalPowerMs", -1L) ?: -1L} " +
                        "routeProbeCount=${result?.getInt("routeProbeCount", -1) ?: -1} " +
''',
        '''                        "physicalPowerMs=${result?.getLong("physicalPowerMs", -1L) ?: -1L} " +
                        "bridgeActive=${result?.getBoolean("physicalBridgeActive", false) == true} " +
                        "opticalProxy=${result?.getBoolean("physicalBridgeOpticalProxy", false) == true} " +
                        "bridgeStack=${result?.getInt("physicalBridgeLayerStack", -1) ?: -1} " +
                        "routeProbeCount=${result?.getInt("routeProbeCount", -1) ?: -1} " +
''',
        "optical wake telemetry",
    )
    return text


def transform_exporter(text: str) -> str:
    if "hallOpticalProxy=S1P_HALL_OPTICAL_PROXY_V1" in text:
        return text
    anchor = '''                        appendLine(
                            "shellProtocolCollisionFix=UNIQUE_30_TO_35"
                        )
'''
    addition = anchor + '''                        appendLine(
                            "hallOpticalProxy=S1P_HALL_OPTICAL_PROXY_V1"
                        )
                        appendLine(
                            "hallOpticalProxySource=LIVE_COVER_DISPLAY_MIRROR_PRIVATE_STACK"
                        )
                        appendLine(
                            "hallOpticalProxyNativeRouteOverride=NONE"
                        )
                        appendLine(
                            "hallOpticalProxyDeviceStateOverride=NONE"
                        )
'''
    return one(text, anchor, addition, "export S1P identity")


def validate(g: str, s: str, c: str, e: str) -> None:
    for needle in ('versionCode = 50', 'versionName = "5.1.0-beta2-zfold7-s1p"'):
        if needle not in g:
            raise RuntimeError("missing S1P gradle invariant: " + needle)
    for needle in (
        MARKER,
        f"innerPhysicalBridgeLayerStack = {PRIVATE_STACK}",
        "createMirrorCandidate(Display.DEFAULT_DISPLAY)",
        "Rect(0, 0, 1080, 2520)",
        "Rect(0, 0, 1968, 2184)",
        "physicalBridgeOpticalProxy",
        "innerPhysicalBridgeOpticalProxy = true",
    ):
        if needle not in s:
            raise RuntimeError("missing S1P shell invariant: " + needle)
    for needle in ("S1P_OPTICAL_PROXY_STATUS", "opticalProxy=", "Bridge.PRESENTING"):
        if needle not in c:
            raise RuntimeError("missing S1P coordinator invariant: " + needle)
    if "hallOpticalProxy=S1P_HALL_OPTICAL_PROXY_V1" not in e:
        raise RuntimeError("missing S1P exporter identity")
    prohibited = (
        "cmd device_state state 5",
        "scheduleConcurrentOuterRouteProbe",
        "PROBE_CONCURRENT_OUTER_DEFAULT",
    )
    combined = "\n".join((s, c, e))
    for needle in prohibited:
        if needle in combined:
            raise RuntimeError("S1P must not reintroduce rejected DeviceState override: " + needle)


def apply(repo: Path, check: bool) -> None:
    for rel in (GRADLE, SHELL, COORDINATOR, EXPORTER):
        if not (repo / rel).exists():
            raise RuntimeError("missing " + str(rel))
    g = transform_gradle((repo / GRADLE).read_text(encoding="utf-8"))
    s = transform_shell((repo / SHELL).read_text(encoding="utf-8"))
    c = transform_coordinator((repo / COORDINATOR).read_text(encoding="utf-8"))
    e = transform_exporter((repo / EXPORTER).read_text(encoding="utf-8"))
    validate(g, s, c, e)
    if not check:
        (repo / GRADLE).write_text(g, encoding="utf-8")
        (repo / SHELL).write_text(s, encoding="utf-8")
        (repo / COORDINATOR).write_text(c, encoding="utf-8")
        (repo / EXPORTER).write_text(e, encoding="utf-8")


def self_test() -> None:
    sample = '        versionCode = 49\n        versionName = "5.1.0-beta2-zfold7-s1o"\n'
    out = transform_gradle(sample)
    assert "versionCode = 50" in out
    assert "zfold7-s1p" in out
    print("S1P Hall optical proxy transformer self-test: PASS")


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
    print("S1P Hall optical proxy: " + ("source shape verified" if args.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
