# Duo Open Final Reconciliation Gate v1

Before Primary produces a final root-safe ZIP for user commit, Primary MUST perform one complete reconciliation pass over the current development round.

## Required inputs

Primary must inspect:
- actual current GitHub `main`;
- all research lanes marked complete/released for the current campaign;
- all Manager/Reviewer dispositions for those lanes;
- unresolved contradictions/objections;
- latest physical field evidence;
- latest CI/build evidence;
- current campaign requirements;
- current debugging/data-gap contract;
- current 120 Hz contract;
- current security/privacy invariants.

## Required reconciliation table

For each completed research lane record:
- lane / subsystem;
- originating artifact/message;
- applicable source HEAD;
- evidence class;
- Manager disposition;
- independent Primary revalidation;
- final action: INTEGRATE / DEFER / REJECT / SUPERSEDED / PHYSICAL_TEST_REQUIRED;
- reason.

No closed research work may be silently omitted.

## Final optimization pass

After reconciliation and before packaging, Primary must run a final cross-cutting audit for:
- hinge/source authority conflicts;
- stale async callbacks / generation fences;
- physical vs logical display wake gaps;
- terminal cover ownership/input correctness;
- mirror/session lifecycle cleanup;
- wallpaper/passive-launcher authority boundaries;
- 120 Hz request / actual cadence / lease release;
- secure/private no-pixel-leak invariants;
- instrumentation/data gaps;
- compile/API/visibility/signature consistency;
- regression risk to proven close behavior.

## Build/package gate

Only after reconciliation + optimization may Primary create one root-safe ZIP for the user to commit to `main`.

The package must include:
- START_HERE instructions;
- exact baseline/current-head gates where applicable;
- deterministic/static/model tests;
- build workflow support when needed;
- checksum manifest;
- no nested ZIPs unless explicitly justified;
- explicit MODEL / CI / PHYSICAL status.

After user commit, Primary verifies new HEAD and CI before calling the implementation build-ready.
