#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

SHELL = Path("app/src/full/java/com/duoopen/shell/DuoShellService.kt")
COORDINATOR = Path("app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt")
MARKER = "INNER_PHYSICAL_BRIDGE_V2"
HANDOFF_MS = 80


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_shell(text: str) -> str:
    if MARKER in text:
        return text
    if "INNER_PHYSICAL_BRIDGE_V1" not in text:
        raise RuntimeError("V1 physical bridge must be applied first")

    text = replace_once(
        text,
        "    private val innerPhysicalBridgeLayerStack = 0x44554F\n",
        "    // INNER_PHYSICAL_BRIDGE_V2: keep the temporary privacy layer on Samsung's native\n"
        "    // INNER layer stack. This removes the private-stack/native-stack ownership race.\n"
        "    private val innerPhysicalBridgeLayerStack = 0\n",
        "native layer stack",
    )

    text = replace_once(
        text,
        "                        floatArrayOf(0.05f, 0.72f, 0.95f),\n",
        "                        // INNER_PHYSICAL_BRIDGE_V2: neutral near-black privacy cover.\n"
        "                        // V1 cyan was diagnostic proof only.\n"
        "                        floatArrayOf(0.012f, 0.012f, 0.016f),\n",
        "neutral bridge color",
    )

    return text


def transform_coordinator(text: str) -> str:
    if MARKER in text:
        return text
    if "INNER_WAKE_PROBE_V1" not in text:
        raise RuntimeError("inner wake probe must be applied first")

    old = '''                if (topologyNow.innerActive) {
                    scope.launch(Dispatchers.IO) {
                        ShizukuBridge.releaseInnerPhysicalBridge(
                            serviceEpoch = openingKey.serviceEpoch,
                            openingAttemptSequence =
                                openingKey.openingAttemptSequence,
                            reason = "topology-inner-active",
                        )
                    }
                    openingWakeGate.complete(openingKey)
                    DuoDiagnostics.event(
                        "inner-wake-stage",
                        "TOPOLOGY_READY serviceEpoch=${openingKey.serviceEpoch} " +
                            "openingAttempt=${openingKey.openingAttemptSequence} retry=$attempt " +
                            "innerDefault=${topologyNow.innerIsDefault}",
                    )
                    return@post
                }
'''

    new = f'''                if (topologyNow.innerActive) {{
                    /* {MARKER}
                     *
                     * V1 released the physical bridge immediately when Android first
                     * reported INNER active. On Fold7 that races Samsung's first native
                     * composition: sometimes the private bridge stack won (cyan), other
                     * times native composition won mid-transition.
                     *
                     * V2 already shares native stack 0. Keep the neutral privacy layer
                     * above Samsung's layers for a short bounded settle window, then
                     * remove only that layer. Closing/reversal/privilege-loss still force
                     * immediate cleanup through the existing V1 fences.
                     */
                    openingWakeGate.complete(openingKey)
                    DuoDiagnostics.event(
                        "inner-wake-stage",
                        "HANDOFF_ARMED serviceEpoch=${{openingKey.serviceEpoch}} " +
                            "openingAttempt=${{openingKey.openingAttemptSequence}} retry=$attempt " +
                            "innerDefault=${{topologyNow.innerIsDefault}} " +
                            "settleMs=$INNER_BRIDGE_HANDOFF_SETTLE_MS",
                    )

                    handler.postDelayed(
                        {{
                            scope.launch(Dispatchers.IO) {{
                                val release =
                                    ShizukuBridge.releaseInnerPhysicalBridge(
                                        serviceEpoch = openingKey.serviceEpoch,
                                        openingAttemptSequence =
                                            openingKey.openingAttemptSequence,
                                        reason = "native-inner-settled",
                                    )

                                DuoDiagnostics.event(
                                    "inner-wake-stage",
                                    "HANDOFF_RELEASED serviceEpoch=${{openingKey.serviceEpoch}} " +
                                        "openingAttempt=${{openingKey.openingAttemptSequence}} " +
                                        "ok=${{release?.getBoolean(\"ok\", false) == true}} " +
                                        "stale=${{release?.getBoolean(\"stale\", false) == true}} " +
                                        "active=${{release?.getBoolean(\"active\", false) == true}}",
                                )
                            }}
                        }},
                        INNER_BRIDGE_HANDOFF_SETTLE_MS,
                    )
                    return@post
                }}
'''

    text = replace_once(text, old, new, "bounded native handoff")

    text = replace_once(
        text,
        "        const val INNER_WAKE_RETRY_MS = 55L\n",
        f"        const val INNER_WAKE_RETRY_MS = 55L\n"
        f"        const val INNER_BRIDGE_HANDOFF_SETTLE_MS = {HANDOFF_MS}L\n",
        "handoff settle constant",
    )

    return text


def apply(repo: Path, check: bool) -> None:
    shell = repo / SHELL
    coordinator = repo / COORDINATOR
    if not shell.exists() or not coordinator.exists():
        raise RuntimeError("required Android sources missing")

    before_shell = shell.read_text(encoding="utf-8")
    before_coord = coordinator.read_text(encoding="utf-8")
    after_shell = transform_shell(before_shell)
    after_coord = transform_coordinator(before_coord)

    required = (
        "private val innerPhysicalBridgeLayerStack = 0",
        "floatArrayOf(0.012f, 0.012f, 0.016f)",
    )
    for value in required:
        if value not in after_shell:
            raise RuntimeError(f"missing V2 shell invariant: {value}")

    for value in (
        f"const val INNER_BRIDGE_HANDOFF_SETTLE_MS = {HANDOFF_MS}L",
        "HANDOFF_ARMED",
        "HANDOFF_RELEASED",
    ):
        if value not in after_coord:
            raise RuntimeError(f"missing V2 coordinator invariant: {value}")

    if not check:
        shell.write_text(after_shell, encoding="utf-8")
        coordinator.write_text(after_coord, encoding="utf-8")


def self_test() -> None:
    shell = '''// INNER_PHYSICAL_BRIDGE_V1\n    private val innerPhysicalBridgeLayerStack = 0x44554F\n                        floatArrayOf(0.05f, 0.72f, 0.95f),\n'''
    shell_out = transform_shell(shell)
    assert "innerPhysicalBridgeLayerStack = 0" in shell_out
    assert "0.012f, 0.012f, 0.016f" in shell_out
    assert "0.05f, 0.72f, 0.95f" not in shell_out
    print("inner physical bridge v2 shell model: PASS")


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
    if args.check:
        print("inner physical bridge v2: source shape verified")
    else:
        print("inner physical bridge v2: applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
