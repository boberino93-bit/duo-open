#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

SHELL = Path("app/src/full/java/com/duoopen/shell/DuoShellService.kt")
COORDINATOR = Path("app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt")
MARKER = "INNER_PHYSICAL_BRIDGE_V4_NON_OCCLUDING"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_shell(text: str) -> str:
    if MARKER in text:
        return text
    if "INNER_PHYSICAL_BRIDGE_V2" not in text:
        raise RuntimeError("V2 physical bridge must be applied first")

    text = replace_once(
        text,
        "                tx.setLayer(layer, Int.MAX_VALUE - 64)\n",
        "                // INNER_PHYSICAL_BRIDGE_V4_NON_OCCLUDING\n"
        "                // Preserve the native-stack routing/projection side effect that wakes INNER,\n"
        "                // but never cover Samsung/native composition while waiting for handoff.\n"
        "                tx.setLayer(layer, Int.MIN_VALUE + 64)\n"
        "                tx.setAlpha(layer, 0.0f)\n",
        "non-occluding bridge layer",
    )

    text = replace_once(
        text,
        "                        // INNER_PHYSICAL_BRIDGE_V2: neutral near-black privacy cover.\n"
        "                        // V1 cyan was diagnostic proof only.\n"
        "                        floatArrayOf(0.012f, 0.012f, 0.016f),\n",
        "                        // INNER_PHYSICAL_BRIDGE_V4_NON_OCCLUDING: color is inert because\n"
        "                        // alpha is forced to zero; this layer is transport/wake plumbing only.\n"
        "                        floatArrayOf(0.012f, 0.012f, 0.016f),\n",
        "bridge color semantics",
    )
    return text


def transform_coordinator(text: str) -> str:
    if "INNER_PHYSICAL_BRIDGE_V4_STATUS" in text:
        return text
    if "Fold7DisplayStatus.Bridge.PRESENTING" not in text:
        raise RuntimeError("display status V3 must be applied before V4 status correction")

    text = replace_once(
        text,
        "                                bridgeActive -> Fold7DisplayStatus.Bridge.PRESENTING\n",
        "                                // INNER_PHYSICAL_BRIDGE_V4_STATUS: bridge existence is not optical proof.\n"
        "                                bridgeActive -> Fold7DisplayStatus.Bridge.HANDOFF_ARMED\n",
        "bridge status semantics",
    )

    text = text.replace(
        "                     * V2 already shares native stack 0. Keep the neutral privacy layer\n"
        "                     * above Samsung's layers for a short bounded settle window, then\n"
        "                     * remove only that layer. Closing/reversal/privilege-loss still force\n",
        "                     * V4 keeps native stack 0 routing but makes the bridge fully transparent\n"
        "                     * and bottom-Z, so native pixels remain visible throughout the bounded\n"
        "                     * settle window. Closing/reversal/privilege-loss still force\n",
        1,
    )
    return text


def validate(shell: str, coordinator: str) -> None:
    required_shell = (
        MARKER,
        "tx.setLayer(layer, Int.MIN_VALUE + 64)",
        "tx.setAlpha(layer, 0.0f)",
        "private val innerPhysicalBridgeLayerStack = 0",
    )
    for value in required_shell:
        if value not in shell:
            raise RuntimeError(f"missing V4 shell invariant: {value}")

    forbidden_shell = (
        "tx.setLayer(layer, Int.MAX_VALUE - 64)",
        "floatArrayOf(0.05f, 0.72f, 0.95f)",
    )
    for value in forbidden_shell:
        if value in shell:
            raise RuntimeError(f"occluding/diagnostic bridge invariant survived V4: {value}")

    if "INNER_PHYSICAL_BRIDGE_V4_STATUS" not in coordinator:
        raise RuntimeError("missing V4 coordinator status marker")
    if "bridgeActive -> Fold7DisplayStatus.Bridge.PRESENTING" in coordinator:
        raise RuntimeError("bridge existence is still mislabeled as PRESENTING")
    if "bridgeActive -> Fold7DisplayStatus.Bridge.HANDOFF_ARMED" not in coordinator:
        raise RuntimeError("missing non-optical bridge status")


def apply(repo: Path, check: bool) -> None:
    shell_path = repo / SHELL
    coordinator_path = repo / COORDINATOR
    if not shell_path.exists() or not coordinator_path.exists():
        raise RuntimeError("required Android sources missing")

    shell_before = shell_path.read_text(encoding="utf-8")
    coordinator_before = coordinator_path.read_text(encoding="utf-8")
    shell_after = transform_shell(shell_before)
    coordinator_after = transform_coordinator(coordinator_before)
    validate(shell_after, coordinator_after)

    if not check:
        shell_path.write_text(shell_after, encoding="utf-8")
        coordinator_path.write_text(coordinator_after, encoding="utf-8")


def self_test() -> None:
    shell = '''// INNER_PHYSICAL_BRIDGE_V2\n    private val innerPhysicalBridgeLayerStack = 0\n                        // INNER_PHYSICAL_BRIDGE_V2: neutral near-black privacy cover.\n                        // V1 cyan was diagnostic proof only.\n                        floatArrayOf(0.012f, 0.012f, 0.016f),\n                tx.setLayer(layer, Int.MAX_VALUE - 64)\n'''
    coordinator = '''                                bridgeActive -> Fold7DisplayStatus.Bridge.PRESENTING\n                     * V2 already shares native stack 0. Keep the neutral privacy layer\n                     * above Samsung's layers for a short bounded settle window, then\n                     * remove only that layer. Closing/reversal/privilege-loss still force\n'''
    shell_out = transform_shell(shell)
    coordinator_out = transform_coordinator(coordinator)
    validate(shell_out, coordinator_out)
    print("inner physical bridge v4 non-occluding model: PASS")


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
        print("inner physical bridge v4: source shape verified")
    else:
        print("inner physical bridge v4: applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
