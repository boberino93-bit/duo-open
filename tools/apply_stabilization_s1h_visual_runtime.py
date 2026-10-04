#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

SERVICE = Path("app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt")
ENGINE = Path("app/src/full/java/com/duoopen/overlay/PanelEngine.kt")
EXPORTER = Path("app/src/main/java/com/duoopen/debug/DebugBundleExporter.kt")
VISUAL = Path("app/src/full/java/com/duoopen/overlay/Fold7VisualForensics.kt")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_engine(text: str) -> str:
    if "diagnosticExcludedLayers" in text:
        return text
    old = '''    private fun excludedLayers(): List<SurfaceControl> {
        val view = (surface as? SnapshotSurface)?.view ?: return emptyList()
        return listOfNotNull(rootSurfaceControl(view))
    }
'''
    new = old + '''
    /**
     * S1H diagnostics use the same exclusion handle as the live renderer so
     * captured evidence shows the wallpaper/widgets/apps beneath Duo Open.
     */
    internal fun diagnosticExcludedLayers(): List<SurfaceControl> =
        excludedLayers()
'''
    return replace_once(text, old, new, "S1H overlay exclusion access")


def transform_service(text: str) -> str:
    if "private lateinit var visualForensics:" in text:
        return text

    text = replace_once(
        text,
        '''    private lateinit var continuity: Fold7ContinuityCoordinator
    private lateinit var gen3Visual: Fold7Gen3VisualCoordinator
''',
        '''    private lateinit var continuity: Fold7ContinuityCoordinator
    private lateinit var gen3Visual: Fold7Gen3VisualCoordinator
    private lateinit var visualForensics: Fold7VisualForensics
''',
        "S1H service field",
    )

    text = replace_once(
        text,
        '''        gen3Visual =
            Fold7Gen3VisualCoordinator(
                service = this,
                displayManager = displayManager,
                handler = handler,
                serviceEpoch = serviceEpoch,
                gen2 = gen2,
                currentHingeAngle = {
                    hinge.lastAngle
                },
            )

        deviceStateObserver =
''',
        '''        gen3Visual =
            Fold7Gen3VisualCoordinator(
                service = this,
                displayManager = displayManager,
                handler = handler,
                serviceEpoch = serviceEpoch,
                gen2 = gen2,
                currentHingeAngle = {
                    hinge.lastAngle
                },
            )

        visualForensics =
            Fold7VisualForensics(
                service = this,
                displayManager = displayManager,
                handler = handler,
                scope = scope,
                excludedLayersForDisplay = { displayId ->
                    engines[displayId]
                        ?.diagnosticExcludedLayers()
                        .orEmpty()
                },
            )

        deviceStateObserver =
''',
        "S1H visual forensics init",
    )

    text = replace_once(
        text,
        '''                if (
                    beforeOpeningState ==
                        Fold7ContinuityController.State.NATIVE_COVER &&
                    continuity.state ==
                        Fold7ContinuityController.State.OPENING_FROM_CLOSED
                ) {
                    gen3Visual.beginOpening(
                        generation = continuity.generation,
                        reason = "device-state:$reason",
                    )
                }
''',
        '''                if (
                    beforeOpeningState ==
                        Fold7ContinuityController.State.NATIVE_COVER &&
                    continuity.state ==
                        Fold7ContinuityController.State.OPENING_FROM_CLOSED
                ) {
                    gen3Visual.beginOpening(
                        generation = continuity.generation,
                        reason = "device-state:$reason",
                    )
                    visualForensics.startOpeningBurst(
                        reason = "device-state:$reason",
                        generation = continuity.generation,
                    )
                }
''',
        "S1H device-state burst trigger",
    )

    text = replace_once(
        text,
        '''            if (
                beforeState ==
                    Fold7ContinuityController.State.NATIVE_COVER &&
                continuity.state ==
                    Fold7ContinuityController.State.OPENING_FROM_CLOSED
            ) {
                gen3Visual.beginOpening(
                    generation = continuity.generation,
                    reason = "authoritative-hinge-opening-edge",
                )
            }
''',
        '''            if (
                beforeState ==
                    Fold7ContinuityController.State.NATIVE_COVER &&
                continuity.state ==
                    Fold7ContinuityController.State.OPENING_FROM_CLOSED
            ) {
                gen3Visual.beginOpening(
                    generation = continuity.generation,
                    reason = "authoritative-hinge-opening-edge",
                )
                visualForensics.startOpeningBurst(
                    reason = "authoritative-hinge-opening-edge",
                    generation = continuity.generation,
                )
            }
''',
        "S1H hinge fallback burst trigger",
    )

    text = replace_once(
        text,
        '''        if (::gen3Visual.isInitialized) {
            gen3Visual.destroy()
        }

        if (::continuity.isInitialized) {
''',
        '''        if (::gen3Visual.isInitialized) {
            gen3Visual.destroy()
        }

        if (::visualForensics.isInitialized) {
            visualForensics.stop("service-destroy")
        }

        if (::continuity.isInitialized) {
''',
        "S1H visual forensics teardown",
    )
    return text


