from pathlib import Path
root=Path(__file__).parent
owner=(root/'payload/app/src/full/java/com/duoopen/overlay/Fold7Gen6OpeningAttemptOwner.kt').read_text()
patch=(root/'tools/apply_gen6_slice_a.py').read_text()
assert 'semanticGeneration' in owner
assert 'val angle' not in owner and 'var angle' not in owner and 'hingeAngle' not in owner
assert 'Shizuku' not in owner and 'Display' not in owner and 'Panel' not in owner
assert 'previousId in learnedFoldedStateIds' in patch
assert 'onWakeHint(previousId, id)' in patch
assert 'continuity.onEarlyOpeningEdge' not in patch.split('onWakeHint =',1)[1].split(') {',1)[0]
assert 'gen6-wake-hint' in patch
assert 'corroborated-closed' in patch
print('GEN6 SLICE A STATIC GATE: PASS')
