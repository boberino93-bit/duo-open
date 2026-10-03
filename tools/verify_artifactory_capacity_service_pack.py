#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse, hashlib, json, sys

REQUIRED = [
    'DuoOpen-AgentBus/control/artifactory/v1/ARTIFACTORY_DAILY_CAPACITY_PROTOCOL_V1.md',
    'DuoOpen-AgentBus/control/artifactory/v1/SERVICE_PUBLICATION_SPLIT_PLANE_V1.md',
    'DuoOpen-AgentBus/control/round_orchestration/v2/ROUND_ORCHESTRATION_CONTROLLER_V2.md',
    'DuoOpen-AgentBus/control/round_orchestration/v2/ROUND_ORCHESTRATION_SCHEMAS_V2.json',
    'DuoOpen-AgentBus/control/round_orchestration/v2/capacity_controller.py',
    'DuoOpen-AgentBus/control/round_orchestration/v2/test_capacity_controller.py',
    'DuoOpen-AgentBus/CURRENT_PRODUCT_STATE.json',
    'DuoOpen-AgentBus/artifacts/primary/20261003T042300Z-capacity-calibration/CAPACITY_RESULT.json',
    'service_packs/artifactory_capacity_round_v1/PACKAGE_SHA256SUMS.txt',
]

def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('repo', nargs='?', default='.')
    args=ap.parse_args()
    root=Path(args.repo).resolve()
    missing=[r for r in REQUIRED if not (root/r).is_file()]
    if missing:
        print('MISSING_REQUIRED:', *missing, sep='\n  ')
        return 2
    for j in [
        root/'DuoOpen-AgentBus/control/round_orchestration/v2/ROUND_ORCHESTRATION_SCHEMAS_V2.json',
        root/'DuoOpen-AgentBus/CURRENT_PRODUCT_STATE.json',
        root/'DuoOpen-AgentBus/artifacts/primary/20261003T042300Z-capacity-calibration/CAPACITY_RESULT.json',
    ]:
        json.loads(j.read_text())
    cap=json.loads((root/'DuoOpen-AgentBus/artifacts/primary/20261003T042300Z-capacity-calibration/CAPACITY_RESULT.json').read_text())
    assert cap['status']=='PASS_ADAPTER_BATCH_TARGET'
    assert cap['attempted']==cap['succeeded']==cap['readback_hash_matches']==18
    assert cap['backend_physical_ceiling']=='UNPROVEN'
    schema=json.loads((root/'DuoOpen-AgentBus/control/round_orchestration/v2/ROUND_ORCHESTRATION_SCHEMAS_V2.json').read_text())
    assert schema['max_concurrent_sessions']==20
    assert schema['target_concurrent_sessions']==18
    sums=root/'service_packs/artifactory_capacity_round_v1/PACKAGE_SHA256SUMS.txt'
    for line in sums.read_text().splitlines():
        if not line.strip(): continue
        expected, rel=line.split('  ',1)
        p=root/rel
        if not p.is_file():
            print('MANIFEST_MISSING', rel); return 3
        actual=sha(p)
        if actual!=expected:
            print('MANIFEST_MISMATCH', rel, expected, actual); return 4
    print('ARTIFACTORY_CAPACITY_SERVICE_PACK_VERIFY_PASS')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
