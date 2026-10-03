#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

MARKER = "RUNTIME_OPTIMIZATION_CYCLE_C_V1"
WALLPAPER = "app/src/main/java/com/duoopen/wallpaper/DuoWallpaperService.kt"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_wallpaper(text: str) -> str:
    if MARKER in text:
        return text

    old_collect = '''            scope.launch { OverlayState.running.collect { draw() } }'''
    new_collect = f'''            scope.launch {{
                OverlayState.running.collect {{ running ->
                    // {MARKER}:OVERLAY_OWNERSHIP
                    // While the full-screen overlay owns visible fold rendering,
                    // keep wallpaper hinge state current without running a second
                    // Choreographer animation underneath it.
                    if (running) {{
                        follower.snap(tiltFor(hinge.lastAngle))
                    }}
                    draw()
                }}
            }}'''
    text = replace_once(text, old_collect, new_collect, "overlay running collector")

    old_hinge = '''        private fun onHingeAngle(angle: Float) {
            val tilt = tiltFor(angle)
            if (isInner() && isVisible && surfaceReady) follower.setTarget(tilt) else follower.snap(tilt)
        }'''
    new_hinge = f'''        private fun onHingeAngle(angle: Float) {{
            val tilt = tiltFor(angle)
            val wallpaperOwnsVisibleFold =
                isInner() &&
                    isVisible &&
                    surfaceReady &&
                    !OverlayState.running.value

            if (wallpaperOwnsVisibleFold) {{
                follower.setTarget(tilt)
            }} else {{
                // {MARKER}:HINGE_SNAP_UNDER_OVERLAY
                // Preserve the exact latest hinge-derived tilt while avoiding
                // hidden wallpaper frame callbacks when the overlay is visible.
                follower.snap(tilt)
            }}
        }}'''
    text = replace_once(text, old_hinge, new_hinge, "wallpaper hinge ownership")
    return text


def apply(repo: Path, check_only: bool) -> None:
    path = repo / WALLPAPER
    if not path.exists():
        raise RuntimeError(f"missing source file: {WALLPAPER}")
    before = path.read_text(encoding="utf-8")
    after = transform_wallpaper(before)
    if MARKER not in after:
        raise RuntimeError("Cycle C marker missing after transform")
    if not check_only and after != before:
        path.write_text(after, encoding="utf-8")


def self_test() -> None:
    fixture = '''            scope.launch { OverlayState.running.collect { draw() } }
        private fun onHingeAngle(angle: Float) {
            val tilt = tiltFor(angle)
            if (isInner() && isVisible && surfaceReady) follower.setTarget(tilt) else follower.snap(tilt)
        }'''
    out = transform_wallpaper(fixture)
    assert "!OverlayState.running.value" in out
    assert "follower.snap(tiltFor(hinge.lastAngle))" in out
    assert MARKER in out
    print("runtime optimization cycle C self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    apply(Path(args.repo).resolve(), check_only=args.check)
    print(
        "runtime optimization cycle C: " +
        ("source shape verified" if args.check else "applied")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
