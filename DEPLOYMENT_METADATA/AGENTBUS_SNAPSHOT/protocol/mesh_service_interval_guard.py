#!/usr/bin/env python3
"""Duo Open active-mesh service interval / regression continuity guard.

Pure helper. Feed it exported JSON snapshots from AgentBus listings/messages.
It never mutates AgentBus and never assumes dormant sessions can self-wake.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional
import argparse, json, sys

TARGET_SECONDS = 30
HARD_SECONDS = 60
HUNG_SECONDS = 90

@dataclass(frozen=True)
class AgentState:
    agent_id: str
    role: str
    active: bool
    last_service_utc: Optional[str]
    contract_ack: bool
    regression_baseline: Optional[str]
    github_head: Optional[str]
    last_output_ref: Optional[str]
    regression_state: Optional[str]

def parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    v = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def classify(agent: AgentState, now: datetime) -> dict:
    if not agent.active:
        return {"agent_id": agent.agent_id, "health": "INACTIVE", "age_seconds": None, "reasons": []}

    reasons = []
    ts = parse_ts(agent.last_service_utc)
    if ts is None:
        age = None
        health = "NONCOMPLIANT"
        reasons.append("missing durable service publication")
    else:
        age = max(0.0, (now - ts).total_seconds())
        if age <= HARD_SECONDS:
            health = "HEALTHY"
        elif age <= HUNG_SECONDS:
            health = "LATE"
            reasons.append("service publication exceeded 60s hard deadline")
        else:
            health = "HUNG_OR_BLOCKED"
            reasons.append("service publication older than 90s")

    if not agent.contract_ack:
        health = "NONCOMPLIANT"
        reasons.append("mandatory service contract not ACKed")
    if not agent.regression_baseline:
        health = "NONCOMPLIANT"
        reasons.append("missing regression baseline digest/ref")
    if not agent.github_head:
        health = "NONCOMPLIANT"
        reasons.append("missing exact GitHub HEAD")
    if not agent.regression_state:
        health = "NONCOMPLIANT"
        reasons.append("missing regression continuity state")
    if not agent.last_output_ref:
        reasons.append("no current/unchanged output ref")

    return {
        "agent_id": agent.agent_id,
        "role": agent.role,
        "health": health,
        "age_seconds": age,
        "reasons": reasons,
        "regression_baseline": agent.regression_baseline,
        "regression_state": agent.regression_state,
        "github_head": agent.github_head,
        "last_output_ref": agent.last_output_ref,
    }

def audit(states: Iterable[AgentState], now: datetime) -> dict:
    rows = [classify(s, now) for s in states]
    counts = {}
    for row in rows:
        counts[row["health"]] = counts.get(row["health"], 0) + 1
    unhealthy = [r for r in rows if r["health"] not in ("HEALTHY", "INACTIVE")]
    return {
        "schema": "duoopen-mesh-service-audit/v1",
        "target_seconds": TARGET_SECONDS,
        "hard_seconds": HARD_SECONDS,
        "hung_seconds": HUNG_SECONDS,
        "generated_utc": now.isoformat().replace("+00:00", "Z"),
        "counts": counts,
        "unhealthy": unhealthy,
        "agents": rows,
        "all_active_healthy": not unhealthy,
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot", help="JSON file containing {'agents':[...]} records")
    ap.add_argument("--now", help="UTC ISO8601 override")
    args = ap.parse_args()
    raw = json.load(open(args.snapshot, "r", encoding="utf-8"))
    now = parse_ts(args.now) if args.now else datetime.now(timezone.utc)
    states = [AgentState(**item) for item in raw.get("agents", [])]
    result = audit(states, now)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_active_healthy"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
