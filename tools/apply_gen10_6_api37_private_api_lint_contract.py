#!/usr/bin/env python3
"""Scope Android 17 private-API lint suppressions to intentional shell primitives.

Gen10.6's first real API-37 build compiled, unit-tested, dexed and assembled, but
AGP 9.4 lint promoted the existing intentional SurfaceControl reflection sites
to fatal BlockedPrivateApi/SoonBlockedPrivateApi findings. Duo Open already
treats these as privileged Shizuku/HiddenApiBypass implementation details;
removing them would remove the physical display control path rather than make it
Android-17 compatible.

This patch does NOT disable lint globally and does NOT suppress these checks for
the file/class. It documents and suppresses only the methods that own the three
reflected SurfaceControl primitives so every other API-37 lint finding remains
fatal in CI.
"""

from __future__ import annotations

import argparse
from pathlib import Path

MARKER = "GEN10_6_API37_PRIVATE_API_LINT_CONTRACT"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def apply(repo: Path) -> None:
    path = repo / "app/src/full/java/com/duoopen/shell/DuoShellService.kt"
    text = path.read_text(encoding="utf-8")

    if MARKER in text:
        return

    text = replace_once(
        text,
        """    private fun physicalDisplayToken(\n""",
        """    /* GEN10_6_API37_PRIVATE_API_LINT_CONTRACT
     * Intentional Shizuku-side hidden SurfaceControl bridge. Runtime access is
     * explicitly mediated by HiddenApiBypass; keep API-37 lint scoped here.
     */
    @android.annotation.SuppressLint("BlockedPrivateApi")
    private fun physicalDisplayToken(\n""",
        "physicalDisplayToken suppression",
    )

    text = replace_once(
        text,
        """    private fun setPhysicalPowerMode(\n""",
        """    @android.annotation.SuppressLint("BlockedPrivateApi", "SoonBlockedPrivateApi")
    private fun setPhysicalPowerMode(\n""",
        "setPhysicalPowerMode suppression",
    )

    text = replace_once(
        text,
        """    private fun setPhysicalBrightness(\n""",
        """    @android.annotation.SuppressLint("BlockedPrivateApi")
    private fun setPhysicalBrightness(\n""",
        "setPhysicalBrightness suppression",
    )

    path.write_text(text, encoding="utf-8")


def verify(repo: Path) -> None:
    shell = (repo / "app/src/full/java/com/duoopen/shell/DuoShellService.kt").read_text(encoding="utf-8")
    build = (repo / "app/build.gradle.kts").read_text(encoding="utf-8")

    required = [
        MARKER,
        '@android.annotation.SuppressLint("BlockedPrivateApi")\n    private fun physicalDisplayToken(',
        '@android.annotation.SuppressLint("BlockedPrivateApi", "SoonBlockedPrivateApi")\n    private fun setPhysicalPowerMode(',
        '@android.annotation.SuppressLint("BlockedPrivateApi")\n    private fun setPhysicalBrightness(',
        '"getPhysicalDisplayToken"',
        '"setDisplayPowerMode"',
        '"setDisplayBrightness"',
    ]
    missing = [needle for needle in required if needle not in shell]
    if missing:
        raise RuntimeError(f"API-37 private-api lint contract verification failed: {missing}")

    # Three method-scoped BlockedPrivateApi entries total: token, power, brightness.
    if shell.count('"BlockedPrivateApi"') != 3:
        raise RuntimeError("BlockedPrivateApi suppression must remain exactly method-scoped to three primitives")
    if shell.count('"SoonBlockedPrivateApi"') != 1:
        raise RuntimeError("SoonBlockedPrivateApi suppression must remain singular on physical power mode")

    # Never trade a method-scoped contract for global lint suppression.
    forbidden = [
        'disable.add("BlockedPrivateApi")',
        'disable += "BlockedPrivateApi"',
        'disable.add("SoonBlockedPrivateApi")',
        'disable += "SoonBlockedPrivateApi"',
        'abortOnError = false',
        'checkReleaseBuilds = false',
    ]
    joined = shell + "\n" + build
    for needle in forbidden:
        if needle in joined:
            raise RuntimeError(f"forbidden lint weakening found: {needle}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    apply(repo)
    verify(repo)
    print("Gen10.6 API-37 private-api lint contract applied and verified")


if __name__ == "__main__":
    main()
