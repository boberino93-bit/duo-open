#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

MARKER = "GEN12_1_WALLPAPER_METADATA_RECEIPT"


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
    path = repo / "app/src/main/java/com/duoopen/settings/DuoSettings.kt"
    text = path.read_text(encoding="utf-8")

    if MARKER not in text:
        old = '''    @Synchronized
    fun bumpImageVersionAfterPayloadCommit(): Long {
        val next = _config.value.copy(imageVersion = _config.value.imageVersion + 1L)
        _config.value = next
        prefs.edit {
            putFloat("intensity", next.intensity)
            putFloat("blurSpread", next.blurSpread)
            putFloat("darkening", next.darkening)
            putFloat("eyeDistanceMm", next.eyeDistanceMm)
            putBoolean("foldSplitsLong", next.foldSplitsLong)
            putInt("movingSide", next.movingSide)
            putBoolean("coverFrostFromRight", next.coverFrostFromRight)
            putBoolean("liveBlur", next.liveBlur)
            putBoolean("instantStart", next.instantStart)
            putBoolean("shizukuCapture", next.shizukuCapture)
            putBoolean("shizukuAngle", next.shizukuAngle)
            putLong("imageVersion", next.imageVersion)
        }
        return next.imageVersion
    }
'''
        new = '''    @Synchronized
    fun bumpImageVersionAfterPayloadCommit(): Long {
        // GEN12_1_WALLPAPER_METADATA_RECEIPT
        // Payload durability has already been established by AtomicFile. Commit
        // metadata synchronously and check the receipt before publishing the new
        // StateFlow value, so process death cannot expose an acknowledged version
        // that never reached SharedPreferences storage.
        val next = _config.value.copy(imageVersion = _config.value.imageVersion + 1L)
        val committed =
            prefs.edit()
                .putFloat("intensity", next.intensity)
                .putFloat("blurSpread", next.blurSpread)
                .putFloat("darkening", next.darkening)
                .putFloat("eyeDistanceMm", next.eyeDistanceMm)
                .putBoolean("foldSplitsLong", next.foldSplitsLong)
                .putInt("movingSide", next.movingSide)
                .putBoolean("coverFrostFromRight", next.coverFrostFromRight)
                .putBoolean("liveBlur", next.liveBlur)
                .putBoolean("instantStart", next.instantStart)
                .putBoolean("shizukuCapture", next.shizukuCapture)
                .putBoolean("shizukuAngle", next.shizukuAngle)
                .putLong("imageVersion", next.imageVersion)
                .commit()

        check(committed) {
            "Wallpaper payload committed but imageVersion metadata commit failed"
        }

        _config.value = next
        return next.imageVersion
    }
'''
        text = replace_once(text, old, new, "wallpaper metadata receipt")
        path.write_text(text, encoding="utf-8")

    final = path.read_text(encoding="utf-8")
    if MARKER not in final or '.putLong("imageVersion", next.imageVersion)\n                .commit()' not in final:
        raise RuntimeError("Gen12.1 metadata receipt verifier failed")
    if final.find(".commit()") > final.find("_config.value = next", final.find(MARKER)):
        raise RuntimeError("Metadata must commit before StateFlow publication")

    print("Gen12.1 wallpaper metadata receipt applied and verified")


if __name__ == "__main__":
    main()
