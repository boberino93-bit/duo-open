#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

MARKER = "GEN12_1_WALLPAPER_RESET_IO"


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
    path = repo / "app/src/main/java/com/duoopen/ui/DuoApp.kt"
    text = path.read_text(encoding="utf-8")

    if MARKER not in text:
        old = '''                onDefaultImage = {
                    WallpaperImage.reset(
                        context.applicationContext
                    )
                },
'''
        new = '''                onDefaultImage = {
                    // GEN12_1_WALLPAPER_RESET_IO
                    // Reset is now a checked durable storage transaction. Keep it
                    // off the Compose/main thread and surface failure without
                    // taking down the activity.
                    scope.launch {
                        val reset =
                            withContext(Dispatchers.IO) {
                                runCatching {
                                    WallpaperImage.reset(
                                        context.applicationContext
                                    )
                                }
                            }

                        reset.onFailure { error ->
                            Toast.makeText(
                                context,
                                "Couldn't reset the wallpaper image: ${error.message ?: error.javaClass.simpleName}",
                                Toast.LENGTH_LONG,
                            ).show()
                        }
                    }
                },
'''
        text = replace_once(text, old, new, "wallpaper reset IO")
        path.write_text(text, encoding="utf-8")

    final = path.read_text(encoding="utf-8")
    if MARKER not in final or "withContext(Dispatchers.IO)" not in final:
        raise RuntimeError("Gen12.1 wallpaper reset IO verifier failed")
    print("Gen12.1 wallpaper reset IO applied and verified")


if __name__ == "__main__":
    main()
