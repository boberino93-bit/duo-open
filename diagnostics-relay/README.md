# Duo Open diagnostics relay

Purpose: keep Artifactory credentials off the Android device while returning a cryptographically correlated receipt to the app.

## Required configuration
- `ARTIFACTORY_BASE_URL`: e.g. `https://example.jfrog.io`
- `ARTIFACTORY_REPO`: local generic repository receiving diagnostic ZIPs
- secret `ARTIFACTORY_TOKEN`: deploy + read/search permission for that repository
- optional secret `DUO_UPLOAD_KEY`: protects the public ingest endpoint. This is not the Artifactory token.
- optional `GITHUB_REPOSITORY` + secret `GITHUB_TOKEN`: emits `duoopen-diagnostic-received` after verified storage.

The relay sends `X-Checksum-Sha256` to Artifactory. It does not return success merely because the HTTP upload completed: it performs a checksum search restricted to the configured repository and verifies the expected artifact path appears before issuing the Android receipt.

## Android BuildConfig inputs
The Alpha2 app client expects:
- `DIAGNOSTIC_UPLOAD_URL`, e.g. `https://relay.example/v1/diagnostics`
- `DIAGNOSTIC_INGEST_KEY` if `DUO_UPLOAD_KEY` is enabled

Do not compile `ARTIFACTORY_TOKEN` into the APK.
