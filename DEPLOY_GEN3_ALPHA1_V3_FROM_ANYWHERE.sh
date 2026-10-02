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

cp "$HERE/.github/workflows/apply-gen3-alpha1-integrated-v3.yml" \
   "$ROOT/.github/workflows/apply-gen3-alpha1-integrated-v3.yml"
cp "$HERE/tools/apply_gen3_phase1_authority.py" \
   "$ROOT/tools/apply_gen3_phase1_authority.py"
cp "$HERE/tools/apply_gen3_alpha1_v2.py" \
   "$ROOT/tools/apply_gen3_alpha1_v2.py"
cp -R "$HERE/payload/." "$ROOT/payload/"

python3 -m py_compile \
  "$ROOT/tools/apply_gen3_phase1_authority.py" \
  "$ROOT/tools/apply_gen3_alpha1_v2.py"

echo
echo "Gen3 Alpha1 V3 deployment support installed at repository root."
echo "Commit/push those root support files."
echo "The V2 workflow commits app/** only if all focused and full Android gates pass."
echo "Do NOT deploy the superseded Alpha1 V1 package. V3 supersedes the earlier V2 handoff bundle."
