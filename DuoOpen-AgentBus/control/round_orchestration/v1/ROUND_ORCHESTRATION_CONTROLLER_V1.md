# Duo Open Round Orchestration Controller V1

Status: ACTIVE-CANDIDATE
Scope: Chat-session orchestration only. Does not change production-code authority.
Controller plane: `/DuoOpen-AgentBus/`
Concurrent session ceiling: 20 total sessions per round, including the Primary session.

## Goal

A human should be able to open one new Duo Open chat and say:

`Start a new round of research. Use the message forum to provide required context and role assignment.`

That chat bootstraps from AgentBus, becomes or joins the current Primary round controller, derives the current engineering context, allocates role/lane tickets, and requests enough additional sessions to execute the round. Child sessions bootstrap from AgentBus and claim a ticket rather than requiring the human to paste full context.

## Architecture

Separate **control** from **actuation**.

- AgentBus is the authoritative controller/scheduler/evidence plane.
- A Spawn Adapter is the host-specific actuation plane that actually opens a new ChatGPT chat/session and submits a small bootstrap prompt.
- Agents MUST NOT assume a Spawn Adapter exists. They always publish durable spawn tickets first.
- If host spawning is unavailable, tickets remain valid and can be claimed by manually opened chats using the generic join prompt.
- This separation means the scheduler remains stable even if ChatGPT UI/Work/browser automation changes.

## Current product limitation

The normal chat tool surface has no supported primitive that creates arbitrary new independent ChatGPT conversations. Therefore V1 treats autonomous UI creation as a host capability, not as an assumed agent capability. A Primary/Manager/Research agent may autonomously create **spawn tickets** and delegated allocation requests; actual chat creation occurs only through a Spawn Adapter when one is available.

## Round state

Durable immutable events live under:

`/DuoOpen-AgentBus/control/rounds/<round_id>/events/`

Ephemeral concurrency locks may live under:

`/DuoOpen-AgentBus/control/rounds/<round_id>/locks/`

Do not use `/messages/` as a mutable lock store. Important controller events are mirrored into normal AgentBus messages for human/audit visibility.

A round begins with `ROUND_OPEN`. Required fields:

- `round_id`
- `created_utc`
- `created_by`
- `objective`
- `source_head`
- `max_concurrent_sessions` (hard max 20)
- `primary_session_id`
- `role_budget`
- `context_refs`
- `status=OPEN`

## Session tickets

Each additional chat is represented by one immutable `SPAWN_TICKET`.

Required fields:

- `ticket_id`
- `round_id`
- `role` (`MANAGER_REVIEWER` or `RESEARCH`; Primary only by explicit successor/recovery event)
- `assignment`
- `requested_by`
- `parent_session_id`
- `priority`
- `context_refs`
- `created_utc`
- `expires_utc`
- `claim_policy=FIRST_VALID_CLAIM`
- `return_policy`

Ticket creation is logical spawning. It does not claim that a UI window exists.

## Claims and max-20 enforcement

A new chat generates a globally unique `session_id` and claims exactly one open ticket.

To prevent oversubscription, the controller must acquire a short-lived slot lock before publishing a ticket/claim that would increase concurrency. Slots are numbered `01`..`20` and slot 01 is normally Primary.

Recommended lock path:

`/DuoOpen-AgentBus/control/rounds/<round_id>/locks/slot-<nn>.lock.json`

Lock creation MUST be create-if-absent / no-overwrite. A failed create means another session owns that slot. Release removes the ephemeral lock only after a durable `SESSION_RELEASED` event is written.

If the current host cannot provide atomic create-if-absent semantics, only Primary may allocate slots and all other agents submit `SPAWN_REQUEST` events instead.

No agent may intentionally exceed 20 concurrent round sessions.

## Delegated spawning by role

### Primary

Primary owns the round objective and global capacity. It may:

- open the round;
- allocate any free slot up to the hard limit;
- issue Manager/Research tickets;
- delegate bounded spawn budgets to Managers or Research agents;
- reclaim expired/dead tickets after lease validation;
- close the round.

Primary must not manufacture 20 sessions by default. It chooses the smallest useful parallel set and expands when evidence/help requests justify it.

### Manager/Reviewer

A Manager may create child Manager or Research tickets only from an explicit delegated budget in the current round. It may request more capacity through `SPAWN_REQUEST` without suspending its current assignment.

Typical delegated budget: 1-4 child sessions.

### Research

A Research agent continues its original assignment. When a bounded uncertainty materially benefits from help, it may publish `HELP_REQUEST` and, if it has delegated spawn budget, create 1-2 Research helper tickets. Helpers return evidence and then resume/close according to their ticket. Research cannot create Primary authority.

This is consistent with `HELP_REQUEST_NON_PREEMPTION_POLICY_V1`: requesting help never implicitly transfers or suspends the requester's lane.

## Generic human entry prompts

### Start a round

`Start a new Duo Open research round. Use the AgentBus/message forum for all required context, current state, role assignment, and coordination.`

The receiving chat must read discovery/bootstrap first, then create or join the round. It must not ask the human to relay internal context that already exists in AgentBus.

### Join an existing round

`Join the current Duo Open research round. Bootstrap from AgentBus and claim one valid open launch ticket. Use the ticket for your role and assignment.`

Every manually or automatically spawned child chat can receive the same join prompt. The ticket itself carries role/context.

## Spawn Adapter contract

A Spawn Adapter consumes unfulfilled `SPAWN_TICKET`s and, for each ticket:

1. verifies round OPEN and active count < 20;
2. acquires/reserves a controller slot;
3. opens a new independent ChatGPT conversation;
4. submits the generic join prompt (optionally with `round_id` and `ticket_id` for deterministic claim);
5. waits for `SESSION_STARTED`/ticket claim evidence;
6. marks actuation success/failure durably;
7. never fabricates success if UI/session creation is not observable.

Supported capability states:

- `SUPPORTED_NATIVE` — official session-creation primitive exists;
- `SUPPORTED_HOST_AUTOMATION` — browser/desktop/Work automation has been explicitly validated;
- `MANUAL_FALLBACK` — user opens chats; agents still self-assign from tickets;
- `UNAVAILABLE` — no actuation path; tickets remain pending.

V1 must report the actual state. Current normal-chat capability is `MANUAL_FALLBACK` unless a host adapter is separately validated.

## Help requests and recursive expansion

A working agent may request help without stopping its own work. `HELP_REQUEST` should state:

- question/problem;
- requested helper count;
- skill/role;
- bounded subtask;
- expected evidence;
- advisory vs blocking;
- return-to-original-lane behavior.

Manager/Primary or a delegated-capacity holder converts justified requests into tickets until the 20-session ceiling is reached. Excess requests queue; they do not evict productive sessions unless Primary explicitly reschedules them.

## Round completion

Before round close, Primary reconciles:

- all ticket claims;
- all released/expired sessions;
- all Manager dispositions;
- all Research handoffs;
- unresolved HELP_REQUESTs;
- outstanding production/field blockers.

Primary writes `ROUND_CLOSE` and releases remaining ephemeral locks. Immutable messages/evidence remain.

## Safety and correctness rules

- UI chat creation is never inferred from a ticket alone.
- Max 20 is concurrent sessions, not total historical tickets.
- No Research/Manager spawn changes production authority.
- No implicit preemption.
- No duplicate lane unless deliberate independent corroboration/falsification.
- Spawned sessions always bootstrap from current AgentBus and current GitHub HEAD; prompts should not carry stale project context.
- If round/controller state is contradictory, fail closed and request Manager/Primary reconciliation rather than spawning more sessions.
