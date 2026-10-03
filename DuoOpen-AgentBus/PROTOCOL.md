# Export recovery protocol index

This file is generated for the export and is not claimed to be an independently persisted live AgentBus protocol.

Authoritative packaged controls are under `control/`. Startup order: verify `EXPORT_MANIFEST.json`, choose exactly one role from `templates/CANONICAL_ROLE_PACKAGE_REGISTRY_20261003.json`, verify its SHA-256, read that role package's START_HERE + canonical refresh state, load the complete `messages/` snapshot, then reconcile live messages newer than the export cutoff.

The REG/3 reference roles inside the first Artifactory NG shadow trial are reference-only and must not replace the canonical role packages in `templates/`.
