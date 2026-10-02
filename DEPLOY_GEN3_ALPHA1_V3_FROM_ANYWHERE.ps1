$ErrorActionPreference = "Stop"

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = (git rev-parse --show-toplevel 2>$null)

if (-not $Root) { throw "Run this from anywhere inside the duo-open Git checkout." }
if (-not (Test-Path (Join-Path $Root "app/build.gradle.kts")) -or
    -not (Test-Path (Join-Path $Root "gradlew"))) {
    throw "$Root does not look like the duo-open repository root."
}

New-Item -ItemType Directory -Force -Path (Join-Path $Root ".github/workflows") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Root "tools") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Root "payload") | Out-Null

Copy-Item (Join-Path $Here ".github/workflows/apply-gen3-alpha1-integrated-v3.yml") `
          (Join-Path $Root ".github/workflows/apply-gen3-alpha1-integrated-v3.yml") -Force
Copy-Item (Join-Path $Here "tools/apply_gen3_phase1_authority.py") `
          (Join-Path $Root "tools/apply_gen3_phase1_authority.py") -Force
Copy-Item (Join-Path $Here "tools/apply_gen3_alpha1_v2.py") `
          (Join-Path $Root "tools/apply_gen3_alpha1_v2.py") -Force
Copy-Item (Join-Path $Here "payload/*") (Join-Path $Root "payload") -Recurse -Force

python -m py_compile `
  (Join-Path $Root "tools/apply_gen3_phase1_authority.py") `
  (Join-Path $Root "tools/apply_gen3_alpha1_v2.py")

Write-Host ""
Write-Host "Gen3 Alpha1 V3 deployment support installed at repository root."
Write-Host "Commit/push those root support files. Do NOT deploy Alpha1 V1. V3 supersedes the earlier V2 handoff bundle."
