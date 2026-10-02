package com.duoopen.overlay

import kotlin.random.Random

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
    gate("second cycle gets new identity", owner.onWakeHint(0, 1, 300L)?.id == 2L)
    owner.finish("closed", 400L)

    val fuzzOwner = Fold7Gen6OpeningAttemptOwner(serviceEpoch = 99L)
    repeat(100_000) { i ->
        val a = fuzzOwner.onWakeHint(0, 1, i.toLong() * 3L)
        check(a != null && a.id == i.toLong() + 1L) { "attempt identity fuzz failed at $i" }
        check(fuzzOwner.onWakeHint(0, 2, i.toLong() * 3L + 1L) == null) { "duplicate attempt escaped at $i" }
        check(fuzzOwner.finish("cycle", i.toLong() * 3L + 2L) != null) { "finish fuzz failed at $i" }
    }
    gate("100k opening-attempt lifecycle fuzz", true)

    val policy = Fold7GlassPrivacyPolicy()
    val normal = policy.decide(Fold7AppPrivacySignals(packageName = "com.example.maps", appLabel = "Maps"))
    gate("normal app public glass", normal.mode == Fold7GlassMode.PUBLIC_GLASS)
    gate("normal app may capture", normal.captureAllowed && normal.cacheAllowed && !normal.proceduralOnly)

    val coast = policy.decide(Fold7AppPrivacySignals(appLabel = "Coast Capital"))
    gate("Coast Capital private frost", coast.mode == Fold7GlassMode.PRIVATE_FROST)
    gate("private frost captures no pixels", !coast.captureAllowed && !coast.cacheAllowed && coast.proceduralOnly)

    val work = policy.decide(Fold7AppPrivacySignals(packageName = "com.example.work", isWorkProfile = true))
    gate("work profile private frost", work.mode == Fold7GlassMode.PRIVATE_FROST && work.proceduralOnly)

    val secure = policy.decide(Fold7AppPrivacySignals(packageName = "com.example.secure", isFlagSecure = true))
    gate("FLAG_SECURE private frost", secure.mode == Fold7GlassMode.PRIVATE_FROST && !secure.captureAllowed)

    val runtime = Fold7PrivacyRuntime(policy)
    runtime.onForegroundApp("com.example.normal", "Normal", false)
    gate("runtime public start", runtime.current().decision.mode == Fold7GlassMode.PUBLIC_GLASS)
    runtime.markCaptureDenied("secure-window")
    gate("capture failure fail-closed", runtime.current().decision.mode == Fold7GlassMode.PRIVATE_FROST)
    runtime.onForegroundApp("com.example.normal", "Normal", false)
    gate("same package keeps denial sticky", runtime.current().decision.mode == Fold7GlassMode.PRIVATE_FROST)
    runtime.onForegroundApp("com.example.other", "Other", false)
    gate("new package clears transient denial", runtime.current().decision.mode == Fold7GlassMode.PUBLIC_GLASS)

    // Deterministic fuzz: PRIVATE_FROST must never admit pixel capture/cache.
    val rng = Random(0xD06)
    repeat(100_000) { i ->
        val signals = Fold7AppPrivacySignals(
            packageName = if (rng.nextBoolean()) "com.example.$i" else "com.example.coastcapital.$i",
            appLabel = if (rng.nextInt(20) == 0) "Coast Capital" else "App $i",
            isFlagSecure = rng.nextInt(17) == 0,
            isWorkProfile = rng.nextInt(19) == 0,
            screenshotDenied = rng.nextInt(23) == 0,
            captureUnavailableForSecurity = rng.nextInt(29) == 0,
        )
        val d = policy.decide(signals)
        if (d.mode == Fold7GlassMode.PRIVATE_FROST) {
            check(!d.captureAllowed && !d.cacheAllowed && d.proceduralOnly) {
                "private invariant failed at fuzz case $i"
            }
        }
    }
    gate("100k privacy invariant fuzz", true)
}
