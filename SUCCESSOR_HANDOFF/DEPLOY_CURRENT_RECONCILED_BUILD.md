# Deploy the reconciled Gen3 Alpha1 candidate

The archive root is directly deployable.

## Windows PowerShell

From anywhere inside your local `duo-open` Git checkout:

1. Extract this ZIP anywhere.
2. Run the extracted `DEPLOY_GEN3_ALPHA1_FROM_ANYWHERE.ps1`.
3. Review `git status --short`.
4. Commit/push only:
   - `.github/workflows/apply-gen3-alpha1-integrated.yml`
   - `tools/apply_gen3_phase1_authority.py`
   - `tools/apply_gen3_alpha1.py`
   - `payload/`
5. The GitHub workflow performs the actual fail-closed source patch/test/build/commit.

## macOS/Linux

Run `DEPLOY_GEN3_ALPHA1_FROM_ANYWHERE.sh` from anywhere inside the checkout, then commit/push the same support files.

## Important

Do not manually copy anything from `SUCCESSOR_HANDOFF/late_rnd/` into `app/`.

Those are post-Alpha1 future-state R&D packages for the successor primary to independently revalidate after Alpha1 CI.
