# Gen6 Alpha 1 V2 — Pre-Build Test Status

## Result

**PRE-BUILD_CANDIDATE = PASS**

This means the package is ready for the repository Android/Gradle build gate. It does **not** mean Android CI or physical Fold7 acceptance has passed.

## Current repository state checked

- repository: `boberino93-bit/duo-open`
- current `main` observed: `12c8f2530afb0523d8d2f83af3c62c1dca8c11b8`
- that commit adds the imported Alpha 1 V1 handoff only; the production runtime blobs patched by V2 remain unchanged

Exact runtime blob gates revalidated:

- `app/build.gradle.kts` — `f11b8c5a15a67f2e7cad874db66d943c768fdce8`
- `Fold7DeviceStateObserver.kt` — `760d075332740e5ee0d73766766175b17e6f9122`
- `FoldOverlayService.kt` — `cfc4706458e1da197e0e86ce74dc80c83489a2e6`
- `PanelEngine.kt` — `866d21ed1bd3fecfc25fffdcd3633489db9a80d9`
- `FoldSurface.kt` — `79cd40dfacc81a87f7af988bca1880cd1ea83625`
- `SnapshotCache.kt` — `4b1b6bb9837de4fb77cdc1bdc26f4a39aa72ab26`
- `Fold7ContinuityFrameStore.kt` — `953200266e6b9117b97f1cdb980cf0ef48190482`
- `DuoShellService.kt` — `e19469eebaa967cbce10f5bcf85eef795e1d6b7d`
- `ShizukuBridge.kt` — `d276f950eb279b3af281b9930dda7a8e8c3fd6a1`
- `duo_accessibility.xml` — `58c06748df97fdc1207bc873b6f0df8bb3573a08`

Key patch anchors were also checked against current `main`; the expected runtime markers remain present.

## V1 failures found during this test round

V1 was rejected before APK compilation for two concrete reasons:

1. The Samsung `0 -> 1` WakeHint created identity/telemetry but did not dispatch the physical inner-panel wake, leaving the principal opening latency dependency intact.
2. Entering private mode during an existing Gen3 closing visual could clear caches without necessarily detaching the already-presented public frozen-frame host.

V2 corrects both before the Android build gate.

## Automated local gates

### Patcher/static gate

- Python compile: PASS
- patcher self-test: PASS
- package security/authority static gate: PASS

### Pure Kotlin harness

17 deterministic PASS checkpoints, including:

- WakeHint identity / duplicate fencing / semantic attachment / terminal cleanup
- second-cycle identity
- **100,000** opening-attempt lifecycle iterations
- PUBLIC_GLASS admission
- Coast Capital PRIVATE_FROST
- work-profile PRIVATE_FROST
- FLAG_SECURE PRIVATE_FROST
- sticky same-package secure denial
- new-package denial reset
- **100,000** randomized privacy-invariant cases

PRIVATE_FROST invariant in fuzz:

`captureAllowed == false && cacheAllowed == false && proceduralOnly == true`

### Raw Fold7 replay

Nine usable Samsung `0 -> 1` leave-closed events:

- min wait to next authoritative hinge: **401 ms**
- median: **910 ms**
- p95: **2,484 ms**
- max: **2,484 ms**

V2 moves physical-wake and visual-material dispatch to the earlier WakeHint. This is replay/model evidence; it is not an observed V2 physical latency result.

## Security checks encoded by V2

- PUBLIC_GLASS opening bootstrap does not reuse a cached previous-app image.
- PRIVATE_FROST is fully procedural/opaque.
- entering private mode clears reusable generic/continuity pixel leases.
- private mode disables the Gen3 privileged pixel renderer, causing stale pixel host teardown.
- shell secure-layer metadata is checked before `getHardwareBuffer()` / `asBitmap()` materialization.
- secure metadata is preserved to the app process through `captureResult()`.
- Accessibility secure-window error fails closed to PRIVATE_FROST.

## Remaining mandatory gate

Run in the actual repository after applying V2:

```bash
git diff --check
./gradlew testFullDebugUnitTest assembleFullDebug --stacktrace
```

Until that succeeds:

- `ANDROID_CI_PASS = NO`
- `PHYSICAL_FOLD7_PASS = NO`
