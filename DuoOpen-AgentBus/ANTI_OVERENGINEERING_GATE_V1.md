# Duo Open Anti-Overengineering Gate V1

**Status:** ACTIVE / ADDITIVE / REVERSIBLE INTERNAL PROCESS RULE  
**Scope:** Duo Open Primary, Manager/Reviewer, Research, successor/bootstrap generation  
**Production authority change:** NONE  
**Background services added:** NONE

## 1. Purpose

Duo Open already has a capable coordination substrate: immutable AgentBus messages, DMSH/3 presence, review/promotion routing, regression continuity, final reconciliation, donor-adoption rules, integrity checks, and current protocol-hardening machinery. This gate prevents engineering effort from drifting into new coordination infrastructure when a product experiment, test, local code change, deletion, or use of an existing primitive would solve the actual problem.

The default is **product evidence first, control-plane expansion last**.

This gate is itself deliberately small. It creates no daemon, polling loop, heartbeat, leader-election service, authority edge, mutable state store, queue, index, or runtime dependency.

## 2. Governing rule: no new mechanism without a witnessed failure

An agent MUST NOT make a new project-wide coordination mechanism mandatory merely because it is cleaner, more elegant, theoretically scalable, or useful in a hypothetical future.

A new global mechanism is eligible only when the proposal names a concrete observed failure or measured bottleneck in the current system and shows why the existing primitives cannot address it safely enough.

Examples of mechanisms covered by this rule:
- new controller/leader-election systems;
- new heartbeat or liveness layers;
- new global schemas or mandatory envelope types;
- new top-level state owners;
- new durable status stores or queues;
- new lease/epoch systems;
- new artifact classes that every agent must emit;
- new authorization/capability layers;
- new background workers/watchdogs;
- new mandatory telemetry or indexing layers.

## 3. Complexity classes

### Level 0 — Local engineering
Examples: implementation change, focused test, measurement, bug fix, local helper, documentation correction, bounded prototype.

Default: **ALLOW_LOCAL**. No architecture ceremony beyond existing lane evidence requirements.

### Level 1 — Reuse/extension of an existing shared primitive
Examples: one new field on an existing message, one additional transition in an existing FSM, one new validation in an existing test/gate, one new disposition value.

Default: **USE_EXISTING_MECHANISM**. Manager/Reviewer checks compatibility and whether the same outcome can be achieved without a protocol change.

### Level 2 — New global mechanism
Any new daemon, global state owner, controller layer, mandatory service, new authority edge, new coordination store, parallel liveness system, or mandatory project-wide artifact family.

Default: **REJECT_OVERENGINEERED** until the hard gate below is satisfied.

## 4. Level-2 hard gate

A Level-2 proposal is incomplete unless it supplies all of the following:

1. `observedFailure` — exact incident, failed handoff, data loss, scaling limit, race, or measured bottleneck.
2. `evidenceRefs` — message/artifact/test/metric references and applicable Git HEAD/protocol version.
3. `existingPrimitivesTried` — which current mechanism(s) were tested and why they were insufficient.
4. `cheaperAlternatives` — at minimum compare against:
   - deleting/consolidating an existing mechanism;
   - documentation/clarification;
   - a local implementation/test fix;
   - an existing message field;
   - an existing FSM transition;
   - a bounded manual/one-shot reconciliation step.
5. `measurableBenefit` — what gets measurably better and how it will be tested.
6. `newFailureModes` — additional races, stale-state risks, write volume, recovery burden, or authority ambiguity introduced.
7. `rollback` — how the mechanism can be removed without losing authoritative history.
8. `sunsetTrigger` — when it must be deprecated if it does not prove value.
9. `authorityDelta` — MUST be `NONE` unless separately approved under the existing high-risk authority-change process.
10. `productionWriteDelta` — MUST NOT grant any autonomous Git production-write capability.

Without all ten, disposition is `REJECT_OVERENGINEERED` or `BOUNDED_EXPERIMENT`, never mandatory adoption.

## 5. Cheapest decisive test first

