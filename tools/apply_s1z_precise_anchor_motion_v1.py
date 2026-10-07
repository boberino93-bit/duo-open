#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

GRADLE = Path("app/build.gradle.kts")
PANEL = Path("app/src/full/java/com/duoopen/overlay/PanelEngine.kt")
SERVICE = Path("app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt")
INGRESS = Path("app/src/full/java/com/duoopen/overlay/Fold7HingeIngressBatch.kt")

MARKER = "S1Z_PRECISE_ANCHOR_MOTION_V1"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_gradle(text: str) -> str:
    if 'versionName = "5.1.0-beta2-zfold7-s1z-precise-anchor"' in text:
        return text
    text = one(text, "        versionCode = 59\n", "        versionCode = 60\n", "versionCode")
    return one(
        text,
        '        versionName = "5.1.0-beta2-zfold7-s1y-motion"\n',
        '        versionName = "5.1.0-beta2-zfold7-s1z-precise-anchor"\n',
        "versionName",
    )


def transform_ingress(text: str) -> str:
    if MARKER in text:
        return text

    text = one(
        text,
        '''    data class Sample(\n        val sequence: Long,\n        val angle: Float,\n        val observedUptimeMs: Long,\n    )\n''',
        f'''    data class Sample(\n        val sequence: Long,\n        val angle: Float,\n        val observedUptimeMs: Long,\n        // {MARKER}: preserve authority provenance across the serialized\n        // control-thread -> main-thread mailbox. S1Z uses this only for\n        // visual Gen5 admission; semantic continuity remains unchanged.\n        val source: String = "UNKNOWN",\n        val coarse: Boolean = false,\n    )\n''',
        "ingress sample provenance",
    )

    text = one(
        text,
        '''    fun offer(\n        angle: Float,\n        observedUptimeMs: Long,\n    ): Boolean {\n''',
        '''    fun offer(\n        angle: Float,\n        observedUptimeMs: Long,\n        source: String = "UNKNOWN",\n        coarse: Boolean = false,\n    ): Boolean {\n''',
        "ingress offer provenance",
    )

    text = one(
        text,
        '''                    angle = angle.coerceIn(0f, 180f),\n                    observedUptimeMs = observedUptimeMs,\n                )\n''',
        '''                    angle = angle.coerceIn(0f, 180f),\n                    observedUptimeMs = observedUptimeMs,\n                    source = source,\n                    coarse = coarse,\n                )\n''',
        "ingress sample population",
    )
    return text


def transform_service(text: str) -> str:
    if MARKER in text:
        return text

    text = one(
        text,
        '''            hingeIngress.offer(\n                angle = sample.angle,\n                observedUptimeMs = sample.observedUptimeMs,\n            )\n''',
        '''            hingeIngress.offer(\n                angle = sample.angle,\n                observedUptimeMs = sample.observedUptimeMs,\n                source = sample.source,\n                coarse = sample.coarse,\n            )\n''',
        "preserve sample provenance into ingress",
    )

    old = '''            continuity.onHinge(\n                angle = sample.angle,\n                observedUptimeMs = sample.observedUptimeMs,\n            )\n\n            if (\n'''
    new = f'''            continuity.onHinge(\n                angle = sample.angle,\n                observedUptimeMs = sample.observedUptimeMs,\n            )\n\n            // {MARKER}: visual-only admission. The S1X/S1Y proof window\n            // continues to block generic PanelEngine hinge evaluation; each\n            // engine independently accepts only Samsung precise samples while\n            // its inner anchor proof is active.\n            for (engine in engines.values.toList()) {{\n                engine.onAuthoritativeAnchorMotionSample(\n                    angle = sample.angle,\n                    observedUptimeMs = sample.observedUptimeMs,\n                    source = sample.source,\n                    coarse = sample.coarse,\n                )\n            }}\n\n            if (\n'''
    return one(text, old, new, "admit authoritative samples to anchor visual path")


