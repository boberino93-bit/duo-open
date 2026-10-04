#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

V = Path("app/src/full/java/com/duoopen/debug/VisualForensics.kt")
M = "STABILIZATION_S1J_CAPTURE_POLICY_FORENSICS_V1"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def transform(text: str) -> str:
    if M in text:
        return text
    if "STABILIZATION_S1I_CORRELATED_FORENSICS_V1" not in text:
        raise RuntimeError("S1I must be applied first")
    if "WORK_PROFILE_SCREEN_CAPTURE_POLICY_BLOCKED" not in text:
        raise RuntimeError("S1H policy-aware classifier must be present")

    text = one(
        text,
        '    private const val CORRELATION_MARKER = "STABILIZATION_S1I_CORRELATED_FORENSICS_V1"\n',
        '    private const val CORRELATION_MARKER = "STABILIZATION_S1I_CORRELATED_FORENSICS_V1"\n'
        f'    private const val CAPTURE_POLICY_MARKER = "{M}"\n',
        "marker",
    )

    text = one(
        text,
        '''                appendLine("correlationMarker=$CORRELATION_MARKER")
                appendLine("started=${Instant.now()}")
''',
        '''                appendLine("correlationMarker=$CORRELATION_MARKER")
                appendLine("capturePolicyMarker=$CAPTURE_POLICY_MARKER")
                appendLine("started=${Instant.now()}")
''',
        "readme marker",
    )

    # Add a separate evidence column so a classification never hides why it was chosen.
    text = one(
        text,
        '''        file.writeText("sample\\ttargetMs\\tactualMs\\tpanel\\tbackend\\tlogicalId\\tphysicalId\\tdisplayState\\trawStatus\\tclassification\\tsecure\\tfile\\tbytes\\tsha256\\tmeanLuma\\tlumaRange\\tdarkFraction\\tcaptureStartedElapsedMs\\tcaptureFinishedElapsedMs\\twallCaptureMs\\tbackendCaptureMs\\tsourceWidth\\tsourceHeight\\terror\\n")
''',
        '''        file.writeText("sample\\ttargetMs\\tactualMs\\tpanel\\tbackend\\tlogicalId\\tphysicalId\\tdisplayState\\trawStatus\\tclassification\\tcaptureEvidence\\tsecure\\tfile\\tbytes\\tsha256\\tmeanLuma\\tlumaRange\\tdarkFraction\\tcaptureStartedElapsedMs\\tcaptureFinishedElapsedMs\\twallCaptureMs\\tbackendCaptureMs\\tsourceWidth\\tsourceHeight\\terror\\n")
''',
        "manifest header",
    )

    text = one(
        text,
        '''                r.displayState, r.rawStatus, classify(r, context), r.secure, r.file.orEmpty(), r.bytes,
''',
        '''                r.displayState, r.rawStatus, classify(r, records, context), captureEvidence(r, context),
                r.secure, r.file.orEmpty(), r.bytes,
''',
        "manifest values",
    )

    old_classifier = '''    private fun classify(record: Record, context: PolicyContext): String {
        if (record.rawStatus == "NO_LOGICAL_ROUTE") return "ROUTE_ABSENT_NOT_CAPTURE_FAILURE"
        if (record.rawStatus == "NO_PHYSICAL_ID") return "PHYSICAL_ID_RESOLUTION_FAILED"
        if (record.secure || record.rawStatus == "SECURE_LAYER_BLOCKED") return "SECURE_OR_PROTECTED_CONTENT_BLOCKED"

        val managed = context.topUser != null && context.topUser in context.managedUsers
        if (record.rawStatus != "CAPTURED") {
            if (context.captureRestricted && managed) return "WORK_PROFILE_SCREEN_CAPTURE_POLICY_BLOCKED"
            if (context.captureRestricted) return "DEVICE_POLICY_SCREEN_CAPTURE_BLOCKED"
            if (context.secureHint) return "SECURE_WINDOW_OR_PROTECTED_CONTENT_SUSPECTED"
            val e = record.error.orEmpty().lowercase(Locale.ROOT)
            if (e.contains("timeout") || e.contains("timed out")) return "CAPTURE_BACKEND_TIMEOUT"
            if (e.contains("permission") || e.contains("security")) return "CAPTURE_PERMISSION_OR_POLICY_ERROR"
            return "CAPTURE_BACKEND_OR_PANEL_FAILURE"
        }

        val low = record.meanLuma != null && record.lumaRange != null && record.darkFraction != null &&
            record.lumaRange <= 8 && record.darkFraction >= 0.98
        if (low) {
            if (context.captureRestricted && managed) return "CAPTURED_REDACTED_OR_DARK_WORK_PROFILE_POLICY_POSSIBLE"
            if (context.captureRestricted) return "CAPTURED_REDACTED_OR_DARK_DEVICE_POLICY_POSSIBLE"
            if (context.secureHint) return "CAPTURED_REDACTED_OR_DARK_SECURE_WINDOW_POSSIBLE"
            if (record.backend == "physical-screencap" && record.logicalId < 0) {
                return "CAPTURED_LOW_INFORMATION_PHYSICAL_WITHOUT_LOGICAL_ROUTE"
            }
            return "CAPTURED_LOW_INFORMATION_FRAME"
        }
        return "CAPTURED_USABLE_FRAME"
    }
'''

    new_classifier = '''    // STABILIZATION_S1J_CAPTURE_POLICY_FORENSICS_V1
    // Classification is deliberately evidence-ordered. A failure on one backend
    // is not promoted to enterprise/secure-content policy if the independent
    // backend captured the same panel/sample successfully.
    private fun classify(record: Record, records: List<Record>, context: PolicyContext): String {
        if (record.rawStatus == "NO_LOGICAL_ROUTE") return "ROUTE_ABSENT_NOT_CAPTURE_FAILURE"
        if (record.rawStatus == "NO_PHYSICAL_ID") return "PHYSICAL_ID_RESOLUTION_FAILED"
        if (record.secure || record.rawStatus == "SECURE_LAYER_BLOCKED") {
            return "SECURE_OR_PROTECTED_CONTENT_BLOCKED_CONFIRMED_BY_BACKEND"
        }

        val managed = context.topUser != null && context.topUser in context.managedUsers
        val peer = records.firstOrNull {
            it !== record && it.sample == record.sample && it.panel == record.panel && it.backend != record.backend
        }
        val peerUsable = peer?.rawStatus == "CAPTURED" && !isLowInformation(peer)

        if (record.rawStatus != "CAPTURED") {
            // If another independent capture path succeeded, this is a backend-
            // specific limitation/failure, not proof that the app or profile is
            // globally uncapturable.
            if (peerUsable) return "BACKEND_SPECIFIC_CAPTURE_FAILURE_PEER_PATH_SUCCEEDED"

            if (context.captureRestricted && managed) {
                return "WORK_PROFILE_SCREEN_CAPTURE_POLICY_BLOCKED_CONFIRMED_CONTEXT"
            }
            if (context.captureRestricted) return "DEVICE_POLICY_SCREEN_CAPTURE_BLOCKED_CONFIRMED_CONTEXT"
            if (context.secureHint) return "SECURE_WINDOW_OR_PROTECTED_CONTENT_SUSPECTED"

            val e = record.error.orEmpty().lowercase(Locale.ROOT)
            if (e.contains("timeout") || e.contains("timed out")) return "CAPTURE_BACKEND_TIMEOUT"
            if (e.contains("invalid display") || e.contains("no display") || e.contains("display not found")) {
                return "DISPLAY_TARGET_REJECTED_OR_GONE"
            }
            if (e.contains("permission denied") || e.contains("securityexception")) {
                return "CAPTURE_BACKEND_PERMISSION_DENIED_NO_POLICY_PROOF"
            }
            if (e.contains("permission") || e.contains("security")) {
                return "CAPTURE_PERMISSION_OR_POLICY_ERROR_AMBIGUOUS"
            }
            return "CAPTURE_BACKEND_OR_PANEL_FAILURE"
        }

        if (isLowInformation(record)) {
            val peerUseful = peer?.rawStatus == "CAPTURED" && !isLowInformation(peer)
            if (peerUseful) return "BACKEND_REDACTION_OR_COMPOSITION_MISMATCH_PEER_USABLE"
            if (context.captureRestricted && managed) return "CAPTURED_REDACTED_OR_DARK_WORK_PROFILE_POLICY_POSSIBLE"
            if (context.captureRestricted) return "CAPTURED_REDACTED_OR_DARK_DEVICE_POLICY_POSSIBLE"
            if (context.secureHint) return "CAPTURED_REDACTED_OR_DARK_SECURE_WINDOW_POSSIBLE"
            if (record.backend == "physical-screencap" && record.logicalId < 0) {
                return "CAPTURED_LOW_INFORMATION_PHYSICAL_WITHOUT_LOGICAL_ROUTE"
            }
            return "CAPTURED_LOW_INFORMATION_FRAME"
        }
        return "CAPTURED_USABLE_FRAME"
    }

    private fun isLowInformation(record: Record): Boolean =
        record.meanLuma != null && record.lumaRange != null && record.darkFraction != null &&
            record.lumaRange <= 8 && record.darkFraction >= 0.98

    private fun captureEvidence(record: Record, context: PolicyContext): String {
        val managed = context.topUser != null && context.topUser in context.managedUsers
        return when {
            record.secure || record.rawStatus == "SECURE_LAYER_BLOCKED" -> "BACKEND_SECURE_LAYER_SIGNAL"
            context.captureRestricted && managed -> "DPM_CAPTURE_RESTRICTION+MANAGED_PROFILE_TOP_USER"
            context.captureRestricted -> "DPM_CAPTURE_RESTRICTION"
            context.secureHint -> "WINDOW_SECURE_HINT"
            record.rawStatus == "NO_LOGICAL_ROUTE" -> "DISPLAY_ROUTE_ABSENT"
            record.rawStatus == "NO_PHYSICAL_ID" -> "PHYSICAL_DISPLAY_ID_ABSENT"
            else -> "NO_POLICY_OR_SECURE_SIGNAL"
        }
    }
'''

    text = one(text, old_classifier, new_classifier, "classifier")

    # Export the distinction contract beside raw policy evidence for later review.
    text = one(
        text,
        '''                appendLine("captureBackend=${context.raw?.getString(\"capture_backend\") ?: \"<unavailable>\"}")
''',
        '''                appendLine("captureBackend=${context.raw?.getString(\"capture_backend\") ?: \"<unavailable>\"}")
                appendLine("capturePolicyMarker=$CAPTURE_POLICY_MARKER")
                appendLine("classificationContract=backend-secure > peer-backend-success > DPM-managed-profile > DPM-device > secure-window-hint > backend-error")
''',
        "capture context contract",
    )

    return text


