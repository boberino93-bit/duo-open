# Gen6 Alpha 1 V2 — WakeHint Replay

The supplied Gen4 field log contains nine `0 -> 1` Samsung device-state departures with a subsequent authoritative hinge sample.

Legacy wait from `0 -> 1` to the next hinge sample:

- minimum: **401 ms**
- median: **910 ms**
- p95: **2,484 ms**
- maximum: **2,484 ms**

Gen6 Alpha 1 V2 changes the dispatch point: physical inner wake plus the visual-material latch are issued directly from the independently learned `0 -> 1` WakeHint. They no longer wait for that later hinge sample.

This is **replay/model evidence only**. It predicts removal of that wait from the dispatch path; the actual Fold7 presentation and wake timing must be measured with the V2 APK.
