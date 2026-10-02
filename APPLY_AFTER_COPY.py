#!/usr/bin/env python3
"""Apply the root-drop service pack after extracting it into duo-open main."""
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SP = ROOT / "service_packs/gen7_shizuku_onboarding_v1/apply_service_pack_v1.py"
PROTOCOL_FILES = [
    "USER_INTERACTION_MODEL_PROTOCOL_V1.md",
    "USER_MODEL_REFERENCE_V1.json",
    "INIT_PACKAGE_USER_MODEL_HOOK_V1.json",
    "BOOTSTRAP_V7.md",
    "DUO_OPEN_AGENT_GENERATION_TEMPLATE_V11.txt",
    "AGENT_DISCOVERY_V7.json",
]

def same(a:Path,b:Path)->bool:
    return a.exists() and b.exists() and hashlib.sha256(a.read_bytes()).digest()==hashlib.sha256(b.read_bytes()).digest()

def copy_create_or_same(src:Path,dst:Path):
    dst.parent.mkdir(parents=True,exist_ok=True)
    if dst.exists():
        if not same(src,dst):
            raise SystemExit(f"REFUSE_OVERWRITE: {dst} exists with different content")
        return "already-present"
    shutil.copy2(src,dst); return "created"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--check",action="store_true")
    ap.add_argument("--agentbus-root",type=Path,help="Optional materialized DuoOpen-AgentBus root to receive protocol + seed events/models")
    a=ap.parse_args()
    repo=ROOT
    if not (repo/"app/src/main").exists():
        raise SystemExit("Run/extract this package in the root of the duo-open checkout (app/src/main must exist).")

    # Fail-closed app patch.
    cmd=[sys.executable,str(SP),str(repo)] + (["--check"] if a.check else [])
    rc=subprocess.run(cmd).returncode
    if rc: raise SystemExit(rc)

    actions=[]
    # Replicate new bootstrap protocol into the successor handoff area when it exists.
    succ=repo/"SUCCESSOR_HANDOFF/GEN7_CURRENT/protocol"
    if succ.exists() and not a.check:
        for name in PROTOCOL_FILES:
            actions.append((str(succ/name),copy_create_or_same(repo/name,succ/name)))
        msgsrc=repo/"AGENTBUS_IMPORT/messages/20261002T223700Z__user-directive-bridge__all__user-interaction-model-v1.json"
        msgdst=repo/"SUCCESSOR_HANDOFF/GEN7_CURRENT/messages"/msgsrc.name
        actions.append((str(msgdst),copy_create_or_same(msgsrc,msgdst)))

    # Optional live/materialized AgentBus import. Never overwrite different files.
    if a.agentbus_root and not a.check:
        bus=a.agentbus_root.resolve()
        for name in ["USER_INTERACTION_MODEL_PROTOCOL_V1.md","USER_MODEL_REFERENCE_V1.json","INIT_PACKAGE_USER_MODEL_HOOK_V1.json","BOOTSTRAP_V7.md","DUO_OPEN_AGENT_GENERATION_TEMPLATE_V11.txt"]:
            actions.append((str(bus/name),copy_create_or_same(repo/name,bus/name)))
        actions.append((str(bus/"AGENT_DISCOVERY.json"),copy_create_or_same(repo/"AGENT_DISCOVERY_V7.json",bus/"AGENT_DISCOVERY.json")))
        for folder in ["events","models"]:
            for src in sorted((repo/f"seed/user-model/v1/{folder}").glob("*.json")):
                dst=bus/f"user-model/v1/{folder}"/src.name
                actions.append((str(dst),copy_create_or_same(src,dst)))
        for src in sorted((repo/"AGENTBUS_IMPORT/messages").glob("*.json")):
            actions.append((str(bus/"messages"/src.name),copy_create_or_same(src,bus/"messages"/src.name)))

    print("ROOT_DROP_SP2_OK")
    if a.check:
        print("- app patch applicability validated; no files written")
    for path,state in actions: print(f"- {state}: {path}")

if __name__=="__main__": main()
