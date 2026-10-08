# Gen12.3 angle-feed forensics

Source bundle: `duoopen-debug-1791442095112.zip`
Source build: `5.6.2-gen12-2-route-retention-fence-zfold7` (`versionCode 58`).

## Confirmed field sequence

- Last accepted Samsung precise sample: `4.0°` at uptime `33686524`.
- Native-cover topology had already become authoritative: cover logical `0`, inner logical `1`.
- The angle-source diagnostic then changed from `live/FoldInteractive` to `none` while the last precise sample was still only 847 ms old.
- At 2.85 s without a callback the feed marked `readerFresh=false`, but the old implementation only expired precise authority; it did not replace the reader.
- Poll commands continued to return `sent=true` in roughly 0.06–0.19 ms while every subsequent poll timed out.
- The transition trace retained the same Samsung hinge sample sequence while vsync continued, proving rendering remained alive while geometry acquisition stopped making forward progress.

## Root cause

The acquisition path assumed the current `Display.DEFAULT_DISPLAY` was always the correct wallpaper-command host. On Fold7 native-cover handoff, logical display 0 becomes the cover while the Samsung FoldInteractive angle producer can remain associated with the hidden inner side. Rebuilding the command anchor only on the default display therefore moves commands away from the producer.

The shell reader also rejected FoldInteractive `onCommand` lines unless Samsung logged the wallpaper as visible. That is incompatible with using the hidden inner FoldInteractive instance as the precise producer during native-cover topology.

Finally, repeated unanswered polls had no reader replacement watchdog, so a wedged/misdirected reader could time out indefinitely.

## Gen12.3 mitigation

1. Maintain wallpaper-command anchors on every available Fold7 built-in panel (1968x2184 inner and 1080x2520 cover), including disabled logical displays when Android 17 exposes them.
2. Send each uniquely tagged poll command through every valid Fold7 anchor. The shell reader deduplicates replies by poll sequence.
3. Accept fresh exact-action FoldInteractive replies even when Samsung reports `isVisible=false`; action identity, epoch freshness and poll sequence remain the authority checks.
4. Replace the reader/session after three consecutive 96 ms timeouts (288 ms detection), with a 750 ms anti-storm restart interval.
5. Preserve session fencing so late callbacks from a replaced reader cannot mutate current geometry.

This is intentionally independent of the Gen12.2 route-retention fix.