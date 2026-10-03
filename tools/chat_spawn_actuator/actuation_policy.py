from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import base64
import json
import re

SCHEMA = "duoopen-chat-actuation-index/v1"
PROJECT = "duo-open"
REPO = "boberino93-bit/duo-open"
ALLOWED_ROLES = {"MANAGER_REVIEWER", "RESEARCH"}
ALLOWED_STATES = {"RUNNING", "STOPPED"}
HARD_CHILD_TAB_CAP = 19
ID_RE = re.compile(r"^[A-Za-z0-9._:-]+$")


class PolicyError(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    round_id: str
    ticket_id: str
    role: str
    generation: int
    desired_state: str


def validate_index(doc: dict) -> list[Entry]:
    required = {
        "schema", "project", "source_repo", "source_branch", "generation",
        "max_managed_child_tabs", "entries"
    }
    extra = set(doc) - required
    missing = required - set(doc)
    if extra or missing:
        raise PolicyError(f"top-level keys invalid: missing={sorted(missing)} extra={sorted(extra)}")
    if doc["schema"] != SCHEMA or doc["project"] != PROJECT or doc["source_repo"] != REPO:
        raise PolicyError("identity mismatch")
    if doc["source_branch"] != "main":
        raise PolicyError("source_branch must be main")
    if not isinstance(doc["generation"], int) or doc["generation"] < 1:
        raise PolicyError("generation invalid")
    cap = doc["max_managed_child_tabs"]
    if not isinstance(cap, int) or not (1 <= cap <= HARD_CHILD_TAB_CAP):
        raise PolicyError("max_managed_child_tabs invalid")
    raw = doc["entries"]
    if not isinstance(raw, list) or len(raw) > cap:
        raise PolicyError("entry count exceeds cap")

    seen: set[str] = set()
    out: list[Entry] = []
    allowed_entry_keys = {"round_id", "ticket_id", "role", "generation", "desired_state"}
    for item in raw:
        if not isinstance(item, dict) or set(item) != allowed_entry_keys:
            raise PolicyError("entry keys invalid")
        round_id = item["round_id"]
        ticket_id = item["ticket_id"]
        role = item["role"]
        generation = item["generation"]
        desired_state = item["desired_state"]
        if not isinstance(round_id, str) or not round_id or len(round_id) > 160 or not ID_RE.fullmatch(round_id):
            raise PolicyError("round_id invalid")
        if not isinstance(ticket_id, str) or not ticket_id or len(ticket_id) > 160 or not ID_RE.fullmatch(ticket_id):
            raise PolicyError("ticket_id invalid")
        if ticket_id in seen:
            raise PolicyError("duplicate ticket_id")
        seen.add(ticket_id)
        if role not in ALLOWED_ROLES:
            raise PolicyError("role invalid")
        if not isinstance(generation, int) or generation < 1:
            raise PolicyError("entry generation invalid")
        if desired_state not in ALLOWED_STATES:
            raise PolicyError("desired_state invalid")
        out.append(Entry(round_id, ticket_id, role, generation, desired_state))
    return out


def bootstrap_prompt(entry: Entry) -> str:
    # Intentionally deterministic. Remote desired-state cannot provide prompt text.
    return (
        f"You are a Duo Open {entry.role} agent joining an existing round.\n\n"
        f"Bootstrap from /DuoOpen-AgentBus/JOIN_ROUND.md. Claim exactly ticket "
        f"{entry.ticket_id} in round {entry.round_id}. Validate the ticket and current round "
        "before substantive work. Publish your own SESSION_STARTED only after the claim is valid. "
        "If the ticket cannot be validly claimed, publish/report SPAWN_REJECTED or the blocking "
        "evidence and do not improvise another assignment.\n\n"
        "Use the local AgentBus/Artifactory as durable coordination truth and GitHub main as "
        "production truth. Follow current role authority, service interval, regression continuity, "
        "and human-isolation rules."
    )


def desired_running(entries: Iterable[Entry]) -> list[Entry]:
    return [e for e in entries if e.desired_state == "RUNNING"]


DOM_COMMAND_SCHEMA = "duoopen-browser-actuation-command/v1"

def validate_dom_command(doc: dict) -> list[Entry]:
    required = {"schema", "command_id", "issued_by", "max_managed_child_tabs", "entries"}
    if set(doc) != required:
        raise PolicyError("dom command keys invalid")
    if doc["schema"] != DOM_COMMAND_SCHEMA or doc["issued_by"] != "primary":
        raise PolicyError("dom command identity invalid")
    command_id = doc["command_id"]
    if not isinstance(command_id, str) or not ID_RE.fullmatch(command_id) or len(command_id) > 160:
        raise PolicyError("command_id invalid")
    pseudo = {
        "schema": SCHEMA, "project": PROJECT, "source_repo": REPO, "source_branch": "main",
        "generation": 1, "max_managed_child_tabs": doc["max_managed_child_tabs"], "entries": doc["entries"]
    }
    return validate_index(pseudo)

def encode_dom_command(doc: dict) -> str:
    validate_dom_command(doc)
    raw = json.dumps(doc, separators=(",", ":"), sort_keys=True).encode("utf-8")
    token = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return f"DUO_ACTUATOR_V1:{token}:END"

def decode_dom_command(marker: str) -> dict:
    m = re.fullmatch(r"DUO_ACTUATOR_V1:([A-Za-z0-9_-]+):END", marker.strip())
    if not m:
        raise PolicyError("invalid marker")
    token = m.group(1)
    raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    doc = json.loads(raw)
    validate_dom_command(doc)
    return doc
