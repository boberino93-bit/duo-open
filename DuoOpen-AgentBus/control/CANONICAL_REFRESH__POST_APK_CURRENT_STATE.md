# Duo Open current state — post-APK canonical refresh

Cutoff: 2026-10-03T02:25:01Z

## Source / CI truth
- GitHub main: `28842ae4d1c4f907257b24a73012bf5015702f81`.
- Gen7 Runtime Regression Beta2 workflow run: `37083926151` — SUCCESS.
- App build: `5.1.0-beta2-zfold7`, versionCode 43.
- APK SHA-256: `03d9877e134a6cc2b1d1bbe24a0bc3ceba959b67981ad523b2adb593f2036199`.
- Root-safe SP4.2 SHA-256: `898e3b40e40b79510711a2f9a93f89c074012573fe5a8a32f84b567d9ec2025e`.
- Physical Galaxy Z Fold7 validation after this CI build: **NOT_RUN** in this package. Do not upgrade CI evidence into FIELD evidence.

## Main development subject
Artifactory NG / AgentBus persistence is now the primary development stream. Work centers on canonical role-package publication, full forum snapshot/restore, persistent inter-agent communication, recursive continuity, fencing/singleton authority, recovery, message-board optimization, multiple design/test cycles by default, and Git mirror integrity.

The Android/Fold7 runtime lane is parked unless new physical-device evidence requires reopening it.

## Canonical lineage correction
The earlier `*_REG3_REFERENCE_V2.zip` role packages in the first Artifactory NG shadow trial are test fixtures only. They are not canonical Duo Open agents. This package is derived from the actual live role-package lineage and preserves those bytes as its predecessor.

## Required startup behavior
1. Verify this package's manifest and role.
2. Read the packaged full AgentBus snapshot.
3. If live Library access is available, reconcile all messages newer than `2026-10-03T02:25:01Z` before substantive work.
4. Treat Artifactory NG as the main subject unless a newer human or Primary directive supersedes it.
5. Persist material findings/handoffs to `/DuoOpen-AgentBus/messages/` before declaring a work unit complete.
6. Preserve the complete forum snapshot in successor/deployment packages and fail closed on incomplete exports.
