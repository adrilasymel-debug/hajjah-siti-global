$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $projectRoot '.runtime/processes.json'
if (Test-Path -LiteralPath $pidFile) {
    foreach ($saved in (Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json)) {
        $processInfo = Get-Process -Id $saved.Id -ErrorAction SilentlyContinue
        # Verify identity so a recycled PID is never stopped; also stop the Python child.
        if ($processInfo -and $processInfo.Path -eq $saved.Path -and $processInfo.StartTime.ToUniversalTime().Ticks.ToString() -eq $saved.StartedAtTicks) {
            & taskkill.exe /PID $processInfo.Id /T /F
        }
    }
    Remove-Item -LiteralPath $pidFile
    Write-Host 'Workspace processes stopped.'
} else { Write-Host 'No processes recorded by this startup script. Stop manually launched terminals from those terminals.' }
