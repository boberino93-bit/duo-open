# Field evidence used for Beta2

Two 5.0.0-beta1-zfold7 (versionCode 42) debug bundles were supplied on
2026-10-02 and inspected before preparing this service pack.

## Bundle A — generated 2026-10-03T00:01:08Z

Input SHA-256: `7a445279df035f00382d1eefdaabcc2a81823fe3c6e16946e502d063b05afe12`

- 5 successful `inner-wake` shell calls.
- Mean reported shell+queue wake latency: ~188.5 ms; max ~249.5 ms.
- All 5 recorded opening visual starts occurred with `precise=90.0`, not at the
  low-angle beginning of physical opening.
- 5 DeviceState opening edges were logged as ignored; 0 were accepted in the
  retained debug-log window.
- 30 explicit `live recapture suppressed` events.
- 0 live-frame events.

## Bundle B — generated 2026-10-02T23:24Z

Input SHA-256: `9cc850b9f6988f339d9d26ba552a4526c8cbb2cfc7b2b057ff9e406ae183c38a`

- 5 successful `inner-wake` shell calls.
- Mean reported shell+queue wake latency: ~210.5 ms; max ~320.7 ms.
- 7 recorded opening visual starts: 3 at precise 0°, 4 at precise 90°.
- 5 DeviceState opening edges were ignored; 2 were accepted.
- 26 logged Gen5 `BLIND_BOOTSTRAP` frames.
- One captured opening held `physical=90.0` while the virtual visual hinge ran
  through approximately 13° -> 92° independently.
- 24 explicit `live recapture suppressed` events.
- 0 live-frame events.

## Conclusions used by this pack

- The Samsung angle path can be very low latency once samples are flowing, but
  opening start frequently reaches our visual pipeline too late/stale.
- Successful physical display-power reflection is not proof that the inner
  logical route/useful pixels are ready.
- Blind visual prediction is demonstrably capable of diverging from the
  measured hinge during the first opening phase.
- The live-content freeze is not speculative: production diagnostics explicitly
  report that live recapture is suppressed on Fold7.
