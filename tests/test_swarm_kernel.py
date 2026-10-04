from datetime import datetime, timedelta, timezone
import unittest

from swarm_kernel.kernel import (
    ProjectConfig,
    backpressure_state,
    can_open_start_gate,
    circuit_state,
    convergence_gate,
    deterministic_backoff,
    lease_transition_allowed,
    new_lease,
    operation_id,
    preflight,
    record_path,
    validate_binding,
)

CFG = ProjectConfig("example", "owner/example", "main", "Example-AgentBus/")


class SwarmKernelTest(unittest.TestCase):
    def test_binding_fails_closed(self):
        with self.assertRaises(PermissionError):
            validate_binding(CFG, "other", "owner/example")

    def test_record_paths_reject_traversal(self):
        self.assertEqual(record_path("leases", "run_1", "task_1"), ".swarm/leases/run_1/task_1.json")
        with self.assertRaises(ValueError):
            record_path("leases", "../run", "task")

    def test_start_gate(self):
        self.assertFalse(can_open_start_gate(["a", "b"], ["a"])[0])
        self.assertTrue(can_open_start_gate(["a", "b"], ["a"], explicit_close=True)[0])

    def test_lease_cas_and_expiry(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        lease = new_lease(CFG, "run_1", "task_1", "agent_a", 0, now)
        self.assertEqual(lease["version"], 1)
        self.assertFalse(lease_transition_allowed(lease, 0, "agent_a", now)[0])
        self.assertEqual(lease_transition_allowed(lease, 1, "agent_b", now)[1], "LEASE_HELD")
        self.assertEqual(
            lease_transition_allowed(lease, 1, "agent_b", now + timedelta(seconds=CFG.lease_ttl_seconds + 1))[1],
            "EXPIRED_RECLAIM",
        )

    def test_idempotency_backoff_circuit_and_gates(self):
        key = operation_id("example", "run_1", "publish", "x")
        self.assertEqual(key, operation_id("example", "run_1", "publish", "x"))
        self.assertEqual(deterministic_backoff(key, 3), deterministic_backoff(key, 3))
        self.assertEqual(circuit_state(CFG, CFG.circuit_breaker_threshold), "DEGRADED_READ_ONLY")
        self.assertEqual(backpressure_state(CFG, CFG.manager_queue_hard_limit), "HARD_STOP_SECONDARY_WORK")
        checks = {"identity_binding": True, "run_epoch": True, "role_binding": True, "package_parity": True, "recovery_state": True, "manager_presence": True, "foreign_write_policy": True, "tests": False}
        self.assertFalse(preflight(CFG, checks)["ready"])
        self.assertFalse(convergence_gate(research_accounted=True, manager_dispositions_complete=True, primary_decisions_persisted=True, package_parity_restored=True, unresolved_leases=1, recovery_checkpoint_valid=True)["complete"])


if __name__ == "__main__":
    unittest.main()
