$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (!(Test-Path -LiteralPath (Join-Path $projectRoot '.git'))) {
    throw 'Run this script from the original project folder, which contains the prepared Git repository.'
}
Write-Host 'Publishing the committed application to the configured GitHub repository.'
Write-Host 'Complete GitHub sign-in in your browser if Git requests it. Do not paste passwords into chat.'
& git -C $projectRoot push -u origin main
if ($LASTEXITCODE) { throw 'GitHub upload did not complete. Check the sign-in/error above and retry.' }
Write-Host 'Source published. Continue with the free Render deployment using render.yaml.'
