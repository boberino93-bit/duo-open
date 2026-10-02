#!/usr/bin/env python3
"""Inject Duo Open user-model bootstrap references into an initiation ZIP.

Does not delete existing files. Adds a versioned bootstrap payload and a
START_HERE_USER_MODEL.txt marker so newer agents/package builders can adopt it.
"""
from __future__ import annotations
import argparse, hashlib, json, shutil, tempfile, zipfile
from pathlib import Path

PAYLOAD_FILES = [
    "USER_INTERACTION_MODEL_PROTOCOL_V1.md",
    "USER_MODEL_REFERENCE_V1.json",
    "BOOTSTRAP_V7.md",
    "DUO_OPEN_AGENT_GENERATION_TEMPLATE_V11.txt",
    "AGENT_DISCOVERY_V7.json",
]

def sha256(p: Path) -> str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('input_zip'); ap.add_argument('output_zip')
    ap.add_argument('--root-drop',default=str(Path(__file__).resolve().parents[1]))
    args=ap.parse_args()
    src=Path(args.input_zip); out=Path(args.output_zip); root=Path(args.root_drop)
    if src.resolve()==out.resolve(): raise SystemExit('output_zip must differ from input_zip')
    with tempfile.TemporaryDirectory() as td:
        t=Path(td)
        with zipfile.ZipFile(src) as z: z.extractall(t)
        dest=t/'USER_MODEL_BOOTSTRAP'
        dest.mkdir(parents=True,exist_ok=True)
        manifest={"schema":"duoopen-user-model-zip-injection/v1","files":{}}
        for name in PAYLOAD_FILES:
            p=root/name
            if not p.exists(): raise SystemExit(f'missing payload file: {p}')
            shutil.copy2(p,dest/name)
            manifest['files'][name]=sha256(p)
        models=sorted((root/'seed/user-model/v1/models').glob('*.json'))
        if models:
            shutil.copy2(models[-1],dest/'CACHED_USER_MODEL.json')
            manifest['files']['CACHED_USER_MODEL.json']=sha256(models[-1])
        (t/'START_HERE_USER_MODEL.txt').write_text(
            'Before substantive work, read USER_MODEL_BOOTSTRAP/BOOTSTRAP_V7.md, '\
            'USER_MODEL_BOOTSTRAP/USER_INTERACTION_MODEL_PROTOCOL_V1.md, and '\
            'USER_MODEL_BOOTSTRAP/USER_MODEL_REFERENCE_V1.json. Then look for the live '\
            '/DuoOpen-AgentBus/user-model/v1/models/ database and prefer its newest valid '\
            'immutable snapshot over the packaged cache. Predictions are advisory only.\n'
        )
        (dest/'INJECTION_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
        out.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(t.rglob('*')):
                if p.is_file(): z.write(p,p.relative_to(t))
    print(out)
if __name__=='__main__': main()
