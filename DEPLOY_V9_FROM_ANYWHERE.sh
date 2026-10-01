#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -ge 1 ]]; then
  REPO_ROOT="$(cd "$1" && pwd)"
else
  REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fi

if [[ -z "${REPO_ROOT:-}" || ! -d "$REPO_ROOT/.git" ]]; then
  echo "ERROR: run this from inside the duo-open Git repository, or pass the repo path as argument 1."
  exit 2
fi

if [[ ! -f "$REPO_ROOT/app/build.gradle.kts" ]]; then
  echo "ERROR: target does not look like the Duo Open repository: $REPO_ROOT"
  exit 3
fi

origin="$(git -C "$REPO_ROOT" config --get remote.origin.url || true)"
if [[ "$origin" != *"boberino93-bit/duo-open"* && "$origin" != *"duo-open.git"* ]]; then
  echo "ERROR: unexpected git origin: $origin"
  exit 4
fi

mkdir -p "$REPO_ROOT/.github/workflows" "$REPO_ROOT/tools"
cp "$SOURCE_DIR/.github/workflows/apply-gen2-field-fix-v9.yml" \
   "$REPO_ROOT/.github/workflows/apply-gen2-field-fix-v9.yml"
cp "$SOURCE_DIR/tools/apply_field_fix_v9.py" \
   "$REPO_ROOT/tools/apply_field_fix_v9.py"

python3 -m py_compile "$REPO_ROOT/tools/apply_field_fix_v9.py"

echo
echo "V9 root files installed into: $REPO_ROOT"
echo "  .github/workflows/apply-gen2-field-fix-v9.yml"
echo "  tools/apply_field_fix_v9.py"
echo
echo "Verify with:"
echo "  git -C \"$REPO_ROOT\" status --short"
echo
echo "Then commit and push those two root files. The V9 workflow will run the tests/build and commit app/** only if all gates pass."
