# MidiMAT — bootstrap venv and run the sidecar (phase 0).
# Usage: .\scripts\run.ps1  [--no-demo]  (extra args pass through to server.py)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "[midimat] creating venv..." -ForegroundColor Cyan
    python -m venv .venv
    & $py -m pip install --quiet --upgrade pip
    & $py -m pip install --quiet -r requirements.txt
    Write-Host "[midimat] venv ready" -ForegroundColor Green
}

Write-Host "[midimat] starting sidecar -> http://127.0.0.1:8080/overlay/index.html?demo=1" -ForegroundColor Cyan
Write-Host "[midimat] OBS browser source: http://127.0.0.1:8080/overlay/index.html?debug=1" -ForegroundColor Cyan
& $py sidecar\server.py @args