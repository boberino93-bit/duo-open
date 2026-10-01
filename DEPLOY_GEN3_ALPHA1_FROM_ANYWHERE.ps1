$ErrorActionPreference = "Stop"

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = (git rev-parse --show-toplevel 2>$null)

if (-not $Root) {
    throw "Run this from anywhere inside the duo-open Git checkout."
}

if (-not (Test-Path (Join-Path $Root "app/build.gradle.kts")) -or
    -not (Test-Path (Join-Path $Root "gradlew"))) {
    throw "$Root does not look like the duo-open repository root."
}

New-Item -ItemType Directory -Force -Path (Join-Path $Root ".github/workflows") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Root "tools") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Root "payload") | Out-Null

Copy-Item (Join-Path $Here ".github/workflows/apply-gen3-alpha1-integrated.yml") `
          (Join-Path $Root ".github/workflows/apply-gen3-alpha1-integrated.yml") -Force
Copy-Item (Join-Path $Here "tools/apply_gen3_phase1_authority.py") `
          (Join-Path $Root "tools/apply_gen3_phase1_authority.py") -Force
Copy-Item (Join-Path $Here "tools/apply_gen3_alpha1.py") `
          (Join-Path $Root "tools/apply_gen3_alpha1.py") -Force

Get-ChildItem (Join-Path $Here "payload") -File | ForEach-Object {
    Copy-Item $_.FullName (Join-Path $Root "payload" $_.Name) -Force
}

python -m py_compile (Join-Path $Root "tools/apply_gen3_phase1_authority.py")
python -m py_compile (Join-Path $Root "tools/apply_gen3_alpha1.py")

Write-Host ""
Write-Host "Gen3 Alpha1 deployment files installed at repository root."
Write-Host "Commit/push the root workflow, tools, and payload directory."
