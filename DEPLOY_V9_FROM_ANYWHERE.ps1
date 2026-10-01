param(
  [string]$RepoRoot = ""
)
$ErrorActionPreference = "Stop"
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
  $RepoRoot = (& git rev-parse --show-toplevel 2>$null)
}
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
  throw "Run this from inside the duo-open Git repository, or pass -RepoRoot <path>."
}
$RepoRoot = (Resolve-Path $RepoRoot).Path
if (-not (Test-Path (Join-Path $RepoRoot ".git"))) { throw "Not a Git repository root: $RepoRoot" }
if (-not (Test-Path (Join-Path $RepoRoot "app/build.gradle.kts"))) { throw "Target does not look like Duo Open: $RepoRoot" }

$origin = (& git -C $RepoRoot config --get remote.origin.url)
if ($origin -notmatch "duo-open") { throw "Unexpected git origin: $origin" }

New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot ".github/workflows") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot "tools") | Out-Null
Copy-Item -Force (Join-Path $SourceDir ".github/workflows/apply-gen2-field-fix-v9.yml") (Join-Path $RepoRoot ".github/workflows/apply-gen2-field-fix-v9.yml")
Copy-Item -Force (Join-Path $SourceDir "tools/apply_field_fix_v9.py") (Join-Path $RepoRoot "tools/apply_field_fix_v9.py")

Write-Host "V9 root files installed into $RepoRoot"
Write-Host "Commit and push the two root files; the workflow will test/build before app runtime changes are committed."
& git -C $RepoRoot status --short
