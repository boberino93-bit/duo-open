package com.duoopen.overlay

/**
 * Android-free holder for the privacy state associated with the currently
 * observed foreground app.
 *
 * A capture denial is sticky only for the current package. Changing packages
 * clears the transient denial and re-runs the base policy.
 */
internal class Fold7PrivacyRuntime(
    private val policy: Fold7GlassPrivacyPolicy = Fold7GlassPrivacyPolicy(),
) {
    data class Snapshot(
        val packageName: String?,
        val appLabel: String?,
        val isWorkProfile: Boolean,
        val captureDeniedReason: String?,
        val decision: Fold7GlassDecision,
    )

    data class Transition(
        val previous: Snapshot,
        val current: Snapshot,
    ) {
        val changed: Boolean
            get() = previous != current

        val becamePrivate: Boolean
            get() =
                previous.decision.mode != Fold7GlassMode.PRIVATE_FROST &&
                    current.decision.mode == Fold7GlassMode.PRIVATE_FROST
    }

    private var packageName: String? = null
    private var appLabel: String? = null
    private var workProfile = false
    private var captureDeniedReason: String? = null

    fun current(): Snapshot = snapshot()

    fun onForegroundApp(
        packageName: String,
        appLabel: String?,
        isWorkProfile: Boolean,
    ): Transition {
        val previous = snapshot()
        val samePackage = this.packageName == packageName

        this.packageName = packageName
        this.appLabel = appLabel
        this.workProfile = isWorkProfile

        if (!samePackage) {
            captureDeniedReason = null
        }

        return Transition(previous, snapshot())
    }

    fun markCaptureDenied(reason: String): Transition {
        val previous = snapshot()
        captureDeniedReason = reason
        return Transition(previous, snapshot())
    }

    private fun snapshot(): Snapshot {
        val decision =
            policy.decide(
                Fold7AppPrivacySignals(
                    packageName = packageName,
                    appLabel = appLabel,
                    isWorkProfile = workProfile,
                    screenshotDenied = captureDeniedReason != null,
                ),
            )

        return Snapshot(
            packageName = packageName,
            appLabel = appLabel,
            isWorkProfile = workProfile,
            captureDeniedReason = captureDeniedReason,
            decision = decision,
        )
    }
}
