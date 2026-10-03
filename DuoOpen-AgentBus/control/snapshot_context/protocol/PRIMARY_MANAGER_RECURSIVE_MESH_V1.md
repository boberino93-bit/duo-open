# Duo Open Primary + Manager Recursive Mesh Contract v1

## Purpose

This contract defines the controlled recursive improvement loop for Duo Open.
It applies to active Primary and Manager/Reviewer work units. Research agents remain bounded evidence producers unless explicitly promoted to a controller role.

The loop is:

Research evidence -> Manager reconciliation -> Primary integration -> tests/field evidence -> process learning -> inherited controller rules -> next research round.

This is recursive process improvement, not autonomous model-weight modification and not background execution after a chat/session is dormant.

## Controller roles

### Primary
During an active work unit, Primary is the integration controller and MUST repeatedly:
1. fetch actual current GitHub `main`;
2. read new AgentBus findings, review decisions, contradictions, and completed handoffs;
3. independently revalidate adopted technical claims against current source/evidence;
4. reconcile compatible recommendations into the current implementation candidate;
5. run the strongest available static/model/CI checks;
6. publish changed assumptions, accepted/rejected findings, and blockers;
7. continue the loop while useful new research/Manager evidence is still arriving and the active turn remains executing.

Primary must not claim background activity after the active work turn ends.

### Manager / Reviewer
During an active work unit, Manager/Reviewer is a continuous quality controller and MUST repeatedly:
1. consume newly completed research work;
2. deduplicate overlapping findings;
3. identify contradictions and missing evidence;
4. request targeted peer/research follow-up where needed;
5. re-evaluate prior dispositions when stronger/newer evidence arrives;
6. publish READY / NEEDS_MORE_EVIDENCE / REJECT / SUPERSEDED dispositions with exact source HEAD/evidence refs;
7. continue reconciling while useful incoming research is active and the work turn remains executing.

Manager has no production-write authority and cannot bypass Primary acceptance.

## Research-agent behavior

Research agents are bounded workers, not continuous mesh controllers.
They MUST:
- check current mesh/board at startup;
- claim a focused lane;
- re-check before overlap-heavy work or a substantial prototype;
- publish findings/tests/contradictions promptly;
- re-check before final handoff;
- terminate/release the lane after durable handoff unless specifically asked for follow-up.

Research agents SHOULD NOT spend their context continuously polling the whole room.

## Recursive inheritance rule

When a Primary or Manager controller prepares a successor/bootstrap/replication artifact for Duo Open, it MUST propagate this controller contract and the current mandatory project contracts.

A successor controller must read and adopt:
- current AgentBus discovery/protocols;
- current campaign/focus brief;
- current debugging/data-gap contract;
- current 120 Hz conditional contract;
- this recursive mesh contract;
- final reconciliation gate contract.

No successor may silently drop inherited mandatory requirements.

## Evidence safety

Recursive incorporation is never automatic truth promotion.
Every adopted finding must preserve:
- originating message/artifact;
- evidence class (SOURCE / MODEL / CI / FIELD);
- applicable GitHub HEAD;
- independent revalidation status;
- Manager disposition;
- Primary decision.

A recursive lesson that conflicts with newer field/source evidence is superseded, not blindly inherited.

## Active-loop stop conditions

The active controller loop may stop when one of the following is true:
- relevant research/Manager lanes are closed and reconciled;
- remaining questions require physical-device evidence;
- no useful new board evidence is arriving during the active work turn;
- a hard external dependency blocks progress;
- the final reconciliation gate is ready to run.

## No-background-work boundary

AgentBus messages do not wake dormant chats. “Continuous” means continuously re-checking and reconciling while the controller's active work turn/session is actually executing.
