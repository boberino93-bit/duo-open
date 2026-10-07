#!/usr/bin/env python3
"""Apply Gen10.6 One UI 9 / Android 17 compatibility after Gen10.5.

One UI 9 is based on Android 17 (API 37). Gen10.5 still builds with compileSdk
35 and AGP 8.9.1. This compatibility bridge moves the compile toolchain to a
supported API-37 stack while deliberately retaining targetSdk 35 for the first
One UI 9 field build. That avoids coupling the OS migration to Android-17
*target-only* behavior changes and tighter non-SDK gating in the same candidate.

Runtime fold behavior is intentionally unchanged. The patch also adds explicit
platform telemetry so field bundles identify API/release/build/target state and
whether the device is running the Android-17 compatibility path.
"""

from __future__ import annotations

import argparse
from pathlib import Path

TARGET_VERSION_CODE = 53
TARGET_VERSION_NAME = "5.4.6-gen10-oneui9-android17-compat-zfold7"
MARKER = "GEN10_6_ONEUI9_ANDROID17_COMPAT"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def write_new(path: Path, content: str) -> None:
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing != content:
            raise RuntimeError(f"new-file collision: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def apply(repo: Path) -> None:
    root_build = repo / "build.gradle.kts"
    text = root_build.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'id("com.android.application") version "8.9.1" apply false',
        'id("com.android.application") version "9.4.0" apply false',
        "AGP 9.4",
    )
    root_build.write_text(text, encoding="utf-8")

    wrapper = repo / "gradle/wrapper/gradle-wrapper.properties"
    text = wrapper.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "gradle-8.14.3-bin.zip",
        "gradle-9.6.0-bin.zip",
        "Gradle 9.6",
    )
    wrapper.write_text(text, encoding="utf-8")

    props = repo / "gradle.properties"
    text = props.read_text(encoding="utf-8")
    if "android.builtInKotlin=false" not in text:
        if not text.endswith("\n"):
            text += "\n"
        text += (
            "\n# GEN10_6_ONEUI9_ANDROID17_COMPAT\n"
            "# AGP 9.4 supports API 37. Keep the existing kotlin-android/new DSL\n"
            "# model for this bridge build so toolchain migration is isolated from\n"
            "# the physical Fold7 runtime changes under test.\n"
            "android.builtInKotlin=false\n"
            "android.newDsl=false\n"
        )
    props.write_text(text, encoding="utf-8")

    app_build = repo / "app/build.gradle.kts"
    text = app_build.read_text(encoding="utf-8")
    text = replace_once(text, "compileSdk = 35", "compileSdk = 37", "compileSdk 37")
    text = replace_once(text, "versionCode = 52", f"versionCode = {TARGET_VERSION_CODE}", "versionCode")
    text = replace_once(
        text,
        'versionName = "5.4.5-gen10-mirror-warmup-retention-zfold7"',
        f'versionName = "{TARGET_VERSION_NAME}"',
        "versionName",
    )
    text = replace_once(
        text,
        "        targetSdk = 35\n",
        """        // GEN10_6_ONEUI9_ANDROID17_COMPAT\n        // Compile against Android 17 / API 37, but retain target 35 for the\n        // first One UI 9 field candidate. This keeps Android-17 target-only\n        // behavior/non-SDK policy changes out of the physical OS migration test.\n        targetSdk = 35\n""",
        "target SDK compatibility annotation",
    )
    app_build.write_text(text, encoding="utf-8")

    compat = repo / "app/src/full/java/com/duoopen/overlay/Android17Compatibility.kt"
    write_new(
        compat,
        '''package com.duoopen.overlay

import android.content.Context
import android.os.Build

/** GEN10_6_ONEUI9_ANDROID17_COMPAT
 * Runtime facts for the One UI 9 / Android 17 bridge build.
 *
 * This intentionally does not infer that every API-37 device is Samsung or
 * One UI 9. It records the actual platform facts so field logs can distinguish
 * OS/toolchain compatibility failures from fold-state regressions.
 */
internal object Android17Compatibility {
    const val ANDROID_17_API = 37

    val runningAndroid17OrNewer: Boolean
        get() = Build.VERSION.SDK_INT >= ANDROID_17_API

    fun describe(context: Context): String {
        val target = context.applicationInfo.targetSdkVersion
        return "sdk=${Build.VERSION.SDK_INT} " +
            "release=${Build.VERSION.RELEASE} " +
            "codename=${Build.VERSION.CODENAME} " +
            "incremental=${Build.VERSION.INCREMENTAL} " +
            "manufacturer=${Build.MANUFACTURER} model=${Build.MODEL} " +
            "targetSdk=$target compileSdk=37 " +
            "android17Plus=$runningAndroid17OrNewer"
    }
}
''',
    )

    service = repo / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt"
    text = service.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''        DuoDiagnostics.event(
            "service-lifecycle",
            "accessibility-connected",
        )
