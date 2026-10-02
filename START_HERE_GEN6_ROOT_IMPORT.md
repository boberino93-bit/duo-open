# Duo Open Gen6 — Root Import Package

This is a **single root-safe import package**. It contains no nested ZIPs.

## Required processing order

1. Read `GEN6_MODEL_GATE/` first.
   - Treat this as the architecture, replay, invariants, and evidence gate.
   - The model gate records `MODEL_PASS=YES`.
   - It does **not** by itself authorize production changes.

2. Then read `GEN6_SLICE_A/`.
   - This is the first implementation candidate: WakeHint / OpeningAttempt identity + telemetry.
   - Compare it against the **actual current GitHub `main` HEAD** before applying anything.
   - Do not blindly copy source files over a newer main branch.

## Authority rules

- Preserve the proven Gen5 closing path.
- A WakeHint is infrastructure/visual-attempt evidence only.
- A WakeHint must never become semantic hinge geometry, terminal handoff authority, or panel ownership truth.
- Keep measured/verified state authoritative.
- Run Manager/review and CI gates before production promotion.
- Do not claim a physical Fold7 pass until an actual device run proves it.

## Baseline when this package was produced

Repository: `boberino93-bit/duo-open`
Verified `main`: `de9eb45086f6eee00dd4e1e01d5e9782e39773d5`

The active GitHub integration was read-capable but branch creation returned HTTP 403, so Slice A is intentionally packaged as an import candidate rather than represented as committed production code.

## What the receiving Primary Agent should do

- Read this file first.
- Read `GEN6_MODEL_GATE/` completely.
- Read `GEN6_SLICE_A/` completely.
- Re-check actual current `main`.
- Compare/rebuild Slice A against current main.
- Independently validate all changed files and tests.
- Route through the normal review/CI gates.
- Only then integrate authorized production changes.
