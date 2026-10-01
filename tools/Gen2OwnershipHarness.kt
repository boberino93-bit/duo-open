package com.duoopen.overlay

private fun checkCase(name: String, body: () -> Unit): Boolean =
    try { body(); println("PASS $name"); true }
    catch (t: Throwable) { println("FAIL $name :: ${t.message}"); false }

private fun requireTrue(v: Boolean, m: String) { if (!v) error(m) }
private fun requireFalse(v: Boolean, m: String) { if (v) error(m) }
private fun requireNull(v: Any?, m: String) { if (v != null) error(m) }

fun main() {
    var passed = 0
    var total = 0
    fun test(name: String, body: () -> Unit) { total++; if (checkCase(name, body)) passed++ }

    test("cycle stable") {
        val e = Fold7CycleEnvelope(1)
        val a = e.beginClose(10)
        val b = e.beginClose(20)
        requireTrue(a == b, "cycle changed mid-close")
        e.invalidateClose(a.closeCycleId)
        requireFalse(e.isCurrent(1, a.closeCycleId), "old cycle survived invalidation")
    }

    test("lease revision fencing") {
        val g = Fold7CoverLeaseSnapshotGate()
        g.onConnectionEpoch(1)
        fun s(rev: Long) = Fold7CoverLeaseSnapshotGate.Snapshot(
            1, 2, rev, "HELD", 3, 4, 5, 6, 7, true, true, true,
        )
        requireTrue(g.accept(s(1)).accepted, "first rejected")
        requireFalse(g.accept(s(1)).accepted, "duplicate accepted")
        requireTrue(g.accept(s(2)).accepted, "newer rejected")
    }

    test("readiness exact logical observation") {
        val token = Fold7CoverLeaseSnapshotGate.LeaseToken(2,3,4,5,6)
        val r = Fold7CoverReadiness()
        val d = Fold7CoverReadiness.Demand(1,2,3,token,9)
        r.begin(d, true)
        requireFalse(r.observe(1,2,Fold7CoverReadiness.Topology(true,true,true,false,8)).becameReady,"wrong route ready")
        requireTrue(r.observe(1,2,Fold7CoverReadiness.Topology(true,true,true,false,9)).becameReady,"right route not ready")
    }

    test("frame provenance exact cycle") {
        val e = Fold7CycleEnvelope(1)
        val s = Fold7ContinuityFrameStore<String>()
        val c1 = e.beginClose(100); s.beginCycle(c1)
        val t = s.beginCapture(c1,1968,2184,101,Fold7ContinuityFrameStore.Source.SHIZUKU)!!
        s.publish(t,102,103,Fold7ContinuityFrameStore.TimestampQuality.REQUEST_BOUNDED,"A") ?: error("publish failed")
        e.invalidateClose(c1.closeCycleId); s.invalidateCycle(1,c1.closeCycleId)
        val c2 = e.beginClose(200); s.beginCycle(c2)
        requireNull(s.current(c2,201,10_000,1968,2184),"prior frame replayed")
    }

    test("timestamp quality fences pre-cycle request") {
        val e = Fold7CycleEnvelope(1); val s = Fold7ContinuityFrameStore<String>()
        val c = e.beginClose(100); s.beginCycle(c)
        val shizuku = s.beginCapture(c,1968,2184,99,Fold7ContinuityFrameStore.Source.SHIZUKU)!!
        requireNull(
            s.publish(shizuku,101,102,Fold7ContinuityFrameStore.TimestampQuality.REQUEST_BOUNDED,"bad"),
            "request-bounded pre-cycle capture accepted",
        )
        val exact = s.beginCapture(c,1968,2184,99,Fold7ContinuityFrameStore.Source.ACCESSIBILITY)!!
        requireTrue(
            s.publish(exact,101,103,Fold7ContinuityFrameStore.TimestampQuality.EXACT_CAPTURE,"good") != null,
            "exact current-cycle capture rejected",
        )
    }

    test("presentation stale attempt rejected") {
        val p = Fold7PresentationLease(); p.openHost()
        val a = p.begin(1,2,3,Fold7PresentationLease.RenderPath.FROZEN_VIEW)
        val b = p.begin(1,2,4,Fold7PresentationLease.RenderPath.FROZEN_VIEW)
        requireFalse(p.onPresented(a),"old attempt accepted")
        requireTrue(p.onDraw(b),"current draw rejected")
        requireTrue(p.onPresented(b),"current present rejected")
    }

    test("presentation attempt invalidation") {
        val p = Fold7PresentationLease(); p.openHost()
        val a = p.begin(1,2,3,Fold7PresentationLease.RenderPath.FROZEN_VIEW)
        p.invalidateAttempt(a)
        requireFalse(p.onFrameCommit(a),"invalid attempt callback accepted")
        val b = p.begin(1,2,4,Fold7PresentationLease.RenderPath.LIVE_MIRROR)
        requireTrue(p.onTransactionCommit(b),"new attempt rejected")
    }

    test("presentation host invalidation") {
        val p = Fold7PresentationLease(); val h = p.openHost()
        val a = p.begin(1,2,3,Fold7PresentationLease.RenderPath.LIVE_MIRROR)
        p.invalidateHost(h)
        requireFalse(p.onPresented(a),"invalid host callback accepted")
    }

    // Deterministic stress: repeatedly create/tear down cycles and make sure
    // old callbacks/tickets never become current again.
    test("100000-op deterministic stale fencing stress") {
        val e = Fold7CycleEnvelope(77)
        val frames = Fold7ContinuityFrameStore<Long>()
        val p = Fold7PresentationLease(); p.openHost()
        var lastOldPresentation: Fold7PresentationLease.Identity? = null
        var now = 1_000L
        repeat(10_000) { i ->
            val cycle = e.beginClose(now); frames.beginCycle(cycle)
            val ticket = frames.beginCapture(cycle,1968,2184,now+1,Fold7ContinuityFrameStore.Source.SHIZUKU)!!
            val frame = frames.publish(ticket,now+2,now+3,Fold7ContinuityFrameStore.TimestampQuality.REQUEST_BOUNDED,i.toLong())!!
            val id = p.begin(cycle.serviceEpoch,cycle.closeCycleId,frame.contentLeaseId,Fold7PresentationLease.RenderPath.FROZEN_VIEW)
            requireTrue(p.onDraw(id),"draw rejected")
            lastOldPresentation?.let { requireFalse(p.onPresented(it),"old presentation revived") }
            requireTrue(p.onPresented(id),"present rejected")
            lastOldPresentation = id
            e.invalidateClose(cycle.closeCycleId); frames.invalidateCycle(cycle.serviceEpoch,cycle.closeCycleId)
            now += 10
        }
    }

    println("RESULT passed=$passed failed=${total-passed} total=$total")
    if (passed != total) error("harness failed")
}
