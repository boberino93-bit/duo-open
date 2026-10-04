#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

MARKER = "STABILIZATION_S1H_VISUAL_METADATA_V1"
SHELL = Path("app/src/full/java/com/duoopen/shell/DuoShellService.kt")
BRIDGE = Path("app/src/full/java/com/duoopen/shell/ShizukuBridge.kt")
PROTOCOL = Path("app/src/full/java/com/duoopen/shell/ShellProtocol.kt")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_protocol(text: str) -> str:
    if "const val VISUAL_FORENSICS = 19" in text:
        return text
    return replace_once(
        text,
        '''    const val COVER_PANEL_GEN4 = 18

    const val CB_ANGLE = 1
''',
        '''    const val COVER_PANEL_GEN4 = 18

    // S1H read-only wallpaper/widget/compositor/policy evidence.
    const val VISUAL_FORENSICS = 19

    const val CB_ANGLE = 1
''',
        "S1H protocol code",
    )


def transform_bridge(text: str) -> str:
    if "fun visualForensicsProbe(): Bundle?" in text:
        return text
    return replace_once(
        text,
        '''    fun displayProbe(): Bundle? =
        call(
            ShellProtocol.DISPLAY_PROBE
        )

''',
        '''    fun displayProbe(): Bundle? =
        call(
            ShellProtocol.DISPLAY_PROBE
        )

    /** Blocking, read-only rendering and capture-policy evidence for S1H. */
    fun visualForensicsProbe(): Bundle? =
        call(
            ShellProtocol.VISUAL_FORENSICS
        )

''',
        "S1H bridge probe",
    )


