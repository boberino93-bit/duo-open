# Duo Open Gen2 Executor V2 — deploy from current staged repository

## Why the prior wrapper failed

The first staged-state wrapper required:

`HEAD == c0a12450524296dccf74401df73d688d9e22f4b1`

Importing that wrapper created commit `de6bb7324026bd8aa5406b6af546543d9e71ce77`,
so the exact-HEAD guard invalidated itself before execution.

V2 fixes that design error.

It does **not** require exact HEAD. It requires that the original staged Gen2
commit `c0a12450524296dccf74401df73d688d9e22f4b1` is an ancestor of the current
checkout, verifies every critical staged Gen2 file by exact Git blob identity,
then asks the original installer to verify every audited production source blob.

Therefore importing/committing this V2 executor does not make it stale.

## Root action

After this package has been imported/committed, from the repository root run:

```bash
python3 deploy_staged_gen2_v2.py .
```

Do not merely import the file. Execute it.

The executor will:

1. require a clean checkout;
2. require the staged Gen2 commit to be in current ancestry;
3. verify the original Gen2 staging tools/models by exact Git blob SHA;
4. invoke `tools/apply_gen2.py --force --check-only`;
5. the original installer then verifies all audited production blob identities;
6. apply the Gen2 runtime changes;
7. run structural post-apply verification;
8. run `git diff --check`;
9. require the expected production runtime diff;
10. run `testFullDebugUnitTest` and `assembleFullDebug`;
11. leave the changes uncommitted for review.

The script never commits or pushes.

## If it fails

Do not import another package immediately. Capture and return the complete
terminal output beginning with `GEN2 EXECUTOR V2: FAIL:` or the Gradle failure.
That output will identify the next real integration issue.

## Expected success markers

- `STAGED GEN2 CONTENT: PASS`
- `AUDITED PRODUCTION BLOBS: PASS`
- `GEN2 PRODUCTION DIFF: PASS`
- `GRADLE GATES: PASS`
- `GEN2 EXECUTION COMPLETE`

After success, review and commit the generated production diff.
