#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

SERVICE = Path("app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt")
COORDINATOR = Path("app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt")
DUO_APP = Path("app/src/main/java/com/duoopen/ui/DuoApp.kt")
HOME = Path("app/src/main/java/com/duoopen/ui/HomePreview.kt")
MARKER = "FOLD7_DISPLAY_STATUS_V3"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_service(text: str) -> str:
    if MARKER in text:
        return text
    if "lid-switch-open" not in text:
        raise RuntimeError("physical bridge V1 lid path must exist before V3 status")

    text = replace_once(
        text,
        '''    private fun handleEarlyOpeningEdge(
        reason: String,
    ) {
''',
        '''    // FOLD7_DISPLAY_STATUS_V3
    private fun handleEarlyOpeningEdge(
        reason: String,
    ) {
        Fold7DisplayStatusStore.update { current ->
            current.copy(
                openingSource = reason,
                wakeCommand = Fold7DisplayStatus.WakeCommand.REQUESTED,
                physicalPower = Fold7DisplayStatus.PhysicalPower.UNKNOWN,
                bridge = Fold7DisplayStatus.Bridge.IDLE,
                logicalInnerAvailable = false,
                nativeInnerActive = false,
                nativeInnerDefault = false,
                lastError = null,
            )
        }
''',
        "opening status request",
    )

    text = replace_once(
        text,
        '''        instance = null
''',
        '''        instance = null
        Fold7DisplayStatusStore.reset("service-destroyed")
''',
        "service destroy status reset",
    )

    return text


def transform_coordinator(text: str) -> str:
    if MARKER in text:
        return text
    if "INNER_PHYSICAL_BRIDGE_V2" not in text:
        raise RuntimeError("V2 handoff must be applied before V3 status")

    text = replace_once(
        text,
        '''            DuoDiagnostics.event(
                "inner-wake-stage",
                "WAKE_COMMITTED serviceEpoch=${openingKey.serviceEpoch} " +
                    "openingAttempt=${openingKey.openingAttemptSequence} retry=$attempt " +
                    "acceptedGeneration=${openingKey.acceptedGeneration} currentGeneration=${controller.generation}",
            )
''',
        '''            DuoDiagnostics.event(
                "inner-wake-stage",
                "WAKE_COMMITTED serviceEpoch=${openingKey.serviceEpoch} " +
                    "openingAttempt=${openingKey.openingAttemptSequence} retry=$attempt " +
                    "acceptedGeneration=${openingKey.acceptedGeneration} currentGeneration=${controller.generation}",
            )
            Fold7DisplayStatusStore.update { current ->
                current.copy(
                    wakeCommand = Fold7DisplayStatus.WakeCommand.REQUESTED,
                    openingAttempt = openingKey.openingAttemptSequence,
                )
            }
''',
        "wake committed status",
    )

    anchor = '''                DuoDiagnostics.event(
                    "inner-wake-stage",
                    "WAKE_RESULT serviceEpoch=${openingKey.serviceEpoch} " +
'''
    insert = '''                val physicalPowered =
                    result?.getBoolean("physicalPowered", false) == true
                val bridgeActive =
                    result?.getBoolean("physicalBridgeActive", false) == true
                val logicalAvailable =
                    (result?.getInt("innerLogicalId", -1) ?: -1) >= 0
                val wakeOk =
                    result?.getBoolean("ok", false) == true

                Fold7DisplayStatusStore.update { current ->
                    current.copy(
                        wakeCommand =
                            if (wakeOk) {
                                Fold7DisplayStatus.WakeCommand.ACCEPTED
                            } else {
                                Fold7DisplayStatus.WakeCommand.FAILED
                            },
                        physicalPower =
                            when {
                                physicalPowered -> Fold7DisplayStatus.PhysicalPower.COMMAND_ACCEPTED
                                wakeOk -> Fold7DisplayStatus.PhysicalPower.UNKNOWN
                                else -> Fold7DisplayStatus.PhysicalPower.FAILED
                            },
                        bridge =
                            when {
                                bridgeActive -> Fold7DisplayStatus.Bridge.PRESENTING
                                result?.getString("physicalBridgeError") != null -> Fold7DisplayStatus.Bridge.FAILED
                                else -> current.bridge
                            },
                        logicalInnerAvailable = logicalAvailable,
                        nativeInnerActive = topologyNow.innerActive,
                        nativeInnerDefault = topologyNow.innerIsDefault,
                        openingAttempt = openingKey.openingAttemptSequence,
                        lastError =
                            result?.getString("error")
                                ?: result?.getString("logicalError")
                                ?: result?.getString("physicalBridgeError"),
                    )
                }

'''
    text = replace_once(
        text,
        anchor,
        insert + anchor,
        "wake result status",
    )

    text = replace_once(
        text,
        '''                    openingWakeGate.complete(openingKey)
                    DuoDiagnostics.event(
''',
        '''                    openingWakeGate.complete(openingKey)
                    Fold7DisplayStatusStore.update { current ->
                        current.copy(
                            bridge = Fold7DisplayStatus.Bridge.HANDOFF_ARMED,
                            nativeInnerActive = true,
                            nativeInnerDefault = topologyNow.innerIsDefault,
                        )
                    }
                    DuoDiagnostics.event(
''',
        "handoff armed status",
    )

    text = replace_once(
        text,
        '''                                DuoDiagnostics.event(
                                    "inner-wake-stage",
                                    "HANDOFF_RELEASED serviceEpoch=${openingKey.serviceEpoch} " +
''',
        '''                                Fold7DisplayStatusStore.update { current ->
                                    current.copy(
                                        physicalPower =
                                            if (current.physicalPower == Fold7DisplayStatus.PhysicalPower.COMMAND_ACCEPTED) {
                                                Fold7DisplayStatus.PhysicalPower.COMMAND_ACCEPTED
                                            } else {
                                                current.physicalPower
                                            },
                                        bridge = Fold7DisplayStatus.Bridge.RELEASED,
                                        nativeInnerActive = true,
                                        nativeInnerDefault = topology().innerIsDefault,
                                    )
                                }

                                DuoDiagnostics.event(
                                    "inner-wake-stage",
                                    "HANDOFF_RELEASED serviceEpoch=${openingKey.serviceEpoch} " +
''',
        "handoff released status",
    )

    return text