def transform_exporter(text: str) -> str:
    if "visualForensicFiles" in text:
        return text

    text = text.replace(
        " * No screen pixels, notification contents, messages, passwords or keystrokes\n * are added here. This packages the diagnostic files Duo Open already records.\n",
        " * S1H diagnostic builds may include user-requested visual-forensics frames.\n * Secure/protected captures are fail-closed and are never persisted by S1H.\n",
    )

    text = replace_once(
        text,
        '''        val sessions =
            transitionDirectory
                .listFiles()
                .orEmpty()
                .filter {
                    it.isFile &&
                        it.name.startsWith(
                            "transition-"
                        ) &&
                        it.name.endsWith(
                            ".jsonl"
                        )
                }
                .sortedByDescending {
                    it.lastModified()
                }
                .take(
                    MAX_TRANSITION_SESSIONS
                )
                .sortedBy {
                    it.lastModified()
                }

        ZipOutputStream(
''',
        '''        val sessions =
            transitionDirectory
                .listFiles()
                .orEmpty()
                .filter {
                    it.isFile &&
                        it.name.startsWith(
                            "transition-"
                        ) &&
                        it.name.endsWith(
                            ".jsonl"
                        )
                }
                .sortedByDescending {
                    it.lastModified()
                }
                .take(
                    MAX_TRANSITION_SESSIONS
                )
                .sortedBy {
                    it.lastModified()
                }

        val visualForensicRoot =
            File(
                app.filesDir,
                "visual-forensics",
            )

        val visualBurstDirectories =
            visualForensicRoot
                .listFiles()
                .orEmpty()
                .filter {
                    it.isDirectory &&
                        it.name.startsWith("burst-")
                }
                .sortedByDescending {
                    it.lastModified()
                }
                .take(MAX_VISUAL_BURSTS)
                .sortedBy {
                    it.lastModified()
                }

        val visualForensicFiles =
            visualBurstDirectories
                .flatMap { directory ->
                    directory.walkTopDown()
                        .filter { it.isFile }
                        .toList()
                }

        ZipOutputStream(
''',
        "S1H exporter visual files",
    )

    text = replace_once(
        text,
        '''                        appendLine(
                            "transitionSessions=${sessions.size}"
                        )
''',
        '''                        appendLine(
                            "transitionSessions=${sessions.size}"
                        )
                        appendLine(
                            "visualForensicBursts=${visualBurstDirectories.size}"
                        )
                        appendLine(
                            "visualForensicFiles=${visualForensicFiles.size}"
                        )
                        appendLine(
                            "visualForensicsMayContainScreenPixels=true"
                        )
                        appendLine(
                            "visualForensicsSecureFramesPersisted=false"
                        )
''',
        "S1H exporter info",
    )

    text = replace_once(
        text,
        '''            sessions.forEach { session ->
                zip.putFileIfPresent(
                    source =
                        session,
                    name =
                        "transition-lab/${session.name}",
                )
            }
        }
''',
        '''            sessions.forEach { session ->
                zip.putFileIfPresent(
                    source =
                        session,
                    name =
                        "transition-lab/${session.name}",
                )
            }

            visualBurstDirectories.forEach { directory ->
                directory.walkTopDown()
                    .filter { it.isFile }
                    .forEach { source ->
                        val relative =
                            source.relativeTo(directory)
                                .invariantSeparatorsPath
                        zip.putFileIfPresent(
                            source = source,
                            name =
                                "visual-forensics/${directory.name}/$relative",
                        )
                    }
            }
        }
''',
        "S1H exporter archive visual files",
    )

    text = replace_once(
        text,
        '''    private const val MAX_TRANSITION_SESSIONS =
        8

    private const val EXPORT_RETENTION_MS =
''',
        '''    private const val MAX_TRANSITION_SESSIONS =
        8

    private const val MAX_VISUAL_BURSTS =
        4

    private const val EXPORT_RETENTION_MS =
''',
        "S1H exporter retention constant",
    )
    return text


def apply(repo: Path, check_only: bool) -> None:
    if not (repo / VISUAL).exists():
        raise RuntimeError("S1H visual source missing")
    outputs = {
        ENGINE: transform_engine((repo / ENGINE).read_text()),
        SERVICE: transform_service((repo / SERVICE).read_text()),
        EXPORTER: transform_exporter((repo / EXPORTER).read_text()),
    }
    visual = (repo / VISUAL).read_text()
    for needle, text in (
        ('diagnosticExcludedLayers', outputs[ENGINE]),
        ('visualForensics.startOpeningBurst(', outputs[SERVICE]),
        ('visualForensicFiles', outputs[EXPORTER]),
        ('MANAGED_PROFILE_SCREEN_CAPTURE_POLICY', visual),
        ('FLAG_SECURE_OR_SECURE_WINDOW', visual),
    ):
        if needle not in text:
            raise RuntimeError(f"S1H runtime check missing: {needle}")
    if not check_only:
        for path, content in outputs.items():
            (repo / path).write_text(content)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=".")
    p.add_argument("--check", action="store_true")
    a = p.parse_args()
    apply(Path(a.repo).resolve(), a.check)
    print("S1H visual runtime/export instrumentation: " + ("verified" if a.check else "applied"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