def transform_panel(text: str) -> str:
    if MARKER in text:
        return text

    anchor = '''    fun onHinge(\n        angle: Float,\n        observedUptimeMs: Long = SystemClock.uptimeMillis(),\n    ) {\n'''
    method = f'''    /**\n     * {MARKER}\n     * Feed Gen5 from the same serialized authoritative stream used by the\n     * continuity controller, but only during the already-proven INNER anchor\n     * proof window and only for Samsung precise geometry. This does not call\n     * evaluate(), change continuity authority, or let public/coarse samples\n     * become visual geometry.\n     */\n    fun onAuthoritativeAnchorMotionSample(\n        angle: Float,\n        observedUptimeMs: Long,\n        source: String,\n        coarse: Boolean,\n    ) {{\n        if (openingAnchorProofBitmap == null) return\n        if (source != "SAMSUNG_PRECISE" || coarse || !angle.isFinite()) return\n\n        val deliveredUptimeMs = SystemClock.uptimeMillis()\n        val result =\n            gen5VirtualHinge.addSample(\n                Fold7VirtualHingeGen5.Sample(\n                    sourceTimeNs =\n                        observedUptimeMs.coerceAtMost(deliveredUptimeMs) * 1_000_000L,\n                    deliveryTimeNs = deliveredUptimeMs * 1_000_000L,\n                    angleDegrees = angle,\n                )\n            )\n\n        com.duoopen.debug.DuoDiagnostics.event(\n            "opening-anchor-motion",\n            "PRECISE_ADMIT display=$displayId angle=$angle " +\n                "observed=$observedUptimeMs delivered=$deliveredUptimeMs " +\n                "accepted=${{result.accepted}} reversal=${{result.reversal}} " +\n                "reacquiring=${{result.reacquiring}}",\n        )\n    }}\n\n'''
    return one(text, anchor, method + anchor, "insert precise anchor-motion admission")


def validate(gradle: str, panel: str, service: str, ingress: str) -> None:
    required = (
        (gradle, ['versionCode = 60', 'versionName = "5.1.0-beta2-zfold7-s1z-precise-anchor"']),
        (panel, [
            MARKER,
            "onAuthoritativeAnchorMotionSample",
            'source != "SAMSUNG_PRECISE"',
            "openingAnchorProofBitmap == null",
            '"PRECISE_ADMIT display=$displayId angle=$angle "',
            "gen5VirtualHinge.addSample",
            "openingAnchorMotionLastTilt",
            "ANCHOR_PROOF_VISIBLE_HOLD_MS = 900L",
            "ANCHOR_AUTHORITY_EMERGENCY_HOLD_MS = 30_000L",
        ]),
        (service, [
            MARKER,
            "engine.onAuthoritativeAnchorMotionSample",
            "source = sample.source",
            "coarse = sample.coarse",
        ]),
        (ingress, [
            MARKER,
            'val source: String = "UNKNOWN"',
            "val coarse: Boolean = false",
            "source = source",
            "coarse = coarse",
        ]),
    )
    for content, needles in required:
        for needle in needles:
            if needle not in content:
                raise RuntimeError("missing S1Z invariant: " + needle)

    # Critical safety invariant from S1V/S1X: generic hinge/evaluate remain
    # fail-closed while the proof bitmap is active.
    for needle in (
        "if (openingAnchorProofBitmap != null) return",
        "if (openingAnchorProofBitmap != null) {",
    ):
        if needle not in panel:
            raise RuntimeError("S1Z lost proof-window generic isolation: " + needle)

    if 'source == "PUBLIC_STANDARD"' in panel or 'source == "PUBLIC_VENDOR"' in panel:
        raise RuntimeError("S1Z must not admit public/coarse geometry into Gen5 proof motion")


def apply(repo: Path, check: bool) -> None:
    paths = [repo / GRADLE, repo / PANEL, repo / SERVICE, repo / INGRESS]
    if not all(path.exists() for path in paths):
        raise RuntimeError("required S1Y materialized sources are missing")

    gradle = transform_gradle((repo / GRADLE).read_text(encoding="utf-8"))
    panel = transform_panel((repo / PANEL).read_text(encoding="utf-8"))
    service = transform_service((repo / SERVICE).read_text(encoding="utf-8"))
    ingress = transform_ingress((repo / INGRESS).read_text(encoding="utf-8"))

    validate(gradle, panel, service, ingress)

    if not check:
        (repo / GRADLE).write_text(gradle, encoding="utf-8")
        (repo / PANEL).write_text(panel, encoding="utf-8")
        (repo / SERVICE).write_text(service, encoding="utf-8")
        (repo / INGRESS).write_text(ingress, encoding="utf-8")


def self_test() -> None:
    def admit(proof_active: bool, source: str, coarse: bool, finite: bool = True) -> bool:
        return proof_active and source == "SAMSUNG_PRECISE" and not coarse and finite

    assert admit(True, "SAMSUNG_PRECISE", False)
    assert not admit(False, "SAMSUNG_PRECISE", False)
    assert not admit(True, "SYNTHETIC_ENDPOINT", False)
    assert not admit(True, "PUBLIC_STANDARD", True)
    assert not admit(True, "PUBLIC_VENDOR", True)
    assert not admit(True, "SAMSUNG_PRECISE", True)
    assert not admit(True, "SAMSUNG_PRECISE", False, finite=False)

    # Four ordered precise samples are sufficient for Gen5's existing fit path;
    # S1Z changes admission only, not the predictor or its confidence policy.
    samples = [94.0, 96.0, 99.0, 116.0]
    assert len(samples) >= 4 and samples == sorted(samples)
    print("S1Z precise anchor-motion admission model: PASS")


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
    print("S1Z precise anchor motion: " + ("source shape verified" if args.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
