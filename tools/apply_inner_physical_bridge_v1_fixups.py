#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

SHELL = Path("app/src/full/java/com/duoopen/shell/DuoShellService.kt")
MARKER = "INNER_PHYSICAL_BRIDGE_V1_FIXUPS"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {n}")
    return text.replace(old, new, 1)


def transform(text: str) -> str:
    if MARKER in text:
        return text

    # The bridge transformer intentionally uses raw Python strings. Collapse
    # its doubled backslash to Kotlin's single '\$' interpolation escape.
    text = text.replace(
        r'"Landroid/view/SurfaceControl\\$Builder;"',
        r'"Landroid/view/SurfaceControl\$Builder;"',
    )
    text = text.replace(
        r'"Landroid/view/SurfaceControl\\$Transaction;"',
        r'"Landroid/view/SurfaceControl\$Transaction;"',
    )

    old = '''            val layer = innerPhysicalBridge
            if (layer != null) {
                runCatching {
                    SurfaceControl.Transaction()
                        .remove(layer)
                        .apply()
                }
                runCatching { layer.release() }
            }
'''
    new = '''            val layer = innerPhysicalBridge
            val physicalId = innerPhysicalBridgePhysicalId
            if (layer != null) {
                runCatching {
                    val tx = SurfaceControl.Transaction()
                    if (physicalId >= 0L) {
                        val token =
                            SurfaceControl::class.java
                                .getDeclaredMethod(
                                    "getPhysicalDisplayToken",
                                    java.lang.Long.TYPE,
                                )
                                .invoke(null, physicalId) as? IBinder
                        if (token != null) {
                            tx.javaClass
                                .getDeclaredMethod(
                                    "setDisplayLayerStack",
                                    IBinder::class.java,
                                    Integer.TYPE,
                                )
                                .apply { isAccessible = true }
                                .invoke(tx, token, 0)
                        }
                    }
                    tx.remove(layer)
                    tx.apply()
                }
                runCatching { layer.release() }
            }
'''
    text = replace_once(text, old, new, "restore native layer stack on release")

    # Marker is a comment only; no runtime mechanism is added.
    text = text.replace(
        '    private fun ensureInnerPhysicalBridge(\n',
        '    // INNER_PHYSICAL_BRIDGE_V1_FIXUPS\n    private fun ensureInnerPhysicalBridge(\n',
        1,
    )
    if MARKER not in text:
        raise RuntimeError("fixup marker missing")
    return text


def apply(repo: Path, check: bool) -> None:
    path = repo / SHELL
    if not path.exists():
        raise RuntimeError(f"missing {SHELL}")
    before = path.read_text(encoding="utf-8")
    if "INNER_PHYSICAL_BRIDGE_V1" not in before:
        raise RuntimeError("physical bridge v1 must be applied before fixups")
    after = transform(before)
    if 'invoke(tx, token, 0)' not in after:
        raise RuntimeError("native stack restore missing")
    if not check:
        path.write_text(after, encoding="utf-8")


def self_test() -> None:
    sample = r'''"Landroid/view/SurfaceControl\\$Builder;"
"Landroid/view/SurfaceControl\\$Transaction;"'''
    fixed = sample.replace(
        r'"Landroid/view/SurfaceControl\\$Builder;"',
        r'"Landroid/view/SurfaceControl\$Builder;"',
    ).replace(
        r'"Landroid/view/SurfaceControl\\$Transaction;"',
        r'"Landroid/view/SurfaceControl\$Transaction;"',
    )
    assert r'SurfaceControl\$Builder' in fixed
    assert r'SurfaceControl\$Transaction' in fixed
    print("inner physical bridge v1 fixups: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    if not args.self_test or args.check:
        apply(Path(args.repo).resolve(), args.check)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
