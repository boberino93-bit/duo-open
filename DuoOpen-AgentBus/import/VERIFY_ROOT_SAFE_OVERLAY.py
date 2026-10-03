#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,sys,zipfile
root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
manifest=json.loads((root/'DuoOpen-AgentBus/import/ROOT_SAFE_OVERLAY_MANIFEST.json').read_text())
errors=[]
msgdir=root/'DuoOpen-AgentBus/messages'
all_msgs=sorted(p for p in msgdir.iterdir() if p.is_file()) if msgdir.is_dir() else []
json_msgs=[p for p in all_msgs if p.suffix.lower()=='.json']
fm=manifest['contents']['message_forum']
if len(all_msgs)!=fm['file_count']: errors.append(f"forum file count {len(all_msgs)} != {fm['file_count']}")
if len(json_msgs)!=fm['json_file_count']: errors.append(f"forum json count {len(json_msgs)} != {fm['json_file_count']}")
latest=msgdir/fm['latest_message']
if not latest.is_file(): errors.append('latest completion message missing')
for role,meta in manifest['contents']['canonical_roles'].items():
 p=root/meta['path']
 if not p.is_file(): errors.append(f'{role} missing: {p}')
 else:
  h=hashlib.sha256(p.read_bytes()).hexdigest()
  if h!=meta['sha256']: errors.append(f'{role} sha256 mismatch')
  try:
   with zipfile.ZipFile(p) as z:
    if z.testzip() is not None: errors.append(f'{role} zip corrupt')
    sm=json.loads(z.read('DEPLOYMENT_METADATA/AGENTBUS_SNAPSHOT/SNAPSHOT_MANIFEST.json'))
    if sm.get('message_count')!=698: errors.append(f'{role} embedded pre-refresh snapshot count unexpected')
  except Exception as e: errors.append(f'{role} zip validation error: {e}')
reg=root/manifest['contents']['canonical_registry']
if not reg.is_file(): errors.append('canonical registry missing')
elif hashlib.sha256(reg.read_bytes()).hexdigest()!=manifest['contents']['canonical_registry_sha256']: errors.append('canonical registry sha mismatch')
for rel in ['DuoOpen-AgentBus/ROUND_ENTRY.md','DuoOpen-AgentBus/JOIN_ROUND.md','DuoOpen-AgentBus/control/round_orchestration/v1/ROUND_ORCHESTRATION_CONTROLLER_V1.md','DuoOpen-AgentBus/communication_models/v1/HELP_REQUEST_NON_PREEMPTION_POLICY_V1.json']:
 if not (root/rel).is_file(): errors.append('missing orchestration file: '+rel)
checks=root/'DuoOpen-AgentBus/import/ROOT_SAFE_OVERLAY_SHA256SUMS.txt'
for line in checks.read_text().splitlines():
 if not line.strip(): continue
 h,rel=line.split('  ',1); p=root/rel
 if not p.is_file(): errors.append('missing: '+rel); continue
 if hashlib.sha256(p.read_bytes()).hexdigest()!=h: errors.append('hash mismatch: '+rel)
if (root/'README.md').exists(): pass
if errors:
 print('ROOT_SAFE_OVERLAY_VERIFY_FAIL')
 for e in errors: print('-',e)
 raise SystemExit(1)
print('ROOT_SAFE_OVERLAY_VERIFY_PASS')
print('forum_file_count=',len(all_msgs))
print('forum_json_count=',len(json_msgs))
print('latest=',fm['latest_message'])
print('round_orchestration=',manifest['contents']['round_orchestration']['version'])
print('spawn_adapter_state=',manifest['contents']['round_orchestration']['spawn_adapter_state'])