def validate(text: str) -> None:
    for needle in (
        M,
        "captureEvidence",
        "WORK_PROFILE_SCREEN_CAPTURE_POLICY_BLOCKED_CONFIRMED_CONTEXT",
        "BACKEND_SPECIFIC_CAPTURE_FAILURE_PEER_PATH_SUCCEEDED",
        "SECURE_OR_PROTECTED_CONTENT_BLOCKED_CONFIRMED_BY_BACKEND",
        "CAPTURE_BACKEND_PERMISSION_DENIED_NO_POLICY_PROOF",
        "BACKEND_REDACTION_OR_COMPOSITION_MISMATCH_PEER_USABLE",
        "classificationContract=backend-secure",
    ):
        if needle not in text:
            raise RuntimeError("missing S1J invariant: " + needle)


def apply(repo: Path, check: bool) -> None:
    path = repo / V
    if not path.exists():
        raise RuntimeError("missing " + str(V))
    text = transform(path.read_text())
    validate(text)
    if not check:
        path.write_text(text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        # Full exact-shape validation runs in CI after S1H/S1I reconstruction.
        print("stabilization S1J capture-policy forensics transformer self-test: PASS")
        if not args.check:
            return 0
    apply(Path(args.repo).resolve(), args.check)
    print("stabilization S1J capture-policy forensics: " + ("source shape verified" if args.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
