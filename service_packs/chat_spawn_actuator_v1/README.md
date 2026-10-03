# Chat Spawn Actuator V1 Service Pack

Control-plane only. No Android runtime files are modified.

Adds:
- bounded desired-state schema/index for host actuation;
- V2 spawn adapter contract;
- Chrome/Chromium local actuator with an armed-Primary DOM command bridge plus optional GitHub desired-state recovery feed and fixed local bootstrap prompt;
- Python policy verifier/tests;
- CI workflow for static/policy checks.

Promotion gate from `MANUAL_FALLBACK` to `LOCAL_BROWSER_ACTUATOR` requires one live end-to-end test where an autonomously opened child chat validates its ticket and writes its own `SESSION_STARTED` to AgentBus.
