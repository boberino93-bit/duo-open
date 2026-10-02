package com.duoopen.overlay

internal enum class Fold7GlassMode {
    PUBLIC_GLASS,
    PRIVATE_FROST,
}

internal data class Fold7AppPrivacySignals(
    val packageName: String? = null,
    val appLabel: String? = null,
    val isFlagSecure: Boolean = false,
    val isWorkProfile: Boolean = false,
    val screenshotDenied: Boolean = false,
    val captureUnavailableForSecurity: Boolean = false,
)

internal data class Fold7GlassDecision(
    val mode: Fold7GlassMode,
    val reason: String,
    val captureAllowed: Boolean,
    val cacheAllowed: Boolean,
    val proceduralOnly: Boolean,
)

internal data class Fold7GlassPrivacyPolicyConfig(
    val explicitPrivatePackages: Set<String> = emptySet(),
    val explicitPrivateKeywords: Set<String> =
        setOf(
            "coast capital",
            "coastcapital",
        ),
)

/**
 * Android-free Gen6 content privacy policy.
 *
 * PUBLIC_GLASS may use current app pixels.
 * PRIVATE_FROST must be procedural/neutral and may not capture/cache protected
 * app pixels merely to blur them.
 */
internal class Fold7GlassPrivacyPolicy(
    config: Fold7GlassPrivacyPolicyConfig = Fold7GlassPrivacyPolicyConfig(),
) {
    private val privatePackages =
        config.explicitPrivatePackages
            .map { it.trim().lowercase() }
            .filter { it.isNotBlank() }
            .toSet()

    private val privateKeywords =
        config.explicitPrivateKeywords
            .map { it.trim().lowercase() }
            .filter { it.isNotBlank() }
            .toSet()

    fun decide(signals: Fold7AppPrivacySignals): Fold7GlassDecision {
        if (signals.isFlagSecure) return privateDecision("flag-secure")
        if (signals.isWorkProfile) return privateDecision("work-profile")
        if (signals.screenshotDenied) return privateDecision("screenshot-denied")
        if (signals.captureUnavailableForSecurity) return privateDecision("capture-unavailable-security")

        val packageName = signals.packageName.orEmpty().trim().lowercase()
        val appLabel = signals.appLabel.orEmpty().trim().lowercase()

        if (packageName.isNotEmpty() && packageName in privatePackages) {
            return privateDecision("explicit-private-package")
        }

        if (matchesPrivateKeyword(packageName) || matchesPrivateKeyword(appLabel)) {
            return privateDecision("explicit-private-keyword")
        }

        return Fold7GlassDecision(
            mode = Fold7GlassMode.PUBLIC_GLASS,
            reason = "ordinary-app",
            captureAllowed = true,
            cacheAllowed = true,
            proceduralOnly = false,
        )
    }

    private fun matchesPrivateKeyword(value: String): Boolean =
        value.isNotBlank() &&
            privateKeywords.any(value::contains)

    private fun privateDecision(reason: String): Fold7GlassDecision =
        Fold7GlassDecision(
            mode = Fold7GlassMode.PRIVATE_FROST,
            reason = reason,
            captureAllowed = false,
            cacheAllowed = false,
            proceduralOnly = true,
        )
}
