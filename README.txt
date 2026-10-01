PURPOSE
R&D-only evidence package for Duo Open Galaxy Z Fold7 deterministic frozen-continuity-frame provenance/lifecycle. It is intended for direct import into the primary supervising agent (Root) for independent comparison against then-current main.

BASELINE SHA
8f844ba8aadd8417a92ec8b568288fd0dd9e06e3

FINAL CHECKED MAIN SHA
8f844ba8aadd8417a92ec8b568288fd0dd9e06e3

FILES INCLUDED
- DUO_OPEN_FROZEN_FRAME_PROVENANCE_GEN2_RND_HANDOFF.txt
- Fold7ContinuityFrameLeaseGen2.kt
- Fold7ContinuityFrameLeaseGen2Test.kt
- timing_model.py
- TEST_OUTPUT.txt
- TIMING_MODEL_OUTPUT.txt
- README.txt
- BASELINE-SHA.txt
- FINAL-MAIN-SHA.txt
- SHA256SUMS.txt

HOW TO REPRODUCE TESTS
kotlinc Fold7ContinuityFrameLeaseGen2.kt Fold7ContinuityFrameLeaseGen2Test.kt -include-runtime -d frame-lease-gen2-tests.jar
java -jar frame-lease-gen2-tests.jar
Expected: RESULT passed=15 failed=0 total=15

python3 timing_model.py
All timing statements are architectural/source-derived or explicitly UNKNOWN/EXPECTED; no Fold7 latency measurement is claimed.

INTEGRATION INTENT
Re-fetch current main first. Treat the package as evidence/model only. Manually integrate a transition-scoped continuity-frame lease if the source-level provenance gap remains. Preserve current geometry, hinge thresholds, task placement, cover-panel lease safety, readiness architecture, deterministic frozen-frame intent, early wake, and Transition Lab.

IMPORTED PRIOR WORK INCORPORATED
- Cover Readiness Gen2 proposal: independently hash-verified and 22/22 model tests rerun successfully.
- Cover Lease Protocol Gen2 proposal: independently hash-verified; 10/10 snapshot gate, 5/5 identity, and 5,000-round / 125,000-delivery fuzz rerun successfully.
Those areas are intentionally not duplicated by this proposal.

KNOWN RISKS
- Fail-closed provenance may increase live-mirror fallback frequency when a current-cycle frame is unavailable.
- Shizuku capture currently lacks an exact public capture timestamp in the app return type; request-bounded provenance is deliberately conservative.
- closeCycleId must be distinct from controller.generation.
- Fold7 field validation is mandatory.

PRODUCTION STATUS=R&D ONLY
MANUAL REVIEW REQUIRED=YES
INSTALLATION AUTHORIZED=NO
