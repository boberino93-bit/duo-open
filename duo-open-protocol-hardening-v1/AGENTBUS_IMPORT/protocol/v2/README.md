# Duo Open AgentBus Protocol Hardening V2 — Draft, Not Activated

This package implements the storage/protocol hardening work that is intentionally separable from production authority, agent identity, branch protection, commit permissions, and human approval gates.

It is **not wired into `AGENT_DISCOVERY.json`, bootstrap order, `main`, or any production acceptance path**. It is designed to be reviewed and applied on a non-production branch only after a human-controlled branch boundary exists.

## Scope implemented here

- deterministic FSM definition and instance schemas;
- idempotency keys and a durable deduplication ledger;
- causal ordering with stream sequence numbers, Lamport clocks, explicit parents, and observed stream frontiers;
- deterministic materialized-index definitions and rebuild logic;
- snapshot manifests and source-frontier capture;
- retention tiers for canonical, derived, ephemeral, and dedupe data;
- a protocol lockfile that pins exact SHA-256 digests of every protocol artifact;
- a dependency-free Python reference implementation and tests.

## Compatibility model

The persisted-event envelope treats the existing immutable AgentBus message as opaque payload. Existing fields such as `schema`, `from`, `to`, `kind`, `subject`, and `body` remain inside `payload` and are not reinterpreted here.

A V2 persisted event has five invariants:

1. **Stable retry identity.** `idempotency.key` is derived from the semantic operation, not from retry time or transport details.
2. **Conflict detection.** Reusing an idempotency key with a different semantic digest is an error, never an overwrite.
3. **Causal application.** An event is materialized only when its stream predecessor and every explicit parent are present or covered by a trusted snapshot frontier.
4. **Derived state is rebuildable.** Materialized indexes are deterministic projections of canonical events plus a pinned protocol lock.
5. **Snapshots are anchored.** Every snapshot records the exact event frontier, protocol lock digest, prior snapshot digest, and content digests for included sections.

## Canonical hashing

The reference tooling uses `DUO-CJSON-1`:

- UTF-8 JSON;
- object keys sorted lexicographically;
- separators are `,` and `:` with no insignificant whitespace;
- only `null`, booleans, integers, strings, arrays, and objects are accepted for hashed semantic material;
- floating-point numbers are rejected from hashed semantic material to avoid cross-runtime representation drift.

Digest form is `sha256:<64 lowercase hex characters>`.

## Causal model

Each event carries:

- `stream.id` and contiguous `stream.seq`;
- `causality.lamport`;
- zero or more explicit parent event IDs;
- an `observed` map of stream IDs to the highest sequence observed when the event was created.

The apply rule is conservative: missing parents or a stream gap make the event pending. Pending events become eligible when their dependencies arrive. Concurrent events are allowed across independent streams, but a single stream remains contiguous and deterministic.

## Retention model

Retention does not silently destroy canonical history. Canonical events move from hot to warm to cold storage but remain retained unless a human-approved policy later supersedes this draft. Derived indexes are rebuildable and may be rotated aggressively. Ephemeral service/checkpoint data may compact to digests. Idempotency evidence keeps a digest-level tombstone indefinitely so an old retry cannot resurrect as a new operation after payload compaction.

## Validation

Run from this directory:

```bash
python -m unittest discover -s tests -v
python tools/agentbus_protocol.py verify-lock PROTOCOL.lock.json
```

The reference implementation is intentionally standard-library-only.