def transform_shell(text: str) -> str:
    if MARKER in text:
        return text
    if "STABILIZATION_S1G_FORENSIC_SUPERSET_V1" not in text:
        raise RuntimeError("S1G forensic superset must be applied before S1H metadata")

    tx_case = r'''            ShellProtocol.VISUAL_FORENSICS -> {
                val identity = clearCallingIdentity()
                val result =
                    try {
                        visualForensicsProbe()
                    } catch (t: Throwable) {
                        failureBundle("visual-forensics", t)
                    } finally {
                        restoreCallingIdentity(identity)
                    }

                out.writeNoException()
                out.writeBundle(result)
            }

'''
    text = replace_once(
        text,
        '''            ShellProtocol.START_ANGLES -> {
''',
        tx_case + '''            ShellProtocol.START_ANGLES -> {
''',
        "S1H visual metadata transaction",
    )

    helper = r'''    // STABILIZATION_S1H_VISUAL_METADATA_V1
    // Read-only evidence for layers beneath Duo Open. Output is capped by the
    // existing runProbe limit and contains state/identity, not pixel content.
    private fun visualForensicsProbe(): Bundle =
        Bundle().apply {
            putString(
                "wallpaper",
                runProbe(
                    "dumpsys wallpaper 2>/dev/null | " +
                        "grep -E -i 'Wallpaper|mWallpaperComponent|mNextWallpaperComponent|" +
                        "mConnection|mEngine|Engine|mVisible|visible=|mDisplayId=|" +
                        "displayId=|mSurface|surface|mWidth=|mHeight=|mLastWallpaper|" +
                        "mWallpaperTarget|which=' | head -n 320"
                ),
            )

            putString(
                "appWidgets",
                runProbe(
                    "dumpsys appwidget 2>/dev/null | " +
                        "grep -E -i 'AppWidget|hostId=|host=|provider=|packageName=|" +
                        "userId=|uid=|appWidgetId=|options=|minWidth|minHeight|" +
                        "maxWidth|maxHeight|launcher|widget' | head -n 360"
                ),
            )

            putString(
                "windowRendering",
                runProbe(
                    "dumpsys window windows 2>/dev/null | " +
                        "grep -E -i 'mCurrentFocus|mFocusedApp|Window\\{|mDisplayId=|" +
                        "displayId=|isOnScreen=|isVisible=|hasSurface=|mAttrs=|" +
                        "FLAG_SECURE|secure|wallpaper|launcher|systemui|appwidget|" +
                        "widget|SurfaceView|Taskbar|NavigationBar|StatusBar|frame=' | head -n 420"
                ),
            )

            putString(
                "surfaceLayers",
                runProbe(
                    "sh -c 'echo ===LIST===; dumpsys SurfaceFlinger --list 2>/dev/null | " +
                        "grep -E -i \"wallpaper|launcher|systemui|widget|surfaceview|duo|" +
                        "navigation|statusbar|taskbar|snapshot|splash|dim\" | head -n 260; " +
                        "echo ===SECURITY===; dumpsys SurfaceFlinger 2>/dev/null | " +
                        "grep -E -i \"secure|protected|drm|trusted.?overlay|wallpaper|" +
                        "launcher|systemui|widget|snapshot|splash|layerStack|composition\" | head -n 260'"
                ),
            )

            putString(
                "capturePolicy",
                runProbe(
                    "sh -c 'echo ===DEVICE_POLICY===; dumpsys device_policy 2>/dev/null | " +
                        "grep -E -i \"screen.?capture|disable.?screen|POLICY_DISABLE_SCREEN_CAPTURE|" +
                        "no_screen_capture|content.?capture|managed.?profile|profile.?owner\" | head -n 220; " +
                        "echo ===USERS===; dumpsys user 2>/dev/null | " +
                        "grep -E -i \"UserInfo|managed|profile|quiet|restriction|no_screen_capture|" +
                        "no_content_capture\" | head -n 220; " +
                        "echo ===FOCUSED_SECURE_WINDOW===; dumpsys window windows 2>/dev/null | " +
                        "grep -E -i \"mCurrentFocus|mFocusedApp|FLAG_SECURE|secure|mOwnerUid|" +
                        "mShowForAllUsers|mDisplayId=\" | head -n 220'"
                ),
            )

            putString(
                "topActivity",
                runProbe(
                    "dumpsys activity activities 2>/dev/null | " +
                        "grep -E -i 'mResumedActivity|topResumedActivity|realActivity=|" +
                        "userId=|mUserId=|Display #[0-9]+|RootTask|launcher|systemui' | head -n 260"
                ),
            )
        }

'''
    return replace_once(
        text,
        '''    private fun runProbe(
        command: String,
    ): String {
''',
        helper + '''    private fun runProbe(
        command: String,
    ): String {
''',
        "S1H visual metadata helper",
    )


def apply(repo: Path, check_only: bool) -> None:
    outputs = {
        PROTOCOL: transform_protocol((repo / PROTOCOL).read_text(encoding="utf-8")),
        BRIDGE: transform_bridge((repo / BRIDGE).read_text(encoding="utf-8")),
        SHELL: transform_shell((repo / SHELL).read_text(encoding="utf-8")),
    }

    checks = (
        (outputs[PROTOCOL], 'const val VISUAL_FORENSICS = 19'),
        (outputs[BRIDGE], 'fun visualForensicsProbe(): Bundle?'),
        (outputs[SHELL], MARKER),
        (outputs[SHELL], '"wallpaper"'),
        (outputs[SHELL], '"appWidgets"'),
        (outputs[SHELL], '"capturePolicy"'),
        (outputs[SHELL], 'dumpsys wallpaper 2>/dev/null'),
        (outputs[SHELL], 'dumpsys appwidget 2>/dev/null'),
        (outputs[SHELL], 'dumpsys device_policy 2>/dev/null'),
    )
    for text, needle in checks:
        if needle not in text:
            raise RuntimeError(f"S1H metadata check missing: {needle}")

    if not check_only:
        for path, content in outputs.items():
            (repo / path).write_text(content, encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=".")
    p.add_argument("--check", action="store_true")
    a = p.parse_args()
    apply(Path(a.repo).resolve(), a.check)
    print("S1H visual metadata instrumentation: " + ("verified" if a.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
