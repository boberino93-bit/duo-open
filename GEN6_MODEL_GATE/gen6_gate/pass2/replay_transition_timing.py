#!/usr/bin/env python3
import json,sys,statistics
from collections import Counter
from pathlib import Path
sys.path.insert(0,'/mnt/data/gen6_pass1'); sys.path.insert(0,str(Path(__file__).parent))
from pass2_model import FrameCadenceTracker,FrameTimelineSample
p=sys.argv[1]
t=FrameCadenceTracker(); leads=[]
with open(p,errors='replace') as f:
    for line in f:
        try:r=json.loads(line)
        except:continue
        if r.get('eventType')!='vsync' or not all(k in r for k in ('vsyncId','frameTimeNs','deadlineNs','expectedPresentNs')):continue
        s=FrameTimelineSample(r['vsyncId'],r['timestampNs'],r['frameTimeNs'],r['deadlineNs'],r['expectedPresentNs'])
        if t.add(s):leads.append((s.expected_present_ns-s.frame_time_ns)/1e6)
vals=[x/1e6 for x in t.intervals_ns]
out={
 'source':p,'accepted_unique_vsync':t.accepted_samples,'duplicates':t.duplicate_samples,'invalid':t.invalid_samples,
 'observed_hz':t.observed_hz,'cadence_class':t.cadence_class,
 'recent_interval_ms_median':statistics.median(vals) if vals else None,
 'expected_present_lead_ms_median':statistics.median(leads) if leads else None,
 'expected_present_lead_ms_p95':sorted(leads)[int(.95*(len(leads)-1))] if leads else None,
 'conclusion':'FrameTimeline provides direct presentation timing; display.mode is not used as effective cadence proof.'
}
print(json.dumps(out,indent=2))
