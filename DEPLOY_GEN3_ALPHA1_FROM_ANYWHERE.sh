#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"

if [[ -z "$ROOT" ]]; then
  echo "ERROR: run this from anywhere inside the duo-open Git checkout."
  exit 1
fi

if [[ ! -f "$ROOT/app/build.gradle.kts" ]] || [[ ! -f "$ROOT/gradlew" ]]; then
  echo "ERROR: $ROOT does not look like the duo-open repository root."
  exit 1
fi

mkdir -p "$ROOT/.github/workflows" "$ROOT/tools" "$ROOT/payload"

cp "$HERE/.github/workflows/apply-gen3-alpha1-integrated.yml" \
   "$ROOT/.github/workflows/apply-gen3-alpha1-integrated.yml"
cp "$HERE/tools/apply_gen3_phase1_authority.py" \
   "$ROOT/tools/apply_gen3_phase1_authority.py"
cp "$HERE/tools/apply_gen3_alpha1.py" \
   "$ROOT/tools/apply_gen3_alpha1.py"

cp "$HERE"/payload/* "$ROOT/payload/"

python3 -m py_compile "$ROOT/tools/apply_gen3_phase1_authority.py"
python3 -m py_compile "$ROOT/tools/apply_gen3_alpha1.py"

echo
echo "Gen3 Alpha1 deployment files installed at repository root."
echo "Commit/push:"
echo "  .github/workflows/apply-gen3-alpha1-integrated.yml"
echo "  tools/apply_gen3_phase1_authority.py"
echo "  tools/apply_gen3_alpha1.py"
echo "  payload/"
