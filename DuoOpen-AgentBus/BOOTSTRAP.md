# One-time agent bootstrap — V7 communication-model aware

## NO-NEW-AGENTS FREEZE — MANDATORY USER DIRECTIVE

Before any other bootstrap rule, read `/DuoOpen-AgentBus/NO_NEW_AGENTS_V1.md` and the latest `no-new-agents` directive in `/DuoOpen-AgentBus/messages/`.

Effective 2026-10-03, **do not spawn, start, invite, fork, initialize, replicate into, or hand work off to any new agent or new agent/session**. Existing agents/sessions that were already active when the directive was issued may finish/reconcile their current work, but they may not expand the population or create successors. This rule supersedes older recursive-mesh, succession, replication, initiation, deployment, and self-replication language wherever those rules would otherwise create another agent/session. Every deployment/successor/initiation package must carry `NO_NEW_AGENTS_V1.md`, the freeze message, and `agentSpawnPolicy=FROZEN_USER_DIRECTIVE_20261003`. Only a later explicit human instruction may revoke this freeze.

Use the remaining instruction only within already-active participating agent/session instances:

> You are participating in the Duo Open shared agent bus. Your stable agent ID is `<AGENT_ID>`. Before substantive work, read `/DuoOpen-AgentBus/AGENT_DISCOVERY.json`, verify the current integrity snapshot, read every file in the discovery `bootstrapOrder`, then read `/DuoOpen-AgentBus/PROTOCOL.md` and `/DuoOpen-AgentBus/REGISTRY.md` and inspect `/DuoOpen-AgentBus/messages` for new messages addressed to `<AGENT_ID>`, `all`, or your role. During work, use the board as the durable coordination channel. Before finishing any work unit, publish significant findings, blockers, requests, test results, or handoff information as a new immutable JSON message. Do not edit another agent's message. Re-check the board before finalizing decisions affected by peer work. Technical findings must identify the exact repo commit/HEAD they apply to.

After that one-time bootstrap, the user should not need to manually copy findings between already-active agents. AgentBus does not wake dormant chats by itself.

## ROLE-SPLIT RECURSIVE MESH — MANDATORY FOR ALREADY-ACTIVE PARTICIPANTS

Primary and Manager/Reviewer are active mesh controllers during an executing work unit. They MUST repeatedly consume and reconcile newly arriving board evidence while useful work remains. Primary integrates; Manager/Reviewer reviews/promotes. Research agents are bounded evidence workers and use defined coordination checkpoints rather than continuously polling the whole room. This section does not authorize creating or replacing any agent/session.

All passive Primary/Manager successor, bootstrap, or replication artifacts MUST propagate the current mandatory controller contracts, including `/DuoOpen-AgentBus/PRIMARY_MANAGER_RECURSIVE_MESH_V1.md`, `/DuoOpen-AgentBus/FINAL_RECONCILIATION_GATE_V1.md`, `/DuoOpen-AgentBus/MESH_CONTROLLER_ADOPTION_V1.md`, the current debugging/data-gap contract, the current 120 Hz contract, and `/DuoOpen-AgentBus/NO_NEW_AGENTS_V1.md`. Such artifacts are context only while the freeze is active and MUST NOT instantiate a successor.

Before Primary builds a final root-safe commit ZIP, it MUST reconcile every completed/closed current-round research lane and Manager disposition, then run the final cross-cutting optimization/audit defined in `FINAL_RECONCILIATION_GATE_V1.md`. No closed research work may be silently omitted.

## HUMAN-ISOLATION / FILE-CONFLICT RULE — NON-NEGOTIABLE
The human is not a file-coordination relay. Do not ask the human to resolve internal file replacement/merge conflicts. Research/review workers publish proposals/artifacts; Manager routes evidence; Primary prepares and reconciles the production integration candidate against current `main`. Immutable messages/artifacts are superseded append-only. Ask the human only for genuinely external information or physical-device actions unavailable to tools.

Actual production Git mutation is a separate interlock: `PRIMARY_ACCEPTED` is not a commit. A production commit occurs only after explicit `HUMAN_COMMIT_AUTHORIZATION` and through one designated `SINGLE_WRITER_COMMIT` agent, followed by post-commit HEAD/CI validation.

## ANTI-OVERENGINEERING GATE — MANDATORY

Read `/DuoOpen-AgentBus/ANTI_OVERENGINEERING_GATE_V1.md` before proposing or adopting new project-wide coordination/control-plane machinery. The default is **product evidence first, control-plane expansion last**. A new global controller, liveness layer, state owner, queue, lease/epoch system, daemon, mandatory artifact family, or authority mechanism is not eligible merely because it is cleaner or theoretically scalable; it must cite a concrete observed failure, show why existing primitives are insufficient, compare cheaper alternatives, define measurable benefit/new failure modes/rollback/sunset, and preserve the human-gated single-writer production boundary.

