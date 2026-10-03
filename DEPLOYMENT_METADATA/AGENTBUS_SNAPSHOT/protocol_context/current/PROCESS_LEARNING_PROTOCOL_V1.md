# DPL/1 Process Learning Protocol v1
DPL/1 learns workflow, not authority. Records are immutable; corrections create later superseding records.

Capture evidence about technical findings and coordination strategy, instruction failures, handoff formats, review methods, routing/liveness, rate limits, tooling/recovery behavior, and downstream Primary/build/field outcomes. Prefer measurable outcomes over agent sentiment. Use downstream evidence when available: Primary decision/rework, raw-evidence reopen, decision latency, build outcome, field outcome, later supersession.

Research normally piggybacks up to three compact process observations on an existing material handoff; do not create one file per minor observation. Managers read broadly and write narrowly: group/dedupe observations, inspect evidence and downstream outcomes, independently peer-review, classify LOW/MEDIUM/HIGH risk, and batch non-promoted dispositions.

Promotion: LOW may become BOOTSTRAP_READY only after Manager + independent peer validation. MEDIUM requires two independent validations or explicit Primary approval. HIGH never auto-applies and MUST become PRIMARY_REVIEW_REQUIRED. No learned overlay may grant authority, permissions, production-write access, credential access, or destructive capability.

The next bootstrap compiler MUST revalidate every lesson and its evidence; directory placement is never sufficient proof.
