#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"
POLICY = ROOT / "app/src/main/java/com/duoopen/overlay/Fold7OpeningRemapHandoffPolicy.kt"
TEST = ROOT / "app/src/test/java/com/duoopen/overlay/Fold7OpeningRemapHandoffPolicyTest.kt"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


service = SERVICE.read_text(encoding="utf-8")

service = replace_once(
    service,
    '''    private var earlyOpeningVisualStarted =
        false
''',
    '''    private var earlyOpeningVisualStarted =
        false

    /**
     * Logical display identity that accepted the current CLOSED -> OPEN visual.
     *
     * Fold7 can morph that same logical display from cover geometry to inner
     * geometry during the handoff. Geometry is therefore routing evidence,
     * not permission to revoke the accepted visual attempt.
     */
    private var openingBridgeDisplayId: Int? =
        null
''',
    "opening bridge field",
)

service = replace_once(
    service,
    '''        val privilegedReady =
            ShizukuBridge.ready &&
                continuity.renderOwnershipEnabled

        /*
         * Alpha2 keeps Gen3 as the semantic/exact owner, but restores the
         * validated Fold7 snapshot/shader renderer for OPENING. The Alpha1
         * field trace showed its LiveBlur host failing to attach on every
         * accepted opening attempt.
         */
        for (engine in engines.values.toList()) {
            engine.setContinuityCoverOwned(
                owned =
                    privilegedReady &&
                        engine.isFold7CoverGeometryNow(),
                reason = "gen3:$reason",
            )
        }
''',
    '''        val privilegedReady =
            ShizukuBridge.ready &&
                continuity.renderOwnershipEnabled

        /*
         * Capture the accepted opening route before Gen3 reconciles topology.
         * On Fold7 the same logical display can morph 1080x2520 -> 1968x2184.
         * Losing cover geometry must not revoke an already accepted opening
         * visual before the successor route has had a chance to take over.
         */
        val openingDemandBeforeReconcile =
            ::gen3Visual.isInitialized &&
                gen3Visual.openingVisualDemandActive

        val openingHostBeforeReconcile =
            if (::gen3Visual.isInitialized) {
                gen3Visual.openingHostDisplayId
            } else {
                null
            }

        if (
            openingDemandBeforeReconcile &&
            openingHostBeforeReconcile != null &&
            openingBridgeDisplayId != openingHostBeforeReconcile
        ) {
            openingBridgeDisplayId =
                openingHostBeforeReconcile

            DuoDiagnostics.event(
                "cover-opening-visual",
                "BRIDGE-LATCH display=$openingHostBeforeReconcile reason=$reason",
            )
        }

        /*
         * Alpha2 keeps Gen3 as the semantic/exact owner, but restores the
         * validated Fold7 snapshot/shader renderer for OPENING. The Alpha1
         * field trace showed its LiveBlur host failing to attach on every
         * accepted opening attempt.
         */
        for (engine in engines.values.toList()) {
            val retainAcceptedOpeningOwner =
                Fold7OpeningRemapHandoffPolicy.shouldRetainAcceptedOpeningOnDisplay(
                    openingVisualActive =
                        openingDemandBeforeReconcile,
                    privilegedCaptureReady =
                        privilegedReady,
                    acceptedLogicalDisplayId =
                        openingBridgeDisplayId,
                    currentLogicalDisplayId =
                        engine.display.displayId,
                )

            engine.setContinuityCoverOwned(
                owned =
                    privilegedReady &&
                        (
                            engine.isFold7CoverGeometryNow() ||
                                retainAcceptedOpeningOwner
                            ),
                reason = "gen3:$reason",
            )
        }
''',
    "pre-reconcile owner retention",
)

service = replace_once(
    service,
    '''        val openingHostDisplayId =
            if (::gen3Visual.isInitialized) {
                gen3Visual.openingHostDisplayId
            } else {
                null
            }

        for (engine in engines.values.toList()) {
''',
    '''        val openingHostDisplayId =
            if (::gen3Visual.isInitialized) {
                gen3Visual.openingHostDisplayId
            } else {
                null
            }

        if (
            openingDemand &&
            openingHostDisplayId != null
        ) {
            openingBridgeDisplayId =
                openingHostDisplayId
        } else if (
            !openingDemand &&
            openingBridgeDisplayId != null
        ) {
            DuoDiagnostics.event(
                "cover-opening-visual",
                "BRIDGE-RELEASE display=$openingBridgeDisplayId reason=$reason",
            )
            openingBridgeDisplayId =
                null
        }

        for (engine in engines.values.toList()) {
''',
    "post-reconcile bridge lifetime",
)

