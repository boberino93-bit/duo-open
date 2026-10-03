#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from actuation_policy import bootstrap_prompt, validate_index


def main() -> int:
    p = Path(sys.argv[1] if len(sys.argv) > 1 else "DuoOpen-AgentBus/control/chat_actuation/v1/ACTUATION_INDEX.json")
    doc = json.loads(p.read_text(encoding="utf-8"))
    entries = validate_index(doc)
    for entry in entries:
        bootstrap_prompt(entry)
    print(f"PASS {p}: {len(entries)} bounded entries; cap={doc['max_managed_child_tabs']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
