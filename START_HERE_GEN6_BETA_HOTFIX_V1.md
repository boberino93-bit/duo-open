# Duo Open Gen6 Alpha 2 Hotfix V1

Frozen source baseline:
`699ed29288ab2aa24463902fcefe752d432717d2`

This package intentionally ignores research published after the freeze point.

Extract this ZIP at the repository root and commit all included files to `main`.

Suggested commit message:

`Gen6 alpha2 hotfix: inner wake, hinge authority, terminal fence, passive wallpaper`

The included workflow will automatically trigger on `main`.

Expected CI-produced runtime:
- versionCode 44
- versionName 6.0.0-alpha2-zfold7
- artifact name DuoOpen-ZFold7-6.0.0-alpha2-hotfix1

Primary changes:
- coarse public hinge remains shadow/posture-only
- physical + logical inner wake attempt
- pre-mutation native-cover terminal fence
- app-side stale route reassert fence
- passive canonical launcher-continuity wallpaper
- extra hinge-authority decision telemetry

Status before CI:
- SOURCE: PASS
- local patcher validation/self-test: PASS
- CI: NOT YET RUN
- PHYSICAL FOLD7: NOT YET RUN
