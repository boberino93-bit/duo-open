package rnd.fold7

import kotlin.random.Random

private class Tests {
    private var passed = 0
    private var failed = 0

    private fun check(name: String, block: () -> Unit) {
        try {
            block()
            passed++
            println("PASS $name")
        } catch (t: Throwable) {
            failed++
            println("FAIL $name: ${t.message}")
        }
    }

    private fun id(
        epoch: Long = 1,
        cycle: Long = 10,
        host: Long = 20,
        content: Long = 30,
        seq: Long = 40,
    ) = PresentationIdentity(epoch, cycle, host, content, seq)

    fun run() {
        check("baseline frozen bind claims success without presentation proof") {
            val b = BaselineFrozenPresentationModel()
            check(b.bindValidBitmap())
            check(b.bound)
        }

        check("baseline late callback can be attributed to newer generation") {
            val b = BaselineLatestContextCorrelation()
            b.currentGeneration = 100
            // transaction was created under generation 100
            b.currentGeneration = 200
            // late callback is observed after generation changed
            b.onTransactionCallback()
            check(b.lastAttributedGeneration == 200L)
        }

        check("frozen path requires draw frame-commit and transaction-presented") {
            val s = PresentationLeaseStore(1)
            val i = id()
            check(s.begin(i, PresentationPath.FROZEN_VIEW))
            s.onDraw(i)
            check(s.snapshot()?.confirmed == false)
            s.onFrameCommitted(i)
            check(s.snapshot()?.confirmed == false)
            s.onTransactionPresented(i, 1234)
            check(s.snapshot()?.confirmed == true)
            check(s.snapshot()?.presentTimeNs == 1234L)
        }

        check("transaction presented before frame commit does not prematurely confirm") {
            val s = PresentationLeaseStore(1)
            val i = id()
            s.begin(i, PresentationPath.FROZEN_VIEW)
            s.onTransactionPresented(i)
            s.onDraw(i)
            check(s.snapshot()?.confirmed == false)
            s.onFrameCommitted(i)
            check(s.snapshot()?.confirmed == true)
        }

        check("frame commit without draw cannot confirm frozen content") {
            val s = PresentationLeaseStore(1)
            val i = id()
            s.begin(i, PresentationPath.FROZEN_VIEW)
            s.onFrameCommitted(i)
            s.onTransactionPresented(i)
            check(s.snapshot()?.confirmed == false)
        }

        check("transaction commit is useful telemetry but not presentation") {
            val s = PresentationLeaseStore(1)
            val i = id()
            s.begin(i, PresentationPath.FROZEN_VIEW)
            s.onDraw(i)
            s.onFrameCommitted(i)
            s.onTransactionCommitted(i)
            check(s.snapshot()?.transactionCommitted == true)
            check(s.snapshot()?.confirmed == false)
        }

        check("live mirror confirms on identity-bearing transaction presentation") {
            val s = PresentationLeaseStore(1)
            val i = id()
            s.begin(i, PresentationPath.LIVE_MIRROR)
            s.onTransactionCommitted(i)
            check(s.snapshot()?.confirmed == false)
            s.onTransactionPresented(i, 5000)
            check(s.snapshot()?.confirmed == true)
        }

        check("old attempt cannot confirm after newer attempt starts") {
            val s = PresentationLeaseStore(1)
            val old = id(seq = 40)
            val newer = id(cycle = 11, content = 31, seq = 41)
            s.begin(old, PresentationPath.FROZEN_VIEW)
            s.onDraw(old)
            s.begin(newer, PresentationPath.FROZEN_VIEW)
            check(!s.onFrameCommitted(old))
            check(!s.onTransactionPresented(old))
            check(s.snapshot()?.identity == newer)
            check(s.snapshot()?.confirmed == false)
        }

        check("reversal invalidation makes all old callbacks inert") {
            val s = PresentationLeaseStore(1)
            val i = id()
            s.begin(i, PresentationPath.FROZEN_VIEW)
            s.onDraw(i)
            s.invalidateCurrent()
            check(!s.onFrameCommitted(i))
            check(!s.onTransactionPresented(i))
            check(s.snapshot() == null)
        }

        check("explicit cancellation is fail closed") {
            val s = PresentationLeaseStore(1)
            val i = id()
            s.begin(i, PresentationPath.FROZEN_VIEW)
            check(s.cancel(i))
            check(!s.onDraw(i))
            check(s.snapshot()?.confirmed == false)
            check(s.snapshot()?.cancelled == true)
        }

        check("service epoch mismatch cannot begin or mutate") {
            val s = PresentationLeaseStore(9)
            val wrong = id(epoch = 8)
            check(!s.begin(wrong, PresentationPath.LIVE_MIRROR))
            check(!s.onTransactionPresented(wrong))
            check(s.snapshot() == null)
        }

        check("duplicate callbacks are idempotent") {
            val s = PresentationLeaseStore(1)
            val i = id()
            s.begin(i, PresentationPath.FROZEN_VIEW)
            repeat(5) { s.onDraw(i) }
            repeat(5) { s.onFrameCommitted(i) }
            repeat(5) { s.onTransactionPresented(i, 9) }
            check(s.snapshot()?.confirmed == true)
            check(s.confirmedCount == 1L)
        }

        check("same cycle but stale host epoch cannot mutate replacement host") {
            val s = PresentationLeaseStore(1)
            val old = id(host = 20, seq = 40)
            val replacement = id(host = 21, seq = 41)
            s.begin(old, PresentationPath.FROZEN_VIEW)
            s.begin(replacement, PresentationPath.FROZEN_VIEW)
            check(!s.onTransactionPresented(old))
            check(s.snapshot()?.identity == replacement)
        }

        check("same host but stale content lease cannot mutate newer content") {
            val s = PresentationLeaseStore(1)
            val old = id(content = 30, seq = 40)
            val newer = id(content = 31, seq = 41)
            s.begin(old, PresentationPath.FROZEN_VIEW)
            s.begin(newer, PresentationPath.FROZEN_VIEW)
            check(!s.onDraw(old))
            check(s.snapshot()?.identity == newer)
        }

        check("attempt sequence must increase monotonically") {
            val s = PresentationLeaseStore(1)
            check(s.begin(id(seq = 50), PresentationPath.LIVE_MIRROR))
            check(!s.begin(id(cycle = 11, seq = 49), PresentationPath.LIVE_MIRROR))
            check(!s.begin(id(cycle = 11, seq = 50), PresentationPath.LIVE_MIRROR))
            check(s.begin(id(cycle = 11, seq = 51), PresentationPath.LIVE_MIRROR))
        }

        check("callback permutation converges only when frozen proof set is complete") {
            val events = listOf("draw", "frame", "commit", "present")
            val permutations = permutations(events)
            check(permutations.size == 24)
            for ((index, p) in permutations.withIndex()) {
                val s = PresentationLeaseStore(1)
                val i = id(seq = 100L + index)
                s.begin(i, PresentationPath.FROZEN_VIEW)
                for (event in p) {
                    when (event) {
                        "draw" -> s.onDraw(i)
                        "frame" -> s.onFrameCommitted(i)
                        "commit" -> s.onTransactionCommitted(i)
                        "present" -> s.onTransactionPresented(i)
                    }
                }
                check(s.snapshot()?.confirmed == true) { "permutation $p did not confirm" }
            }
        }

        check("no completed callback means no false frozen PRESENTED state") {
            val s = PresentationLeaseStore(1)
            val i = id()
            s.begin(i, PresentationPath.FROZEN_VIEW)
            s.onDraw(i)
            s.onFrameCommitted(i)
            s.onTransactionCommitted(i)
            check(s.snapshot()?.confirmed == false)
        }

        check("no completed callback means no false live PRESENTED state") {
            val s = PresentationLeaseStore(1)
            val i = id()
            s.begin(i, PresentationPath.LIVE_MIRROR)
            s.onTransactionCommitted(i)
            check(s.snapshot()?.confirmed == false)
        }

        check("stale completion cannot overwrite present timestamp of current attempt") {
            val s = PresentationLeaseStore(1)
            val old = id(seq = 60)
            val current = id(cycle = 12, content = 33, seq = 61)
            s.begin(old, PresentationPath.LIVE_MIRROR)
            s.begin(current, PresentationPath.LIVE_MIRROR)
            s.onTransactionPresented(current, 999)
            check(!s.onTransactionPresented(old, 111))
            check(s.snapshot()?.presentTimeNs == 999L)
            check(s.snapshot()?.identity == current)
        }


        check("close-open-close makes first-cycle completions inert and second cycle confirmable") {
            val s = PresentationLeaseStore(1)
            val first = id(cycle = 20, host = 30, content = 40, seq = 70)
            val second = id(cycle = 21, host = 31, content = 41, seq = 71)
            s.begin(first, PresentationPath.FROZEN_VIEW)
            s.onDraw(first)
            s.invalidateCurrent() // opening reversal
            s.begin(second, PresentationPath.FROZEN_VIEW)
            check(!s.onFrameCommitted(first))
            check(!s.onTransactionPresented(first, 101))
            s.onTransactionPresented(second, 202)
            s.onFrameCommitted(second)
            s.onDraw(second)
            check(s.snapshot()?.confirmed == true)
            check(s.snapshot()?.identity == second)
            check(s.snapshot()?.presentTimeNs == 202L)
        }

        check("callback storm remains idempotent and cannot inflate confirmation count") {
            val s = PresentationLeaseStore(1)
            val i = id(seq = 80)
            s.begin(i, PresentationPath.FROZEN_VIEW)
            repeat(1_000) {
                s.onDraw(i)
                s.onFrameCommitted(i)
                s.onTransactionCommitted(i)
                s.onTransactionPresented(i, 303)
            }
            check(s.snapshot()?.confirmed == true)
            check(s.confirmedCount == 1L)
        }

        check("cross-attempt callback interleave cannot combine proof from different attempts") {
            val s = PresentationLeaseStore(1)
            val a = id(cycle = 30, host = 40, content = 50, seq = 90)
            val b = id(cycle = 31, host = 41, content = 51, seq = 91)
            s.begin(a, PresentationPath.FROZEN_VIEW)
            s.onDraw(a)
            s.onFrameCommitted(a)
            s.begin(b, PresentationPath.FROZEN_VIEW)
            s.onTransactionPresented(b)
            check(!s.onTransactionPresented(a))
            check(!s.onFrameCommitted(a))
            check(s.snapshot()?.confirmed == false)
            s.onDraw(b)
            s.onFrameCommitted(b)
            check(s.snapshot()?.confirmed == true)
        }

        check("100000-operation fuzz preserves current-attempt proof invariants") {
            val rnd = Random(0xD00F7)
            val s = PresentationLeaseStore(7)
            var nextSeq = 0L
            var current: PresentationIdentity? = null
            var path: PresentationPath
            repeat(100_000) {
                when (rnd.nextInt(10)) {
                    0, 1 -> {
                        val i = PresentationIdentity(
                            serviceEpoch = 7,
                            closeCycleId = rnd.nextLong(0, 200),
                            hostEpoch = rnd.nextLong(0, 200),
                            contentLeaseId = rnd.nextLong(0, 500),
                            attemptSequence = ++nextSeq,
                        )
                        path = if (rnd.nextBoolean()) PresentationPath.FROZEN_VIEW else PresentationPath.LIVE_MIRROR
                        check(s.begin(i, path))
                        current = i
                    }
                    2 -> current?.let { s.onDraw(it) }
                    3 -> current?.let { s.onFrameCommitted(it) }
                    4 -> current?.let { s.onTransactionCommitted(it) }
                    5 -> current?.let { s.onTransactionPresented(it, rnd.nextLong(1, Long.MAX_VALUE)) }
                    6 -> {
                        val stale = PresentationIdentity(7, 999, 999, 999, (nextSeq - rnd.nextInt(1, 20)).coerceAtLeast(0))
                        s.onTransactionPresented(stale)
                    }
                    7 -> s.invalidateCurrent().also { current = null }
                    8 -> current?.let { s.cancel(it) }
                    9 -> {
                        // Duplicate callbacks / callback burst.
                        current?.let {
                            s.onDraw(it)
                            s.onFrameCommitted(it)
                            s.onTransactionPresented(it)
                        }
                    }
                }

                val snap = s.snapshot()
                if (snap?.confirmed == true) {
                    when (snap.path) {
                        PresentationPath.FROZEN_VIEW -> check(
                            snap.drawObserved && snap.frameCommitted && snap.transactionPresented
                        )
                        PresentationPath.LIVE_MIRROR -> check(snap.transactionPresented)
                    }
                    check(!snap.cancelled)
                    check(snap.identity == current)
                }
            }
        }

        println("RESULT passed=$passed failed=$failed total=${passed + failed}")
        if (failed != 0) error("tests failed")
    }

    private fun <T> permutations(items: List<T>): List<List<T>> {
        if (items.size <= 1) return listOf(items)
        val out = ArrayList<List<T>>()
        for (i in items.indices) {
            val head = items[i]
            val rest = items.toMutableList().also { it.removeAt(i) }
            for (tail in permutations(rest)) out += listOf(head) + tail
        }
        return out
    }
}

fun main() = Tests().run()