service = replace_once(
    service,
    '''            if (runOpeningRenderer) {
                engine.beginContinuityOpeningVisual(
                    "gen3-opening-snapshot:$reason"
                )
            } else {
                engine.endContinuityOpeningVisual(
                    "gen3-opening-not-owner:$reason"
                )
            }
''',
    '''            val retainRemappedOpeningRenderer =
                Fold7OpeningRemapHandoffPolicy.shouldRetainAcceptedOpeningOnDisplay(
                    openingVisualActive =
                        openingDemand,
                    privilegedCaptureReady =
                        privilegedReady,
                    acceptedLogicalDisplayId =
                        openingBridgeDisplayId,
                    currentLogicalDisplayId =
                        engine.display.displayId,
                ) &&
                    engine.isFold7InnerGeometryNow()

            if (runOpeningRenderer) {
                engine.beginContinuityOpeningVisual(
                    "gen3-opening-snapshot:$reason"
                )
            } else if (retainRemappedOpeningRenderer) {
                /*
                 * Do not tear down the predecessor solely because Samsung
                 * morphed the accepted logical route to inner geometry. The
                 * PanelEngine sees the same display object and performs its
                 * existing after-swap inner bridge on the next hinge/evaluate
                 * pass. Terminal OPEN_INNER, reversal, privilege loss, or
                 * Gen3 cancellation still makes openingDemand false and
                 * reaches the normal end path below.
                 */
            } else {
                engine.endContinuityOpeningVisual(
                    "gen3-opening-not-owner:$reason"
                )
            }
''',
    "opening renderer retention",
)

SERVICE.write_text(service, encoding="utf-8")

policy = POLICY.read_text(encoding="utf-8")
policy = replace_once(
    policy,
    '''            privilegedCaptureReady
}''',
    '''            privilegedCaptureReady

    /**
     * Keep one accepted opening attempt tied to its logical route while
     * Samsung morphs that route between physical panel geometries.
     *
     * This is intentionally independent of current cover/inner geometry:
     * geometry selects the renderer, while acceptedLogicalDisplayId preserves
     * attempt identity. Privilege loss or semantic opening completion revokes
     * retention immediately.
     */
    fun shouldRetainAcceptedOpeningOnDisplay(
        openingVisualActive: Boolean,
        privilegedCaptureReady: Boolean,
        acceptedLogicalDisplayId: Int?,
        currentLogicalDisplayId: Int,
    ): Boolean =
        openingVisualActive &&
            privilegedCaptureReady &&
            acceptedLogicalDisplayId != null &&
            acceptedLogicalDisplayId == currentLogicalDisplayId
}''',
    "remap retention policy",
)
POLICY.write_text(policy, encoding="utf-8")

test = TEST.read_text(encoding="utf-8")
test = replace_once(
    test,
    '''    @Test
    fun doesNotTransferWhenPrivilegedCaptureIsUnavailable() {
        assertFalse(
            Fold7OpeningRemapHandoffPolicy.shouldTransferToInner(
                openingVisualActive = true,
                previousCoverOwned = true,
                coverGeometryNow = false,
                innerGeometryNow = true,
                privilegedCaptureReady = false,
            )
        )
    }
}''',
    '''    @Test
    fun doesNotTransferWhenPrivilegedCaptureIsUnavailable() {
        assertFalse(
            Fold7OpeningRemapHandoffPolicy.shouldTransferToInner(
                openingVisualActive = true,
                previousCoverOwned = true,
                coverGeometryNow = false,
                innerGeometryNow = true,
                privilegedCaptureReady = false,
            )
        )
    }

    @Test
    fun retainsAcceptedOpeningAcrossSameLogicalDisplayRemap() {
        assertTrue(
            Fold7OpeningRemapHandoffPolicy.shouldRetainAcceptedOpeningOnDisplay(
                openingVisualActive = true,
                privilegedCaptureReady = true,
                acceptedLogicalDisplayId = 0,
                currentLogicalDisplayId = 0,
            )
        )
    }

    @Test
    fun doesNotRetainOpeningAfterSemanticDemandEnds() {
        assertFalse(
            Fold7OpeningRemapHandoffPolicy.shouldRetainAcceptedOpeningOnDisplay(
                openingVisualActive = false,
                privilegedCaptureReady = true,
                acceptedLogicalDisplayId = 0,
                currentLogicalDisplayId = 0,
            )
        )
    }

    @Test
    fun doesNotRetainOpeningAfterPrivilegeLoss() {
        assertFalse(
            Fold7OpeningRemapHandoffPolicy.shouldRetainAcceptedOpeningOnDisplay(
                openingVisualActive = true,
                privilegedCaptureReady = false,
                acceptedLogicalDisplayId = 0,
                currentLogicalDisplayId = 0,
            )
        )
    }

    @Test
    fun doesNotRetainOpeningOnDifferentLogicalDisplay() {
        assertFalse(
            Fold7OpeningRemapHandoffPolicy.shouldRetainAcceptedOpeningOnDisplay(
                openingVisualActive = true,
                privilegedCaptureReady = true,
                acceptedLogicalDisplayId = 0,
                currentLogicalDisplayId = 1,
            )
        )
    }
}''',
    "remap retention tests",
)
TEST.write_text(test, encoding="utf-8")

print("Applied Fold7 opening remap handoff fix")
print(SERVICE.relative_to(ROOT))
print(POLICY.relative_to(ROOT))
print(TEST.relative_to(ROOT))
