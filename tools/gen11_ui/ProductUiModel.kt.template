package com.duoopen.ui

/** Pure product-facing state so readiness and CTA wording can be regression-tested. */
data class ProductUiState(
    val headline: String,
    val detail: String,
    val ready: Boolean,
    val primaryAction: String,
)

fun productUiState(
    overlayEnabled: Boolean,
    shizukuReady: Boolean,
    hingeAngle: Float,
    simulated: Boolean,
): ProductUiState =
    when {
        !overlayEnabled ->
            ProductUiState(
                headline = "Setup required",
                detail = "Enable Duo Open accessibility to give the continuity engine full-screen authority.",
                ready = false,
                primaryAction = "Finish setup",
            )

        !shizukuReady ->
            ProductUiState(
                headline = "Precision bridge offline",
                detail = "Authorize Shizuku for the Fold7 panel bridge and precise hinge geometry.",
                ready = false,
                primaryAction = "Finish setup",
            )

        hingeAngle.isNaN() ->
            ProductUiState(
                headline = "Waiting for hinge",
                detail = "The engine is armed and waiting for a geometry sample from the Fold7.",
                ready = false,
                primaryAction = "Open controls",
            )

        simulated ->
            ProductUiState(
                headline = "Simulation active",
                detail = "Preview geometry is being driven by the simulator instead of live hardware.",
                ready = true,
                primaryAction = "Test continuity",
            )

        else ->
            ProductUiState(
                headline = "Continuity ready",
                detail = "Full-screen continuity, precision geometry, and the visual pipeline are available.",
                ready = true,
                primaryAction = "Test continuity",
            )
    }

fun useExpandedProductLayout(widthDp: Int): Boolean = widthDp >= 700
