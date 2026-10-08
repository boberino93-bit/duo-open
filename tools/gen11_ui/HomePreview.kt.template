package com.duoopen.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.roundToInt

private val Ready = Color(0xFF65F3C4)
private val Warn = Color(0xFFFFC857)
private val Offline = Color(0xFFFF7A90)

/**
 * GEN11_PRODUCT_UI
 *
 * Product-facing adaptive continuity console. Runtime fold ownership remains in
 * the existing overlay/shell architecture; this composable only observes that
 * state and exposes the same actions as the predecessor surface.
 */
@Composable
fun HomePreview(
    image: ImageBitmap?,
    hingeAngle: Float,
    paneTilt: Float,
    simulated: Boolean,
    wallpaperActive: Boolean,
    overlayEnabled: Boolean,
    shizukuReady: Boolean,
    onTest: () -> Unit,
    onSetWallpaper: () -> Unit,
    onTune: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val state =
        productUiState(
            overlayEnabled = overlayEnabled,
            shizukuReady = shizukuReady,
            hingeAngle = hingeAngle,
            simulated = simulated,
        )

    Box(
        modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
    ) {
        if (image != null) {
            Image(
                bitmap = image,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                alpha = 0.30f,
                modifier = Modifier.fillMaxSize(),
            )
        }

        Box(
            Modifier
                .fillMaxSize()
                .background(
                    Brush.verticalGradient(
                        0f to MaterialTheme.colorScheme.background.copy(alpha = 0.52f),
                        0.46f to MaterialTheme.colorScheme.background.copy(alpha = 0.78f),
                        1f to MaterialTheme.colorScheme.background,
                    )
                )
        )

        BoxWithConstraints(
            Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .navigationBarsPadding()
                .padding(horizontal = 20.dp, vertical = 16.dp)
        ) {
            val expanded = useExpandedProductLayout(maxWidth.value.roundToInt())

            if (expanded) {
                Column(Modifier.fillMaxSize()) {
                    ProductHeader()
                    Spacer(Modifier.height(18.dp))
                    Row(
                        Modifier.fillMaxSize(),
                        horizontalArrangement = Arrangement.spacedBy(18.dp),
                    ) {
                        ContinuityVisual(
                            image = image,
                            hingeAngle = hingeAngle,
                            paneTilt = paneTilt,
                            simulated = simulated,
                            modifier = Modifier.weight(1.15f),
                        )
                        StatusPanel(
                            state = state,
                            hingeAngle = hingeAngle,
                            paneTilt = paneTilt,
                            wallpaperActive = wallpaperActive,
                            overlayEnabled = overlayEnabled,
                            shizukuReady = shizukuReady,
                            onPrimary = if (state.ready) onTest else onTune,
                            onTune = onTune,
                            onSetWallpaper = onSetWallpaper,
                            modifier = Modifier.weight(0.85f),
                        )
                    }
                }
            } else {
                Column(
                    Modifier
                        .fillMaxSize()
                        .verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(14.dp),
                ) {
                    ProductHeader()
                    ContinuityVisual(
                        image = image,
                        hingeAngle = hingeAngle,
                        paneTilt = paneTilt,
                        simulated = simulated,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    StatusPanel(
                        state = state,
                        hingeAngle = hingeAngle,
                        paneTilt = paneTilt,
                        wallpaperActive = wallpaperActive,
                        overlayEnabled = overlayEnabled,
                        shizukuReady = shizukuReady,
                        onPrimary = if (state.ready) onTest else onTune,
                        onTune = onTune,
                        onSetWallpaper = onSetWallpaper,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Spacer(Modifier.height(6.dp))
                }
            }
        }
    }
}

@Composable
private fun ProductHeader() {
    Row(
        Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(
                "DUO OPEN",
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.Bold,
                letterSpacing = 2.4.sp,
            )
            Text(
                "Continuity Console",
                style = MaterialTheme.typography.headlineMedium,
                color = MaterialTheme.colorScheme.onBackground,
                fontWeight = FontWeight.SemiBold,
            )
        }

        Surface(
            shape = RoundedCornerShape(999.dp),
            color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.72f),
            border =
                androidx.compose.foundation.BorderStroke(
                    1.dp,
                    MaterialTheme.colorScheme.outline.copy(alpha = 0.35f),
                ),
        ) {
            Text(
                "FOLD7 · ONE UI 9",
                modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                fontWeight = FontWeight.SemiBold,
            )
        }
    }
}

