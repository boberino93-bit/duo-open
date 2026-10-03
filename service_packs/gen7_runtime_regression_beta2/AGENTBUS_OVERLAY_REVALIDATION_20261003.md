# AgentBus Overlay Revalidation Marker — 2026-10-03

This file intentionally contains no Android runtime code.

It exists under the existing Beta2 workflow's watched `service_packs/gen7_runtime_regression_beta2/**` path so that committing the canonical AgentBus root-safe overlay to `main` starts a fresh `Build Gen7 Runtime Regression Beta2` workflow run.

Expected application behavior and patch bytes remain those of SP4.2. The workflow must still pass the baseline, patch applicability, unit-test, and APK build gates before the package is considered CI-revalidated.

Physical Galaxy Z Fold7 validation remains separate and is not implied by this marker.
