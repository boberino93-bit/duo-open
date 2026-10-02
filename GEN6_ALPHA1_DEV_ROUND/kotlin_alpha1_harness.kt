package com.duoopen.overlay

private fun gate(name: String, condition: Boolean) {
    if (!condition) error("FAILED: $name")
    println("PASS: $name")
}

fun main() {
    val owner = Fold7Gen6OpeningAttemptOwner(serviceEpoch = 10L)
    val attempt = owner.onWakeHint(0, 1, 100L)
    gate("wake hint attempt created", attempt?.id == 1L)
    gate("duplicate wake hint fenced", owner.onWakeHint(0, 2, 110L) == null)
    gate("semantic generation attaches", owner.markSemanticAccepted(7L)?.semanticGeneration == 7L)
    gate("attempt finishes", owner.finish("closed", 200L) != null)

    val policy = Fold7GlassPrivacyPolicy()
    val normal = policy.decide(Fold7AppPrivacySignals(packageName = "com.example.maps", appLabel = "Maps"))
    gate("normal app public glass", normal.mode == Fold7GlassMode.PUBLIC_GLASS)
    gate("normal app may capture", normal.captureAllowed)

    val coast = policy.decide(Fold7AppPrivacySignals(appLabel = "Coast Capital"))
    gate("Coast Capital private frost", coast.mode == Fold7GlassMode.PRIVATE_FROST)
    gate("private frost captures no pixels", !coast.captureAllowed && !coast.cacheAllowed && coast.proceduralOnly)

    val runtime = Fold7PrivacyRuntime(policy)
    runtime.onForegroundApp("com.example.normal", "Normal", false)
    gate("runtime public start", runtime.current().decision.mode == Fold7GlassMode.PUBLIC_GLASS)
    runtime.markCaptureDenied("secure-window")
    gate("capture failure fail-closed", runtime.current().decision.mode == Fold7GlassMode.PRIVATE_FROST)
    runtime.onForegroundApp("com.example.other", "Other", false)
    gate("new package clears transient denial", runtime.current().decision.mode == Fold7GlassMode.PUBLIC_GLASS)
}
