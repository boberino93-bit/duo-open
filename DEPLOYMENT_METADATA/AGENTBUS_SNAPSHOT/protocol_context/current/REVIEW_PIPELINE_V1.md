# Three-tier Review Pipeline v1
Research -> Manager/Reviewer -> Primary.

Research produces findings plus raw evidence and may piggyback up to three compact process observations on a material handoff. Research does not self-promote ordinary findings to Primary acceptance.

Manager actively discovers Research outputs, dedupes/supersedes, reads raw evidence, verifies current GitHub HEAD and freshness, independently reviews, seeks an additional independent peer check for material findings when practical, resolves contradictions, and emits one complete `READY_FOR_PRIMARY` dossier only after all gates pass. Manager has no production-write or final-acceptance authority.

`READY_FOR_PRIMARY` is an attention-routing state, not acceptance. Primary consumes reviewed dossiers, inspects raw evidence for medium/high-impact findings, and alone records ACCEPT / DEFER / REJECT / REQUEST_MORE_REVIEW before production integration. Primary also records compact process feedback on dossier quality and later build/field outcomes.
