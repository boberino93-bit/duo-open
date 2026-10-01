PURPOSE
R&D-only evidence package for Duo Open Galaxy Z Fold7 first-visible-frame / compositor-presentation ownership. It is intended for direct import into the primary supervising agent (Root) for independent comparison against then-current main.

BASELINE SHA
331878fc851069dc8b79d5343b371494f64ee1fd

FINAL CHECKED MAIN SHA
331878fc851069dc8b79d5343b371494f64ee1fd

FILES INCLUDED
- DUO_OPEN_PRESENTATION_LEASE_GEN2_RND_HANDOFF.txt
- Fold7PresentationLeaseGen2.kt
- Fold7PresentationLeaseGen2Test.kt
- INTEGRATION_SKETCH.txt
- timing_model.py
- TEST_OUTPUT.txt
- TIMING_MODEL_OUTPUT.txt
- PRIOR_ARTIFACT_HASH_CHECK.txt
- README.txt
- BASELINE-SHA.txt
- FINAL-MAIN-SHA.txt
- SHA256SUMS.txt

HOW TO REPRODUCE TESTS
kotlinc Fold7PresentationLeaseGen2.kt Fold7PresentationLeaseGen2Test.kt -include-runtime -d presentation-gen2-tests.jar
java -jar presentation-gen2-tests.jar
Expected: RESULT passed=23 failed=0 total=23

python3 timing_model.py
Expected final lines:
INTENTIONAL_GEN2_SLEEP_OR_DELAY_MS=0
DEVICE_MEASURED_LATENCY_NUMBERS=NONE

INTEGRATION INTENT
Re-fetch current main first. Treat this package as evidence/model only. Manually integrate immutable presentation-attempt identity and observation-only View frame-commit / SurfaceControl presentation evidence if the source-level gap remains. Preserve existing thresholds, task placement, panel lease safety, cover readiness, deterministic frozen-frame intent, frozen-frame provenance, live-mirror fallback, early wake and Transition Lab.

KNOWN RISKS
- The hidden/inert SurfaceControl marker concept is architecture-supported but not Android-device-tested in this silo.
- Callback threads must not mutate unsynchronized owner state.
- Do not gate first draw on callback receipt in the initial integration.
- Transaction presentation is not proof of physical photons.
- PresentationLease must remain distinct from cover lease, readiness state, controller generation and frame provenance.

PRODUCTION STATUS=R&D ONLY
MANUAL REVIEW REQUIRED=YES
INSTALLATION AUTHORIZED=NO
