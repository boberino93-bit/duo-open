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

    # The bridge transformer intentionally uses a raw Python string. It emits
    # two backslashes before Kotlin '$'. Collapse that to Kotlin's single '\$'
    # interpolation escape before compilation.
    text = text.replace(
        '"Landroid/view/SurfaceControl\\\\$Builder;"',
        '"Landroid/view/SurfaceControl\\$Builder;"',
    )
    text = text.replace(
        '"Landroid/view/SurfaceControl\\\\$Transaction;"',
        '"Landroid/view/SurfaceControl\\$Transaction;"',
    )

    # show()/remove() exist on the hidden Transaction surface at runtime but
    # are absent from the public compile SDK used by CI. Keep the experiment
    # compile-safe by invoking both through the same reflection boundary as the
    # other hidden physical-display methods.
    text = replace_once(
        text,
        '''                tx.setLayer(layer, Int.MAX_VALUE - 64)
                tx.show(layer)

                txClass.getDeclaredMethod(
''',
        '''                tx.setLayer(layer, Int.MAX_VALUE - 64)
                txClass.getDeclaredMethod(
                    "show",
                    SurfaceControl::class.java,
                ).apply { isAccessible = true }
                    .invoke(tx, layer)

                txClass.getDeclaredMethod(
''',
        "reflect hidden Transaction.show",
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
                    tx.javaClass
                        .getDeclaredMethod(
                            "remove",
                            SurfaceControl::class.java,
                        )
                        .apply { isAccessible = true }
                        .invoke(tx, layer)
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
    if '"show",\n                    SurfaceControl::class.java' not in after:
        raise RuntimeError("reflected Transaction.show missing")
    if '"remove",\n                            SurfaceControl::class.java' not in after:
        raise RuntimeError("reflected Transaction.remove missing")
    if 'tx.show(layer)' in after or 'tx.remove(layer)' in after:
        raise RuntimeError("direct hidden Transaction show/remove call remains")
    if 'SurfaceControl\\$Builder;' not in after:
        raise RuntimeError("Kotlin-safe Builder descriptor missing")
    if 'SurfaceControl\\$Transaction;' not in after:
        raise RuntimeError("Kotlin-safe Transaction descriptor missing")
    if not check:
        path.write_text(after, encoding="utf-8")


def self_test() -> None:
    sample = (
        '"Landroid/view/SurfaceControl\\\\$Builder;"\n'
        '"Landroid/view/SurfaceControl\\\\$Transaction;"'
    )
    fixed = sample.replace(
        '"Landroid/view/SurfaceControl\\\\$Builder;"',
        '"Landroid/view/SurfaceControl\\$Builder;"',
    ).replace(
        '"Landroid/view/SurfaceControl\\\\$Transaction;"',
        '"Landroid/view/SurfaceControl\\$Transaction;"',
    )
    assert 'SurfaceControl\\$Builder' in fixed
    assert 'SurfaceControl\\$Transaction' in fixed
    assert 'SurfaceControl\\\\$Builder' not in fixed
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
