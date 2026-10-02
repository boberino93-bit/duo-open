DUO OPEN GEN3 ALPHA3 V2 BUILD FIX

Fixes GitHub Actions run 36955165701.
The Alpha3 baseline/checksum/patch/invariant gates all passed. Kotlin compilation then found one extra closing brace generated in ControlSheet.kt by the Shizuku UI-pruning transform.

This package contains only the corrected patcher, updated support checksum manifest, and the workflow with a V2 marker so the push retriggers automatically.
Extract into repository root and overwrite existing files.
