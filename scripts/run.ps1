# MidiMAT — bootstrap venv and run the sidecar (phase 0+).
# Usage: .\scripts\run.ps1  [--nhl] [--midi] [--no-demo]   (args pass to server.py)
# Any previous sidecar holding ports 8080/8787 is stopped automatically.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# --- auto-replace: free OUR ports from any previous instance ----------------
foreach ($port in 8080, 8787) {
    $owners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
              Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($o in $owners) {
        $proc = Get-Process -Id $o -ErrorAction SilentlyContinue
        if ($proc -and $proc.ProcessName -like 'python*') {
            Write-Host "[midimat] stopping previous sidecar (PID $o, port $port)" -ForegroundColor Yellow
            Stop-Process -Id $o -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 500
        }
    }
}

$py = ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "[midimat] creating venv..." -ForegroundColor Cyan
    python -m venv .venv
    $env:PATH = ($env:PATH -split ';' | Where-Object { $_ -notlike '*fnm_multishells*' }) -join ';'
    & $py -m pip install --quiet --upgrade pip
    & $py -m pip install --quiet -r requirements.txt
    Write-Host "[midimat] venv ready" -ForegroundColor Green
}

Write-Host "[midimat] sidecar -> http://127.0.0.1:8080/overlay/index.html?debug=1" -ForegroundColor Cyan
& $py sidecar\server.py @args