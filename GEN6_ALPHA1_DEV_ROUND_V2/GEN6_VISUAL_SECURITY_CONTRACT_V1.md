# Duo Open Gen6 — Visual Security Contract V1

Status: architecture/acceptance requirement
Applies to: Galaxy Z Fold7 Gen6 Canonical Canvas opening/continuity renderer
Origin: user visual direction supplied 2026-10-02

## Product intent

Gen6 has two visually distinct continuity materials.

### 1. PUBLIC_GLASS — normal apps

Reference intent: the upper supplied example.

- The app remains visually legible through the material.
- The fold animation should read as clear, total glass: transparent/translucent, refractive, polished and continuous rather than a white blur card laid over the UI.
- Geometry, perspective, highlight, edge/refraction and glass amount may animate with hinge state.
- Glass optics and geometry remain independent controls.
- The effect may use a current, provenance-valid app frame when capture/mirroring is permitted.
- No stale cross-app, cross-user, cross-task or cross-cycle content may appear.

### 2. PRIVATE_FROST — secure/work/private apps

Reference intent: the lower supplied example.

- The material should still read as premium glass/frost, but it must be visually opaque enough that protected content cannot be read or inferred through it.
- Protected pixels MUST NOT be used as the blur/refraction source. Blurring a secure screenshot is still possession/rendering of secure pixels and is forbidden.
- Entering PRIVATE_FROST immediately invalidates/destroys any PUBLIC_GLASS pixel lease that could expose the prior app or protected app.
- PRIVATE_FROST renders from synthetic/procedural material (neutral/light field, approved wallpaper/theme source, noise/specular/refraction field) that contains no protected app pixels.
- Secure/capture-denied windows are always PRIVATE_FROST.
- Managed/work-profile apps are always PRIVATE_FROST, even if the app does not assert a platform secure flag.
- Coast Capital must be treated as PRIVATE_FROST even if its installed build does not expose a usable secure/capture-blocked signal. Its package identifier must be learned from actual installed package metadata; do not guess it.
- Architecture must support explicit always-private package policy so additional financial/work apps can be forced private without renderer changes.

## Security classification

Classification must be conservative and monotonic within an active presentation attempt.

Suggested policy inputs, highest priority first:

1. capture denied / secure-window evidence -> PRIVATE_FROST
2. managed/work-profile user or task -> PRIVATE_FROST
3. explicit always-private package policy -> PRIVATE_FROST
4. unknown/untrusted provenance -> PRIVATE_FROST or native handoff; never reuse cached public pixels
5. otherwise -> PUBLIC_GLASS

A downgrade from PRIVATE_FROST to PUBLIC_GLASS requires a new validated content lease and current package/user/task/window provenance. A stale callback may never perform that downgrade.

## Required provenance for PUBLIC_GLASS pixel leases

Every reusable pixel lease must be fenced by at least:

- service epoch
- opening/continuity attempt id
- renderer/host generation
- user/profile identity
- package identity
- window/task identity when available
- capture generation/sequence
- capture timestamp/age

Any mismatch invalidates the lease before presentation.

## Opening behavior

- The WakeHint / virtual hinge remains visual timing only and must not alter privacy classification.
- PRIVATE_FROST can begin immediately from a validated opening attempt because it does not require protected pixels.
- PUBLIC_GLASS may begin only with a current permitted content lease; otherwise show PRIVATE_FROST or native content rather than a stale screenshot/black frame.
- Make-before-break host migration remains required. PRIVATE_FROST is an acceptable safe bridge when a public content lease is not yet ready.

## Closing behavior

- Preserve the proven Gen4/Gen5 close path unless a reviewed later slice deliberately changes it.
- If a private app is active during close, no cached/mirrored protected app pixels may be written into SnapshotCache or Fold7ContinuityFrameStore.
- The terminal native-cover authority fence remains unchanged.

## Visual acceptance

PUBLIC_GLASS:
- content visibly readable through the glass except where intentional optical distortion occurs
- no milky opaque card appearance
- smooth refraction/highlight continuity across hinge motion
- no intentional black frames during migration

PRIVATE_FROST:
- no readable protected text/icons/account data through the material
- no protected screenshot/mirror/cached pixels behind the frost
- premium frosted-glass appearance, not a blank error screen
- can safely appear on the first presentation opportunity before native secure content is ready

## Verification gates

Model/unit:
- secure classification beats all public classifications
- managed profile forces PRIVATE_FROST
- explicit private-package override forces PRIVATE_FROST
- secure transition destroys prior PUBLIC_GLASS lease immediately
- stale callback cannot downgrade PRIVATE_FROST
- PRIVATE_FROST owns no protected pixel payload
- PUBLIC_GLASS lease rejects cross-user/package/task/window/capture-generation reuse

Physical Fold7:
- normal app opening matches transparent reference style
- Coast Capital opening uses opaque private frost with zero readable app content during bridge
- at least one work-profile app uses opaque private frost
- repeated app switching public<->private never leaks one frame of the previous app
- 30 normal cycles + 20 repeated 30–70 degree reversals retain privacy and no-black-frame invariants

## Slice mapping

This contract does not expand Gen6 Slice A (WakeHint + attempt identity + telemetry).
It becomes a mandatory design/acceptance gate for the first slice that owns content provenance, renderer mode, capture/mirror routing or native-fresh release (anticipated Gen6 content/security/renderer slices).
