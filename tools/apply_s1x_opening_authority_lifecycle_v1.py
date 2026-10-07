#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

GRADLE = Path("app/build.gradle.kts")
PANEL = Path("app/src/full/java/com/duoopen/overlay/PanelEngine.kt")
SERVICE = Path("app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt")

MARKER = "S1X_OPENING_AUTHORITY_LIFECYCLE_V1"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_gradle(text: str) -> str:
    if 'versionName = "5.1.0-beta2-zfold7-s1x-lifecycle"' in text:
        return text
    text = one(text, "        versionCode = 57\n", "        versionCode = 58\n", "versionCode")
    return one(
        text,
        '        versionName = "5.1.0-beta2-zfold7-s1w-authority"\n',
        '        versionName = "5.1.0-beta2-zfold7-s1x-lifecycle"\n',
        "versionName",
    )


def transform_panel(text: str) -> str:
    if MARKER in text:
        return text

    old_watchdog = '''        handler.postDelayed(
            {
                if (
                    openingAnchorAuthorityArmed &&
                    openingAnchorAuthorityStartedUptimeMs == started &&
                    openingAnchorProofBitmap == null
                ) {
                    com.duoopen.debug.DuoDiagnostics.event(
                        "opening-anchor-proof",
                        "AUTHORITY_TIMEOUT display=$displayId elapsedMs=" +
                            "${SystemClock.uptimeMillis() - started} reason=$reason",
                    )
                    if (continuityOpeningVisual) {
                        endContinuityOpeningVisual("anchor-authority-timeout")
                    } else {
                        clearOpeningAnchorAuthority("timeout:$reason")
                        if (surface != null) removeOverlay()
                    }
                }
            },
            ANCHOR_AUTHORITY_MAX_HOLD_MS,
        )
'''
    new_watchdog = f'''        // {MARKER}: wall-clock expiry is leak protection only. The normal
        // lifetime ends on physical cover-owner release or an authoritative
        // closed/reversal edge. The Fold7 field trace showed a valid opening
        // taking just over 10 s to publish INNER, so an 8.5 s semantic timeout
        // was incorrectly destroying the exact frame before handoff.
        handler.postDelayed(
            {{
                if (
                    openingAnchorAuthorityStartedUptimeMs == started &&
                    (openingAnchorAuthorityArmed || openingAnchorAuthorityBitmap != null) &&
                    openingAnchorProofBitmap == null
                ) {{
                    com.duoopen.debug.DuoDiagnostics.event(
                        "opening-anchor-proof",
                        "AUTHORITY_EMERGENCY_TIMEOUT display=$displayId elapsedMs=" +
                            "${{SystemClock.uptimeMillis() - started}} reason=$reason",
                    )
                    cancelContinuityOpeningAuthority(
                        "emergency-watchdog:$reason"
                    )
                }}
            }},
            ANCHOR_AUTHORITY_EMERGENCY_HOLD_MS,
        )
'''
    text = one(text, old_watchdog, new_watchdog, "replace semantic timeout with emergency watchdog")

    insert_before = '''    private fun lockOpeningAnchorAuthority(
        bitmap: Bitmap,
        source: String,
    ) {
'''
    cancel_method = f'''    // {MARKER}: authoritative reversal/cancellation entrypoint. This is
    // called from SW_LID closed=true, where the service already has stronger
    // evidence than stale or unavailable hinge samples.
    fun cancelContinuityOpeningAuthority(reason: String) {{
        val hadAuthority =
            openingAnchorAuthorityArmed || openingAnchorAuthorityBitmap != null
        val hadProof =
            openingAnchorProofBitmap != null || openingAnchorProofGate != null
        val hadOpeningVisual = continuityOpeningVisual

        if (!hadAuthority && !hadProof && !hadOpeningVisual) return

        com.duoopen.debug.DuoDiagnostics.event(
            "opening-anchor-proof",
            "AUTHORITY_CANCEL display=$displayId reason=$reason " +
                "armed=$openingAnchorAuthorityArmed locked=${{openingAnchorAuthorityBitmap != null}} " +
                "proof=$hadProof openingVisual=$hadOpeningVisual",
        )

        if (hadProof) {{
            abortOpeningAnchorProof("authority-cancel:$reason")
        }}

        if (continuityOpeningVisual) {{
            endContinuityOpeningVisual("authority-cancel:$reason")
        }} else {{
            clearOpeningAnchorAuthority("authority-cancel:$reason")
            if (surface != null && isFold7CoverGeometryNow()) {{
                removeOverlay()
            }}
        }}
    }}

'''
    text = one(text, insert_before, cancel_method + insert_before, "insert authoritative cancel entrypoint")

    text = one(
        text,
        "        const val ANCHOR_AUTHORITY_MAX_HOLD_MS = 8_500L\n",
        "        const val ANCHOR_AUTHORITY_EMERGENCY_HOLD_MS = 30_000L\n",
        "authority emergency watchdog constant",
    )

    return text


