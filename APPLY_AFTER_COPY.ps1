$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
python "$Root/APPLY_AFTER_COPY.py"
