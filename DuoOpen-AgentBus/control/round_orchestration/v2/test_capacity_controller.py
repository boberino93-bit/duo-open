import importlib.util
from pathlib import Path
import random
import sys
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("capacity_controller", HERE / "capacity_controller.py")
M = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = M
SPEC.loader.exec_module(M)

class CapacityControllerCycle2Tests(unittest.TestCase):
    def test_target_and_tolerance(self):
        p = M.capacity_plan()
        self.assertEqual(p.raw_target_sessions, 18)
        self.assertEqual(p.recommended_sessions, 18)
        self.assertEqual((p.minimum_tolerance_sessions, p.maximum_tolerance_sessions), (14, 20))

    def test_useful_parallelism_prevents_busywork(self):
        p = M.capacity_plan(useful_parallel_lanes=5)
        self.assertEqual(p.recommended_sessions, 6)
        self.assertTrue(p.under_target_justification_required)

    def test_17_sibling_lanes_support_target(self):
        p = M.capacity_plan(useful_parallel_lanes=17)
        self.assertEqual(p.recommended_sessions, 18)
        self.assertFalse(p.under_target_justification_required)

    def test_calibration_pass_is_adapter_only(self):
        c = M.evaluate_calibration(20, 18, 18, 0, 18, 18)
        self.assertEqual(c.status, "PASS_ADAPTER_BATCH_TARGET")
        self.assertEqual(c.proven_safe_batch_floor, 18)
        self.assertEqual(c.backend_physical_ceiling, "UNPROVEN")

    def test_calibration_wrong_size_invalid(self):
        c = M.evaluate_calibration(20, 20, 20, 0, 20, 20)
        self.assertEqual(c.status, "INVALID_PROBE_SIZE")

    def test_calibration_path_alias_fails_closed(self):
        c = M.evaluate_calibration(20, 18, 18, 0, 17, 18)
        self.assertEqual(c.status, "FAIL_CLOSED")
        self.assertEqual(c.proven_safe_batch_floor, 17)

    def test_publication_ack_rejects_auto_rename(self):
        h = "a" * 64
        self.assertFalse(M.publication_ack("/messages/x.json", "/messages/x(1).json", h, h))
        self.assertTrue(M.publication_ack("/messages/x.json", "/messages/x.json", h, h))

    def test_hash_mismatch_fails_ack(self):
        self.assertFalse(M.publication_ack("x", "x", "a" * 64, "b" * 64))

    def test_pending_ticket_never_counts_active(self):
        r = M.RoundState()
        r.apply({"event_type":"SPAWN_TICKET","ticket_id":"t1"})
        self.assertEqual(len(r.active_sessions), 0)

    def test_started_and_released(self):
        r = M.RoundState()
        r.apply({"event_type":"SESSION_STARTED","ticket_id":"t1","session_id":"s1"})
        self.assertEqual(len(r.active_sessions), 1)
        r.apply({"event_type":"SESSION_RELEASED","ticket_id":"t1","session_id":"s1"})
        self.assertEqual(len(r.active_sessions), 0)

    def test_ticket_double_claim_fails(self):
        r = M.RoundState()
        r.apply({"event_type":"SESSION_STARTED","ticket_id":"t1","session_id":"s1"})
        with self.assertRaises(ValueError):
            r.apply({"event_type":"SESSION_STARTED","ticket_id":"t1","session_id":"s2"})

    def test_hard_ceiling(self):
        r = M.RoundState()
        for i in range(20):
            r.apply({"event_type":"SESSION_STARTED","ticket_id":f"t{i}","session_id":f"s{i}"})
        with self.assertRaises(ValueError):
            r.apply({"event_type":"SESSION_STARTED","ticket_id":"overflow","session_id":"overflow"})

    def test_split_plane_no_delta(self):
        self.assertFalse(M.should_write_material_message("SERVICE", "NO_DELTA", False))
        self.assertTrue(M.should_write_material_message("FINDING", "NEW", False))
        self.assertTrue(M.should_write_material_message("SERVICE", "NO_DELTA", True))

    def test_invoke_or_justify(self):
        self.assertTrue(M.valid_collaboration_invocation("HELP_REQUEST"))
        self.assertTrue(M.valid_collaboration_invocation("NO_HELP_JUSTIFICATION", "lane is already independently covered"))
        self.assertFalse(M.valid_collaboration_invocation("NO_HELP_JUSTIFICATION", ""))
        self.assertFalse(M.valid_collaboration_invocation("NONE"))

    def test_stop_barrier(self):
        self.assertFalse(M.stop_barrier_satisfied(["STOPPED", "RUNNING"]))
        self.assertTrue(M.stop_barrier_satisfied(["STOPPED", "SAFE_CHECKPOINT", "STALE", "RELEASED"]))
        self.assertFalse(M.stop_barrier_satisfied([]))

    def test_randomized_session_reducer_never_overflows(self):
        rnd = random.Random(0xD00F07)
        r = M.RoundState()
        active = []
        counter = 0
        for _ in range(50000):
            if not active or (len(active) < 20 and rnd.random() < 0.57):
                counter += 1
                sid, tid = f"s{counter}", f"t{counter}"
                r.apply({"event_type":"SESSION_STARTED","ticket_id":tid,"session_id":sid})
                active.append((sid, tid))
            else:
                idx = rnd.randrange(len(active))
                sid, tid = active.pop(idx)
                r.apply({"event_type":"SESSION_RELEASED","ticket_id":tid,"session_id":sid})
            self.assertLessEqual(len(r.active_sessions), 20)
            self.assertEqual(len(r.active_sessions), len(active))

if __name__ == '__main__':
    unittest.main(verbosity=2)
