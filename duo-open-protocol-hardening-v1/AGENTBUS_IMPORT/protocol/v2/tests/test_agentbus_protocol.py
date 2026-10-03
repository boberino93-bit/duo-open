import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "agentbus_protocol.py"
spec = importlib.util.spec_from_file_location("agentbus_protocol", MODULE_PATH)
ap = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ap
assert spec.loader is not None
spec.loader.exec_module(ap)


class ProtocolTests(unittest.TestCase):
    def event(self, *, event_id, seq, lamport, payload, parents=(), stream="s1", scope=None):
        return ap.make_event(
            event_id=event_id,
            event_kind="MESSAGE_APPENDED",
            entity_key=f"message:{payload['id']}",
            stream_id=stream,
            stream_seq=seq,
            lamport=lamport,
            scope=scope or f"append:{payload['id']}",
            payload=payload,
            parents=list(parents),
            observed={stream: seq - 1},
            recorded_at_utc="2026-10-03T00:00:00Z",
        )

    def test_canonical_hash_rejects_float(self):
        with self.assertRaises(ap.ProtocolError):
            ap.digest_value({"x": 1.2})

    def test_idempotency_replay_is_noop(self):
        event = self.event(event_id="e1", seq=1, lamport=1, payload={"id": "m1", "body": "x"})
        store = ap.CausalStore()
        self.assertEqual(store.offer(event), "applied")

        retry = copy.deepcopy(event)
        retry["event_id"] = "e1-retry"
        retry["causality"]["lamport"] = 2
        retry["stream"]["seq"] = 2
        retry["causality"]["observed"]["s1"] = 1
        ap.validate_event(retry)
        self.assertEqual(store.offer(retry), "replay")
        self.assertEqual(store.frontier["s1"], 1)

    def test_idempotency_key_cannot_be_reused_for_different_semantics(self):
        event = self.event(event_id="e1", seq=1, lamport=1, payload={"id": "m1", "body": "x"})
        ledger = ap.IdempotencyLedger()
        self.assertEqual(ledger.check_or_record(event), "accepted")

        altered = copy.deepcopy(event)
        altered["event_id"] = "e2"
        altered["payload"]["body"] = "different"
        altered["idempotency"]["semantic_digest"] = ap.semantic_digest(altered)
        # Preserve the old key deliberately to simulate an illegal conflicting retry.
        with self.assertRaises(ap.ProtocolError):
            ap.validate_event(altered)

    def test_causal_gap_waits_then_drains(self):
        e1 = self.event(event_id="e1", seq=1, lamport=1, payload={"id": "m1"})
        e2 = self.event(
            event_id="e2",
            seq=2,
            lamport=2,
            payload={"id": "m2"},
            parents=("e1",),
        )
        store = ap.CausalStore()
        self.assertEqual(store.offer(e2), "pending")
        self.assertEqual(store.offer(e1), "applied")
        self.assertEqual(store.applied_order, ["e1", "e2"])
        self.assertEqual(store.frontier["s1"], 2)
        self.assertFalse(store.pending)

    def test_parent_lamport_must_precede_child(self):
        e1 = self.event(event_id="e1", seq=1, lamport=5, payload={"id": "m1"})
        e2 = self.event(event_id="e2", seq=2, lamport=5, payload={"id": "m2"}, parents=("e1",))
        store = ap.CausalStore()
        self.assertEqual(store.offer(e1), "applied")
        with self.assertRaises(ap.CausalConflict):
            store.offer(e2)

    def test_materialized_indexes_are_deterministic(self):
        e1 = self.event(event_id="e1", seq=1, lamport=1, payload={"id": "m1"})
        e2 = self.event(event_id="e2", seq=2, lamport=2, payload={"id": "m2"}, parents=("e1",))
        catalog = json.loads((ROOT / "indexes" / "materialized-index.catalog.json").read_text())
        a = ap.build_index_catalog([e1, e2], catalog)
        b = ap.build_index_catalog([e2, e1], catalog)
        self.assertEqual(a, b)
        frontier_values = list(a["stream-frontier"].values())
        self.assertEqual(frontier_values, [2])

    def test_fsm_is_deterministic(self):
        definition = json.loads((ROOT / "fsm" / "ingest-lifecycle.fsm.json").read_text())
        engine = ap.FsmEngine(definition)
        state = engine.initial_state
        state, _ = engine.transition(state, "IDEMPOTENCY_ACCEPTED")
        self.assertEqual(state, "IDEMPOTENCY_VALIDATED")
        state, _ = engine.transition(state, "CAUSAL_READY")
        self.assertEqual(state, "CAUSAL_READY")
        state, _ = engine.transition(state, "APPEND_DURABLE")
        self.assertEqual(state, "DURABLE")
        state, _ = engine.transition(state, "MATERIALIZE_INDEXES")
        self.assertEqual(state, "INDEXED")
        state, _ = engine.transition(state, "SNAPSHOT_MARK")
        self.assertEqual(state, "SNAPSHOT_ELIGIBLE")

    def test_snapshot_records_frontier_and_lock(self):
        e1 = self.event(event_id="e1", seq=1, lamport=1, payload={"id": "m1"})
        store = ap.CausalStore()
        store.offer(e1)
        catalog = json.loads((ROOT / "indexes" / "materialized-index.catalog.json").read_text())
        indexes = ap.build_index_catalog(store.canonical_events(), catalog)
        manifest = ap.build_snapshot_manifest(
            snapshot_id="snap-1",
            created_at_utc="2026-10-03T00:01:00Z",
            protocol_lock_digest="sha256:" + "1" * 64,
            events=store.canonical_events(),
            index_catalog_materialization=indexes,
            dedupe_entries=store.ledger.export(),
            previous_snapshot_digest=None,
        )
        self.assertEqual(manifest["source_frontier"], {"s1": 1})
        self.assertTrue(ap.DIGEST_RE.match(manifest["snapshot_digest"]))

    def test_lock_verifies(self):
        verified = ap.verify_lock(ROOT / "PROTOCOL.lock.json")
        self.assertGreaterEqual(len(verified), 8)


if __name__ == "__main__":
    unittest.main()
