package rnd.fold7

import kotlin.random.Random

private var passed = 0
private var failed = 0

private fun checkCase(name: String, block: () -> Unit) {
    try {
        block()
        println("PASS $name")
        passed++
    } catch (t: Throwable) {
        println("FAIL $name :: ${t.message}")
        failed++
    }
}

private fun candidate(
    epoch: Long = 1,
    cycle: Long = 1,
    seq: Long = 1,
    request: Long = 100,
    capture: Long = 110,
    complete: Long = 120,
    source: CaptureSource = CaptureSource.ACCESSIBILITY,
    quality: TimestampQuality = TimestampQuality.EXACT_CAPTURE,
    width: Int = 1968,
    height: Int = 2184,
    content: String = "current",
) = FrameCandidate(epoch, cycle, seq, width, height, request, capture, complete, source, quality, content)

fun main() {
    checkCase("baseline accepts previous-cycle frame when age and geometry match") {
        val baseline = BaselineAgeOnlyFrameCache(10_000)
        baseline.putInner(1968, 2184, 1_000, "cycle-A")
        val got = baseline.getInner(1968, 2184, 6_000)
        require(got?.contentId == "cycle-A")
    }

    checkCase("gen2 new close cycle starts without inheriting previous frame") {
        val store = ContinuityFrameLeaseStore(serviceEpoch = 7)
        store.beginCloseCycle(10, 1_000)
        require(store.publish(candidate(epoch=7, cycle=10, capture=1_100, complete=1_110, content="cycle-A")))
        require(store.leaseForVisual(10, 1_200)?.contentId == "cycle-A")
        store.beginCloseCycle(11, 2_000)
        require(store.leaseForVisual(11, 2_050) == null)
    }

    checkCase("gen2 accepts exact same-cycle accessibility capture") {
        val store = ContinuityFrameLeaseStore(serviceEpoch = 1)
        store.beginCloseCycle(2, 100)
        require(store.publish(candidate(cycle=2, capture=111, complete=120)))
        require(store.leaseForVisual(2, 130)?.contentId == "current")
    }

    checkCase("gen2 rejects exact capture timestamp before cycle start") {
        val store = ContinuityFrameLeaseStore(serviceEpoch = 1)
        store.beginCloseCycle(2, 100)
        require(!store.publish(candidate(cycle=2, request=80, capture=90, complete=120)))
    }

    checkCase("gen2 rejects shizuku request that began before cycle even if it completes later") {
        val store = ContinuityFrameLeaseStore(serviceEpoch = 1)
        store.beginCloseCycle(2, 100)
        require(!store.publish(candidate(cycle=2, request=90, capture=115, complete=120,
            source=CaptureSource.SHIZUKU, quality=TimestampQuality.REQUEST_BOUNDED)))
    }

    checkCase("gen2 accepts shizuku capture request begun after cycle start") {
        val store = ContinuityFrameLeaseStore(serviceEpoch = 1)
        store.beginCloseCycle(2, 100)
        require(store.publish(candidate(cycle=2, request=105, capture=118, complete=120,
            source=CaptureSource.SHIZUKU, quality=TimestampQuality.REQUEST_BOUNDED)))
    }

    checkCase("late capture from reversed cycle is inert") {
        val store = ContinuityFrameLeaseStore(serviceEpoch = 1)
        store.beginCloseCycle(2, 100)
        store.invalidateCloseCycle(2)
        require(!store.publish(candidate(cycle=2, capture=130, complete=140)))
        require(store.leaseForVisual(2, 150) == null)
    }

    checkCase("late prior-cycle capture cannot populate newer close") {
        val store = ContinuityFrameLeaseStore(serviceEpoch = 1)
        store.beginCloseCycle(2, 100)
        store.beginCloseCycle(3, 200)
        require(!store.publish(candidate(cycle=2, seq=9, request=210, capture=220, complete=230)))
        require(store.leaseForVisual(3, 240) == null)
    }

    checkCase("service restart epoch rejects old-process capture") {
        val store = ContinuityFrameLeaseStore(serviceEpoch = 9)
        store.beginCloseCycle(1, 100)
        require(!store.publish(candidate(epoch=8, cycle=1, request=110, capture=120, complete=130)))
    }

    checkCase("geometry mismatch is never eligible") {
        val store = ContinuityFrameLeaseStore(serviceEpoch = 1)
        store.beginCloseCycle(1, 100)
        require(!store.publish(candidate(width=1080, height=2520)))
    }

    checkCase("older sequence cannot replace newer exact-cycle frame") {
        val store = ContinuityFrameLeaseStore(serviceEpoch = 1)
        store.beginCloseCycle(1, 100)
        require(store.publish(candidate(seq=4, capture=130, complete=140, content="newer")))
        require(!store.publish(candidate(seq=3, capture=150, complete=160, content="late-old-seq")))
        require(store.leaseForVisual(1, 170)?.contentId == "newer")
    }

    checkCase("state transitions inside one close cycle do not invalidate frame lease") {
        val store = ContinuityFrameLeaseStore(serviceEpoch = 1)
        store.beginCloseCycle(42, 100)
        require(store.publish(candidate(cycle=42, capture=120, complete=125)))
        // CLOSING_INTENT -> PREWARM -> READY_HIDDEN -> VISUAL are intentionally not new cycle IDs.
        require(store.leaseForVisual(42, 130) != null)
        require(store.leaseForVisual(42, 180) != null)
    }

    checkCase("existing 10s freshness cap can remain independent of provenance") {
        val store = ContinuityFrameLeaseStore(serviceEpoch = 1, maxAgeMs = 10_000)
        store.beginCloseCycle(1, 100)
        require(store.publish(candidate(capture=110, complete=120)))
        require(store.leaseForVisual(1, 10_110) != null)
        require(store.leaseForVisual(1, 10_111) == null)
    }

    checkCase("current-cycle absence fails closed instead of replaying prior content") {
        val baseline = BaselineAgeOnlyFrameCache(10_000)
        baseline.putInner(1968, 2184, 5_000, "previous-app-state")
        require(baseline.getInner(1968, 2184, 8_000) != null)

        val store = ContinuityFrameLeaseStore(serviceEpoch = 1)
        store.beginCloseCycle(2, 7_500)
        // Simulate current capture failure: no publish.
        require(store.leaseForVisual(2, 8_000) == null)
    }

    checkCase("fixed-seed fuzz never leases stale provenance") {
        val rng = Random(20261001)
        var serviceEpoch = 1L
        var cycle = 0L
        var now = 0L
        var store = ContinuityFrameLeaseStore(serviceEpoch)
        var active: Long? = null
        var activeStart: Long? = null
        var seq = 0L
        repeat(100_000) {
            now += rng.nextLong(0, 4)
            when (rng.nextInt(7)) {
                0 -> {
                    cycle++
                    active = cycle
                    activeStart = now
                    store.beginCloseCycle(cycle, now)
                }
                1 -> {
                    active?.let { store.invalidateCloseCycle(it) }
                    active = null
                    activeStart = null
                }
                2 -> {
                    serviceEpoch++
                    store = ContinuityFrameLeaseStore(serviceEpoch)
                    active = null
                    activeStart = null
                }
                3,4,5 -> {
                    seq++
                    val current = active
                    val chosenCycle = if (current != null && rng.nextBoolean()) current else (cycle - rng.nextInt(0, 3)).coerceAtLeast(0)
                    val chosenEpoch = if (rng.nextInt(5) == 0) serviceEpoch - 1 else serviceEpoch
                    val exact = rng.nextBoolean()
                    val start = activeStart ?: now
                    val request = if (rng.nextInt(4) == 0) (start - rng.nextLong(1, 20)).coerceAtLeast(0) else now
                    val capture = request + rng.nextLong(0, 10)
                    val completion = capture + rng.nextLong(0, 10)
                    store.publish(candidate(
                        epoch=chosenEpoch,
                        cycle=chosenCycle,
                        seq=seq,
                        request=request,
                        capture=capture,
                        complete=completion,
                        source=if (exact) CaptureSource.ACCESSIBILITY else CaptureSource.SHIZUKU,
                        quality=if (exact) TimestampQuality.EXACT_CAPTURE else TimestampQuality.REQUEST_BOUNDED,
                        content="fuzz-$seq"
                    ))
                }
                else -> {
                    val a = active
                    val lease = if (a == null) null else store.leaseForVisual(a, now)
                    if (lease != null) {
                        require(lease.serviceEpoch == serviceEpoch)
                        require(lease.closeCycleId == active)
                        require(activeStart != null && lease.capturedAtMs >= activeStart!!)
                    }
                }
            }
        }
    }

    println("RESULT passed=$passed failed=$failed total=${passed + failed}")
    if (failed != 0) error("tests failed")
}
