# Apply instructions — after a safe non-main branch exists

This package is intentionally not applied to `main`.

When a human-created non-production branch is available, apply the patch from repository root:

```bash
git checkout <non-main-branch>
git apply DUO_OPEN_AGENTBUS_PROTOCOL_HARDENING_V2.patch
python AGENTBUS_IMPORT/protocol/v2/tools/agentbus_protocol.py verify-lock AGENTBUS_IMPORT/protocol/v2/PROTOCOL.lock.json
python -m unittest discover -s AGENTBUS_IMPORT/protocol/v2/tests -v
```

Do not wire these files into discovery/bootstrap or merge them to production as part of this patch. That is deliberately outside this package.
