#!/usr/bin/env python3
"""Apply the already-staged Duo Open Gen2 bundle to production source.

Target repository state:
  c0a12450524296dccf74401df73d688d9e22f4b1

This wrapper intentionally does not commit or push. It validates the staged
bundle and audited runtime blobs, invokes the repository's existing Gen2
installer, runs post-apply verification, and by default executes the mandatory
Gradle gates.
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

EXPECTED_HEAD = "c0a12450524296dccf74401df73d688d9e22f4b1"
AUDITED_RUNTIME_BASELINE = "586c308649258145b3da9b5ea27b726a6fb3647a"

# Git blob identities of the staging machinery as committed at EXPECTED_HEAD.
EXPECTED_STAGED_BLOBS = {
    "tools/apply_gen2.py": "84309532ff6abb772c9a6730a0d293d3c5d9d10f",
    "tools/verify_gen2_postapply.py": "9bd7c227c719b33e1818bc52030c0f5db601ade3",
    "BASELINE_SHA.txt": "2e68c3e974178099be97da86af19eedbf7e9e98f",
    "repo_overlay/app/src/full/java/com/duoopen/overlay/Fold7Gen2Kernel.kt": "f5fa04446b96b4f1d2ea99745d21fb339681b71c",
    "repo_overlay/app/src/test/java/com/duoopen/overlay/Fold7Gen2OwnershipTest.kt": "4e74dddff8dafd22f7a2e6f056472bd559c32e2b",
}

EXPECTED_PRODUCTION_PATHS = [
    ".github/workflows/build-direct-fold7.yml",
    "app/build.gradle.kts",
    "app/src/main/java/com/duoopen/fold/HingeAngleSource.kt",
    "app/src/full/java/com/duoopen/lab/TransitionEvent.kt",
    "app/src/full/java/com/duoopen/lab/TransitionLab.kt",
    "app/src/full/java/com/duoopen/lab/TransitionSessionWriter.kt",
    "app/src/full/java/com/duoopen/overlay/DisplayMirrorHost.kt",
    "app/src/full/java/com/duoopen/overlay/Fold7ContinuityCoordinator.kt",
    "app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt",
    "app/src/full/java/com/duoopen/overlay/PanelEngine.kt",
    "app/src/full/java/com/duoopen/shell/DuoShellService.kt",
    "app/src/full/java/com/duoopen/shell/ShellProtocol.kt",
    "app/src/full/java/com/duoopen/shell/ShizukuBridge.kt",
    "app/src/full/java/com/duoopen/shell/WallpaperAngleFeed.kt",
    "app/src/full/java/com/duoopen/overlay/Fold7CycleEnvelope.kt",
    "app/src/full/java/com/duoopen/overlay/Fold7CoverLeaseSnapshotGate.kt",
    "app/src/full/java/com/duoopen/overlay/Fold7CoverReadiness.kt",
    "app/src/full/java/com/duoopen/overlay/Fold7ContinuityFrameStore.kt",
    "app/src/full/java/com/duoopen/overlay/Fold7PresentationLease.kt",
    "app/src/full/java/com/duoopen/overlay/Fold7Gen2Kernel.kt",
    "app/src/test/java/com/duoopen/overlay/Fold7Gen2OwnershipTest.kt",
]


def capture(repo: Path, *args: str) -> str:
    return subprocess.check_output(args, cwd=repo, text=True, stderr=subprocess.STDOUT).strip()


def run(repo: Path, *args: str) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.check_call(args, cwd=repo)


def git_blob(repo: Path, rel: str) -> str:
    return capture(repo, "git", "hash-object", rel)


def verify_staging(repo: Path) -> None:
    head = capture(repo, "git", "rev-parse", "HEAD")
    if head != EXPECTED_HEAD:
        raise RuntimeError(
            f"wrong HEAD: expected staged Gen2 state {EXPECTED_HEAD}, got {head}. "
            "Do not use this corrective package on another revision."
        )

    dirty = capture(repo, "git", "status", "--porcelain")
    if dirty:
        raise RuntimeError(
            "working tree is not clean before Gen2 application:\n" + dirty
        )

    for rel, expected in EXPECTED_STAGED_BLOBS.items():
        path = repo / rel
        if not path.is_file():
            raise RuntimeError(f"missing staged Gen2 file: {rel}")
        actual = git_blob(repo, rel)
        if actual != expected:
            raise RuntimeError(
                f"staged file drift {rel}: expected blob {expected}, got {actual}"
            )

    baseline = (repo / "BASELINE_SHA.txt").read_text().strip()
    if baseline != AUDITED_RUNTIME_BASELINE:
        raise RuntimeError(
            f"BASELINE_SHA.txt mismatch: expected {AUDITED_RUNTIME_BASELINE}, got {baseline}"
        )


def verify_package_manifest(repo: Path) -> None:
    manifest = repo / "SHA256SUMS.txt"
    if not manifest.is_file():
        raise RuntimeError("staged SHA256SUMS.txt is missing")

    failures: list[str] = []
    for raw in manifest.read_text().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            expected, rel = raw.split(None, 1)
        except ValueError:
            failures.append(f"malformed manifest line: {raw!r}")
            continue
        rel = rel.strip()
        if rel.startswith("*"):
            rel = rel[1:]
        if rel.startswith("./"):
            rel = rel[2:]
        p = repo / rel
        if not p.is_file():
            failures.append(f"missing {rel}")
            continue
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        if actual != expected:
            failures.append(f"sha256 mismatch {rel}: expected {expected}, got {actual}")

    if failures:
        raise RuntimeError("staged package integrity failed:\n- " + "\n- ".join(failures))


def verify_production_diff(repo: Path) -> None:
    changed = set(
        line.strip()
        for line in capture(repo, "git", "status", "--short").splitlines()
        if line.strip()
    )
    # Parse the path component from porcelain v1 lines (XY<space>path).
    changed_paths = set()
    for line in changed:
        path = line[3:] if len(line) >= 4 else ""
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        changed_paths.add(path)

    missing = [p for p in EXPECTED_PRODUCTION_PATHS if p not in changed_paths]
    if missing:
        raise RuntimeError(
            "Gen2 apply finished but expected production paths were not changed/added:\n- "
            + "\n- ".join(missing)
        )

    version = (repo / "app/build.gradle.kts").read_text()
    required = [
        "versionCode = 35",
        'versionName = "2.0.0-zfold7-gen2-ownership"',
    ]
    for needle in required:
        if needle not in version:
            raise RuntimeError(f"post-apply version marker missing: {needle}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", nargs="?", type=Path, default=Path("."))
    ap.add_argument(
        "--no-gradle",
        action="store_true",
        help="stop after structural verification; Root must still run Gradle before commit",
    )
    args = ap.parse_args()
    repo = args.repo.resolve()

    if not (repo / ".git").exists():
        raise RuntimeError(f"not a Git checkout: {repo}")

    print("Duo Open Gen2 staged-state deployment")
    print(f"expected HEAD: {EXPECTED_HEAD}")
    print(f"audited runtime baseline: {AUDITED_RUNTIME_BASELINE}")

    verify_staging(repo)
    verify_package_manifest(repo)
    print("STAGING INTEGRITY: PASS")

    # --force relaxes only HEAD equality inside the original installer. Its
    # audited production blob checks remain mandatory and fail closed.
    run(repo, sys.executable, "tools/apply_gen2.py", str(repo), "--force", "--check-only")
    print("AUDITED RUNTIME BLOBS: PASS")

    run(repo, sys.executable, "tools/apply_gen2.py", str(repo), "--force")
    run(repo, sys.executable, "tools/verify_gen2_postapply.py", str(repo))
    run(repo, "git", "diff", "--check")
    verify_production_diff(repo)
    print("PRODUCTION GEN2 DIFF: PRESENT AND STRUCTURALLY VERIFIED")

    if not args.no_gradle:
        run(repo, "./gradlew", "testFullDebugUnitTest", "assembleFullDebug", "--stacktrace")
        print("GRADLE GATES: PASS")
    else:
        print("GRADLE GATES: SKIPPED BY REQUEST -- DO NOT COMMIT UNTIL THEY PASS")

    print("\nDEPLOYMENT APPLY COMPLETE")
    print("No commit or push was created.")
    print("Review with: git status --short && git diff --check && git diff")
    print("Commit only if all required gates above passed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"GEN2 STAGED-STATE DEPLOY: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
