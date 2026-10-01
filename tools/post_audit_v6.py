#!/usr/bin/env python3
from pathlib import Path


def once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"{label}: expected anchor exactly once in {path}, found {count}"
        )
    p.write_text(text.replace(old, new, 1))


def main() -> None:
    # 1) Version this audited correction separately from the Gen2 base.
    gradle = "app/build.gradle.kts"
    once(gradle, "versionCode = 35", "versionCode = 36", "versionCode")
    once(
        gradle,
        'versionName = "2.0.0-zfold7-gen2-ownership"',
        'versionName = "2.0.1-zfold7-gen2-audit1"',
        "versionName",
    )

    # 2) Fold7 portal geometry: carry the RIGHT inner pane onto the cover.
    # Inner: 1968x2184 => right pane starts at x=984.
    # Cover aspect 1080:2520 == 3:7, canonical source width = 936.
    # Preserve hinge edge at x=984 and crop outer 48 px: [984, 1920).
    host = "app/src/full/java/com/duoopen/overlay/DisplayMirrorHost.kt"

    once(
        host,
        " * used here: sourceRect selects only the LEFT half of the 1968x2184 inner\n",
        " * used here: sourceRect selects the RIGHT half of the 1968x2184 inner\n",
        "host header pane",
    )

    once(
        host,
        (
            "     * Draw the same canonical left-pane crop used by setGeometry:\n"
            "     * 1968x2184 inner -> left 984px pane -> crop outer edge to 936x2184,\n"
            "     * which is exactly the cover's 3:7 aspect ratio.\n"
        ),
        (
            "     * Draw the same canonical right-pane crop used by setGeometry:\n"
            "     * 1968x2184 inner -> right 984px pane -> crop the outer edge to 936x2184,\n"
            "     * preserving the hinge edge. This is exactly the cover's 3:7 aspect ratio.\n"
        ),
        "frozen geometry comment",
    )

    old_frozen = (
        "        val paneWidth =\n"
        "            (bitmap.width / 2)\n"
        "                .coerceAtLeast(1)\n"
        "\n"
        "        val paneHeight =\n"
        "            bitmap.height\n"
        "                .coerceAtLeast(1)\n"
        "\n"
        "        val canonicalPaneWidth =\n"
        "            (\n"
        "                paneHeight.toLong() *\n"
        "                    destinationWidth.toLong() /\n"
        "                    destinationHeight.toLong()\n"
        "                )\n"
        "                .toInt()\n"
        "                .coerceIn(\n"
        "                    1,\n"
        "                    paneWidth,\n"
        "                )\n"
        "\n"
        "        val sourceLeft =\n"
        "            paneWidth -\n"
        "                canonicalPaneWidth\n"
        "\n"
        "        val sourceRect =\n"
        "            Rect(\n"
        "                sourceLeft,\n"
        "                0,\n"
        "                paneWidth,\n"
        "                paneHeight,\n"
        "            )\n"
    )

    new_frozen = (
        "        val paneLeft =\n"
        "            (bitmap.width / 2)\n"
        "                .coerceIn(0, bitmap.width - 1)\n"
        "\n"
        "        val paneWidth =\n"
        "            (bitmap.width - paneLeft)\n"
        "                .coerceAtLeast(1)\n"
        "\n"
        "        val paneHeight =\n"
        "            bitmap.height\n"
        "                .coerceAtLeast(1)\n"
        "\n"
        "        val canonicalPaneWidth =\n"
        "            (\n"
        "                paneHeight.toLong() *\n"
        "                    destinationWidth.toLong() /\n"
        "                    destinationHeight.toLong()\n"
        "                )\n"
        "                .toInt()\n"
        "                .coerceIn(\n"
        "                    1,\n"
        "                    paneWidth,\n"
        "                )\n"
        "\n"
        "        val sourceRight =\n"
        "            paneLeft +\n"
        "                canonicalPaneWidth\n"
        "\n"
        "        val sourceRect =\n"
        "            Rect(\n"
        "                paneLeft,\n"
        "                0,\n"
        "                sourceRight,\n"
        "                paneHeight,\n"
        "            )\n"
    )
    once(host, old_frozen, new_frozen, "frozen right-pane geometry")

    once(
        host,
        '"FROZEN LEFT PANE: inner snapshot → cover $displayId."',
        '"FROZEN RIGHT PANE: inner snapshot → cover $displayId."',
        "frozen status",
    )

    old_live = (
        "        val paneWidth =\n"
        "            (sourceWidth / 2)\n"
        "                .coerceAtLeast(1)\n"
        "\n"
        "        val paneHeight = sourceHeight\n"
        "\n"
        "        /*\n"
        "         * Canonical projection: preserve the hinge edge and crop only the\n"
        "         * outer edge of the left inner pane so source and cover have exactly\n"
        "         * the same aspect ratio. On Fold7 this is 936x2184 -> 1080x2520,\n"
        "         * both exactly 3:7. No destination overscan or non-uniform stretch.\n"
        "         */\n"
        "        val canonicalPaneWidth =\n"
        "            (\n"
        "                paneHeight.toLong() *\n"
        "                    destinationWidth.toLong() /\n"
        "                    destinationHeight.toLong()\n"
        "                ).toInt()\n"
        "                .coerceIn(1, paneWidth)\n"
        "\n"
        "        val sourceLeft =\n"
        "            paneWidth - canonicalPaneWidth\n"
        "\n"
        "        val sourceRect =\n"
        "            Rect(\n"
        "                sourceLeft,\n"
        "                0,\n"
        "                paneWidth,\n"
        "                paneHeight,\n"
        "            )\n"
    )

    new_live = (
        "        val paneLeft =\n"
        "            (sourceWidth / 2)\n"
        "                .coerceIn(0, sourceWidth - 1)\n"
        "\n"
        "        val paneWidth =\n"
        "            (sourceWidth - paneLeft)\n"
        "                .coerceAtLeast(1)\n"
        "\n"
        "        val paneHeight = sourceHeight\n"
        "\n"
        "        /*\n"
        "         * Canonical projection: preserve the hinge edge and crop only the\n"
        "         * outer edge of the right inner pane so source and cover have exactly\n"
        "         * the same aspect ratio. On Fold7 this is x=984..1920 (936x2184)\n"
        "         * -> 1080x2520, both exactly 3:7. No destination overscan or\n"
        "         * non-uniform stretch.\n"
        "         */\n"
        "        val canonicalPaneWidth =\n"
        "            (\n"
        "                paneHeight.toLong() *\n"
        "                    destinationWidth.toLong() /\n"
        "                    destinationHeight.toLong()\n"
        "                ).toInt()\n"
        "                .coerceIn(1, paneWidth)\n"
        "\n"
        "        val sourceRight =\n"
        "            paneLeft + canonicalPaneWidth\n"
        "\n"
        "        val sourceRect =\n"
        "            Rect(\n"
        "                paneLeft,\n"
        "                0,\n"
        "                sourceRight,\n"
        "                paneHeight,\n"
        "            )\n"
    )
    once(host, old_live, new_live, "live right-pane geometry")

    once(
        host,
        '"LEFT PANE GEOMETRY LIVE: inner ${source.displayId} → cover $displayId."',
        '"RIGHT PANE GEOMETRY LIVE: inner ${source.displayId} → cover $displayId."',
        "live status",
    )

    # 3) Never replay an older current-cycle frame after a newer capture starts.
    store = "app/src/full/java/com/duoopen/overlay/Fold7ContinuityFrameStore.kt"
    once(
        store,
        (
            "        if (activeCycle != cycle) return null\n"
            "        if (width <= 0 || height <= 0) return null\n"
            "\n"
            "        return CaptureTicket(\n"
        ),
        (
            "        if (activeCycle != cycle) return null\n"
            "        if (width <= 0 || height <= 0) return null\n"
            "\n"
            "        // A newer capture attempt supersedes the previous frame immediately.\n"
            "        // If this attempt later fails, current() must return null rather than\n"
            "        // resurrecting an older same-cycle image.\n"
            "        latest = null\n"
            "\n"
            "        return CaptureTicket(\n"
        ),
        "capture supersedes old frame",
    )

    # 4) Revisions are authoritative only when stamped in the serialized executor.
    shell = "app/src/full/java/com/duoopen/shell/DuoShellService.kt"
    once(
        shell,
        (
            '                    } catch (t: Throwable) {\n'
            '                        stampCoverLeaseV3(failureBundle("cover-lease-v3", t))\n'
            '                    } finally {\n'
        ),
        (
            '                    } catch (t: Throwable) {\n'
            '                        // Do not manufacture an authoritative shellRevision\n'
            '                        // outside coverMutationExecutor. An unstamped failure\n'
            '                        // is intentionally rejected by the app-side V3 gate.\n'
            '                        failureBundle("cover-lease-v3", t)\n'
            '                    } finally {\n'
        ),
        "serialized V3 failure stamp",
    )

    # 5) Regression test for frame revocation.
    test = "app/src/test/java/com/duoopen/overlay/Fold7Gen2OwnershipTest.kt"
    marker = (
        "    @Test\n"
        "    fun presentationLease_rejectsLateOldAttempt() {\n"
    )
    test_method = (
        "    @Test\n"
        "    fun frameStore_newCaptureRevokesOlderSameCycleFrame() {\n"
        "        val envelope = Fold7CycleEnvelope(9L)\n"
        "        val store = Fold7ContinuityFrameStore<String>()\n"
        "        val cycle = envelope.beginClose(100L)\n"
        "        store.beginCycle(cycle)\n"
        "\n"
        "        val first =\n"
        "            store.beginCapture(\n"
        "                cycle,\n"
        "                width = 1968,\n"
        "                height = 2184,\n"
        "                requestStartedUptimeMs = 110L,\n"
        "                source = Fold7ContinuityFrameStore.Source.SHIZUKU,\n"
        "            )!!\n"
        "\n"
        "        assertNotNull(\n"
        "            store.publish(\n"
        "                first,\n"
        "                capturedUptimeMs = 115L,\n"
        "                completedUptimeMs = 120L,\n"
        "                timestampQuality = Fold7ContinuityFrameStore.TimestampQuality.REQUEST_BOUNDED,\n"
        '                payload = "first",\n'
        "            ),\n"
        "        )\n"
        "        assertNotNull(store.current(cycle, 121L, 10_000L, 1968, 2184))\n"
        "\n"
        "        val second =\n"
        "            store.beginCapture(\n"
        "                cycle,\n"
        "                width = 1968,\n"
        "                height = 2184,\n"
        "                requestStartedUptimeMs = 122L,\n"
        "                source = Fold7ContinuityFrameStore.Source.SHIZUKU,\n"
        "            )!!\n"
        "\n"
        "        assertNull(store.current(cycle, 123L, 10_000L, 1968, 2184))\n"
        "\n"
        "        assertNotNull(\n"
        "            store.publish(\n"
        "                second,\n"
        "                capturedUptimeMs = 124L,\n"
        "                completedUptimeMs = 125L,\n"
        "                timestampQuality = Fold7ContinuityFrameStore.TimestampQuality.REQUEST_BOUNDED,\n"
        '                payload = "second",\n'
        "            ),\n"
        "        )\n"
        "        assertEquals(\n"
        '            "second",\n'
        "            store.current(cycle, 126L, 10_000L, 1968, 2184)?.payload,\n"
        "        )\n"
        "    }\n"
        "\n"
    )
    once(test, marker, test_method + marker, "frame revocation regression test")

    print("POST-AUDIT SOURCE PATCH: PASS")


if __name__ == "__main__":
    main()
