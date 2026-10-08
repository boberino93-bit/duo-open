#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

TARGET_VERSION_CODE = 55
TARGET_VERSION_NAME = "5.5.0-gen11-product-ui-zfold7"
TEMPLATE_ROOT = Path("tools/gen11_ui")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_build_gradle(text: str) -> str:
    if TARGET_VERSION_NAME not in text:
        text = replace_once(text, "versionCode = 54", f"versionCode = {TARGET_VERSION_CODE}", "versionCode")
        text = replace_once(
            text,
            'versionName = "5.4.7-gen10-oneui9-display-angle-zfold7"',
            f'versionName = "{TARGET_VERSION_NAME}"',
            "versionName",
        )

    if "testInstrumentationRunner" not in text:
        text = replace_once(
            text,
            f'versionName = "{TARGET_VERSION_NAME}"\n',
            f'versionName = "{TARGET_VERSION_NAME}"\n        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"\n',
            "instrumentation runner",
        )

    if 'androidx.compose.ui:ui-test-junit4' not in text:
        anchor = '    testImplementation("junit:junit:4.13.2")\n'
        extra = (
            anchor
            + '    androidTestImplementation(platform("androidx.compose:compose-bom:2025.06.01"))\n'
            + '    androidTestImplementation("androidx.compose.ui:ui-test-junit4")\n'
            + '    androidTestImplementation("androidx.test.ext:junit:1.2.1")\n'
            + '    androidTestImplementation("androidx.test:runner:1.6.2")\n'
            + '    debugImplementation("androidx.compose.ui:ui-test-manifest")\n'
        )
        text = replace_once(text, anchor, extra, "android test dependencies")

    return text


def transform_control_sheet(text: str) -> str:
    # PageColumn is invoked from the ModalBottomSheet Column; make that scope
    # explicit so its weight modifier is legal and the tab body consumes the
    # remaining sheet height.
    if "private fun ColumnScope.PageColumn" not in text:
        text = replace_once(
            text,
            "private fun PageColumn(content: @Composable ColumnScope.() -> Unit)",
            "private fun ColumnScope.PageColumn(content: @Composable ColumnScope.() -> Unit)",
            "PageColumn scope",
        )
    return text


def install_templates(repo: Path) -> None:
    root = repo / TEMPLATE_ROOT
    mappings = {
        "MainActivity.kt.template": "app/src/main/java/com/duoopen/MainActivity.kt",
        "HomePreview.kt.template": "app/src/main/java/com/duoopen/ui/HomePreview.kt",
        "ControlSheet.kt.template": "app/src/main/java/com/duoopen/ui/ControlSheet.kt",
        "DuoTheme.kt.template": "app/src/main/java/com/duoopen/ui/DuoTheme.kt",
        "ProductUiModel.kt.template": "app/src/main/java/com/duoopen/ui/ProductUiModel.kt",
        "ProductUiModelTest.kt.template": "app/src/test/java/com/duoopen/ui/ProductUiModelTest.kt",
        "ProductUiSmokeTest.kt.template": "app/src/androidTest/java/com/duoopen/ui/ProductUiSmokeTest.kt",
    }

    for template, target in mappings.items():
        source = root / template
        if not source.is_file():
            raise RuntimeError(f"missing Gen11 template: {source}")
        text = read(source)
        if template == "ControlSheet.kt.template":
            text = transform_control_sheet(text)
        write(repo / target, text)


def verify(repo: Path) -> None:
    build = read(repo / "app/build.gradle.kts")
    home = read(repo / "app/src/main/java/com/duoopen/ui/HomePreview.kt")
    controls = read(repo / "app/src/main/java/com/duoopen/ui/ControlSheet.kt")
    theme = read(repo / "app/src/main/java/com/duoopen/ui/DuoTheme.kt")
    main = read(repo / "app/src/main/java/com/duoopen/MainActivity.kt")
    model_test = read(repo / "app/src/test/java/com/duoopen/ui/ProductUiModelTest.kt")
    smoke_test = read(repo / "app/src/androidTest/java/com/duoopen/ui/ProductUiSmokeTest.kt")
    panel = read(repo / "app/src/full/java/com/duoopen/overlay/PanelEngine.kt")
    coordinator = read(repo / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt")

    required = {
        "version": TARGET_VERSION_NAME in build and f"versionCode = {TARGET_VERSION_CODE}" in build,
        "android-ui-test": "androidx.compose.ui:ui-test-junit4" in build,
        "theme": "DuoOpenTheme" in main and "DuoOpenColors" in theme,
        "dashboard": "GEN11_PRODUCT_UI" in home and "Continuity Console" in home,
        "settings-tabs": "GEN11_PRODUCT_UI_SETTINGS" in controls and 'listOf("Setup", "Look", "Diagnostics")' in controls,
        "settings-scope": "private fun ColumnScope.PageColumn" in controls,
        "model-tests": "layoutThresholdKeepsCoverCompactAndInnerExpanded" in model_test,
        "smoke-tests": "readyDashboardRendersAndPrimaryActionFires" in smoke_test,
        "secure-fail-open": "capture-protected-or-black" in panel,
        "gen10-7-angle-hold": "GEN10_7_TOPOLOGY_ANGLE_HOLD" in coordinator,
        "compile37-target35": "compileSdk = 37" in build and "targetSdk = 35" in build,
    }

    missing = [name for name, ok in required.items() if not ok]
    if missing:
        raise RuntimeError(f"Gen11 product UI verification failed: {missing}")

    if "targetSdk = 37" in build:
        raise RuntimeError("Gen11 must preserve the Gen10.7 targetSdk 35 compatibility bridge")

    print("Gen11 product UI applied and verified")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()

    build = repo / "app/build.gradle.kts"
    install_templates(repo)
    write(build, transform_build_gradle(read(build)))
    verify(repo)


if __name__ == "__main__":
    main()
