#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, found {count}")
    file.write_text(text.replace(old, new, 1))
    print(f"patched {path}")


SERVICE = "app/src/full/java/com/duoopen/shell/DuoShellService.kt"
COORDINATOR = "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt"

replace_once(
    SERVICE,
    '''            ShellProtocol.COVER_PANEL_GEN4 -> {
                val operation = data.readInt()
                val serviceEpoch = data.readLong()
                val closeCycleId = data.readLong()
                val transitionGeneration = data.readLong()
                val intentSequence = data.readLong()
                val reason = data.readString() ?: "unspecified"
                val identity = clearCallingIdentity()

                val result =
                    try {
                        runCoverMutation {
                            handleGen4PanelCommand(
                                operation = operation,
                                serviceEpoch = serviceEpoch,
                                closeCycleId = closeCycleId,
                                transitionGeneration = transitionGeneration,
                                intentSequence = intentSequence,
                                reason = reason,
                            )
                        }
                    } catch (t: Throwable) {
                        failureBundle("cover-panel-gen4", t)
                    } finally {
                        restoreCallingIdentity(identity)
                    }

                out.writeNoException()
                out.writeBundle(result)
            }
''',
    '''            ShellProtocol.COVER_PANEL_GEN4 -> {
                val binderArrivalNs = SystemClock.elapsedRealtimeNanos()
                val operation = data.readInt()
                val serviceEpoch = data.readLong()
                val closeCycleId = data.readLong()
                val transitionGeneration = data.readLong()
                val intentSequence = data.readLong()
                val reason = data.readString() ?: "unspecified"
                val identity = clearCallingIdentity()
                var mutationStartedNs = 0L

                val result =
                    try {
                        runCoverMutation {
                            mutationStartedNs = SystemClock.elapsedRealtimeNanos()
                            handleGen4PanelCommand(
                                operation = operation,
                                serviceEpoch = serviceEpoch,
                                closeCycleId = closeCycleId,
                                transitionGeneration = transitionGeneration,
                                intentSequence = intentSequence,
                                reason = reason,
                            )
                        }
                    } catch (t: Throwable) {
                        failureBundle("cover-panel-gen4", t)
                    } finally {
                        restoreCallingIdentity(identity)
                    }

                val completedNs = SystemClock.elapsedRealtimeNanos()
                val startedNs = mutationStartedNs
                result.putInt("gen4Operation", operation)
                result.putLong(
                    "gen4QueueUs",
                    if (startedNs > 0L) {
                        ((startedNs - binderArrivalNs) / 1_000L).coerceAtLeast(0L)
                    } else {
                        -1L
                    },
                )
                result.putLong(
                    "gen4ExecutionUs",
                    if (startedNs > 0L) {
                        ((completedNs - startedNs) / 1_000L).coerceAtLeast(0L)
                    } else {
                        -1L
                    },
                )
                result.putLong(
                    "gen4TotalUs",
                    ((completedNs - binderArrivalNs) / 1_000L).coerceAtLeast(0L),
                )

                out.writeNoException()
                out.writeBundle(result)
            }
''',
)

replace_once(
    COORDINATOR,
    '''                "physical=${snapshot.physicalDisplayId} logical=${snapshot.targetLogicalId} " +
                "held=${snapshot.physicalLeaseHeld} routeReady=${snapshot.routeReady}",
''',
    '''                "physical=${snapshot.physicalDisplayId} logical=${snapshot.targetLogicalId} " +
                "held=${snapshot.physicalLeaseHeld} routeReady=${snapshot.routeReady} " +
                "op=${result.getInt("gen4Operation", -1)} " +
                "queueUs=${result.getLong("gen4QueueUs", -1L)} " +
                "execUs=${result.getLong("gen4ExecutionUs", -1L)} " +
                "totalUs=${result.getLong("gen4TotalUs", -1L)}",
''',
)

print("Gen12 Gen4 lane telemetry patch applied successfully")
