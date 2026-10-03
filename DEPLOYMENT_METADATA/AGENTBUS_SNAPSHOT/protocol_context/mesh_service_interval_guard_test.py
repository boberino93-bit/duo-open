from datetime import datetime, timezone
from mesh_service_interval_guard import AgentState, audit

now = datetime(2026,10,2,18,30,0,tzinfo=timezone.utc)
states = [
    AgentState("primary","PRIMARY",True,"2026-10-02T18:29:40Z",True,"base1","abc","out1","REGRESSION_OK"),
    AgentState("manager","MANAGER_REVIEWER",True,"2026-10-02T18:28:50Z",True,"base1","abc","out2","REGRESSION_TESTED"),
    AgentState("research","RESEARCH",True,"2026-10-02T18:29:25Z",False,"base1","abc","out3","REGRESSION_OK"),
]
r = audit(states, now)
by = {x["agent_id"]:x for x in r["agents"]}
assert by["primary"]["health"] == "HEALTHY"
assert by["manager"]["health"] == "LATE"
assert by["research"]["health"] == "NONCOMPLIANT"
assert r["all_active_healthy"] is False
print("mesh_service_interval_guard_test: PASS")
