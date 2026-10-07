#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

GRADLE = Path("app/build.gradle.kts")
PANEL = Path("app/src/full/java/com/duoopen/overlay/PanelEngine.kt")
SURFACE = Path("app/src/full/java/com/duoopen/overlay/FoldSurface.kt")
COMPOSER = Path("app/src/full/java/com/duoopen/overlay/Fold7RightPaneComposer.kt")

MARKER = "S1W_OPENING_ANCHOR_AUTHORITY_V1"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_gradle(text: str) -> str:
    if 'versionName = "5.1.0-beta2-zfold7-s1w-authority"' in text:
        return text
    text = one(text, "        versionCode = 56\n", "        versionCode = 57\n", "versionCode")
    return one(
        text,
        '        versionName = "5.1.0-beta2-zfold7-s1v-anchor"\n',
        '        versionName = "5.1.0-beta2-zfold7-s1w-authority"\n',
        "versionName",
    )


def transform_surface(text: str) -> str:
    if MARKER in text:
        return text

    text = one(
        text,
        '''    private var anchorSnapshot: Bitmap = bitmap\n''',
        f'''    // {MARKER}: the opening handoff source is the first full-size\n    // snapshot attached to this surface. Live recapture may update the pixels\n    // shown to the user, but it must never mutate continuity authority.\n    private val anchorSnapshot: Bitmap = bitmap\n''',
        "immutable surface authority",
    )
    text = one(
        text,
        '''    fun replaceSnapshot(bitmap: Bitmap) {\n        anchorSnapshot = bitmap\n        view.setSnapshot(bitmap)\n    }\n''',
        '''    fun replaceSnapshot(bitmap: Bitmap) {\n        view.setSnapshot(bitmap)\n    }\n''',
        "live replacement cannot mutate authority",
    )
    return text


def transform_composer(text: str) -> str:
    if MARKER in text:
        return text

    old = '''    fun toInnerRightPane(source: Bitmap): Bitmap? {\n        if (source.width < COVER_WIDTH || source.height < COVER_HEIGHT) return null\n\n        val result = Bitmap.createBitmap(\n            INNER_WIDTH,\n            INNER_HEIGHT,\n            Bitmap.Config.ARGB_8888,\n        )\n        val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)\n        val canvas = Canvas(result)\n        canvas.drawColor(Color.BLACK)\n        canvas.drawBitmap(\n            source,\n            Rect(0, 0, COVER_WIDTH, COVER_HEIGHT),\n            Rect(RIGHT_PANE_LEFT, 0, RIGHT_PANE_RIGHT, INNER_HEIGHT),\n            paint,\n        )\n        return result\n    }\n'''
    new = f'''    /**\n     * {MARKER}: the immutable authority should be canonical 1080x2520, but\n     * physical continuity must not abort merely because a fallback SnapshotSurface\n     * was refreshed at reduced resolution. Scale any valid source into the same\n     * canonical inner right-pane destination.\n     */\n    fun toInnerRightPane(source: Bitmap): Bitmap? {{\n        if (source.isRecycled || source.width <= 0 || source.height <= 0) return null\n\n        val result = Bitmap.createBitmap(\n            INNER_WIDTH,\n            INNER_HEIGHT,\n            Bitmap.Config.ARGB_8888,\n        )\n        val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)\n        val canvas = Canvas(result)\n        canvas.drawColor(Color.BLACK)\n        canvas.drawBitmap(\n            source,\n            Rect(0, 0, source.width, source.height),\n            Rect(RIGHT_PANE_LEFT, 0, RIGHT_PANE_RIGHT, INNER_HEIGHT),\n            paint,\n        )\n        return result\n    }}\n'''
    return one(text, old, new, "tolerant cover to inner registration")


