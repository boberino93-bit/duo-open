# Duo Open Expanded Capability Research Directive V1

## Purpose
Duo Open research is no longer limited to improving fold/unfold animation. The project now treats the Fold7 hinge, dual internal displays, posture, privileged display control, continuity pipeline, and presentation/capture stack as possible foundations for new device interaction models.

This directive records standing speculative research subjects for future Research, Manager/Reviewer, and Primary rounds. These are hypotheses to investigate, not production claims. They must be falsified or validated against current source, Android/One UI behavior, security/privacy constraints, and physical Fold7 evidence before adoption.

## Relationship to active beta work
Current beta blockers and regression contracts remain authoritative for production readiness. Expanded-capability work must not casually destabilize known-good closing behavior, panel authority, secure/private rendering, recovery, or diagnostic transport.

However, when new R&D rounds or spare research lanes are created, the allocator should include one or more bounded lanes from this directive by default unless an urgent blocker consumes all available capacity. Results remain future-state evidence until Manager/Reviewer and Primary accept them.

## Standing research subjects

### R1 — Hinge as an analog system controller
Research whether continuous hinge angle, velocity, direction, dwell, acceleration, reversal, and motion history can become a general-purpose input language rather than merely an animation parameter.

Candidate behaviors include:
- crack-open glance/peek actions;
- continuous volume, scrolling, zoom, timeline or media scrubbing;
- angle-gated contextual controls;
- deliberate slow/fast opening gestures;
- reversal gestures;
- posture-specific commands.

Required research:
- characterize Fold7 sample rate, latency, noise, stationary jitter and quantization;
- distinguish intentional micro-motion from ordinary hinge vibration;
- measure false positives across slow/fast/reversal/endurance sequences;
- determine which interactions are safe without privileged input injection;
- define fail-closed behavior when precise angle authority becomes stale.

### R2 — Physical app switcher / portal through the hinge
Research a navigation model in which opening the Fold progressively reveals or previews another app/workspace/context behind the current surface, with physical hinge motion scrubbing the transition and full opening committing the destination.

Questions:
- can destination content be prewarmed without stealing focus prematurely;
- can capture/mirror/presentation surfaces preview a future task while preserving security classification;
- can reversal cancel cleanly without stale task/presentation ownership;
- can recent-app/workspace selection be mapped to angle bands or motion direction;
- how should secure/private surfaces degrade.

### R3 — Universal Flex Deck for arbitrary apps
Research a system-owned control deck that appears in tabletop/laptop-like posture while leaving an unmodified foreground app usable.

Candidate control surfaces:
- trackpad / scroll pad;
- keyboard or macro deck;
- media transport;
- timeline scrubber;
- app shortcuts;
- clipboard/history tools;
- game/camera controls;
- contextual accessibility controls.

Questions:
- can a Duo-owned region coexist with arbitrary apps without breaking layout/focus;
- what can be implemented using overlays/accessibility/public APIs versus Shizuku/shell privileges;
- whether safe input injection or gesture forwarding is feasible;
- posture hysteresis, accidental activation, and recovery semantics.

### R4 — Backside OS / dual-face companion display
Research using the cover display as a persistent second-purpose surface while the inner display is active.

Candidate uses:
- translator output facing another person;
- QR codes, tickets, boarding passes and identity-neutral public cards;
- camera subject preview / tally / framing aid;
- presentation notes or outward presentation surface;
- Now Playing / recording / timer / navigation status;
- call controls or meeting status;
- game status or companion information;
- intentionally public summaries of otherwise private inner content.

Required research:
- concurrent inner/outer device states available on Fold7;
- whether both panels can remain lit reliably;
- arbitrary Presentation/SurfaceControl content on the secondary physical panel;
- power/thermal/refresh implications;
- exact secure/private content policy so private inner pixels are never mirrored accidentally;
- recovery when Samsung remaps logical displays.

### R5 — True two-person mode
Research whether two people can independently interact with different physical sides of the same Fold.

This is a deeper systems hypothesis than R4 and must be treated as such.

Questions:
- does the cover digitizer remain active while the inner display is primary;
- can input events be attributed to the physical panel despite logical remapping;
- can secondary input be safely routed/reinjected without breaking Android security;
- can a secondary task or Duo-hosted surface remain active while Samsung forbids normal top focus;
- what is possible without framework/SystemUI modification;
- whether the useful near-term form is two interactive Duo-owned surfaces rather than two independent Android desktops.

### R6 — Posture as workspace selector
Research treating physical device shape as a workspace switch rather than merely a responsive-layout hint.

Candidate posture model:
- closed = phone;
- barely open = glance/peek;
- partial open = context controls;
- tabletop = control deck / laptop mode;
- wide open = two-pane workspace;
- fully flat = tablet/desktop mode;
- tent/wedge = ambient, camera, presentation or media mode.