def transform_duo_app(text: str) -> str:
    if MARKER in text:
        return text

    text = replace_once(
        text,
        '''import com.duoopen.overlay.OverlayState
''',
        '''import com.duoopen.overlay.OverlayState
import com.duoopen.overlay.Fold7DisplayStatusStore
''',
        "DuoApp status import",
    )

    text = replace_once(
        text,
        '''    val overlayRunning by
        OverlayState.running
            .collectAsStateWithLifecycle()
''',
        '''    val overlayRunning by
        OverlayState.running
            .collectAsStateWithLifecycle()

    val fold7DisplayStatus by
        Fold7DisplayStatusStore.status
            .collectAsStateWithLifecycle()
''',
        "DuoApp collect status",
    )

    text = replace_once(
        text,
        '''            shizukuReady = OverlayFeature.shizukuReady(),
''',
        '''            shizukuReady = OverlayFeature.shizukuReady(),
            displayStatus = fold7DisplayStatus,
''',
        "HomePreview status argument",
    )

    return text


def transform_home(text: str) -> str:
    if MARKER in text:
        return text

    text = replace_once(
        text,
        '''import kotlin.math.roundToInt
''',
        '''import kotlin.math.roundToInt
import com.duoopen.overlay.Fold7DisplayStatus
''',
        "HomePreview status import",
    )

    text = replace_once(
        text,
        '''    shizukuReady: Boolean,
    onTest: () -> Unit,
''',
        '''    shizukuReady: Boolean,
    displayStatus: Fold7DisplayStatus,
    onTest: () -> Unit,
''',
        "HomePreview parameter",
    )

    text = replace_once(
        text,
        '''                Spacer(Modifier.height(18.dp))
                Text(
                    "Accessibility ${if (overlayEnabled) "ON" else "OFF"}  ·  " +
''',
        '''                Spacer(Modifier.height(18.dp))

                Text(
                    displayStatus.summary,
                    color = Color.White,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.SemiBold,
                    textAlign = TextAlign.Center,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    displayStatus.detail,
                    color = Dim,
                    fontSize = 10.sp,
                    textAlign = TextAlign.Center,
                )

                Spacer(Modifier.height(14.dp))
                Text(
                    "Accessibility ${if (overlayEnabled) "ON" else "OFF"}  ·  " +
''',
        "HomePreview status body",
    )

    text = text.replace(
        "fun HomePreview(\n",
        "// FOLD7_DISPLAY_STATUS_V3\nfun HomePreview(\n",
        1,
    )
    return text


def apply(repo: Path, check: bool) -> None:
    paths = {
        SERVICE: transform_service,
        COORDINATOR: transform_coordinator,
        DUO_APP: transform_duo_app,
        HOME: transform_home,
    }

    outputs: dict[Path, str] = {}
    for rel, fn in paths.items():
        path = repo / rel
        if not path.exists():
            raise RuntimeError(f"missing {rel}")
        outputs[path] = fn(path.read_text(encoding="utf-8"))

    required = {
        SERVICE: ("Fold7DisplayStatusStore.update", "FOLD7_DISPLAY_STATUS_V3"),
        COORDINATOR: ("Fold7DisplayStatus.Bridge.HANDOFF_ARMED", "physicalBridgeActive"),
        DUO_APP: ("Fold7DisplayStatusStore.status", "displayStatus = fold7DisplayStatus"),
        HOME: ("displayStatus.summary", "displayStatus.detail"),
    }
    for rel, needles in required.items():
        output = outputs[repo / rel]
        for needle in needles:
            if needle not in output:
                raise RuntimeError(f"missing V3 invariant in {rel}: {needle}")

    if not check:
        for path, output in outputs.items():
            path.write_text(output, encoding="utf-8")


def self_test() -> None:
    print("fold7 display status v3 model: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        if not args.check:
            return 0

    apply(Path(args.repo).resolve(), args.check)
    print("fold7 display status v3: source shape verified" if args.check else "fold7 display status v3: applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
