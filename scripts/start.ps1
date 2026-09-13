param([string]$Python = 'python', [switch]$Demo)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    foreach ($port in @(8000,5173)) {
        $connection = New-Object System.Net.Sockets.TcpClient
        try { $connection.Connect('127.0.0.1',$port); throw "Port $port is already in use. Stop the running workspace before starting another copy." }
        catch [System.Net.Sockets.SocketException] { }
        finally { $connection.Dispose() }
    }
    if (Test-Path '.runtime/processes.json') {
        foreach ($saved in (Get-Content '.runtime/processes.json' -Raw | ConvertFrom-Json)) {
            $running = Get-Process -Id $saved.Id -ErrorAction SilentlyContinue
            if ($running -and $running.StartTime.ToUniversalTime().Ticks.ToString() -eq $saved.StartedAtTicks) { throw 'A workspace process is still running. Run scripts/stop.ps1 before restarting.' }
        }
    }
    if (!(Test-Path '.venv/Scripts/python.exe')) { & $Python -m venv .venv; if ($LASTEXITCODE) { throw 'Python environment creation failed' } }
    $pythonExe = Join-Path $projectRoot '.venv/Scripts/python.exe'
    & $pythonExe -m pip install -r backend/requirements.lock
    if ($LASTEXITCODE) { throw 'Dependency installation failed' }
    if (!(Test-Path 'backend/.env')) { Copy-Item backend/.env.example backend/.env }
    Push-Location backend
    try {
        & $pythonExe -m alembic upgrade head
        if ($LASTEXITCODE) { throw 'Database migration failed' }
        if ($Demo) {
            $env:DEMO_PASSWORD = Read-Host 'Choose a demo password (12+ characters; both demo accounts use it)'
            & $pythonExe -m app.seed
            Remove-Item Env:DEMO_PASSWORD
            if ($LASTEXITCODE) { throw 'Demo seed failed' }
        }
    } finally { Pop-Location }
    Push-Location backend/ocr
    try { & pnpm.cmd install --frozen-lockfile; if ($LASTEXITCODE) { throw 'Free OCR installation failed' } } finally { Pop-Location }
    Push-Location frontend
    try {
        & pnpm.cmd install --frozen-lockfile
        if ($LASTEXITCODE) { throw 'Frontend dependency installation failed' }
        & node node_modules/typescript/bin/tsc -b
        if ($LASTEXITCODE) { throw 'Frontend type check failed' }
        & node node_modules/vite/bin/vite.js build --configLoader runner
        if ($LASTEXITCODE) { throw 'Frontend build failed' }
    } finally { Pop-Location }
    New-Item -ItemType Directory -Force .runtime | Out-Null
    $apiProcess = Start-Process -FilePath $pythonExe -ArgumentList '-m uvicorn app.main:app --host 127.0.0.1 --port 8000' -WorkingDirectory "$projectRoot/backend" -WindowStyle Hidden -PassThru -RedirectStandardOutput "$projectRoot/.runtime/api.log" -RedirectStandardError "$projectRoot/.runtime/api-error.log"
    $workerProcess = Start-Process -FilePath $pythonExe -ArgumentList '-m app.worker' -WorkingDirectory "$projectRoot/backend" -WindowStyle Hidden -PassThru -RedirectStandardOutput "$projectRoot/.runtime/worker.log" -RedirectStandardError "$projectRoot/.runtime/worker-error.log"
    $webProcess = Start-Process -FilePath (Get-Command node).Source -ArgumentList 'node_modules/vite/bin/vite.js preview --configLoader runner --host 127.0.0.1 --port 5173 --strictPort' -WorkingDirectory "$projectRoot/frontend" -WindowStyle Hidden -PassThru -RedirectStandardOutput "$projectRoot/.runtime/web.log" -RedirectStandardError "$projectRoot/.runtime/web-error.log"
    @($apiProcess,$workerProcess,$webProcess) | ForEach-Object { @{ Id=$_.Id; StartedAtTicks=$_.StartTime.ToUniversalTime().Ticks.ToString(); Path=$_.Path } } | ConvertTo-Json | Set-Content .runtime/processes.json
    Write-Host 'Open http://localhost:5173. Logs are in .runtime. Use scripts/stop.ps1 to stop.'
} finally { Pop-Location }