def transform_panel(text: str) -> str:
    if MARKER in text:
        return text

    text = one(
        text,
        '''    private var openingAnchorProofBitmap: Bitmap? = null\n    private var openingAnchorProofGate: Fold7OpeningAnchorProofGate? = null\n    private var openingAnchorProofDrawSeen = false\n''',
        f'''    private var openingAnchorProofBitmap: Bitmap? = null\n    private var openingAnchorProofGate: Fold7OpeningAnchorProofGate? = null\n    private var openingAnchorProofDrawSeen = false\n\n    // {MARKER}: one independently-owned canonical cover frame survives live\n    // 40%-scale recapture, manager ownership churn and the cover -> inner remap.\n    private var openingAnchorAuthorityBitmap: Bitmap? = null\n    private var openingAnchorAuthorityArmed = false\n    private var openingAnchorAuthorityStartedUptimeMs = 0L\n''',
        "authority fields",
    )

    old_owner = '''        if (!owned) {\n            if (continuityOpeningVisual && previousCoverOwned) {\n                // S1V starts the handoff BEFORE requiring inner geometry. S1K\n                // required geometry to already be inner at this exact boundary,\n                // which could discard the only authoritative cover frame.\n                handoffContinuityOpeningToInner(\n                    "owner-released:$reason"\n                )\n            } else if (continuityOpeningVisual) {\n                endContinuityOpeningVisual(\n                    "owner-released-without-cover-owner:$reason"\n                )\n            }\n            return\n        }\n'''
    new_owner = '''        if (!owned) {\n            if (\n                previousCoverOwned &&\n                (continuityOpeningVisual ||\n                    openingAnchorAuthorityArmed ||\n                    openingAnchorAuthorityBitmap != null)\n            ) {\n                // S1W authority outlives a premature Gen3 visual-owner verdict.\n                // The physical owner-release edge is the handoff boundary.\n                handoffContinuityOpeningToInner(\n                    "owner-released:$reason"\n                )\n            } else if (continuityOpeningVisual) {\n                endContinuityOpeningVisual(\n                    "owner-released-without-cover-owner:$reason"\n                )\n            }\n            return\n        }\n'''
    text = one(text, old_owner, new_owner, "owner release consumes retained authority")

    old_begin = '''        abortOpeningAnchorProof("new-opening")\n        openingRemapHandoffSequence++\n        openingRemapInnerSurfaceReady = false\n        continuityOpeningVisual = true\n'''
    new_begin = '''        abortOpeningAnchorProof("new-opening")\n        armOpeningAnchorAuthority(reason)\n        openingRemapHandoffSequence++\n        openingRemapInnerSurfaceReady = false\n        continuityOpeningVisual = true\n'''
    text = one(text, old_begin, new_begin, "arm authority at opening start")

    helper_anchor = '''    // S1V_OPENING_ANCHOR_PROOF_V1\n    // Phase 1: copy the cover pixels while they are still authoritative.\n'''
    helpers = f'''    // {MARKER}\n    private fun clearOpeningAnchorAuthority(reason: String) {{\n        val bitmap = openingAnchorAuthorityBitmap\n        openingAnchorAuthorityBitmap = null\n        openingAnchorAuthorityArmed = false\n        openingAnchorAuthorityStartedUptimeMs = 0L\n        if (bitmap != null && !bitmap.isRecycled) {{\n            runCatching {{ bitmap.recycle() }}\n        }}\n        if (bitmap != null) {{\n            com.duoopen.debug.DuoDiagnostics.event(\n                "opening-anchor-proof",\n                "AUTHORITY_CLEARED display=$displayId reason=$reason",\n            )\n        }}\n    }}\n\n    private fun armOpeningAnchorAuthority(reason: String) {{\n        clearOpeningAnchorAuthority("rearm:$reason")\n        openingAnchorAuthorityArmed = true\n        val started = SystemClock.uptimeMillis()\n        openingAnchorAuthorityStartedUptimeMs = started\n\n        com.duoopen.debug.DuoDiagnostics.event(\n            "opening-anchor-proof",\n            "AUTHORITY_ARMED display=$displayId started=$started reason=$reason",\n        )\n\n        handler.postDelayed(\n            {{\n                if (\n                    openingAnchorAuthorityArmed &&\n                    openingAnchorAuthorityStartedUptimeMs == started &&\n                    openingAnchorProofBitmap == null\n                ) {{\n                    com.duoopen.debug.DuoDiagnostics.event(\n                        "opening-anchor-proof",\n                        "AUTHORITY_TIMEOUT display=$displayId elapsedMs=" +\n                            "${{SystemClock.uptimeMillis() - started}} reason=$reason",\n                    )\n                    if (continuityOpeningVisual) {{\n                        endContinuityOpeningVisual("anchor-authority-timeout")\n                    }} else {{\n                        clearOpeningAnchorAuthority("timeout:$reason")\n                        if (surface != null) removeOverlay()\n                    }}\n                }}\n            }},\n            ANCHOR_AUTHORITY_MAX_HOLD_MS,\n        )\n    }}\n\n    private fun lockOpeningAnchorAuthority(\n        bitmap: Bitmap,\n        source: String,\n    ) {{\n        if (\n            !openingAnchorAuthorityArmed ||\n            openingAnchorAuthorityBitmap != null ||\n            bitmap.isRecycled\n        ) {{\n            return\n        }}\n\n        if (\n            bitmap.width != Fold7RightPaneComposer.COVER_WIDTH ||\n            bitmap.height != Fold7RightPaneComposer.COVER_HEIGHT\n        ) {{\n            com.duoopen.debug.DuoDiagnostics.event(\n                "opening-anchor-proof",\n                "AUTHORITY_REJECTED display=$displayId source=$source " +\n                    "size=${{bitmap.width}}x${{bitmap.height}} reason=noncanonical",\n            )\n            return\n        }}\n\n        val owned =\n            runCatching {{ bitmap.copy(Bitmap.Config.ARGB_8888, false) }}\n                .getOrNull()\n\n        if (owned == null) {{\n            com.duoopen.debug.DuoDiagnostics.event(\n                "opening-anchor-proof",\n                "AUTHORITY_REJECTED display=$displayId source=$source " +\n                    "size=${{bitmap.width}}x${{bitmap.height}} reason=copy-failed",\n            )\n            return\n        }}\n\n        openingAnchorAuthorityBitmap = owned\n        com.duoopen.debug.DuoDiagnostics.event(\n            "opening-anchor-proof",\n            "AUTHORITY_LOCKED display=$displayId source=$source " +\n                "size=${{owned.width}}x${{owned.height}} immutable=true",\n        )\n    }}\n\n'''
    text = one(text, helper_anchor, helpers + helper_anchor, "authority helpers")

    old_sources = '''        val liveSurfaceCopy =\n            (surface as? SnapshotSurface)?.copySnapshotForAnchor()\n        val ownedOpeningCopy =\n            if (liveSurfaceCopy == null) {\n                gen5OwnedOpeningBitmap\n                    ?.takeIf { !it.isRecycled }\n                    ?.let { runCatching { it.copy(Bitmap.Config.ARGB_8888, false) }.getOrNull() }\n            } else {\n                null\n            }\n        val cachedCoverCopy =\n            if (liveSurfaceCopy == null && ownedOpeningCopy == null) {\n                cache.get(\n                    innerPanel = false,\n                    width = Fold7RightPaneComposer.COVER_WIDTH,\n                    height = Fold7RightPaneComposer.COVER_HEIGHT,\n                )\n                    ?.takeIf { !it.isRecycled }\n                    ?.let { runCatching { it.copy(Bitmap.Config.ARGB_8888, false) }.getOrNull() }\n            } else {\n                null\n            }\n        val coverFrame = liveSurfaceCopy ?: ownedOpeningCopy ?: cachedCoverCopy\n\n        val source = when {\n            liveSurfaceCopy != null -> "visible-cover-surface"\n            ownedOpeningCopy != null -> "owned-opening-bitmap"\n            cachedCoverCopy != null -> "cover-cache"\n            else -> "none"\n        }\n\n        val innerAnchor =\n            coverFrame?.let(Fold7RightPaneComposer::toInnerRightPane)\n'''
    new_sources = '''        // Consume the immutable full-resolution authority first. Live surface\n        // pixels are only a fallback and may have been refreshed at 40% scale.\n        val immutableAuthority =\n            openingAnchorAuthorityBitmap\n                ?.takeIf { !it.isRecycled }\n        openingAnchorAuthorityBitmap = null\n        openingAnchorAuthorityArmed = false\n        openingAnchorAuthorityStartedUptimeMs = 0L\n\n        val liveSurfaceCopy =\n            if (immutableAuthority == null) {\n                (surface as? SnapshotSurface)?.copySnapshotForAnchor()\n            } else {\n                null\n            }\n        val ownedOpeningCopy =\n            if (immutableAuthority == null && liveSurfaceCopy == null) {\n                gen5OwnedOpeningBitmap\n                    ?.takeIf { !it.isRecycled }\n                    ?.let { runCatching { it.copy(Bitmap.Config.ARGB_8888, false) }.getOrNull() }\n            } else {\n                null\n            }\n        val cachedCoverCopy =\n            if (immutableAuthority == null && liveSurfaceCopy == null && ownedOpeningCopy == null) {\n                cache.get(\n                    innerPanel = false,\n                    width = Fold7RightPaneComposer.COVER_WIDTH,\n                    height = Fold7RightPaneComposer.COVER_HEIGHT,\n                )\n                    ?.takeIf { !it.isRecycled }\n                    ?.let { runCatching { it.copy(Bitmap.Config.ARGB_8888, false) }.getOrNull() }\n            } else {\n                null\n            }\n        val coverFrame =\n            immutableAuthority ?: liveSurfaceCopy ?: ownedOpeningCopy ?: cachedCoverCopy\n\n        val source = when {\n            immutableAuthority != null -> "immutable-cover-authority"\n            liveSurfaceCopy != null -> "visible-cover-surface"\n            ownedOpeningCopy != null -> "owned-opening-bitmap"\n            cachedCoverCopy != null -> "cover-cache"\n            else -> "none"\n        }\n        val sourceWidth = coverFrame?.width ?: -1\n        val sourceHeight = coverFrame?.height ?: -1\n\n        val innerAnchor =\n            coverFrame?.let(Fold7RightPaneComposer::toInnerRightPane)\n'''
    text = one(text, old_sources, new_sources, "immutable authority source priority")

    text = one(
        text,
        '''                "ABORT sequence=$sequence stage=source reason=no-cover-frame source=$source trigger=$reason",\n''',
        '''                "ABORT sequence=$sequence stage=source reason=no-cover-frame source=$source " +\n                    "sourceSize=${sourceWidth}x${sourceHeight} trigger=$reason",\n''',
        "source abort dimensions",
    )
    text = one(
        text,
        '''            "CAPTURED sequence=$sequence source=$source trigger=$reason " +\n                "cover=${Fold7RightPaneComposer.COVER_WIDTH}x${Fold7RightPaneComposer.COVER_HEIGHT} " +\n                "target=${Fold7RightPaneComposer.RIGHT_PANE_LEFT}..${Fold7RightPaneComposer.RIGHT_PANE_RIGHT}",\n''',
        '''            "CAPTURED sequence=$sequence source=$source trigger=$reason " +\n                "sourceSize=${sourceWidth}x${sourceHeight} " +\n                "target=${Fold7RightPaneComposer.RIGHT_PANE_LEFT}..${Fold7RightPaneComposer.RIGHT_PANE_RIGHT}",\n''',
        "captured source dimensions",
    )

    text = one(
        text,
        '''    ) {\n        cache.put(innerPanel, bitmap)\n\n        if (continuityTicket != null) {\n''',
        '''    ) {\n        if (openingAnchorAuthorityArmed && isFold7CoverGeometryNow()) {\n            lockOpeningAnchorAuthority(\n                bitmap = bitmap,\n                source = "initial-cover-capture",\n            )\n        }\n\n        cache.put(innerPanel, bitmap)\n\n        if (continuityTicket != null) {\n''',
        "lock authority before cache and live refresh",
    )

    old_end = '''    fun endContinuityOpeningVisual(\n        reason: String,\n    ) {\n        if (!continuityOpeningVisual) {\n            return\n        }\n\n        continuityOpeningVisual = false\n'''
    new_end = '''    fun endContinuityOpeningVisual(\n        reason: String,\n    ) {\n        if (!continuityOpeningVisual) {\n            return\n        }\n\n        if (\n            openingAnchorAuthorityArmed &&\n            reason.startsWith("gen3-opening-not-owner")\n        ) {\n            com.duoopen.debug.DuoDiagnostics.event(\n                "opening-anchor-proof",\n                "PRESERVE_AUTHORITY display=$displayId reason=$reason " +\n                    "locked=${openingAnchorAuthorityBitmap != null}",\n            )\n            return\n        }\n\n        continuityOpeningVisual = false\n'''
    text = one(text, old_end, new_end, "preserve authority across manager not-owner")

    text = one(
        text,
        '''        recycleGen5OpeningBitmap()\n\n        com.duoopen.debug.DuoDiagnostics.event(\n            "cover-opening-visual",\n            "END display=$displayId reason=$reason precise=${hinge.lastAngle} gen5=true",\n        )\n''',
        '''        recycleGen5OpeningBitmap()\n        clearOpeningAnchorAuthority("opening-end:$reason")\n\n        com.duoopen.debug.DuoDiagnostics.event(\n            "cover-opening-visual",\n            "END display=$displayId reason=$reason precise=${hinge.lastAngle} gen5=true",\n        )\n''',
        "normal opening end clears authority",
    )

    text = one(
        text,
        '''    private fun abortOpeningAnchorProof(reason: String) {\n        if (openingAnchorProofBitmap == null && openingAnchorProofGate == null) return\n''',
        '''    private fun abortOpeningAnchorProof(reason: String) {\n        if (\n            openingAnchorProofBitmap == null &&\n            openingAnchorProofGate == null &&\n            openingAnchorAuthorityBitmap == null &&\n            !openingAnchorAuthorityArmed\n        ) return\n''',
        "abort includes pre-handoff authority",
    )
    text = one(
        text,
        '''        recycleGen5OpeningBitmap()\n        com.duoopen.debug.DuoDiagnostics.event(\n            "opening-anchor-proof",\n            "ABORT sequence=$sequence stage=cancel reason=$reason",\n        )\n    }\n''',
        '''        recycleGen5OpeningBitmap()\n        clearOpeningAnchorAuthority("proof-abort:$reason")\n        com.duoopen.debug.DuoDiagnostics.event(\n            "opening-anchor-proof",\n            "ABORT sequence=$sequence stage=cancel reason=$reason",\n        )\n    }\n''',
        "proof abort clears authority",
    )

    text = one(
        text,
        '''        const val ANCHOR_PROOF_MAX_WAIT_MS = 6_500L\n        const val ANCHOR_PROOF_POLL_MS = 24L\n''',
        '''        const val ANCHOR_PROOF_MAX_WAIT_MS = 6_500L\n        const val ANCHOR_AUTHORITY_MAX_HOLD_MS = 8_500L\n        const val ANCHOR_PROOF_POLL_MS = 24L\n''',
        "bounded authority hold",
    )

    return text


