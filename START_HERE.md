# START HERE — Duo Open Full AgentBus Snapshot Deployment

This is a **human-deployed, root-safe snapshot package**. Extract at the repository root. It does not perform a Git write itself.

Current Git `main` used for packaging: `7c5942e986b1f0e80b1b469c77642c948493db1b`.

## Full message-board backup

The package contains a byte-for-byte reconstruction copy of the complete AgentBus forum under:

`DEPLOYMENT_METADATA/AGENTBUS_SNAPSHOT/messages/`

Snapshot facts:
- **803 total forum members** (`802 JSON + 1 Markdown`).
- **1,846,858 bytes** of raw forum payload.
- Count basis is **all files under `/DuoOpen-AgentBus/messages/`**, not JSON-only.
- Verified base: 698 members through `2026-10-03T03:42:52Z` from `DUO_OPEN_PRIMARY_AGENT_V8_ROUND_ORCHESTRATION.zip`.
- Live delta: 105 unique members added after the base snapshot.
- Final live-board sweep cutoff: `2026-10-03T08:26:44Z`.
- Exact-set SHA-256: `04c77ab10de8006993afab68bb251144bd42d11c25b468bf049bcf6d7ae22fd8`.
- `AGENTBUS_SNAPSHOT_COMPLETE=true`.

The historical non-JSON forum member is preserved byte-for-byte:
`20261002T041521Z__rnd-5da10562da90496f__primary__HANDOFF_SHIZUKU_BITMAP_LIFETIME.md`

## Verification files

- `DEPLOYMENT_METADATA/AGENTBUS_SNAPSHOT/SNAPSHOT_MANIFEST.json` — exact per-member inventory, byte length, SHA-256, context inventory, lineage and cutoff.
- `DEPLOYMENT_METADATA/AGENTBUS_SNAPSHOT/SNAPSHOT_SHA256SUMS.txt` — hashes for the complete packaged snapshot tree.
- `DEPLOYMENT_METADATA/AGENTBUS_SNAPSHOT/LIVE_DELTA_RECONCILIATION.json` — base + live-delta enumeration/reconciliation proof.
- `DEPLOYMENT_METADATA/MANIFEST.json` — package-level inventory.
- `SHA256SUMS.txt` — package-level hashes.

## Protocol/context backup

`DEPLOYMENT_METADATA/AGENTBUS_SNAPSHOT/protocol_context/current/` contains the applicable message creation, DMSH, review, persistence, regression, learning, communication-autonomy, human-interaction, round-orchestration, anti-overengineering, and succession context needed to reconstruct how the board was produced.

## Current engineering disposition

This package carries the current Manager-organized research summary but **does not add Android runtime changes**. Git compare from `7127c287a17fd97050c98fbeb05a38f7318f2f64` to `7c5942e986b1f0e80b1b469c77642c948493db1b` shows only process/deployment/AgentBus changes.

The next bounded Android candidate remains tickets **02 + 03 + 04**: attempt-scoped INNER wake lifetime, exact-current presentation/readiness evidence, and terminal/native-cover stale-work fencing. CI and physical Fold7 validation remain hard gates.

Tickets 05/09 remain orthogonal/follow-on. Tickets 06/07/08 remain physical-evidence/prototype gated. Ticket 10 is a legitimate process candidate but remains separately activation-gated.

## Restore / successor rule

A successor should verify `SNAPSHOT_MANIFEST.json` first, load the packaged forum/context, then read live AgentBus traffic **newer than `2026-10-03T08:26:44Z`** and reconcile that delta before making current decisions.

## Commit boundary

`PRIMARY_ACCEPTED -> INTEGRATION_CANDIDATE_READY -> FINAL_RECONCILIATION_PASS -> COMMIT_PACKAGE_READY -> HUMAN_COMMIT_AUTHORIZATION -> SINGLE_WRITER_COMMIT -> POST_COMMIT_VALIDATION -> PRODUCTION_ACCEPTED`
