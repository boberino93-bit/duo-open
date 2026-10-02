# Service Pack V1 implementation report

## Scope

This patch addresses the concrete setup/reliability complaints shown in the supplied report while preserving the Gen7 continuity architecture already on `main`.

| Reported concern | Implemented response |
| --- | --- |
| Authorise appears successful when helper is not actually usable | `Ready` now requires granted permission, live Binder, and successful shell ping. Explicit `Binding` and `BindFailed` states added. |
| “Authorise Shizuku” can do nothing | If permission already exists, the action now performs a forced helper reconnect. Denied state opens Shizuku for permission repair. |
| App can wait indefinitely for Shizuku connection | 8-second bind watchdog fails visibly and clears the stuck binding state; user can retry. |
| Open Shizuku / setup lacks feedback | Existing open action remains; settings now hide meaningless actions and show Connecting/Retry/denied guidance. |
| Wallpaper button implies Duo Open silently installs/configures wallpaper | Copy now states Android requires system confirmation; activation is verified after returning. |
| Samsung FoldInteractive requirement is unclear | Samsung precise-angle wallpaper is explicitly separated from Duo wallpaper, explained as a Fold7 hinge-source dependency, and given a dedicated setup action. |
| Generic “Shizuku needed/off” masks actual failure | Home status card consumes the live Shizuku status string and shows the concrete state. |
| Wallpaper settings are generic | App first attempts `ACTION_CHANGE_LIVE_WALLPAPER` for Samsung `FoldInteractive`, then falls back to the normal wallpaper screen. |

## Important existing Gen7 recovery work verified

The current `Fold7ContinuityCoordinator` already contains the deeper privilege-loss recovery fence from earlier R&D: on privileged loss it revokes render authority, hides the mirror, cancels the active cycle, invalidates cover authority/readiness, and resets the continuity controller. This service pack therefore concentrates on the remaining connection-state truth and onboarding failures rather than duplicating that recovery machinery.

## Validation completed here

- Patch script Python syntax: PASS.
- Exact replacement self-tests: 4/4 PASS.
- Idempotence: PASS.
- Fail-closed missing-block behavior: PASS.
- Exact Git-blob guard behavior: PASS.
- Target baseline and blob IDs were independently read from live GitHub before packaging.

## Validation not completed here

- Android Gradle compilation: NOT RUN because the GitHub connector exposes source reads but not a materialized checkout in this environment.
- Physical Galaxy Z Fold7: NOT RUN.
- Production GitHub integration: NOT PERFORMED because the connected GitHub integration returned HTTP 403 for both branch creation and file updates despite reporting push permission. The package is ready for the Primary/integration agent to apply to a normal checkout.

Those limitations are intentional release gates, not assumed successes.
