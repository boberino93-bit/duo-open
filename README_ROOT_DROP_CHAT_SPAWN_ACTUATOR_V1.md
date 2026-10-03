# DUO OPEN — Chat Spawn Actuator V1 Root Drop

Baseline observed when authored: `boberino93-bit/duo-open@9a5e5cbf36aa9c721f238ba974b44d2a13578b07`.

This package does not modify Android runtime source. V1.1 adds an armed-Primary DOM command bridge so the active Primary can actuate child tabs without requiring GitHub writes, while retaining the GitHub desired-state feed for recovery/future background control. Promotion still requires a live child-authored SESSION_STARTED.

Important: simply extracting this package does not make spawning autonomous. The browser extension must be installed/configured and this Primary conversation armed once from the extension popup. GitHub repository writes are still 403 and therefore block only the durable/recovery feed, not the active DOM command path.