@Composable
private fun ContinuityVisual(
    image: ImageBitmap?,
    hingeAngle: Float,
    paneTilt: Float,
    simulated: Boolean,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(32.dp),
        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.92f),
        tonalElevation = 8.dp,
        border =
            androidx.compose.foundation.BorderStroke(
                1.dp,
                MaterialTheme.colorScheme.outline.copy(alpha = 0.28f),
            ),
    ) {
        Box(
            Modifier
                .fillMaxWidth()
                .height(360.dp)
                .clip(RoundedCornerShape(32.dp))
        ) {
            if (image != null) {
                Image(
                    bitmap = image,
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    alpha = 0.55f,
                    modifier = Modifier.fillMaxSize(),
                )
            }

            Box(
                Modifier
                    .fillMaxSize()
                    .background(
                        Brush.radialGradient(
                            listOf(
                                MaterialTheme.colorScheme.primary.copy(alpha = 0.17f),
                                Color.Transparent,
                            )
                        )
                    )
            )

            Column(
                Modifier
                    .fillMaxSize()
                    .padding(24.dp),
                verticalArrangement = Arrangement.SpaceBetween,
            ) {
                Row(
                    Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        if (simulated) "SIMULATION" else "LIVE GEOMETRY",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.2.sp,
                    )
                    Spacer(Modifier.weight(1f))
                    Text(
                        if (hingeAngle.isNaN()) "—°" else "${hingeAngle.roundToInt()}°",
                        style = MaterialTheme.typography.titleLarge,
                        color = MaterialTheme.colorScheme.onSurface,
                        fontWeight = FontWeight.Medium,
                    )
                }

                FoldDeviceGraphic(
                    hingeAngle = hingeAngle,
                    paneTilt = paneTilt,
                    modifier = Modifier.align(Alignment.CenterHorizontally),
                )

                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    MiniMetric(
                        label = "HINGE",
                        value = if (hingeAngle.isNaN()) "WAIT" else "${hingeAngle.roundToInt()}°",
                        modifier = Modifier.weight(1f),
                    )
                    MiniMetric(
                        label = "VISUAL",
                        value = if (paneTilt < 0.05f) "FLAT" else "ACTIVE",
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        }
    }
}

@Composable
private fun FoldDeviceGraphic(
    hingeAngle: Float,
    paneTilt: Float,
    modifier: Modifier = Modifier,
) {
    val progress =
        if (hingeAngle.isNaN()) {
            0.55f
        } else {
            hingeAngle.coerceIn(0f, 180f) / 180f
        }

    val movingWidth = (54f + 70f * progress).dp
    val glow = MaterialTheme.colorScheme.primary.copy(alpha = 0.28f)

    Row(
        modifier,
        horizontalArrangement = Arrangement.spacedBy(5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier
                .width(124.dp)
                .height(188.dp)
                .clip(RoundedCornerShape(topStart = 24.dp, bottomStart = 24.dp))
                .background(
                    Brush.verticalGradient(
                        listOf(
                            MaterialTheme.colorScheme.onSurface.copy(alpha = 0.18f),
                            MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.72f),
                        )
                    )
                )
                .border(
                    1.dp,
                    MaterialTheme.colorScheme.outline.copy(alpha = 0.48f),
                    RoundedCornerShape(topStart = 24.dp, bottomStart = 24.dp),
                )
        )

        Box(
            Modifier
                .width(3.dp)
                .height(164.dp)
                .clip(CircleShape)
                .background(
                    if (paneTilt > 0.05f) glow else MaterialTheme.colorScheme.outline.copy(alpha = 0.3f)
                )
        )

        Box(
            Modifier
                .width(movingWidth)
                .height(188.dp)
                .clip(RoundedCornerShape(topEnd = 24.dp, bottomEnd = 24.dp))
                .background(
                    Brush.verticalGradient(
                        listOf(
                            MaterialTheme.colorScheme.primary.copy(alpha = 0.16f),
                            MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.82f),
                        )
                    )
                )
                .border(
                    1.dp,
                    MaterialTheme.colorScheme.primary.copy(alpha = 0.38f),
                    RoundedCornerShape(topEnd = 24.dp, bottomEnd = 24.dp),
                )
        )
    }
}

