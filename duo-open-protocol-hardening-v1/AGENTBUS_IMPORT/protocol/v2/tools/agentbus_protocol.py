#!/usr/bin/env python3
"""Reference implementation for Duo Open AgentBus protocol-hardening V2 draft.

No external dependencies. This module does not perform GitHub writes, authority
checks, identity resolution, or production integration.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class ProtocolError(ValueError):
    pass


class IdempotencyConflict(ProtocolError):
    pass


class CausalConflict(ProtocolError):
    pass


def _assert_hashable_json(value: Any, path: str = "$") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        raise ProtocolError(f"DUO-CJSON-1 rejects floating point at {path}")
    if isinstance(value, list):
        for i, item in enumerate(value):
            _assert_hashable_json(item, f"{path}[{i}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ProtocolError(f"DUO-CJSON-1 requires string object keys at {path}")
            _assert_hashable_json(item, f"{path}.{key}")
        return
    raise ProtocolError(f"DUO-CJSON-1 rejects {type(value).__name__} at {path}")


def canonical_json_bytes(value: Any) -> bytes:
    _assert_hashable_json(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest_value(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def digest_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def semantic_material(event: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "event_kind": event["event_kind"],
        "entity_key": event["entity_key"],
        "payload": event["payload"],
    }


def semantic_digest(event: Mapping[str, Any]) -> str:
    return digest_value(semantic_material(event))


def expected_idempotency_key(event: Mapping[str, Any]) -> str:
    scope = event.get("idempotency", {}).get("scope")
    if not isinstance(scope, str) or not scope:
        raise ProtocolError("idempotency.scope is required and must be non-empty")
    sem = semantic_digest(event)
    return digest_value({"scope": scope, "semantic_digest": sem})


def _parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ProtocolError("recorded_at_utc must use UTC Z notation")
    try:
        dt = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ProtocolError(f"invalid UTC timestamp: {value}") from exc
    if dt.tzinfo is None or dt.utcoffset() != timezone.utc.utcoffset(dt):
        raise ProtocolError("timestamp must be UTC")
    return dt


def validate_event(event: Mapping[str, Any]) -> None:
    required = {
        "schema",
        "event_id",
        "event_kind",
        "entity_key",
        "recorded_at_utc",
        "stream",
        "idempotency",
        "causality",
        "payload",
    }
    missing = sorted(required - set(event))
    if missing:
        raise ProtocolError(f"event missing required fields: {missing}")
    if event["schema"] != "duoopen-agentbus/persisted-event-v2":
        raise ProtocolError("unexpected event schema")
    if not isinstance(event["event_id"], str) or not event["event_id"]:
        raise ProtocolError("event_id must be non-empty")
    if not isinstance(event["event_kind"], str) or not re.match(r"^[A-Z][A-Z0-9_]*$", event["event_kind"]):
        raise ProtocolError("event_kind must be upper snake case")
    if not isinstance(event["entity_key"], str) or not event["entity_key"]:
        raise ProtocolError("entity_key must be non-empty")
    _parse_utc(event["recorded_at_utc"])

    stream = event["stream"]
    if not isinstance(stream, dict) or not isinstance(stream.get("id"), str) or not stream["id"]:
        raise ProtocolError("stream.id must be non-empty")
    if not isinstance(stream.get("seq"), int) or isinstance(stream.get("seq"), bool) or stream["seq"] < 1:
        raise ProtocolError("stream.seq must be an integer >= 1")

    idem = event["idempotency"]
    if not isinstance(idem, dict):
        raise ProtocolError("idempotency must be an object")
    for field in ("key", "semantic_digest"):
        if not isinstance(idem.get(field), str) or not DIGEST_RE.match(idem[field]):
            raise ProtocolError(f"idempotency.{field} must be sha256:<hex>")
    if not isinstance(idem.get("scope"), str) or not idem["scope"]:
        raise ProtocolError("idempotency.scope is required")
    calculated_semantic = semantic_digest(event)
    if idem["semantic_digest"] != calculated_semantic:
        raise ProtocolError("idempotency.semantic_digest does not match semantic event content")
    calculated_key = expected_idempotency_key(event)
    if idem["key"] != calculated_key:
        raise ProtocolError("idempotency.key does not match scope + semantic digest")

    causality = event["causality"]
    if not isinstance(causality, dict):
        raise ProtocolError("causality must be an object")
    lamport = causality.get("lamport")
    if not isinstance(lamport, int) or isinstance(lamport, bool) or lamport < 1:
        raise ProtocolError("causality.lamport must be an integer >= 1")
    parents = causality.get("parents")
    if not isinstance(parents, list) or any(not isinstance(p, str) or not p for p in parents):
        raise ProtocolError("causality.parents must be a list of event ids")
    if len(parents) != len(set(parents)):
        raise ProtocolError("causality.parents must be unique")
    if event["event_id"] in parents:
        raise ProtocolError("event cannot be its own causal parent")
    observed = causality.get("observed")
    if not isinstance(observed, dict):
        raise ProtocolError("causality.observed must be an object")
    for stream_id, seq in observed.items():
        if not isinstance(stream_id, str) or not stream_id:
            raise ProtocolError("observed stream ids must be non-empty strings")
        if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
            raise ProtocolError("observed stream positions must be integers >= 0")
    own_observed = observed.get(stream["id"], 0)
    if own_observed > stream["seq"] - 1:
        raise ProtocolError("event cannot claim to have observed a future position in its own stream")


def make_event(
    *,
    event_id: str,
    event_kind: str,
    entity_key: str,
    stream_id: str,
    stream_seq: int,
    lamport: int,
    scope: str,
    payload: Any,
    parents: Optional[Sequence[str]] = None,
    observed: Optional[Mapping[str, int]] = None,
    recorded_at_utc: str = "2026-10-03T00:00:00Z",
    retention_class: str = "canonical",
) -> Dict[str, Any]:
    event: Dict[str, Any] = {
        "schema": "duoopen-agentbus/persisted-event-v2",
        "event_id": event_id,
        "event_kind": event_kind,
        "entity_key": entity_key,
        "recorded_at_utc": recorded_at_utc,
        "stream": {"id": stream_id, "seq": stream_seq},
        "idempotency": {"key": "", "semantic_digest": "", "scope": scope},
        "causality": {
            "lamport": lamport,
            "parents": list(parents or []),
            "observed": dict(observed or {}),
        },
        "payload": payload,
        "retention_class": retention_class,
    }
    event["idempotency"]["semantic_digest"] = semantic_digest(event)
    event["idempotency"]["key"] = expected_idempotency_key(event)
    validate_event(event)
    return event


@dataclass(frozen=True)
class LedgerEntry:
    key: str
    semantic_digest: str
    first_event_id: str
    first_seen_at_utc: str


class IdempotencyLedger:
    def __init__(self) -> None:
        self._entries: Dict[str, LedgerEntry] = {}

    def check_or_record(self, event: Mapping[str, Any]) -> str:
        validate_event(event)
        idem = event["idempotency"]
        key = idem["key"]
        sem = idem["semantic_digest"]
        existing = self._entries.get(key)
        if existing is None:
            self._entries[key] = LedgerEntry(
                key=key,
                semantic_digest=sem,
                first_event_id=event["event_id"],
                first_seen_at_utc=event["recorded_at_utc"],
            )
            return "accepted"
        if existing.semantic_digest != sem:
            raise IdempotencyConflict(
                f"idempotency key {key} reused with different semantic digest"
            )
        return "replay"

    def export(self) -> List[Dict[str, Any]]:
        out = []
        for key in sorted(self._entries):
            item = self._entries[key]
            out.append(
                {
                    "schema": "duoopen-agentbus/idempotency-ledger-entry-v1",
                    "key": item.key,
                    "semantic_digest": item.semantic_digest,
                    "first_event_id": item.first_event_id,
                    "first_seen_at_utc": item.first_seen_at_utc,
                    "retention_class": "dedupe",
                }
            )
        return out


def causal_sort_key(event: Mapping[str, Any]) -> Tuple[int, str, int, str]:
    return (
        int(event["causality"]["lamport"]),
        str(event["stream"]["id"]),
        int(event["stream"]["seq"]),
        str(event["event_id"]),
    )


class CausalStore:
    """Conservative causal buffer with contiguous per-stream application."""

    def __init__(
        self,
        *,
        frontier: Optional[Mapping[str, int]] = None,
        covered_event_ids: Optional[Iterable[str]] = None,
    ) -> None:
        self.frontier: Dict[str, int] = dict(frontier or {})
        self.covered_event_ids = set(covered_event_ids or [])
        self.ledger = IdempotencyLedger()
        self.applied: Dict[str, Dict[str, Any]] = {}
        self.applied_order: List[str] = []
        self.pending: Dict[str, Dict[str, Any]] = {}

    def _parent_ready(self, parent_id: str) -> bool:
        return parent_id in self.applied or parent_id in self.covered_event_ids

    def _ready(self, event: Mapping[str, Any]) -> bool:
        stream = event["stream"]
        expected_seq = self.frontier.get(stream["id"], 0) + 1
        if stream["seq"] != expected_seq:
            return False
        return all(self._parent_ready(parent) for parent in event["causality"]["parents"])

    def _apply(self, event: Mapping[str, Any]) -> None:
        event_id = event["event_id"]
        if event_id in self.applied:
            return
        stream = event["stream"]
        expected_seq = self.frontier.get(stream["id"], 0) + 1
        if stream["seq"] != expected_seq:
            raise CausalConflict(
                f"stream {stream['id']} expected seq {expected_seq}, got {stream['seq']}"
            )
        for parent_id in event["causality"]["parents"]:
            parent = self.applied.get(parent_id)
            if parent is not None and parent["causality"]["lamport"] >= event["causality"]["lamport"]:
                raise CausalConflict(
                    f"parent {parent_id} must have lower Lamport clock than child {event_id}"
                )
        frozen = copy.deepcopy(dict(event))
        self.applied[event_id] = frozen
        self.applied_order.append(event_id)
        self.frontier[stream["id"]] = stream["seq"]
        self.pending.pop(event_id, None)

    def offer(self, event: Mapping[str, Any]) -> str:
        validate_event(event)
        event_id = str(event["event_id"])
        if event_id in self.applied:
            return "replay"
        if event_id in self.pending:
            existing = self.pending[event_id]
            if digest_value(existing) != digest_value(event):
                raise CausalConflict(f"event_id {event_id} reused with different content")
            return "pending"

        idem_result = self.ledger.check_or_record(event)
        if idem_result == "replay":
            # A different event id with the same semantic operation is a no-op.
            return "replay"

        self.pending[event_id] = copy.deepcopy(dict(event))
        if self._ready(event):
            self._apply(event)
            self._drain()
            return "applied"
        return "pending"

    def _drain(self) -> None:
        while True:
            ready = [event for event in self.pending.values() if self._ready(event)]
            if not ready:
                return
            ready.sort(key=causal_sort_key)
            for event in ready:
                if self._ready(event):
                    self._apply(event)

    def canonical_events(self) -> List[Dict[str, Any]]:
        return [copy.deepcopy(self.applied[event_id]) for event_id in self.applied_order]



def get_path(value: Mapping[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise ProtocolError(f"missing path {path}")
        current = current[part]
    return current


def project_paths(value: Mapping[str, Any], paths: Sequence[str]) -> Any:
    if not paths:
        return value["event_id"]
    if len(paths) == 1:
        return get_path(value, paths[0])
    return {path: get_path(value, path) for path in paths}


def _index_keys(event: Mapping[str, Any], spec: Mapping[str, Any]) -> List[str]:
    key_paths = spec["key_paths"]
    if spec.get("explode_array_key"):
        if len(key_paths) != 1:
            raise ProtocolError("explode_array_key requires exactly one key path")
        raw = get_path(event, key_paths[0])
        if not isinstance(raw, list):
            raise ProtocolError("explode_array_key path must resolve to a list")
        return [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in raw]
    raw_parts = [get_path(event, path) for path in key_paths]
    return [json.dumps(raw_parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))]


def _filter_matches(event: Mapping[str, Any], filter_spec: Mapping[str, Any]) -> bool:
    for path, expected in filter_spec.items():
        try:
            actual = get_path(event, path)
        except ProtocolError:
            return False
        if actual != expected:
            return False
    return True


def build_materialized_index(
    events: Sequence[Mapping[str, Any]], spec: Mapping[str, Any]
) -> Dict[str, Any]:
    if spec.get("schema") != "duoopen-agentbus/materialized-index-v1":
        raise ProtocolError("unexpected materialized index schema")
    reducer = spec["reducer"]
    if reducer not in {"unique", "append", "latest", "max"}:
        raise ProtocolError(f"unsupported reducer: {reducer}")

    result: Dict[str, Any] = {}
    ordered = sorted(events, key=causal_sort_key)
    for event in ordered:
        validate_event(event)
        if not _filter_matches(event, spec.get("filter", {})):
            continue
        value = project_paths(event, spec["value_paths"])
        for key in _index_keys(event, spec):
            if reducer == "unique":
                if key in result and result[key] != value:
                    raise ProtocolError(f"unique index conflict in {spec['index_id']} for key {key}")
                result[key] = copy.deepcopy(value)
            elif reducer == "append":
                result.setdefault(key, []).append(copy.deepcopy(value))
            elif reducer == "latest":
                result[key] = copy.deepcopy(value)
            elif reducer == "max":
                if not isinstance(value, int) or isinstance(value, bool):
                    raise ProtocolError("max reducer requires one integer value path")
                result[key] = max(result.get(key, value), value)
    return result


def build_index_catalog(
    events: Sequence[Mapping[str, Any]], catalog: Mapping[str, Any]
) -> Dict[str, Any]:
    if catalog.get("schema") != "duoopen-agentbus/materialized-index-catalog-v1":
        raise ProtocolError("unexpected index catalog schema")
    output: Dict[str, Any] = {}
    seen: set[str] = set()
    for spec in catalog.get("indexes", []):
        index_id = spec.get("index_id")
        if not isinstance(index_id, str) or not index_id:
            raise ProtocolError("index_id must be non-empty")
        if index_id in seen:
            raise ProtocolError(f"duplicate index_id {index_id}")
        seen.add(index_id)
        output[index_id] = build_materialized_index(events, spec)
    return output


class FsmEngine:
    def __init__(self, definition: Mapping[str, Any]) -> None:
        self.definition = copy.deepcopy(dict(definition))
        self._validate_definition()
        self.transitions: Dict[Tuple[str, str], Mapping[str, Any]] = {}
        for transition in self.definition["transitions"]:
            self.transitions[(transition["from"], transition["on"])] = transition

    def _validate_definition(self) -> None:
        d = self.definition
        if d.get("schema") != "duoopen-agentbus/fsm-definition-v1":
            raise ProtocolError("unexpected FSM definition schema")
        states = d.get("states")
        if not isinstance(states, list) or not states or len(states) != len(set(states)):
            raise ProtocolError("FSM states must be a non-empty unique list")
        state_set = set(states)
        if d.get("initial_state") not in state_set:
            raise ProtocolError("FSM initial_state is not declared")
        for terminal in d.get("terminal_states", []):
            if terminal not in state_set:
                raise ProtocolError(f"terminal state {terminal} is not declared")
        seen: set[Tuple[str, str]] = set()
        transition_ids: set[str] = set()
        for transition in d.get("transitions", []):
            if transition["id"] in transition_ids:
                raise ProtocolError(f"duplicate transition id {transition['id']}")
            transition_ids.add(transition["id"])
            if transition["from"] not in state_set or transition["to"] not in state_set:
                raise ProtocolError(f"transition {transition['id']} references undeclared state")
            key = (transition["from"], transition["on"])
            if key in seen:
                raise ProtocolError(
                    f"non-deterministic FSM: multiple transitions from {key[0]} on {key[1]}"
                )
            seen.add(key)

    @property
    def initial_state(self) -> str:
        return self.definition["initial_state"]

    def transition(self, state: str, event_name: str, context: Optional[Mapping[str, Any]] = None) -> Tuple[str, str]:
        transition = self.transitions.get((state, event_name))
        if transition is None:
            raise ProtocolError(f"no FSM transition from {state} on {event_name}")
        context = context or {}
        for predicate in transition.get("when", []):
            actual = get_path(context, predicate["path"])
            if actual != predicate["equals"]:
                raise ProtocolError(
                    f"FSM guard failed for {transition['id']}: {predicate['path']} != {predicate['equals']!r}"
                )
        return transition["to"], transition["id"]



def build_snapshot_manifest(
    *,
    snapshot_id: str,
    created_at_utc: str,
    protocol_lock_digest: str,
    events: Sequence[Mapping[str, Any]],
    index_catalog_materialization: Mapping[str, Any],
    dedupe_entries: Sequence[Mapping[str, Any]],
    previous_snapshot_digest: Optional[str],
) -> Dict[str, Any]:
    _parse_utc(created_at_utc)
    if not DIGEST_RE.match(protocol_lock_digest):
        raise ProtocolError("protocol_lock_digest must be sha256:<hex>")
    if previous_snapshot_digest is not None and not DIGEST_RE.match(previous_snapshot_digest):
        raise ProtocolError("previous_snapshot_digest must be sha256:<hex> or null")

    frontier: Dict[str, int] = {}
    for event in events:
        validate_event(event)
        stream = event["stream"]
        frontier[stream["id"]] = max(frontier.get(stream["id"], 0), stream["seq"])

    sections = [
        {
            "name": "canonical-events",
            "digest": digest_value(list(events)),
            "retention_class": "canonical",
            "record_count": len(events),
        },
        {
            "name": "materialized-indexes",
            "digest": digest_value(index_catalog_materialization),
            "retention_class": "derived",
            "record_count": len(index_catalog_materialization),
        },
        {
            "name": "idempotency-ledger",
            "digest": digest_value(list(dedupe_entries)),
            "retention_class": "dedupe",
            "record_count": len(dedupe_entries),
        },
    ]
    manifest: Dict[str, Any] = {
        "schema": "duoopen-agentbus/snapshot-manifest-v1",
        "snapshot_id": snapshot_id,
        "created_at_utc": created_at_utc,
        "protocol_lock_digest": protocol_lock_digest,
        "source_frontier": dict(sorted(frontier.items())),
        "event_count": len(events),
        "sections": sections,
        "previous_snapshot_digest": previous_snapshot_digest,
        "snapshot_digest": "sha256:" + "0" * 64,
    }
    content_for_digest = dict(manifest)
    content_for_digest.pop("snapshot_digest")
    manifest["snapshot_digest"] = digest_value(content_for_digest)
    return manifest


def verify_lock(lock_path: Path) -> List[Tuple[str, str]]:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("schema") != "duoopen-agentbus/protocol-lock-v1":
        raise ProtocolError("unexpected protocol lock schema")
    base = lock_path.parent
    verified: List[Tuple[str, str]] = []
    seen: set[str] = set()
    for artifact in lock.get("artifacts", []):
        rel = artifact.get("path")
        expected = artifact.get("sha256")
        if not isinstance(rel, str) or not rel or rel.startswith("/") or ".." in Path(rel).parts:
            raise ProtocolError(f"unsafe lock path: {rel!r}")
        if rel in seen:
            raise ProtocolError(f"duplicate lock path: {rel}")
        seen.add(rel)
        if not isinstance(expected, str) or not DIGEST_RE.match(expected):
            raise ProtocolError(f"invalid lock digest for {rel}")
        path = base / rel
        if not path.is_file():
            raise ProtocolError(f"locked artifact missing: {rel}")
        actual = digest_file(path)
        if actual != expected:
            raise ProtocolError(f"locked artifact digest mismatch for {rel}: expected {expected}, got {actual}")
        verified.append((rel, actual))
    if not verified:
        raise ProtocolError("protocol lock contains no artifacts")
    return verified


def _cmd_verify_lock(args: argparse.Namespace) -> int:
    verified = verify_lock(Path(args.lockfile).resolve())
    for path, digest in verified:
        print(f"OK {digest} {path}")
    print(f"VERIFIED {len(verified)} artifacts")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify-lock", help="verify every artifact pinned by PROTOCOL.lock.json")
    verify.add_argument("lockfile")
    verify.set_defaults(func=_cmd_verify_lock)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