''',
        '''        DuoDiagnostics.event(
            "service-lifecycle",
            "accessibility-connected",
        )

        // GEN10_6_ONEUI9_ANDROID17_COMPAT
        DuoDiagnostics.event(
            "platform-compat",
            Android17Compatibility.describe(this),
        )
''',
        "platform compatibility telemetry",
    )
    service.write_text(text, encoding="utf-8")


def verify(repo: Path) -> None:
    root_build = (repo / "build.gradle.kts").read_text(encoding="utf-8")
    wrapper = (repo / "gradle/wrapper/gradle-wrapper.properties").read_text(encoding="utf-8")
    props = (repo / "gradle.properties").read_text(encoding="utf-8")
    app_build = (repo / "app/build.gradle.kts").read_text(encoding="utf-8")
    compat = (repo / "app/src/full/java/com/duoopen/overlay/Android17Compatibility.kt").read_text(encoding="utf-8")
    service = (repo / "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt").read_text(encoding="utf-8")
    host = (repo / "app/src/full/java/com/duoopen/overlay/DisplayMirrorHost.kt").read_text(encoding="utf-8")
    panel = (repo / "app/src/full/java/com/duoopen/overlay/PanelEngine.kt").read_text(encoding="utf-8")
    coordinator = (repo / "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt").read_text(encoding="utf-8")

    required = [
        'version "9.4.0"',
        "gradle-9.6.0-bin.zip",
        "android.builtInKotlin=false",
        "android.newDsl=false",
        "compileSdk = 37",
        "targetSdk = 35",
        f"versionCode = {TARGET_VERSION_CODE}",
        f'versionName = "{TARGET_VERSION_NAME}"',
        MARKER,
        "ANDROID_17_API = 37",
        '"platform-compat"',
        "Android17Compatibility.describe(this)",
        "GEN10_5_MIRROR_WARMUP_RETENTION",
        "current.isAttachInProgress",
        "coverPresentationGate.offer(",
        '"capture-protected-or-black"',
        '"Protected/uncapturable content: native display passthrough."',
    ]
    joined = "\n".join([
        root_build,
        wrapper,
        props,
        app_build,
        compat,
        service,
        host,
        panel,
        coordinator,
    ])
    missing = [needle for needle in required if needle not in joined]
    if missing:
        raise RuntimeError(f"Gen10.6 verification failed; missing: {missing}")

    # This bridge must compile against API 37 without enabling target-37
    # behavior changes yet. Promotion to targetSdk 37 requires a separate
    # field-validated candidate.
    if "targetSdk = 37" in app_build:
        raise RuntimeError("Gen10.6 verification failed: targetSdk 37 enabled prematurely")

    # Preserve Gen10.2 secure-content proof ordering and fail-open behavior.
    proof_index = host.index("val captureProof =")
    start_index = host.index("ShizukuBridge.startDisplayMirrorV2(")
    if proof_index >= start_index:
        raise RuntimeError("Gen10.6 verification failed: secure proof no longer gates live mirror")

    forbidden = [
        "FLAG_SECURE bypass",
        "clear FLAG_SECURE",
        "disable FLAG_SECURE",
    ]
    for needle in forbidden:
        if needle.lower() in joined.lower():
            raise RuntimeError(f"Gen10.6 verification failed: forbidden secure behavior: {needle}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    apply(repo)
    verify(repo)
    print("Gen10.6 One UI 9 / Android 17 compatibility bridge applied and verified")


if __name__ == "__main__":
    main()
