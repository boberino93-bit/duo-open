package com.duoopen.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ProductUiSmokeTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun readyDashboardRendersAndPrimaryActionFires() {
        var clicked = false

        composeRule.setContent {
            DuoOpenTheme {
                HomePreview(
                    image = null,
                    hingeAngle = 132f,
                    paneTilt = 18f,
                    simulated = false,
                    wallpaperActive = true,
                    overlayEnabled = true,
                    shizukuReady = true,
                    onTest = { clicked = true },
                    onSetWallpaper = {},
                    onTune = {},
                )
            }
        }

        composeRule.onNodeWithText("Continuity Console").assertIsDisplayed()
        composeRule.onNodeWithText("Continuity ready").assertIsDisplayed()
        composeRule.onNodeWithText("Test continuity").performClick()
        composeRule.runOnIdle { assertTrue(clicked) }
    }

    @Test
    fun incompleteSetupDoesNotPresentTestAsPrimary() {
        composeRule.setContent {
            DuoOpenTheme {
                HomePreview(
                    image = null,
                    hingeAngle = 120f,
                    paneTilt = 12f,
                    simulated = false,
                    wallpaperActive = false,
                    overlayEnabled = false,
                    shizukuReady = false,
                    onTest = {},
                    onSetWallpaper = {},
                    onTune = {},
                )
            }
        }

        composeRule.onNodeWithText("Setup required").assertIsDisplayed()
        composeRule.onNodeWithText("Finish setup").assertIsDisplayed()
    }
}
