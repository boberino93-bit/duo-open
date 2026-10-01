# Duo Open — Gen2 staged-state corrective deployment

This is the package to use **after** the full Gen2 bundle has already been committed to `main` as review/staging material but the actual runtime changes were not applied.

## Exact target

Repository: `boberino93-bit/duo-open`

Required starting `HEAD`:

`c0a12450524296dccf74401df73d688d9e22f4b1`

That commit contains the staged Gen2 bundle (`repo_overlay/`, `tools/apply_gen2.py`, verifier, tests and docs) while the production runtime still matches audited baseline:

`586c308649258145b3da9b5ea27b726a6fb3647a`

## Root action

From a clean checkout of current `main`, run:

```bash
python3 /path/to/DUO_OPEN_GEN2_STAGED_STATE_FIX/deploy_staged_gen2.py .
```

The wrapper will:

1. Require exact starting HEAD `c0a12450524296dccf74401df73d688d9e22f4b1`.
2. Require a clean worktree.
3. Verify the already-staged Gen2 machinery by Git blob identity.
4. Verify the staged package SHA-256 manifest.
5. Invoke the existing `tools/apply_gen2.py --force --check-only`.
   - `--force` only bypasses the old HEAD equality check.
   - The existing installer still verifies every guarded production blob against the audited runtime baseline and fails closed on drift.
6. Apply the staged Gen2 overlay and production transforms.
7. Run `tools/verify_gen2_postapply.py`.
8. Run `git diff --check`.
9. Verify the expected production files really changed/appeared.
10. Run the mandatory Gradle gates:

```bash
./gradlew testFullDebugUnitTest assembleFullDebug --stacktrace
```

The wrapper creates **no commit and no push**. Root must review the resulting diff and commit only if all gates pass.

## Expected post-apply version

- `versionCode = 35`
- `versionName = "2.0.0-zfold7-gen2-ownership"`

## Expected architecture

`Angle / Device State`
→ `Transition Policy`
→ `Physical Cycle Envelope`
→ `Cover Lease V3 Authority`
→ `Cover Readiness`
→ `Frame Provenance`
→ `Host / Rendering`
→ `Presentation Evidence`
→ `Samsung Native Handoff`

## Stop conditions

Do not commit if any structural verifier or Gradle gate fails. Do not use this package if `main` has advanced beyond the exact target HEAD; reconcile first instead of forcing it onto newer production work.
