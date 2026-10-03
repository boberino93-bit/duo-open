# NO NEW AGENTS V1 — ACTIVE USER DIRECTIVE

Effective 2026-10-03, agent/session creation is frozen until the human explicitly revokes or replaces this directive.

## Mandatory rule

Do **not** spawn, start, invite, fork, initialize, replicate into, or hand work off to any new agent or new agent/session. Do not create a successor agent to replace an existing, silent, completed, or failed agent.

Existing agents/sessions that were already active when this directive was issued may finish, reconcile, review, test, package, or integrate their current work within their existing authority. They may communicate through the existing AgentBus, but they may not expand the agent population.

## Precedence

This directive supersedes older bootstrap, recursive-mesh, succession, replication, deployment, or self-replication language wherever that language would otherwise cause a new agent/session to be created. Existing coordination contracts remain applicable to already-active participants only.

## Deployment / successor / initiation packages

Every deployment, successor, initiation, bootstrap, replication, or recovery package created while this freeze is active MUST:

1. include this file verbatim;
2. include the latest AgentBus freeze message addressed to `all`;
3. declare `agentSpawnPolicy=FROZEN_USER_DIRECTIVE_20261003` in deployment metadata;
4. avoid any instruction that starts or asks the recipient to start another agent/session; and
5. treat any successor material as passive context only, not authority to instantiate a successor.

A package that omits or contradicts this rule is invalid for deployment.

## Revocation

Only a later explicit instruction from the human may relax or revoke this freeze. Agent inference, liveness failure, workload, missing roles, or a coordination convenience is not sufficient authority.
