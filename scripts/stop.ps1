# MidiMAT — stop any running sidecar (frees ports 8080/8787).
$found = $false
foreach ($port in 8080, 8787) {
    $owners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
              Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($o in $owners) {
        $proc = Get-Process -Id $o -ErrorAction SilentlyContinue
        if ($proc -and $proc.ProcessName -like 'python*') {
            Write-Host "[midimat] stopping sidecar PID $o (port $port)" -ForegroundColor Yellow
            Stop-Process -Id $o -Force -ErrorAction SilentlyContinue
            $found = $true
        }
    }
}
if (-not $found) { Write-Host "[midimat] no sidecar running" -ForegroundColor Green }