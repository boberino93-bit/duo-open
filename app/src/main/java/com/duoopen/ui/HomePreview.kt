package com.duoopen.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilledTonalButton
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
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.roundToInt

private val Glass = Color.White.copy(alpha = 0.14f)
private val GlassEdge = Color.White.copy(alpha = 0.22f)
private val Dim = Color.White.copy(alpha = 0.76f)

/** Product-facing Duo Open home screen; engineering controls live in Settings. */
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
    val ready = overlayEnabled && shizukuReady
    val status = when {
        !overlayEnabled -> "Setup needed"
        !shizukuReady -> "Shizuku needed"
        hingeAngle.isNaN() -> "Waiting for hinge"
        else -> "Ready"
    }
    val detail = when {
        !overlayEnabled -> "Turn on Duo Open accessibility to enable full-screen continuity."
        !shizukuReady -> "Start or authorize Shizuku for Fold7 panel control and precise hinge data."
        hingeAngle.isNaN() -> "The service is running; waiting for a hinge sample."
        simulated -> "Simulation active · ${hingeAngle.roundToInt()}°"
        else -> "Fold7 continuity active · hinge ${hingeAngle.roundToInt()}°"
    }

    Box(modifier.fillMaxSize().background(Color(0xFF0D0A1C))) {
        if (image != null) {
            Image(
                bitmap = image,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )
        }
        Box(
            Modifier
                .fillMaxSize()
                .background(
                    Brush.verticalGradient(
                        0f to Color.Black.copy(alpha = 0.52f),
                        0.45f to Color.Black.copy(alpha = 0.18f),
                        1f to Color.Black.copy(alpha = 0.58f),
                    )
                )
        )

        Column(
            Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .navigationBarsPadding()
                .padding(horizontal = 24.dp, vertical = 20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                "DUO OPEN",
                color = Color.White,
                fontSize = 16.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 3.sp,
            )
            Text(
                "Fold continuity for Galaxy Z Fold7",
                color = Dim,
                fontSize = 14.sp,
            )

            Spacer(Modifier.weight(1f))

            Column(
                Modifier
                    .widthIn(max = 440.dp)
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(28.dp))
                    .background(Glass)
                    .border(1.dp, GlassEdge, RoundedCornerShape(28.dp))
                    .padding(horizontal = 22.dp, vertical = 24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(
                    status,
                    color = Color.White,
                    fontSize = 34.sp,
                    fontWeight = FontWeight.SemiBold,
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    detail,
                    color = Dim,
                    fontSize = 14.sp,
                    textAlign = TextAlign.Center,
                )
                Spacer(Modifier.height(18.dp))
                Text(
                    "Accessibility ${if (overlayEnabled) "ON" else "OFF"}  ·  " +
                        "Shizuku ${if (shizukuReady) "READY" else "OFF"}  ·  " +
                        "Visual ${if (paneTilt < 0.05f) "FLAT" else "ACTIVE"}",
                    color = if (ready) Color.White else Dim,
                    fontSize = 12.sp,
                    textAlign = TextAlign.Center,
                )
            }

            Spacer(Modifier.weight(1f))

            Row(
                Modifier.widthIn(max = 440.dp).fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Button(
                    onClick = onTest,
                    enabled = overlayEnabled,
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Color.White,
                        contentColor = Color(0xFF14121F),
                    ),
                ) {
                    Text("Test fold")
                }
                FilledTonalButton(
                    onClick = onTune,
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.filledTonalButtonColors(
                        containerColor = Glass,
                        contentColor = Color.White,
                    ),
                ) {
                    Text("Settings")
                }
            }

            TextButton(onClick = onSetWallpaper) {
                Text(if (wallpaperActive) "Wallpaper settings" else "Set Duo wallpaper")
            }
        }
    }
}
