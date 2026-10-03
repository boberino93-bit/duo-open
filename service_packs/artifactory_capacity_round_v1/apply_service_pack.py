#!/usr/bin/env python3
"""Root-drop pack application is extraction; this command validates the result in place."""
from pathlib import Path
import subprocess, sys
root=Path(__file__).resolve().parents[2]
subprocess.run([sys.executable, str(root/'tools/verify_artifactory_capacity_service_pack.py'), str(root)], check=True)
subprocess.run([sys.executable, str(root/'DuoOpen-AgentBus/control/round_orchestration/v2/test_capacity_controller.py')], check=True)
print('ARTIFACTORY_CAPACITY_ROUND_V1_APPLY_CHECK_PASS')