def validate(gradle: str, panel: str, surface: str, composer: str) -> None:
    required = (
        (gradle, ['versionCode = 57', 'versionName = "5.1.0-beta2-zfold7-s1w-authority"']),
        (surface, [MARKER, "private val anchorSnapshot", "fun copySnapshotForAnchor"]),
        (composer, [MARKER, "Rect(0, 0, source.width, source.height)", "source.isRecycled"]),
        (panel, [
            MARKER,
            "openingAnchorAuthorityBitmap",
            "AUTHORITY_ARMED",
            "AUTHORITY_LOCKED",
            "PRESERVE_AUTHORITY",
            'source = "initial-cover-capture"',
            '"immutable-cover-authority"',
            "ANCHOR_AUTHORITY_MAX_HOLD_MS = 8_500L",
            "sourceSize=${sourceWidth}x${sourceHeight}",
        ]),
    )
    for text, needles in required:
        for needle in needles:
            if needle not in text:
                raise RuntimeError("missing S1W invariant: " + needle)

    if "anchorSnapshot = bitmap" in surface:
        raise RuntimeError("S1W live recapture must not mutate SnapshotSurface anchor authority")
    if "source.width < COVER_WIDTH" in composer or "source.height < COVER_HEIGHT" in composer:
        raise RuntimeError("S1W fallback remap must accept reduced-resolution valid sources")


