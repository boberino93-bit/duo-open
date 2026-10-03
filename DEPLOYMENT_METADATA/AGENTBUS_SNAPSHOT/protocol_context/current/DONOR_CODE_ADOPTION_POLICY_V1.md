# Duo Open Donor Code Adoption Policy V1

**Status:** MANDATORY engineering-process rule

Duo Open should learn aggressively from external/open-source implementations without confusing useful code with validated Fold7 runtime truth.

## Three adoption classes

### A. RUNTIME_CANDIDATE
Use when donor code or behavior may affect:
- panel power/routing
- hinge semantic authority
- display identity
- privacy/security
- capture/mirroring
- wake behavior
- terminal state
- physical timing/readiness

Requirements:
- license/attribution preserved;
- current-source revalidation;
- isolation behind Duo Open authority contracts;
- deterministic/model/CI testing;
- Fold7 field validation where device behavior is involved.

### B. FEATURE_FLAGGED_EXPERIMENT
Use when a donor idea is useful but physical Fold7 validation is incomplete.

Allowed examples:
- alternate visual projection
- animation profile
- reflection mode
- AA method
- visual smoothing/tuning
- non-authoritative visual endpoint threshold

Requirements:
- cannot mutate semantic hinge, power, route, privacy, terminal state;
- bounded/sanitized settings;
- safe default and rollback;
- diagnostics identify active experiment;
- existing regression baseline remains authoritative.

### C. PROCESS_TOOLING_ADOPTION
Adopt whenever it improves engineering quality and does not assert device runtime behavior.

Examples:
- unit-test structure
- fuzz/adversarial test patterns
- bounded setting sanitizers
- status/recovery logs
- bug-report schema ideas
- health telemetry
- source-layout organization
- onboarding/recovery workflows
- build/CI validation
- feature-policy decomposition
- documentation/attribution practices

This class does **not** require physical Fold7 validation before use, because it does not claim Fold7 hardware semantics.

## Donor: joeconsorti/duo-fold-live

Observed donor license: MIT. Third-party notices identify additional upstream MIT and Apache-2.0 components. Preserve applicable copyright/license notices for copied or substantially derived code.

Portable concepts currently approved for study/adaptation:
- selectable animation profiles
- fold-only / unfold-only direction gates
- window-reveal projection controls
- independent cover/inner visual tuning
- bounded frame-rate-independent smoothing
- blur/glass/seam controls
- AA methods
- full/half resolution render quality
- requested 60/120 render targets with actual-cadence diagnostics
- recovery/status reports
- bounded process-health telemetry
- narrow policy classes with dedicated tests
- visual preview/reflection modes
- setup/recovery UX

Not automatically validated for Fold7:
- Fold8 hinge reader assumptions
- Fold8 wake/power routing
- logical/physical display IDs
- direct handoff thresholds
- Fold8 capture/mirror lifecycle
- Fold8 Samsung wallpaper/API behavior

## Principle

If donor code cannot be safely promoted into runtime, extract the reusable invariant, test pattern, API boundary, diagnostic, or workflow improvement rather than discarding the work.

Never let lack of device validation prevent process/tooling learning.
Never let process/tooling usefulness masquerade as device validation.
