DUO OPEN GEN5 BETA1 — VIRTUAL HINGE OPENING BUILD

1. Import this ZIP at repository root. Do not nest it in an outer folder.
2. Commit/push the imported support files including APPLY_GEN5_BETA1_NOW.txt.
3. The workflow `Apply Duo Open Gen5 Beta1 Virtual Hinge` will verify the exact current runtime blobs.
4. CI applies the Gen5 patch ephemerally, validates invariants, runs focused regression tests, then runs the full Android build gate.
5. Only if all gates pass does CI commit the runtime and upload the Beta1 APK artifact.

This package also changes the obsolete `Build Z Fold 7 Motion-Gated Cover Power 1.3.16` workflow to manual-only so a successful Gen5 runtime commit is not followed by a meaningless historical red workflow.

Do not treat import alone as a successful build. The dedicated workflow result is authoritative.
