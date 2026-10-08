#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

MARKER = "GEN12_1_UI_SMOKE_SCROLL"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    path = repo / "app/src/androidTest/java/com/duoopen/ui/ProductUiSmokeTest.kt"
    text = path.read_text(encoding="utf-8")

    if MARKER not in text:
        text = replace_once(
            text,
            "import androidx.compose.ui.test.performClick\n",
            "import androidx.compose.ui.test.performClick\nimport androidx.compose.ui.test.performScrollTo\n",
            "scroll import",
        )
        text = replace_once(
            text,
            '        composeRule.onNodeWithText("Test continuity").performClick()\n',
            '        // GEN12_1_UI_SMOKE_SCROLL: the Fold7 compatibility warning adds one\n'
            '        // readiness row on compact layouts. Prove the CTA remains reachable\n'
            '        // through the real scroll container before invoking its action.\n'
            '        composeRule.onNodeWithText("Test continuity")\n'
            '            .performScrollTo()\n'
            '            .assertIsDisplayed()\n'
            '            .performClick()\n',
            "ready CTA scroll-aware interaction",
        )
        path.write_text(text, encoding="utf-8")

    final = path.read_text(encoding="utf-8")
    required = [
        MARKER,
        "performScrollTo()",
        ".assertIsDisplayed()",
        ".performClick()",
        "assertTrue(clicked)",
    ]
    missing = [item for item in required if item not in final]
    if missing:
        raise RuntimeError(f"Gen12.1 UI smoke scroll verifier failed: {missing}")

    print("Gen12.1 compact UI smoke scroll hardening applied and verified")


if __name__ == "__main__":
    main()