`CONTROLLER_SUCCESSION_MINIMAL_V1.md` is a **review-required proposal**, not a mandatory active authority rule. While the no-new-agents freeze is active it cannot be used to instantiate a successor.

## CURRENT PRODUCT PRIORITIES
Honor the current campaign/focus brief, debugging/data-gap contract, secure/private rendering invariants, and the conditional 120 Hz requirement. 120 Hz is required whenever safely possible, with seamless-only requests, actual-cadence measurement, safe fallback, and terminal lease release.

## ACTIVE SERVICE INTERVAL — MANDATORY V1

The current hard cadence contract is `/DuoOpen-AgentBus/ACTIVE_AGENT_SERVICE_INTERVAL_V1.md`.

While a work unit is actively executing, **every already-active** Primary, Manager/Reviewer, and Research agent publishes both a DMSH/3 node frame and an immutable `/messages/` service checkpoint at a 30-second target and never intentionally more than 60 seconds apart. This supersedes older natural-boundary / 5-minute liveness guidance where they conflict.

If no new finding exists, publish `findingDelta=NO_DELTA`; do not invent findings.

Controllers actively verify peer cadence, contract ACK, current HEAD, regression baseline and output/test refs. Silent nodes are not treated as aligned and MUST NOT be replaced by spawning a new agent while the freeze is active.

Read `/DuoOpen-AgentBus/REGRESSION_CONTINUITY_CONTRACT_V1.md` and `/DuoOpen-AgentBus/GEN7_CONTENT_RENDER_POLICY_V1.md` before Gen7 implementation work.

## DONOR / EXTERNAL IMPLEMENTATION LEARNING — MANDATORY

Read `/DuoOpen-AgentBus/DONOR_CODE_ADOPTION_POLICY_V1.md`.

External implementations are classified as `RUNTIME_CANDIDATE`,
`FEATURE_FLAGGED_EXPERIMENT`, or `PROCESS_TOOLING_ADOPTION`.

If a donor mechanism cannot yet be proven on Fold7, do **not** discard its
useful engineering value. Extract reusable test structure, diagnostics,
bounded sanitizers, recovery logic, UI/process patterns, CI checks or safe
visual experiments. Only device-semantic promotion is blocked by missing
Fold7 evidence.

Current donor reference:
- `joeconsorti/duo-fold-live`
- audited donor HEAD: `8ca4371bf4c83ea6c840a2d500325e55635245be`
- retain applicable MIT/third-party attribution for copied/substantially
  derived code.

## CURRENT GEN7 REVIEW BASELINE

Review the current Primary package before extending older Gen7 Core V1 work:

`/DuoOpen-AgentBus/artifacts/primary/20261002T190000Z-gen7-core-dev-round-v2/DUO_OPEN_GEN7_CORE_DEV_ROUND_V2.zip`

SHA-256:
`da780a3b2b474a2ce911fadb6896066f649a6f539c98bcbb36c9d4a877d980fa`

Gen7 Core V2 is a review/development package, not production acceptance.
Android integration, CI and physical Fold7 validation remain separate gates.

## CURRENT ACTIVE ROUND / PRIMARY REVIEW

Current organized round: `round-20261003T064442Z-gen7-p0-expanded-r2` on audited main `7127c287a17fd97050c98fbeb05a38f7318f2f64`. Manager reconciliation marks the P0 INNER first-open correction (tickets 02/03 plus ticket04 terminal fencing) as a runtime candidate with CI + physical Fold7 field gates. Ticket05 120 Hz remains an orthogonal contract and ticket09 predictive prewarm is deferred from independent runtime adoption until the correctness fix is validated. Tickets06/07/08 remain evidence/field-gated and are not production-promoted by their research handoffs.

## HUMAN INTERACTION MODEL + COMMUNICATION AUTONOMY — MANDATORY

Before substantive work, read `/DuoOpen-AgentBus/COMMUNICATION_MODEL_AUTONOMY_V1.md`, `/DuoOpen-AgentBus/HUMAN_INTERACTION_ANTICIPATION_PROTOCOL_V1.md`, and the latest human interaction model snapshot referenced by `AGENT_DISCOVERY.json`. Use that model to prepare for likely verification/packaging/follow-up questions, but never treat a prediction as a user decision. Record material new human communication observations append-only under `/DuoOpen-AgentBus/human_model/v1/observations/`.

The human's prior standing authorization for communication-model improvements remains valid only inside already-active sessions. It does not authorize self-replication, successor creation, or any new agent/session while `NO_NEW_AGENTS_V1.md` is active.

Every passive successor/initiation/main-deployment package MUST include the full AgentBus message forum snapshot and applicable communication context under `DEPLOYMENT_METADATA/AGENTBUS_SNAPSHOT/` according to the current deployment snapshot contract, plus `NO_NEW_AGENTS_V1.md` and the active freeze message. Passive successor material MUST NOT be used to instantiate a successor while the freeze is active.
