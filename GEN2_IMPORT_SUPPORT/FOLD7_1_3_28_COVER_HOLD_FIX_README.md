# Fold7 1.3.28 Cover Hold Fix

This patch is driven directly by the 1.3.27 device debug bundle.

The trace shows that the 174° prewarm succeeds and logical cover display 1 is
active at 168°, but Samsung removes the secondary cover route before the 135°
visual threshold while the lease remains HELD. At 133° the controller enters
COVER_VISUAL with `coverLogical=null` and `coverActive=false`, so no mirror host
can be created.

1.3.28 adds an owner-scoped `ensure-held` operation to the existing cover lease
protocol. It can run only when the exact owner still owns a HELD lease.

When Samsung drops the route during COVER_READY_HIDDEN or COVER_VISUAL, the
coordinator asks the shell to:
- reassert physical cover NORMAL;
- freshly resolve the non-default 1080x2520 route;
- require the route to map to the lease-owned physical cover;
- enable the route;
- revalidate after the mutation;
- request logical STATE_ON.

It never issues raw physical OFF and does not transfer lease ownership.

Version:
- versionCode 33
- versionName `1.3.28-zfold7-cover-hold-fix`
