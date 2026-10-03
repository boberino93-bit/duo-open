# DPL/1 Bootstrap Learning Gate v1
Bootstrap generations are immutable files at `learning/v1/bootstrap/<generation>.json`; there is no mutable CURRENT pointer. New Research, Manager, and Primary bootstraps list that directory, select the newest valid generation, validate schema/evidence, and apply only the overlay for their role.

Every compilation revalidates every included lesson instead of trusting `bootstrap-ready/` placement. LOW requires Manager + independent peer validation. MEDIUM requires two independent validations or Primary approval. HIGH is forbidden from automatic application and must route to `primary-review/` as PRIMARY_REVIEW_REQUIRED.

Overlays optimize workflow only. They cannot grant or expand authority, permissions, production-write access, credential access, destructive capabilities, or bypass the Research -> Manager -> Primary review pipeline. Primary remains sole production acceptance/integration authority.
