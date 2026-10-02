#!/usr/bin/env python3
"""Append-only Duo Open user interaction model helper.

This tool records project-scoped user interaction events and compiles an
inspectable model snapshot. It intentionally avoids psychological/sensitive
trait inference. Predictions are workflow hypotheses only.
"""
from __future__ import annotations
import argparse, hashlib, json, re, uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

EVENT_SCHEMA = "duoopen-user-interaction-event/v1"
MODEL_SCHEMA = "duoopen-user-interaction-model/v1"
SENSITIVE_PATTERNS = [
    (re.compile(r"(?i)\b(password|passwd|token|api[_ -]?key|secret)\b\s*[:=]\s*\S+"), r"\1=[REDACTED]"),
    (re.compile(r"\b\d{12,19}\b"), "[REDACTED_NUMBER]"),
]

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def safe_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def digest_text(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()

def redact(text: str) -> tuple[str,bool]:
    out=text; changed=False
    for pat,repl in SENSITIVE_PATTERNS:
        new=pat.sub(repl,out)
        changed |= new != out
        out=new
    return out,changed

def infer_intents(text: str) -> list[str]:
    t=text.lower(); tags=[]
    rules={
        "VERIFY":["verify","integrity","check","still to be made","still isn't","still isnt","working"],
        "IMPLEMENT":["implement","fix","edit","change","do what you can","create"],
        "PACKAGE":["package","zip","folder","copy into root","drag","root of main"],
        "PERSISTENCE":["message forum","message board","self replicating","replicating","database","reference"],
        "AUTOMATE":["automatically","automatic","running sequences","initiation"],
        "STATUS":["successful","successfully","committed","applied","working"],
    }
    for tag,phrases in rules.items():
        if any(p in t for p in phrases): tags.append(tag)
    return tags or ["GENERAL"]

def workflow_preferences(text: str) -> list[str]:
    t=text.lower(); prefs=[]
    if "root" in t and ("copy" in t or "drag" in t): prefs.append("ROOT_SAFE_PACKAGE")
    if "do what you can" in t or "implement" in t: prefs.append("IMPLEMENT_OVER_ONLY_DESCRIBE")
    if "verify" in t or "integrity" in t: prefs.append("VERIFY_BEFORE_CLAIM")
    if "automatically" in t or "self replic" in t: prefs.append("AUTOMATIC_SUCCESSOR_INHERITANCE")
    if len(text.split()) < 35: prefs.append("DIRECT_COMPACT_REQUESTS")
    return prefs

def candidate_followups(tags:list[str], prefs:list[str]) -> list[dict]:
    q=[]
    def add(question,confidence):
        if question not in [x["question"] for x in q]: q.append({"question":question,"confidence":confidence})
    if "PACKAGE" in tags or "ROOT_SAFE_PACKAGE" in prefs:
        add("Can I copy or drag this directly into the root of main?",0.82)
        add("Does this package contain everything the next agent needs?",0.72)
    if "IMPLEMENT" in tags:
        add("What did you actually change versus only document?",0.74)
    if "VERIFY" in tags:
        add("What still is not fixed or still needs physical validation?",0.78)
    if "PERSISTENCE" in tags or "AUTOMATIC_SUCCESSOR_INHERITANCE" in prefs:
        add("Will future initiation ZIPs load this automatically without me repeating it?",0.86)
    if "STATUS" in tags:
        add("Was it actually committed/applied successfully?",0.80)
    return q

def record(args):
    root=Path(args.root)
    events=root/"events"; events.mkdir(parents=True,exist_ok=True)
    text,redacted=redact(args.text)
    tags=infer_intents(text); prefs=workflow_preferences(text)
    event={
        "schema":EVENT_SCHEMA,
        "id":f"ui-{safe_ts()}-{uuid.uuid4().hex[:8]}",
        "timestamp_utc":utc_now(),
        "agent_instance_id":args.agent,
        "source":"USER_MESSAGE",
        "user_text":text,
        "user_text_sha256":digest_text(text),
        "intent_tags":tags,
        "mannerism_features":{
            "brevity":"HIGH" if len(text.split())<35 else "MEDIUM" if len(text.split())<90 else "LOW",
            "action_bias":"HIGH" if "IMPLEMENT" in tags else "MEDIUM",
            "prefers_direct_answer":True,
            "spelling_normalization_needed":False
        },
        "workflow_preferences":prefs,
        "candidate_followups":candidate_followups(tags,prefs),
        "sensitive_redaction_applied":redacted
    }
    path=events/f"{safe_ts()}__{args.agent}__{event['id']}.json"
    path.write_text(json.dumps(event,indent=2)+"\n")
    print(path)

def compile_model(args):
    root=Path(args.root); events_dir=root/"events"; models=root/"models"; models.mkdir(parents=True,exist_ok=True)
    events=[]
    for p in sorted(events_dir.glob("*.json")):
        try:
            e=json.loads(p.read_text())
            if e.get("schema")==EVENT_SCHEMA: events.append(e)
        except Exception: pass
    if not events: raise SystemExit("no valid events")
    intents=Counter(); prefs=Counter(); follow=defaultdict(lambda:{"sum":0.0,"count":0,"events":[]})
    for e in events:
        intents.update(e.get("intent_tags",[])); prefs.update(e.get("workflow_preferences",[]))
        for c in e.get("candidate_followups",[]):
            f=follow[c["question"]]; f["sum"]+=float(c.get("confidence",0)); f["count"]+=1; f["events"].append(e["id"])
    n=len(events)
    model={
        "schema":MODEL_SCHEMA,
        "id":f"uim-{safe_ts()}-{uuid.uuid4().hex[:8]}",
        "timestamp_utc":utc_now(),
        "source_event_ids":[e["id"] for e in events],
        "source_event_sha256":[e.get("user_text_sha256") for e in events],
        "intent_frequencies":dict(intents.most_common()),
        "workflow_preferences":[
            {"name":k,"evidence_count":v,"confidence":round(min(.97,.5+.1*v),2)} for k,v in prefs.most_common()
        ],
        "likely_next_questions":sorted([
            {"question":q,"confidence":round(min(.95, d["sum"]/d["count"] + .02*(d["count"]-1)),2),"evidence_event_ids":d["events"]}
            for q,d in follow.items()
        ], key=lambda x:x["confidence"], reverse=True)[:12],
        "interaction_count":n,
        "guardrails":[
            "Predictions are advisory and never override current user instructions.",
            "No sensitive-trait inference.",
            "Do not store credentials, secrets, unrelated private data, or private account identifiers.",
            "Use predictions to prepare evidence, not to perform unrequested actions."
        ]
    }
    path=models/f"{safe_ts()}__{model['id']}.json"
    path.write_text(json.dumps(model,indent=2)+"\n")
    print(path)

def latest(args):
    paths=sorted((Path(args.root)/"models").glob("*.json"))
    if not paths: raise SystemExit("no model snapshots")
    print(paths[-1]); print(paths[-1].read_text())

def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd",required=True)
    r=sub.add_parser("record"); r.add_argument("--root",required=True); r.add_argument("--agent",required=True); r.add_argument("--text",required=True); r.set_defaults(func=record)
    c=sub.add_parser("compile"); c.add_argument("--root",required=True); c.set_defaults(func=compile_model)
    l=sub.add_parser("latest"); l.add_argument("--root",required=True); l.set_defaults(func=latest)
    a=ap.parse_args(); a.func(a)
if __name__=="__main__": main()