@Composable
private fun StatusPanel(
    state: ProductUiState,
    hingeAngle: Float,
    paneTilt: Float,
    wallpaperActive: Boolean,
    overlayEnabled: Boolean,
    shizukuReady: Boolean,
    onPrimary: () -> Unit,
    onTune: () -> Unit,
    onSetWallpaper: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(32.dp),
        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.96f),
        border =
            androidx.compose.foundation.BorderStroke(
                1.dp,
                MaterialTheme.colorScheme.outline.copy(alpha = 0.26f),
            ),
    ) {
        Column(
            Modifier.padding(22.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Row(
                Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                StatusDot(state.ready)
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(
                        state.headline,
                        style = MaterialTheme.typography.titleLarge,
                        color = MaterialTheme.colorScheme.onSurface,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        state.detail,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                ReadinessRow(
                    title = "Full-screen service",
                    detail = if (overlayEnabled) "Accessibility authority active" else "Enable Duo Open accessibility",
                    active = overlayEnabled,
                )
                ReadinessRow(
                    title = "Precision bridge",
                    detail = if (shizukuReady) "Shizuku ready" else "Shizuku authorization required",
                    active = shizukuReady,
                )
                ReadinessRow(
                    title = "Hinge telemetry",
                    detail =
                        when {
                            hingeAngle.isNaN() -> "Waiting for geometry"
                            paneTilt < 0.05f -> "Geometry available · visual flat"
                            else -> "Tracking · visual active"
                        },
                    active = !hingeAngle.isNaN(),
                )
            }

            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Button(
                    onClick = onPrimary,
                    modifier = Modifier.weight(1f),
                    colors =
                        ButtonDefaults.buttonColors(
                            containerColor = MaterialTheme.colorScheme.primary,
                            contentColor = MaterialTheme.colorScheme.onPrimary,
                        ),
                ) {
                    Text(state.primaryAction)
                }
                FilledTonalButton(
                    onClick = onTune,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Controls")
                }
            }

            TextButton(
                onClick = onSetWallpaper,
                modifier = Modifier.align(Alignment.End),
            ) {
                Text(if (wallpaperActive) "Wallpaper settings" else "Set Duo wallpaper")
            }
        }
    }
}

@Composable
private fun ReadinessRow(
    title: String,
    detail: String,
    active: Boolean,
) {
    Surface(
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.58f),
    ) {
        Row(
            Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                Modifier
                    .size(9.dp)
                    .clip(CircleShape)
                    .background(if (active) Ready else Offline)
            )
            Spacer(Modifier.width(11.dp))
            Column {
                Text(
                    title,
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onSurface,
                    fontWeight = FontWeight.Medium,
                )
                Text(
                    detail,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun MiniMetric(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(18.dp),
        color = Color.Black.copy(alpha = 0.28f),
        border =
            androidx.compose.foundation.BorderStroke(
                1.dp,
                Color.White.copy(alpha = 0.11f),
            ),
    ) {
        Column(Modifier.padding(horizontal = 14.dp, vertical = 12.dp)) {
            Text(
                label,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp,
            )
            Text(
                value,
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurface,
                fontWeight = FontWeight.SemiBold,
            )
        }
    }
}

@Composable
private fun StatusDot(ready: Boolean) {
    Box(
        Modifier
            .size(18.dp)
            .clip(CircleShape)
            .background((if (ready) Ready else Warn).copy(alpha = 0.18f))
            .border(1.dp, if (ready) Ready else Warn, CircleShape)
    )
}
