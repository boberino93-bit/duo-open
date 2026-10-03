#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, sys
root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
manifest_path=root/'DuoOpen-AgentBus/import/ROOT_SAFE_OVERLAY_MANIFEST.json'
manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
errors=[]
msgdir=root/'DuoOpen-AgentBus/messages'
msgs=sorted(msgdir.glob('*.json'))
expected=manifest['contents']['message_forum']['json_file_count']
if len(msgs)!=expected: errors.append(f'message count {len(msgs)} != {expected}')
for role,meta in manifest['contents']['canonical_roles'].items():
    p=root/meta['path']
    if not p.is_file(): errors.append(f'{role} missing: {p}')
    else:
        h=hashlib.sha256(p.read_bytes()).hexdigest()
        if h!=meta['sha256']: errors.append(f'{role} sha256 mismatch')
if (root/'README.md').exists():
    pass  # repository README is expected to pre-exist; the overlay does not ship one.
trigger=root/manifest['contents']['workflow_trigger_marker']
if not trigger.is_file(): errors.append('workflow trigger marker missing')
checks=root/'DuoOpen-AgentBus/import/ROOT_SAFE_OVERLAY_SHA256SUMS.txt'
for line in checks.read_text(encoding='utf-8').splitlines():
    if not line.strip(): continue
    h,rel=line.split('  ',1)
    p=root/rel
    if not p.is_file(): errors.append(f'missing: {rel}'); continue
    got=hashlib.sha256(p.read_bytes()).hexdigest()
    if got!=h: errors.append(f'hash mismatch: {rel}')
if errors:
    print('ROOT_SAFE_OVERLAY_VERIFY_FAIL')
    for e in errors: print('-',e)
    raise SystemExit(1)
print('ROOT_SAFE_OVERLAY_VERIFY_PASS')
print('message_json_count=',len(msgs))
print('latest=',msgs[-1].name if msgs else 'NONE')
