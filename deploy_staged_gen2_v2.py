#!/usr/bin/env python3
"""Execute the already-staged Duo Open Gen2 deployment from any clean descendant
of the staging commit.

Why V2 exists:
The first corrective wrapper required HEAD to equal the staging commit exactly.
Importing/committing that wrapper necessarily advanced HEAD, causing it to
fail before doing any work. This executor instead verifies ancestry plus exact
staged-file blob identities, while the original Gen2 installer independently
verifies every audited production blob before modifying runtime source.

This script never commits or pushes.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

STAGED_GEN2_COMMIT = "c0a12450524296dccf74401df73d688d9e22f4b1"
AUDITED_RUNTIME_BASELINE = "586c308649258145b3da9b5ea27b726a6fb3647a"

# Exact Git blob identities of the staging machinery/content that the original
# audited installer consumes. These must remain unchanged.
EXPECTED_STAGED_BLOBS = {
    "tools/apply_gen2.py": "84309532ff6abb772c9a6730a0d293d3c5d9d10f",
    "tools/verify_gen2_postapply.py": "9bd7c227c719b33e1818bc52030c0f5db601ade3",
    "BASELINE_SHA.txt": "2e68c3e974178099be97da86af19eedbf7e9e98f",
    "repo_overlay/app/src/full/java/com/duoopen/overlay/Fold7ContinuityFrameStore.kt":
        "f531c239d02858d6e230d774012d10eff99fd3bf",
    "repo_overlay/app/src/full/java/com/duoopen/overlay/Fold7CoverLeaseSnapshotGate.kt":
        "4d2ca533c2d84834e8ded4cc5efe5305dac16ab8",
    "repo_overlay/app/src/full/java/com/duoopen/overlay/Fold7CoverReadiness.kt":
        "f3c0db5ed3b061930a769d7085f4af59de0bc6ab",
    "repo_overlay/app/src/full/java/com/duoopen/overlay/Fold7CycleEnvelope.kt":
        "25ae3f2820de4351ea7c9d1387e598c1f24a1320",
    "repo_overlay/app/src/full/java/com/duoopen/overlay/Fold7Gen2Kernel.kt":
        "f5fa04446b96b4f1d2ea99745d21fb339681b71c",
    "repo_overlay/app/src/full/java/com/duoopen/overlay/Fold7PresentationLease.kt":
        "87481dbcad644dc534b9cfba4ec7f77811e70991",
    "repo_overlay/app/src/test/java/com/duoopen/overlay/Fold7Gen2OwnershipTest.kt":
        "4e74dddff8dafd22f7a2e6f056472bd559c32e2b",
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
    return subprocess.check_output(
        args, cwd=repo, text=True, stderr=subprocess.STDOUT
    ).strip()

def run(repo: Path, *args: str) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.check_call(args, cwd=repo)

def git_blob(repo: Path, rel: str) -> str:
    return capture(repo, "git", "hash-object", rel)

def require_clean(repo: Path) -> None:
    dirty = capture(repo, "git", "status", "--porcelain")
    if dirty:
        raise RuntimeError(
            "working tree must be clean before Gen2 execution:\n" + dirty
        )

def require_staging_ancestor(repo: Path) -> None:
    # Important: do NOT require exact HEAD. Importing this executor creates a
    # newer commit by design. We only require that the audited staging commit
    # is in current history.
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", STAGED_GEN2_COMMIT, "HEAD"],
        cwd=repo,
    )
    if proc.returncode != 0:
        head = capture(repo, "git", "rev-parse", "HEAD")
        raise RuntimeError(
            f"current HEAD {head} is not a descendant of staged Gen2 commit "
            f"{STAGED_GEN2_COMMIT}; reconcile manually rather than applying"
        )

def verify_staged_content(repo: Path) -> None:
    for rel, expected in EXPECTED_STAGED_BLOBS.items():
        path = repo / rel
        if not path.is_file():
            raise RuntimeError(f"missing staged Gen2 file: {rel}")
        actual = git_blob(repo, rel)
        if actual != expected:
            raise RuntimeError(
                f"staged Gen2 drift {rel}: expected blob {expected}, got {actual}"
            )

    baseline = (repo / "BASELINE_SHA.txt").read_text().strip()
    if baseline != AUDITED_RUNTIME_BASELINE:
        raise RuntimeError(
            f"BASELINE_SHA.txt mismatch: expected {AUDITED_RUNTIME_BASELINE}, "
            f"got {baseline}"
        )

def changed_paths(repo: Path) -> set[str]:
    out = capture(repo, "git", "status", "--porcelain")
    result: set[str] = set()
    for line in out.splitlines():
        if not line:
            continue
        path = line[3:] if len(line) >= 4 else ""
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        result.add(path)
    return result

def verify_production_diff(repo: Path) -> None:
    paths = changed_paths(repo)
    missing = [p for p in EXPECTED_PRODUCTION_PATHS if p not in paths]
    if missing:
        raise RuntimeError(
            "Gen2 installer completed but expected runtime paths are absent "
            "from the working-tree diff:\n- " + "\n- ".join(missing)
        )

    gradle = (repo / "app/build.gradle.kts").read_text()
    for needle in (
        "versionCode = 35",
        'versionName = "2.0.0-zfold7-gen2-ownership"',
    ):
        if needle not in gradle:
            raise RuntimeError(f"missing Gen2 version marker: {needle}")

def already_applied(repo: Path) -> bool:
    gradle = repo / "app/build.gradle.kts"
    kernel = repo / "app/src/full/java/com/duoopen/overlay/Fold7Gen2Kernel.kt"
    if not gradle.is_file() or not kernel.is_file():
        return False
    text = gradle.read_text()
    return (
        "versionCode = 35" in text
        and 'versionName = "2.0.0-zfold7-gen2-ownership"' in text
    )

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", nargs="?", type=Path, default=Path("."))
    ap.add_argument(
        "--no-gradle",
        action="store_true",
        help="run structural gates only; do not commit until Gradle gates pass",
    )
    args = ap.parse_args()
    repo = args.repo.resolve()

    if not (repo / ".git").exists():
        raise RuntimeError(f"not a Git checkout: {repo}")

    print("Duo Open Gen2 executor V2")
    print(f"staging ancestor: {STAGED_GEN2_COMMIT}")
    print(f"audited runtime baseline: {AUDITED_RUNTIME_BASELINE}")
    print(f"current HEAD: {capture(repo, 'git', 'rev-parse', 'HEAD')}")

    require_clean(repo)
    require_staging_ancestor(repo)
    verify_staged_content(repo)
    print("STAGED GEN2 CONTENT: PASS")

    # The original installer remains the authority for audited runtime blob
    # identity. --force relaxes only its obsolete exact-HEAD comparison.
    run(
        repo, sys.executable, "tools/apply_gen2.py",
        str(repo), "--force", "--check-only"
    )
    print("AUDITED PRODUCTION BLOBS: PASS")

    if already_applied(repo):
        print("Gen2 version markers already exist; running verification only.")
    else:
        run(repo, sys.executable, "tools/apply_gen2.py", str(repo), "--force")

    run(repo, sys.executable, "tools/verify_gen2_postapply.py", str(repo))
    run(repo, "git", "diff", "--check")
    verify_production_diff(repo)
    print("GEN2 PRODUCTION DIFF: PASS")

    if args.no_gradle:
        print("GRADLE GATES: SKIPPED -- DO NOT COMMIT UNTIL THEY PASS")
    else:
        run(
            repo,
            "./gradlew",
            "testFullDebugUnitTest",
            "assembleFullDebug",
            "--stacktrace",
        )
        print("GRADLE GATES: PASS")

    print()
    print("GEN2 EXECUTION COMPLETE")
    print("No commit or push was created.")
    print("Review: git status --short && git diff --check && git diff")
    print("Commit the generated production diff only after all gates pass.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"GEN2 EXECUTOR V2: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
