package com.duoopen.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.weight
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.duoopen.fold.HingeAngleSource
import com.duoopen.settings.DuoConfig
import com.duoopen.settings.DuoSettings
import kotlinx.coroutines.delay
import kotlin.math.roundToInt

/**
 * GEN11_PRODUCT_UI_SETTINGS
 *
 * Same settings contract as the predecessor, reorganized into task-oriented
 * pages so setup, appearance tuning and diagnostics no longer compete in one
 * giant scroll surface.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ControlSheet(
    config: DuoConfig,
    hinge: HingeAngleSource?,
    hingeAngle: Float,
    paneTilt: Float,
    simulate: Boolean,
    onSimulateChange: (Boolean) -> Unit,
    simulatedAngle: Float,
    onSimulatedAngleChange: (Float) -> Unit,
    onPickImage: () -> Unit,
    onDefaultImage: () -> Unit,
    onSetWallpaper: () -> Unit,
    wallpaperActive: Boolean,
    overlayAvailable: Boolean,
    overlayEnabled: Boolean,
    liveBlurSupported: Boolean,
    shizukuAvailable: Boolean,
    shizukuStatus: String,
    shizukuReady: Boolean,
    shizukuInstalled: Boolean,
    onShizukuAuthorize: () -> Unit,
    onOpenShizuku: () -> Unit,
    foldWallpaperActive: Boolean,
    angleFeedStatus: () -> String,
    onOpenWallpaperSettings: () -> Unit,
    onEnableOverlay: () -> Unit,
    onTestOverlay: () -> Unit,
    onExportDebugBundle: () -> Unit,
    onSendDebugBundle: () -> Unit,
    diagnosticUploadEnabled: Boolean,
    diagnosticUploadStatus: String?,
    onDismiss: () -> Unit,
) {
    val clipboard = LocalClipboardManager.current
    val hasSensor = hinge?.sensor != null
    var selectedTab by rememberSaveable { mutableStateOf(0) }
    var showGuide by remember { mutableStateOf(false) }

    val sensorStatus by
        produceState(
            initialValue = hinge?.statusText() ?: angleFeedStatus(),
            hinge,
        ) {
            while (true) {
                delay(250)
                value = hinge?.statusText() ?: angleFeedStatus()
            }
        }

    if (showGuide) {
        SetupGuide(
            onOpenAccessibility = {
                showGuide = false
                onEnableOverlay()
            },
            onDismiss = { showGuide = false },
        )
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = MaterialTheme.colorScheme.surface,
        contentColor = MaterialTheme.colorScheme.onSurface,
    ) {
        Column(
            Modifier
                .fillMaxWidth()
                .heightIn(max = 780.dp)
                .navigationBarsPadding()
        ) {
            Column(Modifier.padding(horizontal = 24.dp)) {
                Text(
                    "Controls",
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    "Configure the continuity engine without disturbing its runtime architecture.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(14.dp))
            }

            TabRow(
                selectedTabIndex = selectedTab,
                containerColor = MaterialTheme.colorScheme.surface,
            ) {
                listOf("Setup", "Look", "Diagnostics").forEachIndexed { index, title ->
                    Tab(
                        selected = selectedTab == index,
                        onClick = { selectedTab = index },
                        text = { Text(title) },
                    )
                }
            }

            when (selectedTab) {
                0 ->
                    SetupPage(
                        overlayAvailable = overlayAvailable,
                        overlayEnabled = overlayEnabled,
                        wallpaperActive = wallpaperActive,
                        onSetWallpaper = onSetWallpaper,
                        onEnableOverlay = onEnableOverlay,
                        onTestOverlay = onTestOverlay,
                        onShowGuide = { showGuide = true },
                        shizukuAvailable = shizukuAvailable,
                        shizukuStatus = shizukuStatus,
                        shizukuReady = shizukuReady,
                        shizukuInstalled = shizukuInstalled,
                        onShizukuAuthorize = onShizukuAuthorize,
                        onOpenShizuku = onOpenShizuku,
                        foldWallpaperActive = foldWallpaperActive,
                        angleFeedStatus = angleFeedStatus,
                        onOpenWallpaperSettings = onOpenWallpaperSettings,
                    )

                1 ->
                    LookPage(
                        config = config,
                        liveBlurSupported = liveBlurSupported,
                        onPickImage = onPickImage,
                        onDefaultImage = onDefaultImage,
                    )

                else ->
                    DiagnosticsPage(
                        hinge = hinge,
                        hingeAngle = hingeAngle,
                        paneTilt = paneTilt,
                        hasSensor = hasSensor,
                        sensorStatus = sensorStatus,
                        angleFeedStatus = angleFeedStatus,
                        overlayAvailable = overlayAvailable,
                        simulate = simulate,
                        onSimulateChange = onSimulateChange,
                        simulatedAngle = simulatedAngle,
                        onSimulatedAngleChange = onSimulatedAngleChange,
                        onCopySensorReport = {
                            clipboard.setText(
                                AnnotatedString(
                                    hinge?.report() ?: angleFeedStatus()
                                )
                            )
                        },
                        onExportDebugBundle = onExportDebugBundle,
                        onSendDebugBundle = onSendDebugBundle,
                        diagnosticUploadEnabled = diagnosticUploadEnabled,
                        diagnosticUploadStatus = diagnosticUploadStatus,
                    )
            }
        }
    }
}

@Composable
private fun SetupPage(
    overlayAvailable: Boolean,
    overlayEnabled: Boolean,
    wallpaperActive: Boolean,
    onSetWallpaper: () -> Unit,
    onEnableOverlay: () -> Unit,
    onTestOverlay: () -> Unit,
    onShowGuide: () -> Unit,
    shizukuAvailable: Boolean,
    shizukuStatus: String,
    shizukuReady: Boolean,
    shizukuInstalled: Boolean,
    onShizukuAuthorize: () -> Unit,
    onOpenShizuku: () -> Unit,
    foldWallpaperActive: Boolean,
    angleFeedStatus: () -> String,
    onOpenWallpaperSettings: () -> Unit,
) {
    PageColumn {
        PageIntro(
            "Get the engine ready",
            "The app can run system-wide through Accessibility or as wallpaper-only. Shizuku adds the Fold7-specific precision bridge.",
        )

        if (overlayAvailable) {
            SettingsCard(
                title = "Full-screen continuity",
                subtitle =
                    if (overlayEnabled) {
                        "Active · folds wallpaper, icons, lock screen and open apps."
                    } else {
                        "Off · enable the Duo Open accessibility service."
                    },
            ) {
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Button(
                        onClick = if (overlayEnabled) onTestOverlay else onEnableOverlay,
                        modifier = Modifier.weight(1f),
                    ) {
                        Text(if (overlayEnabled) "Test transition" else "Enable")
                    }
                    OutlinedButton(
                        onClick = onEnableOverlay,
                        modifier = Modifier.weight(1f),
                    ) {
                        Text("System settings")
                    }
                }
                if (!overlayEnabled) {
                    TextButton(onClick = onShowGuide) {
                        Text("Restricted toggle greyed out?")
                    }
                }
            }
        }

        SettingsCard(
            title = "Wallpaper mode",
            subtitle =
                if (wallpaperActive) {
                    "Active · the wallpaper folds while icons remain native."
                } else {
                    "Optional fallback that does not require Accessibility."
                },
        ) {
            OutlinedButton(
                onClick = onSetWallpaper,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (wallpaperActive) "Wallpaper settings" else "Set Duo wallpaper")
            }
        }

        if (shizukuAvailable) {
            SettingsCard(
                title = "Precision bridge",
                subtitle = shizukuStatus,
            ) {
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    if (!shizukuReady) {
                        Button(
                            onClick = onShizukuAuthorize,
                            enabled = shizukuInstalled,
                            modifier = Modifier.weight(1f),
                        ) {
                            Text("Authorize")
                        }
                    }
                    OutlinedButton(
                        onClick = onOpenShizuku,
                        modifier = Modifier.weight(1f),
                    ) {
                        Text(if (shizukuInstalled) "Open Shizuku" else "Get Shizuku")
                    }
                }

                if (shizukuReady) {
                    Hint(
                        if (foldWallpaperActive) {
                            angleFeedStatus()
                        } else {
                            "Precision bridge is authorized. Samsung interactive wallpaper remains the temporary angle fallback. ${angleFeedStatus()}"
                        },
                        warn = !foldWallpaperActive,
                    )
                    if (!foldWallpaperActive) {
                        TextButton(onClick = onOpenWallpaperSettings) {
                            Text("Open wallpaper settings")
                        }
                    }
                }
            }
        }

        SettingsCard(
            title = "Renderer contract",
            subtitle = "Fold7 keeps the deterministic frozen-frame AGSL glass path and the existing secure-content fail-open behavior.",
        ) {
            Hint("The product redesign changes controls and presentation only; renderer ownership remains outside the UI layer.")
        }
    }
}

@Composable
private fun LookPage(
    config: DuoConfig,
    liveBlurSupported: Boolean,
    onPickImage: () -> Unit,
    onDefaultImage: () -> Unit,
) {
    PageColumn {
        PageIntro(
            "Tune the fold",
            "Visual controls are grouped here so setup and diagnostics stay out of the way.",
        )

        SettingsCard(title = "Glass") {
            LabeledSlider(
                label = "Strength",
                hint = "How heavy the frost gets. 1× follows the physical hinge angle.",
                valueText = "%.2f×".format(config.intensity),
                value = config.intensity,
                onValueChange = { v -> DuoSettings.update { it.copy(intensity = v) } },
                range = 0.5f..3f,
            )
            LabeledSlider(
                label = "Frost",
                hint = "How quickly blur grows away from the crease.",
                valueText = "%.2f".format(config.blurSpread),
                value = config.blurSpread,
                onValueChange = { v -> DuoSettings.update { it.copy(blurSpread = v) } },
                range = 0.02f..0.3f,
            )
            LabeledSlider(
                label = "Darkening",
                hint = "How much the glass dims content behind it.",
                valueText = "%.3f".format(config.darkening),
                value = config.darkening,
                onValueChange = { v -> DuoSettings.update { it.copy(darkening = v) } },
                range = 0f..0.04f,
            )
            LabeledSlider(
                label = "Eye distance",
                hint = "Perspective depth for snapshot rendering.",
                valueText = "${config.eyeDistanceMm.roundToInt()} mm",
                value = config.eyeDistanceMm,
                onValueChange = { v -> DuoSettings.update { it.copy(eyeDistanceMm = v) } },
                range = 200f..800f,
                enabled = !(config.liveBlur && liveBlurSupported),
            )
            TextButton(onClick = DuoSettings::resetTuning) {
                Text("Reset visual tuning")
            }
        }

        SettingsCard(
            title = "Inner screen motion",
            subtitle = "Choose which half appears to swing around the crease.",
        ) {
            Choice(
                options = listOf(-1 to "Left", 1 to "Right", 0 to "Both"),
                selected = config.movingSide,
                onSelect = { side -> DuoSettings.update { it.copy(movingSide = side) } },
            )
        }

        SettingsCard(
            title = "Cover frost direction",
            subtitle = "Choose which cover edge develops frost first during opening.",
        ) {
            Choice(
                options = listOf(true to "Right edge", false to "Left edge"),
                selected = config.coverFrostFromRight,
                onSelect = { v -> DuoSettings.update { it.copy(coverFrostFromRight = v) } },
            )
        }

        SettingsCard(
            title = "Crease orientation",
            subtitle = "Detected automatically; flip only when the visual crease is mapped to the wrong axis.",
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "Across the ${if (config.foldSplitsLong) "long" else "short"} side",
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.bodyMedium,
                )
                OutlinedButton(
                    onClick = {
                        DuoSettings.update { it.copy(foldSplitsLong = !it.foldSplitsLong) }
                    }
                ) {
                    Text("Flip")
                }
            }
        }

        SettingsCard(
            title = "Wallpaper preview image",
            subtitle = "Used by wallpaper mode and the product preview; whole-screen continuity still mirrors whatever is actually on screen.",
        ) {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(
                    onClick = onPickImage,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Choose image")
                }
                OutlinedButton(
                    onClick = onDefaultImage,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Default")
                }
            }
        }
    }
}

@Composable
private fun DiagnosticsPage(
    hinge: HingeAngleSource?,
    hingeAngle: Float,
    paneTilt: Float,
    hasSensor: Boolean,
    sensorStatus: String,
    angleFeedStatus: () -> String,
    overlayAvailable: Boolean,
    simulate: Boolean,
    onSimulateChange: (Boolean) -> Unit,
    simulatedAngle: Float,
    onSimulatedAngleChange: (Float) -> Unit,
    onCopySensorReport: () -> Unit,
    onExportDebugBundle: () -> Unit,
    onSendDebugBundle: () -> Unit,
    diagnosticUploadEnabled: Boolean,
    diagnosticUploadStatus: String?,
) {
    PageColumn {
        PageIntro(
            "Observe before changing",
            "Live telemetry and evidence export stay separate from setup and appearance controls.",
        )

        SettingsCard(
            title = "Hinge telemetry",
            subtitle = sensorStatus,
        ) {
            Hint(
                "Hinge ${if (hingeAngle.isNaN()) "—" else "${hingeAngle.roundToInt()}°"} · pane tilt %.1f°".format(paneTilt)
            )
            if (hasSensor && hinge?.isCoarse == true) {
                Hint(
                    "This public sensor reports endpoint-style geometry rather than continuous Fold7 motion.",
                    warn = true,
                )
            }
            TextButton(onClick = onCopySensorReport) {
                Text("Copy sensor report")
            }
        }

        if (!overlayAvailable) {
            SettingsCard(
                title = "Hinge simulator",
                subtitle = "Drive the preview without live hardware geometry.",
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Simulation", modifier = Modifier.weight(1f))
                    Switch(
                        checked = simulate,
                        onCheckedChange = onSimulateChange,
                        enabled = hasSensor,
                    )
                }
                if (simulate) {
                    LabeledSlider(
                        label = "Hinge angle",
                        hint = null,
                        valueText = "${simulatedAngle.roundToInt()}°",
                        value = simulatedAngle,
                        onValueChange = onSimulatedAngleChange,
                        range = 60f..180f,
                    )
                }
            }
        }

        SettingsCard(
            title = "Debug evidence",
            subtitle = "Capture this immediately after a bad fold, flash, freeze or crash.",
        ) {
            Button(
                onClick = onExportDebugBundle,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Export debug bundle")
            }
            OutlinedButton(
                onClick = onSendDebugBundle,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (diagnosticUploadEnabled) "Send diagnostic data" else "Share diagnostic data")
            }
            Hint(
                diagnosticUploadStatus
                    ?: if (diagnosticUploadEnabled) {
                        "Success is reported only after the server returns a checksum-matched diagnostic receipt."
                    } else {
                        "Remote upload is not configured; Android sharing is used instead."
                    },
                warn = diagnosticUploadStatus?.startsWith("Send failed") == true,
            )
            Hint("Bundles include field logs and Transition Lab sessions, not intentional screen pixels, passwords or keystrokes.")
        }

        SettingsCard(
            title = "Raw angle feed",
            subtitle = angleFeedStatus(),
        ) {
            Hint("Useful when comparing public, wallpaper and Shizuku geometry sources.")
        }
    }
}

@Composable
private fun PageColumn(content: @Composable ColumnScope.() -> Unit) {
    Column(
        Modifier
            .fillMaxWidth()
            .weight(1f)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp, vertical = 18.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
        content = content,
    )
}

@Composable
private fun PageIntro(title: String, detail: String) {
    Column {
        Text(
            title,
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.SemiBold,
        )
        Text(
            detail,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun SettingsCard(
    title: String,
    subtitle: String? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    Surface(
        shape = RoundedCornerShape(22.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.48f),
    ) {
        Column(
            Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(
                title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            if (subtitle != null) {
                Text(
                    subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            content()
        }
    }
}

@Composable
private fun Hint(
    text: String,
    warn: Boolean = false,
) {
    Text(
        text,
        style = MaterialTheme.typography.bodySmall,
        color =
            if (warn) {
                MaterialTheme.colorScheme.tertiary
            } else {
                MaterialTheme.colorScheme.onSurfaceVariant
            },
    )
}

@Composable
private fun <T> Choice(
    options: List<Pair<T, String>>,
    selected: T,
    onSelect: (T) -> Unit,
) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        options.forEach { (value, label) ->
            FilterChip(
                selected = selected == value,
                onClick = { onSelect(value) },
                label = { Text(label) },
            )
        }
    }
}

@Composable
private fun LabeledSlider(
    label: String,
    hint: String?,
    valueText: String,
    value: Float,
    onValueChange: (Float) -> Unit,
    range: ClosedFloatingPointRange<Float>,
    enabled: Boolean = true,
) {
    Column(Modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth()) {
            Text(
                label,
                modifier = Modifier.weight(1f),
                style = MaterialTheme.typography.bodyMedium,
            )
            Text(
                valueText,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        if (hint != null) Hint(hint)
        Slider(
            value = value,
            onValueChange = onValueChange,
            valueRange = range,
            enabled = enabled,
        )
    }
}
