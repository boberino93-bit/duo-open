#!/usr/bin/env python3
"""HERD V32-R2 static contract checker. Does NOT certify ChatGPT host connectivity."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys

EXPECTED_SHA = "1dd3cbd73092b810f934ff32d33e3f4d968c5474c8e92b6ec7462fb417d0ca47"

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def check(ok, reason):
    if not ok:
        raise AssertionError(reason)

def main():
    root = Path(__file__).resolve().parents[1]
    a = read(root / "AGENT_BOOTSTRAP.json")
    c = read(root / "HERD_V32R2_COMMUNICATION_CONTRACT.json")
    b = read(root / "CHATGPT_PROJECT_REPOSITORY_LINK.json")
    proj = c["project_id"]
    repo = c["repository"]["full_name"]
    logical_board = c["authoritative_transport"]["logical_board"]
    check(a["project_id"] == b["project_id"] == proj, "project identity mismatch")
    check(a["repository"]["full_name"] == b["github_repository"] == repo, "repository mismatch")
    check(a["repository"]["id"] == b["github_repository_id"] == c["repository"]["id"], "repository stable id mismatch")
    check(a["forum"]["authority"] == c["authoritative_transport"]["provider"] == "CHATGPT_NATIVE_LIBRARY", "provider mismatch")
    check(a["forum"]["namespace"] == logical_board and logical_board.endswith("/AgentBus/messages"), "Library logical board path mismatch")
    check(c["canonical_specification"]["sha256"] == EXPECTED_SHA, "canonical specification SHA mismatch")
    check(a["v32r2_required_communication_contract"]["mandatory_on_startup"] is True, "bootstrap does not require policy")
    check(a["v32r2_required_communication_contract"]["path"] == "HERD_V32R2_COMMUNICATION_CONTRACT.json", "wrong policy source")
    check(b["required_for_active_chatgpt_project"] is True, "mandatory GitHub link disabled")
    check(c["chatgpt_project_binding"]["required_for_active_project"] is True, "project link gate disabled")
    check(c["security"]["cross_project_state_default"] == "DENY", "cross-project access expansion")
    check(c["separate_transports"]["github"].endswith("NOT_AGENTBUS"), "GitHub falsely used as live AgentBus")
    check(c["canonical_specification"]["operational_certification"] == "HOLD", "unverified operational certification")
    check(c["canonical_specification"]["independently_certified_gates"] == 0, "fabricated certification gates")
    if b["active_in_chatgpt"] == "ACTIVE":
        check(bool(b["chatgpt_project_id"]) and b["chatgpt_project_file_attachment_readback_verified"],
              "active ChatGPT project lacks independently verified native Project-to-GitHub link")
    if c["authoritative_transport"]["host_verified"]:
        check(c["authoritative_transport"]["independent_authenticated_roundtrips"] > 0 and
              c["authoritative_transport"]["host_scoped_agent_grants_verified"],
              "falsely verified native agent transport")
    if proj == "cv-support":
        check(c["security"]["cross_project_federation"] == "FORBIDDEN_UNLESS_NEW_SEPARATE_OWNER_AUTHORIZATION",
              "CV Support isolation was weakened")
        check(a["original_startup_authority"] == "bootstrap/SECURITY_BOOTSTRAP.md",
              "CV Support security bootstrap displaced")
    if os.environ.get("GITHUB_REPOSITORY"):
        check(os.environ["GITHUB_REPOSITORY"] == repo, "GitHub workflow running in wrong repository")
    print("PASS: Static V32-R2 contract consistent for", repo)
    print("HOLD: Native ChatGPT Project binding and Library agent transport require separate host receipts.")
    if (root / "PROJECT_ROLE_ROUTING_REGISTRY.json").exists():
        reg = read(root / "PROJECT_ROLE_ROUTING_REGISTRY.json")
        link = read(root / "governance/V32R2_CHATGPT_PROJECT_REPOSITORY_BINDINGS.json")
        check(len(reg["projects"]) == len(link["projects"]) == 11, "central portfolio does not contain 11 projects")
        for pid, record in link["projects"].items():
            check(reg["projects"][pid]["repository"] == record["github_repository"], "central routing mismatch " + pid)
            check(reg["projects"][pid]["forum_namespace"] == record["intended_native_library_board"],
                  "central board mismatch " + pid)
        check(reg["projects"]["cv-support"]["non_federated"] is True, "CV Support federation violation")
        print("PASS: Central registry 11-project coverage (host-native linkage still unverified).")

if __name__ == "__main__":
    try:
        main()
    except (AssertionError, KeyError, OSError, ValueError) as exc:
        print("FAIL: V32-R2 static policy:", exc, file=sys.stderr)
        raise SystemExit(1)