Before designing new infrastructure, the proposing agent must identify the cheapest experiment capable of falsifying the need for it.

Preferred order:
1. inspect existing evidence/current code;
2. reproduce the concrete failure;
3. add/repair a focused test or measurement;
4. try an existing primitive;
5. simplify/delete redundant machinery;
6. only then propose a new shared primitive.

An unmeasured architectural concern is a hypothesis, not a mandate.

## 6. Product-work-first allocation

When both product research and coordination work are available, agents SHOULD choose product evidence unless a current coordination failure is actively blocking reliable work.

In particular, donor/runtime questions, Fold7 physical evidence, latency, display ownership, task routing, hinge sensing, stale callback fencing, privacy, frame pacing, and regression reproduction outrank speculative control-plane redesign.

A Manager/Reviewer seeing repeated protocol invention without a cited blocking incident must publish `CONTROL_PLANE_DRIFT` and stop assigning nonessential control-plane work until concrete product/evidence lanes resume.

`CONTROL_PLANE_DRIFT` is a review disposition/message label only. It does not create another monitoring service.

## 7. One-in / one-out simplification rule

After one new mandatory global coordination construct has been added during a campaign, any additional Level-2 construct in the same campaign must identify at least one existing construct to remove, merge, downgrade, or render optional, unless two distinct blocking incidents make that impossible.

The goal is not literal line-count symmetry; it is preventing monotonically increasing mandatory architecture.

## 8. Reuse must justify abstraction

Adopt the donor project's practical bias:
- extract/reuse a component only when actual reuse justifies it;
- add diagnostics/performance tooling when a real bug or measurement question needs it;
- do not generalize a Fold7-specific path into multi-device/multi-hinge infrastructure until an actual requirement or second validated consumer exists.

## 9. No duplicate truth owners

A proposal that creates a second authoritative representation of information already owned elsewhere is rejected by default.

Examples:
- another current-room state file when DMSH/3 derives state from immutable frames;
- another acceptance flag when existing review/Primary decisions already carry the state;
- another production authority token when human-gated single-writer commit remains the external interlock.

Derived/cache views must be explicitly non-authoritative and disposable.

## 10. Human-gated production boundary remains unchanged

This gate changes no production permissions.

The intended production lifecycle remains:

`PRIMARY_ACCEPTED`
→ `INTEGRATION_CANDIDATE_READY`
→ `FINAL_RECONCILIATION_PASS`
→ `COMMIT_PACKAGE_READY`
→ `HUMAN_COMMIT_AUTHORIZATION`
→ `SINGLE_WRITER_COMMIT`
→ `POST_COMMIT_VALIDATION`
→ `PRODUCTION_ACCEPTED`

No Research, Manager/Reviewer, controller epoch, succession event, learning overlay, or protocol acceptance grants autonomous Git production-write authority.

## 11. Review dispositions

Use the existing AgentBus/review path and one of these dispositions:
- `ALLOW_LOCAL`
- `USE_EXISTING_MECHANISM`
- `BOUNDED_EXPERIMENT`
- `DEFER_NO_OBSERVED_NEED`
- `REJECT_OVERENGINEERED`

A disposition should be short and point to the durable evidence rather than duplicating it.

## 12. Interaction with current service-cadence contract

This gate does **not** silently supersede `ACTIVE_AGENT_SERVICE_INTERVAL_V1.md`.

However, the existing requirement for a durable DMSH/3 frame **and** durable AgentBus message every 30 seconds is now an explicit simplification-review target because it conflicts with the existing write-budget principle of fewer, smaller, higher-value durable writes.

Any successor cadence must be reviewed through the normal process. A preferred direction is cheap/ephemeral presence plus durable messages only for material engineering/authority events, but this is not activated merely by this document.

## 13. Success condition

This gate is working when:
- product/research evidence grows faster than coordination machinery;
- agents solve local failures locally when possible;
- current primitives are reused rather than cloned;
- mandatory architecture can shrink as well as grow;
- protocol work points to observed failures and measurable benefit;
- future agents can explain *why* every global mechanism exists.
