# MidiMAT — run NHL tools with the project venv automatically.
# Usage: .\scripts\nhl.ps1 probe
#        .\scripts\nhl.ps1 dump --seconds 900 --out nhl_set_02.jsonl
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "[midimat] creating venv + installing deps..." -ForegroundColor Cyan
    python -m venv .venv
    $env:PATH = ($env:PATH -split ';' | Where-Object { $_ -notlike '*fnm_multishells*' }) -join ';'
    & $py -m pip install --quiet --upgrade pip
    & $py -m pip install --quiet -r requirements.txt
}

& $py -m sidecar.nhl_tap @args