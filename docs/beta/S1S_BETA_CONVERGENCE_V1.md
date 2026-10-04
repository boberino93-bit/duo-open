# S1S Beta Convergence V1

Status: committed beta-convergence candidate; not merged to production.

Validated implementation head: `edc9ea650e4aabdb583c1d6f7fafa022226bc346`
Successful CI run: `37185438716`
Artifact ID: `11296153936`
Artifact SHA-256: `649c65f8006e0a5f66e852f5070b88241122420ba1f7eef19d709a8ead680007`
APK SHA-256: `381830804a6b74117915c7f3f069ebafaf17cf04103fa6195a2e7d5678690e93`
Version: `5.1.0-beta2-zfold7-s1s` / versionCode 53

## Beta-convergence scope

S1S preserves the validated S1P optical proxy, S1Q animation-coherence/vsync work, and S1R precise-hinge reader reacquisition while integrating the remaining beta-critical safeguards identified by the original beta-entry campaign.

### 1. Hinge semantic truth

Coarse public hinge midpoint samples (especially Samsung-style ~90-degree fallback readings) are no longer permitted to become continuous authoritative geometry when the precise feed expires. Coarse data may corroborate canonical endpoint/rest state only. The ordered bounded ingress path and S1R reader reacquisition remain authoritative for continuous motion.

### 2. Presentation readiness instead of topology existence

Logical display existence is not treated as proof that useful pixels can be presented. The opening optical bridge is held until INNER is the default display and `STATE_ON` continuously for 160 ms. Readiness loss resets the stability window. A bounded 500 ms timeout prevents a stranded proxy. Cover-side readiness is also strengthened with actual presentation truth.

### 3. Terminal native-cover fencing

`NATIVE_COVER` is terminal for the completed close cycle at the privileged daemon authority boundary. A delayed same-service secondary-route prepare is rejected, and completion is phase-fenced, preventing stale privileged work from resurrecting a secondary route after native cover ownership is established.

### 4. Refresh-rate lease and truth

The active visual attempt requests high refresh through both SurfaceControl frame-rate signaling and the overlay window's preferred refresh rate. Real Choreographer cadence is measured and classified so field evidence distinguishes honored high refresh from 60-class fallback rather than assuming a 120 Hz request succeeded.

### 5. Preserved stability work

S1S retains Hall-triggered early wake, safe `0 -> 1` fallback prewake, bounded optical proxy behavior, opening-remap ownership transfer, ordered hinge reversals, S1Q acceleration-limited/vsync-calibrated motion, S1R session-level hinge reacquisition, generation fencing, and existing close-path behavior.

## Diagnostic transport gate

The final APK verifier is now the source of truth for diagnostic transport configuration. The validated S1S artifact compiled without a configured HTTPS relay/ingest key, so automatic receipt-capable diagnostic upload remains an external beta-infrastructure gate. Manual debug-bundle export remains available. This candidate does not falsely mark diagnostic upload configured.

## Validation

The successful workflow reconstructed the full deployed Beta2 stack and S1 through S1R history, applied S1S, passed source invariants, Kotlin compilation, the full unit/regression suite, APK assembly, final compiled-APK diagnostic verification, and artifact packaging.

No unsafe `CONCURRENT_OUTER_DEFAULT`/DeviceState-state-5 route override is reintroduced.

## Production state

This record represents the committed S1S candidate on `fix/s1s-beta-convergence-v1-20261004`. Production merge remains a separate action and is not implied by this commit.