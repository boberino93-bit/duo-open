# Duo Open Gen7 Root-Drop SP2 — Shizuku/Onboarding + User Interaction Model

This archive is intentionally laid out to be extracted/copied **directly into the root of the `duo-open` checkout**. It does not require placing a wrapper folder in the repository.

## What it adds

1. Carries forward the fail-closed Shizuku + wallpaper onboarding service-pack patch.
2. Adds `USER_INTERACTION_MODEL_PROTOCOL_V1.md`, an append-only project interaction model that records material user questions/directives, recurring workflow preferences, and possible next questions.
3. Adds `BOOTSTRAP_V7.md`, `AGENT_DISCOVERY_V7.json`, and `DUO_OPEN_AGENT_GENERATION_TEMPLATE_V11.txt` so future agents and generated initiation ZIPs automatically look for the live user-model database.
4. Adds a deterministic helper at `tools/user_interaction_model.py` and a ZIP injector at `tools/inject_user_model_into_zip.py`.
5. Includes a seed model built only from the project-scoped user messages in the current service-pack conversation.
6. Includes `AGENTBUS_IMPORT/` containing the files/messages/events that a Primary agent can publish to the live `/DuoOpen-AgentBus/` tree.

## Apply after copying/extracting into repo root

Windows PowerShell:

```powershell
.\APPLY_AFTER_COPY.ps1
```

macOS/Linux:

```bash
./APPLY_AFTER_COPY.sh
```

Or explicitly:

```bash
python APPLY_AFTER_COPY.py --check
python APPLY_AFTER_COPY.py
```

The app patch is exact-baseline/fail-closed. If overlapping Android source has drifted, it stops instead of guessing.

If you have a materialized local copy of the live AgentBus, the Primary can additionally run:

```bash
python APPLY_AFTER_COPY.py --agentbus-root /path/to/DuoOpen-AgentBus
```

That import is create-only: it refuses to overwrite a different existing protocol/message/event.

## User-model behavior

The user model is advisory. It can prepare evidence for likely follow-ups, but it cannot invent authorization or override the current request. The protocol explicitly excludes credentials/secrets, unrelated private data, and sensitive-trait inference.

The current seed predicts workflow questions such as whether a package can be copied directly into root, what remains unfixed/unvalidated, whether changes were actually applied, and whether future initiation ZIPs inherit the new behavior automatically. These are hypotheses with evidence/confidence, not assumptions.
