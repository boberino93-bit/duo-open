# Duo Open Transition Lab — Batch 1

Additive-only observational core for the Fold7 direct-source tree.

This batch adds six files under:
`app/src/full/java/com/duoopen/lab/`

It does NOT hook into production code yet and does not change any thresholds, state transitions, panel power, mirror behavior, or rendering.

Correction applied relative to the R&D v0 handoff:
- Samsung Binder arrival and main-thread consumer delivery are separate timestamps.
- JSONL schema records source->Binder, Binder->consumer, and source->consumer latency independently.

After extracting this ZIP into the repository root, commit and push. The existing direct-source workflow will automatically compile/test because it watches `app/**`.
