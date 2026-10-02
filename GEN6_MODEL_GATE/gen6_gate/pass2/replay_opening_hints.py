#!/usr/bin/env python3
import bisect,json,re,statistics,sys
sys.path.insert(0,'/mnt/data/gen6_pass1')
from gen6_model import VirtualHinge
field,trace=sys.argv[1:3]
up=re.compile(r'uptime=(\d+)'); ds=re.compile(r'device-state previous=(\d+) current=(\d+)')
hints=[]
with open(field,errors='replace') as f:
    for line in f:
        u=up.search(line); d=ds.search(line)
        if u and d and int(d.group(1))==0 and int(d.group(2)) in (1,2):
            hints.append((int(u.group(1))*1_000_000,int(d.group(2))))
frames=[]; seen=set()
with open(trace,errors='replace') as f:
    for line in f:
        try:r=json.loads(line)
        except:continue
        if r.get('eventType')!='vsync':continue
        if not all(k in r for k in ('vsyncId','timestampNs','frameTimeNs','expectedPresentNs')):continue
        k=(r['vsyncId'],r['frameTimeNs'])
        if k in seen:continue
        seen.add(k); frames.append((r['timestampNs'],r['expectedPresentNs'],r['vsyncId']))
frames.sort(); times=[x[0] for x in frames]
rows=[]
for h,mode in hints:
    i=bisect.bisect_left(times,h)
    if i>=len(frames):continue
    cb,ep,vid=frames[i]
    if cb-h>200_000_000: # trace gap means no usable immediate presentation opportunity
        rows.append({'hint_ns':h,'hint':f'0->{mode}','usable_frame':False,'frame_delay_ms':(cb-h)/1e6})
        continue
    v=VirtualHinge(); v.start(h); angle=v.frame(cb,ep)
    rows.append({'hint_ns':h,'hint':f'0->{mode}','usable_frame':True,'frame_delay_ms':(cb-h)/1e6,'expected_present_delay_ms':(ep-h)/1e6,'first_visual_angle_deg':angle,'vsync_id':vid})
valid=[r for r in rows if r.get('usable_frame')]
out={'hint_count':len(hints),'usable_immediate_frame_count':len(valid),'events':rows}
if valid:
    for k in ('frame_delay_ms','expected_present_delay_ms'):
        vals=sorted(r[k] for r in valid); out[k]={'min':min(vals),'median':statistics.median(vals),'p95':vals[int(.95*(len(vals)-1))],'worst':max(vals)}
print(json.dumps(out,indent=2))