def transform_service(text: str) -> str:
    if MARKER in text:
        return text

    old = '''                    if (closed) {
                        Fold7DisplayStatusStore.reset("lid-switch-closed")
                        continuity.onPhysicalClosedEdge("lid-switch-closed")
                        scope.launch(Dispatchers.IO) {
'''
    new = f'''                    if (closed) {{
                        Fold7DisplayStatusStore.reset("lid-switch-closed")
                        continuity.onPhysicalClosedEdge("lid-switch-closed")
                        // {MARKER}: SW_LID closed=true is authoritative reversal.
                        // Cancel the retained opening frame immediately instead
                        // of leaving it allocated until a wall-clock timeout.
                        for (engine in engines.values) {{
                            engine.cancelContinuityOpeningAuthority(
                                "lid-switch-closed"
                            )
                        }}
                        scope.launch(Dispatchers.IO) {{
'''
    return one(text, old, new, "cancel opening authority on authoritative lid close")


def validate(gradle: str, panel: str, service: str) -> None:
    required = (
        (gradle, ['versionCode = 58', 'versionName = "5.1.0-beta2-zfold7-s1x-lifecycle"']),
        (panel, [
            MARKER,
            "AUTHORITY_EMERGENCY_TIMEOUT",
            "cancelContinuityOpeningAuthority",
            "ANCHOR_AUTHORITY_EMERGENCY_HOLD_MS = 30_000L",
            '"emergency-watchdog:$reason"',
            "AUTHORITY_CANCEL",
            '"immutable-cover-authority"',
            "ANCHOR_PROOF_VISIBLE_HOLD_MS = 900L",
        ]),
        (service, [
            MARKER,
            'engine.cancelContinuityOpeningAuthority(',
            '"lid-switch-closed"',
        ]),
    )
    for content, needles in required:
        for needle in needles:
            if needle not in content:
                raise RuntimeError("missing S1X invariant: " + needle)

    forbidden = (
        "ANCHOR_AUTHORITY_MAX_HOLD_MS = 8_500L",
        'endContinuityOpeningVisual("anchor-authority-timeout")',
        '"AUTHORITY_TIMEOUT display=$displayId elapsedMs="',
    )
    for needle in forbidden:
        if needle in panel:
            raise RuntimeError("stale S1W semantic timeout survives: " + needle)


def apply(repo: Path, check: bool) -> None:
    paths = [repo / GRADLE, repo / PANEL, repo / SERVICE]
    if not all(path.exists() for path in paths):
        raise RuntimeError("required S1W materialized sources are missing")

    gradle = transform_gradle((repo / GRADLE).read_text(encoding="utf-8"))
    panel = transform_panel((repo / PANEL).read_text(encoding="utf-8"))
    service = transform_service((repo / SERVICE).read_text(encoding="utf-8"))

    validate(gradle, panel, service)

    if not check:
        (repo / GRADLE).write_text(gradle, encoding="utf-8")
        (repo / PANEL).write_text(panel, encoding="utf-8")
        (repo / SERVICE).write_text(service, encoding="utf-8")


def self_test() -> None:
    emergency_ms = 30_000

    def authority_alive(elapsed_ms: int, lid_closed: bool, owner_released: bool) -> bool:
        if lid_closed:
            return False
        if owner_released:
            return False
        return elapsed_ms < emergency_ms

    # Field-observed legitimate opening crossed the physical boundary at ~10.08 s.
    assert authority_alive(10_100, lid_closed=False, owner_released=False)
    # Reversal is semantic, not timer-based.
    assert not authority_alive(5_000, lid_closed=True, owner_released=False)
    # Real cover-owner release consumes the authority immediately.
    assert not authority_alive(10_100, lid_closed=False, owner_released=True)
    # A watchdog remains solely for leak containment.
    assert authority_alive(29_999, lid_closed=False, owner_released=False)
    assert not authority_alive(30_000, lid_closed=False, owner_released=False)
    print("S1X opening authority lifecycle model: PASS")


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
    print("S1X opening authority lifecycle: " + ("source shape verified" if args.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
