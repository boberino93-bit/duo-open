package com.duoopen.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val DuoOpenColors =
    darkColorScheme(
        primary = Color(0xFF8FE9FF),
        onPrimary = Color(0xFF001F28),
        primaryContainer = Color(0xFF123B46),
        onPrimaryContainer = Color(0xFFC7F4FF),
        secondary = Color(0xFFB9A7FF),
        onSecondary = Color(0xFF211553),
        tertiary = Color(0xFFFFC857),
        background = Color(0xFF070A10),
        onBackground = Color(0xFFF2F6FA),
        surface = Color(0xFF0E141D),
        onSurface = Color(0xFFF2F6FA),
        surfaceVariant = Color(0xFF18212D),
        onSurfaceVariant = Color(0xFFB8C5D2),
        outline = Color(0xFF607080),
        error = Color(0xFFFF7A90),
    )

@Composable
fun DuoOpenTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DuoOpenColors,
        content = content,
    )
}
