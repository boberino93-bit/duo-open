# Fold7 1.3.27 Cover Route Regression Fix

Observed on the Galaxy Z Fold7 after Batch D:
- front screen no longer wakes when closing starts;
- front-screen fold animation has no destination and does not run.

Root cause:
`prewarmCoverLeaseV2()` powered the stable physical cover to NORMAL and
established a lease, but unlike the previous working path it did not enable the
fresh 1080x2520 logical cover route or request logical `STATE_ON`.

Fix:
1. preserve the Gen2 cover lease;
2. physical NORMAL first;
3. enumerate a fresh non-default 1080x2520 route;
4. require that route's physical ID to match the lease-owned cover panel;
5. enable the logical route;
6. re-resolve after mutation;
7. require the 1968x2184 inner display to remain default and the cover route to
   still map to the owned physical panel;
8. request logical `STATE_ON`;
9. never cache logical display IDs;
10. never issue raw physical OFF.

Version:
- versionCode 32
- versionName 1.3.27-zfold7-cover-route-fix
