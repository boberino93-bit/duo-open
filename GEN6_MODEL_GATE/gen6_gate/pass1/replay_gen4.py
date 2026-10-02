import json,re,statistics,sys
p=sys.argv[1]
lines=open(p,errors='replace').read().splitlines()
up=re.compile(r'uptime=(\d+)'); ds=re.compile(r'device-state previous=(\d+) current=(\d+)')
ang=re.compile(r'\[angle-authority\] accepted .* angle=([0-9.]+)'); st=re.compile(r'\[fold7-state\] STATE .* -> OPENING_FROM_CLOSED')
ev=[]
for line in lines:
    u=up.search(line)
    if not u: continue
    t=int(u.group(1)); d=ds.search(line)
    if d: ev.append((t,'device',int(d.group(1)),int(d.group(2))))
    a=ang.search(line)
    if a and float(a.group(1))>0: ev.append((t,'angle',float(a.group(1)),None))
    if st.search(line): ev.append((t,'open_state',None,None))
rows=[]
for i,e in enumerate(ev):
    if e[1]=='device' and e[2]==0 and e[3] in (1,2):
        na=next((x for x in ev[i+1:] if x[0]>=e[0] and x[1]=='angle'),None)
        ns=next((x for x in ev[i+1:] if x[0]>=e[0] and x[1]=='open_state'),None)
        rows.append({'hint_uptime_ms':e[0],'hint':f'0->{e[3]}','first_angle_delay_ms':None if na is None else na[0]-e[0],'first_angle_deg':None if na is None else na[2],'opening_state_delay_ms':None if ns is None else ns[0]-e[0]})
d=[r['opening_state_delay_ms'] for r in rows if r['opening_state_delay_ms'] is not None]
out={'source':p,'leave_closed_events':len(rows),'zero_to_one':sum(r['hint']=='0->1' for r in rows),'opening_state_delay_ms':{'min':min(d),'median':statistics.median(d),'max':max(d)},'events':rows}
print(json.dumps(out,indent=2))