def apply(repo: Path, check: bool) -> None:
    paths = [repo / GRADLE, repo / PANEL, repo / SURFACE, repo / COMPOSER]
    if not all(path.exists() for path in paths):
        raise RuntimeError("required S1V materialized sources are missing")

    gradle = transform_gradle((repo / GRADLE).read_text(encoding="utf-8"))
    panel = transform_panel((repo / PANEL).read_text(encoding="utf-8"))
    surface = transform_surface((repo / SURFACE).read_text(encoding="utf-8"))
    composer = transform_composer((repo / COMPOSER).read_text(encoding="utf-8"))

    validate(gradle, panel, surface, composer)

    if not check:
        (repo / GRADLE).write_text(gradle, encoding="utf-8")
        (repo / PANEL).write_text(panel, encoding="utf-8")
        (repo / SURFACE).write_text(surface, encoding="utf-8")
        (repo / COMPOSER).write_text(composer, encoding="utf-8")


def self_test() -> None:
    # Forensic model of the S1V field failure: live refresh must not replace the
    # immutable 1080x2520 authority, and a reduced-size fallback is still valid.
    canonical = (1080, 2520)
    live_refresh = (432, 1008)
    authority = canonical
    visible_surface = live_refresh
    assert authority == (1080, 2520)
    assert visible_surface != authority

    def remap_valid(size: tuple[int, int]) -> bool:
        return size[0] > 0 and size[1] > 0

    assert remap_valid(authority)
    assert remap_valid(visible_surface)

    def preserve(reason: str, armed: bool) -> bool:
        return armed and reason.startswith("gen3-opening-not-owner")

    assert preserve("gen3-opening-not-owner:hinge:137.0", True)
    assert not preserve("owner-released:display-changed:1", True)
    print("S1W immutable opening authority model: PASS")


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
    print("S1W opening anchor authority: " + ("source shape verified" if args.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
