#!/usr/bin/env python3
from __future__ import annotations

import argparse, fnmatch, hashlib, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / ".swarm" / "role_templates"
OUT = ROOT / ".swarm" / "generated"
ROLES = ("PRIMARY", "MANAGER", "RESEARCHER")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()


def revision() -> str:
    try: return git("rev-parse", "HEAD")
    except Exception: return "UNKNOWN"


def changed(base: str | None) -> list[str]:
    env = os.environ.get("SWARM_CHANGED_FILES", "").strip()
    if env: return sorted({x.strip() for x in env.splitlines() if x.strip()})
    try:
        spec = f"{base}...HEAD" if base else "HEAD^..HEAD"
        return sorted({x for x in git("diff", "--name-only", spec).splitlines() if x})
    except Exception:
        try: return sorted({x for x in git("ls-files").splitlines() if x})
        except Exception: return []


def load_json(name: str) -> dict:
    return json.loads((SRC / name).read_text(encoding="utf-8"))


def roles_for(path: str, impact: dict) -> set[str]:
    result: set[str] = set()
    for rule in impact.get("rules", []):
        if fnmatch.fnmatch(path.lower(), rule["glob"].lower()): result.update(rule["roles"])
    return result or set(impact.get("default_roles", ["PRIMARY", "MANAGER"]))


def render(role: str, spec: dict, impact: dict, rev: str, paths: list[str]) -> str:
    shared = spec["shared"]
    role_spec = spec["roles"][role]
    relevant = [p for p in paths if role in roles_for(p, impact)]
    lines = [
        "<!-- GENERATED: edit role-specs.json / role-impact-map.json, not this file. -->",
        f"<!-- source_revision: {rev} -->", "",
        f"# Duo Open {role.title()} Agent Template", "",
        f"Project: `{shared['project_id']}`  ",
        f"Repository: `{shared['repository']}`  ",
        f"Live forum: `{shared['forum']}`", "",
        "## Shared operating requirements", ""
    ]
    lines += [f"{i}. {text}" for i, text in enumerate(shared["requirements"], 1)]
    lines += ["", "## Role mission", "", role_spec["mission"], "", "## Role responsibilities", ""]
    lines += [f"{i}. {text}" for i, text in enumerate(role_spec["responsibilities"], 1)]
    lines += ["", "## Current project-change context", "", f"Generated from revision `{rev}`.", "", "Role-relevant changed paths:"]
    lines += [f"- `{p}`" for p in relevant] if relevant else ["- No changed path mapped specifically to this role in the selected range."]
    lines += ["", "Inspect the actual diff/source for these paths before deciding what changed semantically. If a durable role or protocol responsibility changed, update the canonical role spec and regenerate.", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    spec, impact, rev, paths = load_json("role-specs.json"), load_json("role-impact-map.json"), revision(), changed(args.base)
    OUT.mkdir(parents=True, exist_ok=True)
    expected: dict[Path, str] = {}
    for role in ROLES: expected[OUT / f"{role}_PROMPT.md"] = render(role, spec, impact, rev, paths)
    manifest = {
        "schema": "duo-open/generated-role-prompts/v1",
        "source_revision": rev,
        "changed_files": paths,
        "affected_roles": sorted({r for p in paths for r in roles_for(p, impact)}),
        "source_hashes": {
            "role-specs.json": hashlib.sha256((SRC / "role-specs.json").read_bytes()).hexdigest(),
            "role-impact-map.json": hashlib.sha256((SRC / "role-impact-map.json").read_bytes()).hexdigest()
        },
        "generated_hashes": {p.name: hashlib.sha256(t.encode()).hexdigest() for p, t in expected.items()}
    }
    expected[OUT / "manifest.json"] = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    stale = []
    for path, text in expected.items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != text:
            stale.append(path)
            if not args.check: path.write_text(text, encoding="utf-8")
    if args.check and stale:
        print("Stale generated role artifacts:", file=sys.stderr)
        for path in stale: print(f" - {path.relative_to(ROOT)}", file=sys.stderr)
        return 1
    print("Generated role artifacts are current." if not stale else "Regenerated: " + ", ".join(str(p.relative_to(ROOT)) for p in stale))
    return 0


if __name__ == "__main__": raise SystemExit(main())
