# Duo Open Regression Continuity Contract V1

**Status:** MANDATORY  
**Applies to:** PRIMARY, MANAGER_REVIEWER, RESEARCH

## Purpose

Prevent a fast recursive mesh from improving one subsystem while silently dropping previously proven outputs, tests, security invariants, or field lessons.

## Baseline object

Every development round maintains a `RegressionBaseline` containing:
- exact GitHub HEAD;
- baseline id + SHA-256 digest;
- accepted invariant ids;
- accepted test/result refs;
- accepted field-evidence refs;
- known failing tests;
- deferred/physical-only gates;
- superseded items.

Every active agent service checkpoint carries the baseline id/digest it is working against.

## Required agent behavior

At startup:
1. read the current baseline;
2. ACK its digest;
3. identify the subset relevant to the lane.

During work:
- reference the baseline in each 30-second service checkpoint;
- publish any invalidated invariant/test as `REGRESSION_DIRTY`;
- never silently drop a previously accepted output;
- if a finding supersedes an output, name both the old and replacement refs.

At handoff:
- list `PRESERVED`, `CHANGED`, `SUPERSEDED`, `FAILED`, and `PHYSICAL_TEST_REQUIRED`;
- include exact tests run;
- state whether existing outputs were revalidated against current HEAD.

## Contribution rule

An active agent contributes to continuity if each service checkpoint contains:
- current baseline digest;
- latest relevant test/output ref;
- regression state;
- any changed invariant ids.

`NO_DELTA` is valid only when the agent explicitly confirms the same baseline/output refs still apply.

## Controller gate

Manager/Reviewer and Primary maintain a reconciliation matrix keyed by invariant/output id.

Before a final root-safe ZIP:
- every accepted prior invariant/output must have a disposition;
- every closed current-round lane must have a disposition;
- no missing cell may be treated as pass;
- unvalidated rows are `UNKNOWN`/`PHYSICAL_TEST_REQUIRED`, never inferred.

## Security precedence

Security/privacy regression rows are fail-closed and cannot be waived by visual smoothness/performance results.

## Current Gen7 mandatory regression families

At minimum:
- coarse public hinge never becomes continuous semantic geometry;
- semantic state is not driven by PresentationHinge;
- stale/cross-generation callbacks are exact no-ops;
- cover/inner host migration is make-before-break;
- FIRST_PRESENTED <= FIRST_USEFUL <= FIRST_INTERACTIVE ordering;
- readiness is exact attempt + current generation + host/resource fenced;
- physical wake != logical readiness != useful presentation;
- secure/private paths never materialize protected pixels;
- PRIVATE_FROST remains procedural/no captured protected content;
- public video bypass never overrides secure/private policy;
- wallpaper remains passive;
- 120 Hz requests are seamless-only and measured, with safe fallback and terminal release;
- terminal native cover rejects stale route/mirror/power mutations;
- debugging preserves causal identity and sufficient field evidence;
- ordinary close/open regressions and 30–70° oscillation stress remain covered.
