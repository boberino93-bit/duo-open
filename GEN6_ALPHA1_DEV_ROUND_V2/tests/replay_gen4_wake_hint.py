#!/usr/bin/env python3
"""Replay the Gen4 field delay between Samsung 0->1 WakeHint and next hinge sample."""
import argparse, json, re, statistics
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("log")
p.add_argument("--out")
a = p.parse_args()
lines = Path(a.log).read_text(errors="replace").splitlines()
state_pat = re.compile(r"uptime=(\d+) \[early-wake\] device-state previous=(\d+|null) current=(\d+)")
angle_pat = re.compile(r"uptime=(\d+) \[angle-authority\] accepted source=([^ ]+) angle=([0-9.]+)")
events=[]
for idx,line in enumerate(lines):
    m=state_pat.search(line)
    if not (m and m.group(2)=="0" and m.group(3)=="1"):
        continue
    t=int(m.group(1))
    for line2 in lines[idx+1:]:
        sm=state_pat.search(line2)
        if sm and sm.group(2)=="0" and sm.group(3)=="1":
            break
        am=angle_pat.search(line2)
        if am:
            events.append({
                "wake_hint_uptime_ms": t,
                "next_angle_uptime_ms": int(am.group(1)),
                "legacy_wait_ms": int(am.group(1))-t,
                "next_angle_source": am.group(2),
                "next_angle_degrees": float(am.group(3)),
                "gen6_v2_wake_dispatch_offset_ms": 0,
                "gen6_v2_visual_dispatch_offset_ms": 0,
            })
            break
vals=[e["legacy_wait_ms"] for e in events]
if not vals:
    raise SystemExit("no 0->1 wake-hint events found")
sv=sorted(vals)
p95=sv[min(len(sv)-1, round(.95*(len(sv)-1)))]
report={
    "event_count": len(vals),
    "legacy_wait_ms": {
        "min": min(vals),
        "median": statistics.median(vals),
        "p95": p95,
        "max": max(vals),
    },
    "interpretation": "Gen6 V2 dispatches physical wake and visual material from 0->1 instead of waiting for the next hinge sample. This is replay/model evidence, not a physical Gen6 timing measurement.",
    "events": events,
}
out=json.dumps(report,indent=2)+"\n"
print(out,end="")
if a.out:
    Path(a.out).write_text(out)