Required research:
- reliable posture bands and hysteresis;
- workspace persistence and restore;
- interaction with Samsung native fold states;
- task/windowing options available on Android 16/One UI for Fold7;
- reversals and ambiguous posture transitions.

### R7 — Anticipatory UI / predictive prewarming
Research using hinge kinematics to infer likely destination state before the user completes the motion and prewarm the next surface, task, panel, renderer, camera, workspace or control deck.

Goals:
- reduce physical-edge-to-first-useful-pixels latency;
- pre-create expensive surfaces before terminal handoff;
- abort prediction safely on reversal/oscillation;
- never let prediction become authority for physical ownership.

Required evidence:
- prediction precision/recall across real motion traces;
- false-positive cost;
- source-age and timebase fencing;
- cancellation latency;
- measurable end-to-end latency improvement on Fold7.

### R8 — Angle-controlled information density
Research continuously revealing more information as the Fold opens rather than switching only between discrete layouts.

Examples:
- notification title -> preview -> actions -> full context;
- single-pane -> supporting pane -> full workspace;
- progressively richer controls as available physical area and angle increase.

Questions:
- whether this can be implemented as a Duo-owned companion layer for arbitrary apps;
- whether application-specific integrations are necessary for deeper semantics;
- visual stability and accessibility at intermediate angles;
- cancellation/reversal behavior.

### R9 — Hinge micro-gestures / hidden hardware button
Research whether small deliberate hinge motions can be recognized reliably enough to function as a new hardware input channel.

Candidate gestures:
- squeeze/open a few degrees and return;
- double squeeze;
- sharp versus slow micro-motion;
- small oscillation while already in a stable posture.

First phase is measurement only. Characterize noise floor, mechanical play, sensor cadence, repeatability, user effort, false positives during walking/handling, and whether gesture recognition remains safe after sensor-source failover.

## Cross-cutting systems questions
Every lane should consider the following shared questions where applicable:
- concurrent device-state availability and ownership;
- physical panel identity versus disposable logical display IDs;
- secondary-panel focus/input restrictions in One UI;
- Presentation, SurfaceControl, capture and task-routing primitives;
- accessibility/Shizuku/public-API boundary;
- secure/private/protected-content handling;
- refresh-rate/120 Hz behavior and measured cadence;
- power, thermal and battery cost;
- crash/recovery and stale-async fencing;
- reversal/oscillation/endurance behavior;
- app compatibility and graceful degradation.

## Research priority guidance
High-value early probes:
1. Fold7 hinge telemetry characterization for micro-gesture feasibility.
2. Concurrent-state experiment: both panels lit + arbitrary secondary presentation.
3. Secondary digitizer/input observability while inner is primary.
4. Predictive-prewarm accuracy versus current first-useful-inner latency.
5. Universal Flex Deck feasibility with an arbitrary unmodified app.

## Evidence discipline
- Label speculation as HYPOTHESIS until measured.
- Exact source/firmware/repo revision must accompany technical conclusions.
- Do not infer that an Android/AOSP capability is exposed by Samsung until Fold7 evidence confirms it.
- A visually successful demo is not proof of focus, input, power, privacy, or lifecycle correctness.
- Security/privacy failure overrides feature success.
- Preserve working production invariants unless a dedicated Primary-authorized experiment explicitly isolates them.

## Handoff requirement
Every material result from these subjects must be published to `/DuoOpen-AgentBus/messages/` and routed Research -> Manager/Reviewer -> Primary under the existing AgentBus authority model.

## Message-board communication optimization mandate
These expanded research subjects are expected to increase coordination volume. The AgentBus/message-board architecture must therefore be optimized as part of the next process revision so throughput limits do not become a recurring project bottleneck.

Primary and Manager/Reviewer must treat this as a communication-architecture problem, not as permission to weaken durable handoff guarantees. The optimization target is **fewer, smaller, higher-value durable writes** while preserving complete provenance, supersession, review, and recovery semantics.

Required process action:
- audit current `/DuoOpen-AgentBus/messages/` write volume and identify redundant/duplicative message classes;
- keep immutable messages for material state changes, findings, blockers, contradictions, reviews, decisions, handoffs and supersessions;
- move bulky evidence/details to one canonical artifact and make messages concise pointers;
- batch logically related low-level checkpoints where doing so does not hide authority changes or material findings;
- avoid duplicating the same evidence in chat, message, artifact and review payloads;
- distinguish ephemeral service/liveness telemetry from durable engineering communication, preserving only the minimum durable checkpoint required by the current control contracts;
- add deduplication/content-addressing where practical;
- measure write count/bytes per active agent and per development cycle;
- preserve fail-closed behavior: if the optimized board cannot persist a required material event, the event is not considered handed off.

This communication optimization itself must follow the normal Research -> Manager/Reviewer -> Primary review route and must not silently relax auditability.
