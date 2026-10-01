# Duo Open Gen2 — one-shot production execution

The repository already contains the staged Gen2 installer and V2 executor.

The only missing step is execution in a writable GitHub checkout.

Place:

`.github/workflows/apply-gen2-production.yml`

on `main`.

The workflow triggers on that file being added/changed. It:

1. checks out current `main`;
2. sets up Java 17;
3. runs `python3 deploy_staged_gen2_v2.py .`;
4. the executor applies the Gen2 production runtime;
5. runs structural verification and Gradle unit/build gates;
6. verifies the generated diff;
7. commits only `app/**` and `.github/workflows/build-direct-fold7.yml`;
8. pushes the verified production commit to `main`.

If any installer, verifier, unit-test, or build step fails, the commit/push step is never reached.

Current repository staging lineage expected:
- audited runtime baseline: 586c308649258145b3da9b5ea27b726a6fb3647a
- staged Gen2 commit: c0a12450524296dccf74401df73d688d9e22f4b1
- V2 executor is already present on current main lineage.
