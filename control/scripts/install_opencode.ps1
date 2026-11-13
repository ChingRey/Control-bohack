$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$packageDir = Join-Path $projectRoot 'tools/opencode-next'

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw 'Node.js is not installed or not on PATH. Install Node.js 20+ and reopen PowerShell.'
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw 'npm is not installed or not on PATH. Reinstall Node.js with npm, then reopen PowerShell.'
}

$nodeVersion = [version]((node --version).TrimStart('v'))
if ($nodeVersion.Major -lt 20) {
    throw "Node.js 20+ is required; found $nodeVersion."
}

Push-Location $packageDir
try {
    npm ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed with exit code $LASTEXITCODE." }
} finally {
    Pop-Location
}

$binary = Join-Path $packageDir 'node_modules/opencode-ai/bin/opencode.exe'
if (-not (Test-Path $binary -PathType Leaf)) {
    $binary = Join-Path $packageDir 'node_modules/opencode-windows-x64/bin/opencode.exe'
}
if (-not (Test-Path $binary -PathType Leaf)) {
    $binary = Join-Path $packageDir 'node_modules/opencode-windows-x64-baseline/bin/opencode.exe'
}
if (-not (Test-Path $binary -PathType Leaf)) {
    throw 'npm completed, but the OpenCode Windows executable was not found. Check npm output and Windows architecture.'
}

& $binary --version
if ($LASTEXITCODE -ne 0) { throw 'OpenCode executable was found but failed its version check.' }
Write-Host 'OpenCode is installed for this Control project.' -ForegroundColor Green
