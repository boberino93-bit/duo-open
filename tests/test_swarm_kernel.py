from datetime import datetime, timedelta, timezone
import pytest
from swarm_kernel.kernel import ProjectConfig, backpressure_state, can_open_start_gate, circuit_state, convergence_gate, deterministic_backoff, lease_transition_allowed, new_lease, operation_id, preflight, record_path, validate_binding
CFG=ProjectConfig(project_id="example",repository="owner/example",canonical_branch="main",coordination_root="Example-AgentBus/")
def test_binding_fails_closed():
    with pytest.raises(PermissionError): validate_binding(CFG,"other","owner/example")
def test_record_paths_reject_traversal():
    assert record_path("leases","run_1","task_1")==".swarm/leases/run_1/task_1.json"
    with pytest.raises(ValueError): record_path("leases","../run","task")
def test_start_gate():
    assert not can_open_start_gate(["a","b"],["a"])[0]; assert can_open_start_gate(["a","b"],["a"],explicit_close=True)[0]
def test_lease_cas_and_expiry():
    now=datetime(2026,1,1,tzinfo=timezone.utc); lease=new_lease(CFG,"run_1","task_1","agent_a",0,now); assert lease["version"]==1; assert not lease_transition_allowed(lease,0,"agent_a",now)[0]; assert lease_transition_allowed(lease,1,"agent_b",now)[1]=="LEASE_HELD"; assert lease_transition_allowed(lease,1,"agent_b",now+timedelta(seconds=CFG.lease_ttl_seconds+1))[1]=="EXPIRED_RECLAIM"
def test_idempotency_backoff_circuit_and_gates():
    key=operation_id("example","run_1","publish","x"); assert key==operation_id("example","run_1","publish","x"); assert deterministic_backoff(key,3)==deterministic_backoff(key,3); assert circuit_state(CFG,CFG.circuit_breaker_threshold)=="DEGRADED_READ_ONLY"; assert backpressure_state(CFG,CFG.manager_queue_hard_limit)=="HARD_STOP_SECONDARY_WORK"; checks={"identity_binding":True,"run_epoch":True,"role_binding":True,"package_parity":True,"recovery_state":True,"manager_presence":True,"foreign_write_policy":True,"tests":False}; assert not preflight(CFG,checks)["ready"]; assert not convergence_gate(research_accounted=True,manager_dispositions_complete=True,primary_decisions_persisted=True,package_parity_restored=True,unresolved_leases=1,recovery_checkpoint_valid=True)["complete"]
