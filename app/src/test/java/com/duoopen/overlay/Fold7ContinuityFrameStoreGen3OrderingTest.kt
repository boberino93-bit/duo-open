package com.duoopen.overlay

import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class Fold7ContinuityFrameStoreGen3OrderingTest {
    @Test
    fun olderCaptureCannotPublishAfterNewerCaptureHasStarted() {
        val store =
            Fold7ContinuityFrameStore<String>()

        val cycle =
            Fold7CycleEnvelope.CloseCycle(
                serviceEpoch = 7L,
                closeCycleId = 11L,
                startedUptimeMs = 100L,
            )

        store.beginCycle(
            cycle
        )

        val first =
            store.beginCapture(
                cycle = cycle,
                width = 1968,
                height = 2184,
                requestStartedUptimeMs = 110L,
                source =
                    Fold7ContinuityFrameStore.Source.SHIZUKU,
            )!!

        val newer =
            store.beginCapture(
                cycle = cycle,
                width = 1968,
                height = 2184,
                requestStartedUptimeMs = 120L,
                source =
                    Fold7ContinuityFrameStore.Source.SHIZUKU,
            )!!

        assertNull(
            store.publish(
                ticket = first,
                capturedUptimeMs = 110L,
                completedUptimeMs = 130L,
                timestampQuality =
                    Fold7ContinuityFrameStore.TimestampQuality.REQUEST_BOUNDED,
                payload = "old",
            )
        )

        assertNotNull(
            store.publish(
                ticket = newer,
                capturedUptimeMs = 120L,
                completedUptimeMs = 140L,
                timestampQuality =
                    Fold7ContinuityFrameStore.TimestampQuality.REQUEST_BOUNDED,
                payload = "new",
            )
        )
    }
}
