package com.duoopen.overlay

/**
 * Pure admission rule for the Fold7 CLOSED -> OPEN renderer handoff.
 *
 * Samsung may keep the same logical display id while its geometry changes from
 * cover (1080x2520) to inner (1968x2184). That geometry mutation is a route
 * handoff, not proof that the accepted opening attempt has ended.
 */
internal object Fold7OpeningRemapHandoffPolicy {
    fun shouldTransferToInner(
        openingVisualActive: Boolean,
        previousCoverOwned: Boolean,
        coverGeometryNow: Boolean,
        innerGeometryNow: Boolean,
        privilegedCaptureReady: Boolean,
    ): Boolean =
        openingVisualActive &&
            previousCoverOwned &&
            !coverGeometryNow &&
            innerGeometryNow &&
            privilegedCaptureReady

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
}
