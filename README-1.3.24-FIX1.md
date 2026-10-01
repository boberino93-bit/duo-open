# Duo Open 1.3.24 Early Wake — Fix 1

CI exposed a real opening-state regression before field installation.

Problem:
After WakeInner at ~3 degrees, Samsung can still report the cover as native
below 12 degrees. The old native-cover-authoritative guard could immediately
collapse OPENING_FROM_CLOSED / INNER_HANDOFF back to NATIVE_COVER before the
physical inner panel had time to wake.

Fix:
Latch the opening states while angle >= 3 degrees and direction has not
reversed toward closing. Native-cover ownership resumes immediately if the
hinge actually reverses toward closed.

Added regression coverage:
- opening reaches INNER_HANDOFF at ~8 degrees while cover topology is still native;
- a steady sample does not collapse the opening state;
- a real closing reversal does return to NATIVE_COVER.

No thresholds, shell power code, renderer code, Transition Lab code, or mirror
geometry are changed by this corrective package.
