# Fold7 Gen2 Ownership Batch D Fix 1

The failed Batch D build exposed a second legacy mirror/panel ownership path in
FoldOverlayService. That path was no longer driven by onHinge(), and its old
safety-reset runnable was never scheduled, but it still contained direct
DisplayMirrorHost construction and global stopDisplayMirror() teardown.

Fix 1 applies the original Batch D ownership integration, removes that orphaned
service-level state machine, and makes Fold7ContinuityCoordinator the single
production owner for mirror and cover-panel continuity.

CI rejects any remaining service-level DisplayMirrorHost construction, global
mirror STOP, or retired secondary-display experiment path. It then runs
testFullDebugUnitTest and assembleFullDebug and commits only if both pass.

Batch C thread-confinement work remains intentionally excluded.
