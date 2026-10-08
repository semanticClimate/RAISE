@echo off
title RAISE
cd /d "%~dp0"
set "BAT_FILE=%~f0"
set "BAT_DIR=%~dp0"

:: ============================================================================
::  RAISE
:: ============================================================================

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$raw = [System.IO.File]::ReadAllText($env:BAT_FILE); $tag = '<' + '#PS_CODE#>'; $idx = $raw.LastIndexOf($tag); if ($idx -ge 0) { Invoke-Expression $raw.Substring($idx + $tag.Length) }"

if %ERRORLEVEL% neq 0 (
    echo.
    echo ============================================================================
    echo  [NOTICE] Process exited with code %ERRORLEVEL%.
    echo ============================================================================
    echo.
    pause
)
exit /b %ERRORLEVEL%

<#PS_CODE#>
[Console]::Title = "RAISE"
$ErrorActionPreference = "Continue"

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13

# 1. Resolve repository root
$repoRoot = if ($env:BAT_DIR -and (Test-Path -LiteralPath $env:BAT_DIR)) {
    (Resolve-Path -LiteralPath $env:BAT_DIR).Path
} else {
    (Get-Location).Path
}

$backendDir  = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "                                   RAISE" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Helper to test TCP port availability
function Test-PortOpen {
    param([string]$Address, [int]$Port, [int]$TimeoutMs = 800)
    try {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $iar = $tcpClient.BeginConnect($Address, $Port, $null, $null)
        $wait = $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
        if ($wait -and $tcpClient.Connected) {
            $tcpClient.EndConnect($iar)
            $tcpClient.Close()
            return $true
        }
        $tcpClient.Close()
        return $false
    } catch {
        return $false
    }
}

# ------------------------------------------------------------------------------
# [1/4] Environment Pre-flight Verification
# ------------------------------------------------------------------------------
Write-Host "[1/4] Verifying workspace integrity..." -ForegroundColor Yellow

if (-not (Test-Path (Join-Path $backendDir "server.py"))) {
    Write-Host "[ERROR] backend/server.py was not found at: $backendDir" -ForegroundColor Red
    Write-Host "Please ensure you have cloned the full RAISE repository." -ForegroundColor Red
    Pause
    exit 1
}

if (-not (Test-Path (Join-Path $frontendDir "package.json"))) {
    Write-Host "[ERROR] frontend/package.json was not found at: $frontendDir" -ForegroundColor Red
    Write-Host "Please ensure you have cloned the full RAISE repository." -ForegroundColor Red
    Pause
    exit 1
}

# Ensure root .env exists from template
$envFile = Join-Path $repoRoot ".env"
$envEx   = Join-Path $repoRoot ".env.example"
if (-not (Test-Path $envFile) -and (Test-Path $envEx)) {
    Copy-Item -Path $envEx -Destination $envFile -Force
    Write-Host "      [CONFIG] Created .env configuration from root .env.example." -ForegroundColor Green
}

Write-Host "      [SUCCESS] Directory structure verified." -ForegroundColor Green
Write-Host ""

# ------------------------------------------------------------------------------
# [2/4] Prepare Backend Runtime (Python / .venv)
# ------------------------------------------------------------------------------
Write-Host "[2/4] Checking Backend runtime (Python / FastAPI)..." -ForegroundColor Yellow

$venvDir = Join-Path $backendDir ".venv"
$venvPy  = Join-Path $venvDir "Scripts\python.exe"

# 1. Discover host Python if .venv is absent
if (-not (Test-Path $venvPy)) {
    Write-Host "      [SETUP] Initializing backend virtual environment (.venv)..." -ForegroundColor Cyan
    $hostPy = $null
    if (Get-Command "python" -ErrorAction SilentlyContinue) {
        $p = (Get-Command "python").Source
        if ($p -notmatch "WindowsApps") { $hostPy = $p }
    }
    if (-not $hostPy -and (Get-Command "py" -ErrorAction SilentlyContinue)) {
        $hostPy = "py -3"
    }

    if ($hostPy) {
        if ($hostPy -eq "py -3") {
            & py -3 -m venv $venvDir
        } else {
            & $hostPy -m venv $venvDir
        }
    } else {
        Write-Host "      [NOTICE] System Python not found. Provisioning portable Python runner..." -ForegroundColor Yellow
        $uvCmd = Get-Command "uv" -ErrorAction SilentlyContinue
        if ($uvCmd) {
            & uv venv $venvDir --python 3.12
        }
    }
}

$activePy = if (Test-Path $venvPy) { $venvPy } else { (Get-Command "python" -ErrorAction SilentlyContinue).Source }

if (-not $activePy) {
    Write-Host "[ERROR] Could not detect a valid Python interpreter." -ForegroundColor Red
    Write-Host "Please install Python 3.10+ (Add to PATH) from python.org" -ForegroundColor Red
    Pause
    exit 1
}

# Quick check of core dependencies
$reqFile = Join-Path $backendDir "requirements.txt"
$checkFastAPI = & $activePy -c "import fastapi; print('OK')" 2>$null
if ($checkFastAPI -ne "OK" -and (Test-Path $reqFile)) {
    Write-Host "      [SETUP] Installing core backend dependencies..." -ForegroundColor Cyan
    $pipExe = Join-Path $venvDir "Scripts\pip.exe"
    if (Test-Path $pipExe) {
        & $pipExe install -r $reqFile --quiet
    } else {
        & $activePy -m pip install -r $reqFile --quiet
    }
}

Write-Host "      [SUCCESS] Backend Python engine ready: $(& $activePy --version 2>&1)" -ForegroundColor Green
Write-Host ""

# ------------------------------------------------------------------------------
# [3/4] Prepare Frontend Runtime (Node.js / npm)
# ------------------------------------------------------------------------------
Write-Host "[3/4] Checking Frontend runtime (Node.js / Vite)..." -ForegroundColor Yellow

$nodeFound = $false
$portableNodeDir = Join-Path $frontendDir ".node\node-v26.10.0-win-x64"
$portableNodeExe = Join-Path $portableNodeDir "node.exe"
$npmCmd = "npm.cmd"

if (Test-Path -LiteralPath $portableNodeExe) {
    $env:PATH = "$portableNodeDir;$env:PATH"
    $nodeFound = $true
} elseif (Get-Command "node" -ErrorAction SilentlyContinue) {
    $nodeFound = $true
}

if (-not $nodeFound) {
    Write-Host "      [SETUP] Node.js not detected on system. Provisioning portable runtime..." -ForegroundColor Cyan
    $nodeZipUrl = "https://nodejs.org/dist/v20.18.0/node-v20.18.0-win-x64.zip"
    $nodeZipTemp = Join-Path $env:TEMP "node-v20-win-x64.zip"
    $nodeContainer = Join-Path $frontendDir ".node"
    if (-not (Test-Path $nodeContainer)) { New-Item -ItemType Directory -Path $nodeContainer -Force | Out-Null }
    try {
        $wc = New-Object System.Net.WebClient
        $wc.Headers.Add("User-Agent", "Mozilla/5.0")
        $wc.DownloadFile($nodeZipUrl, $nodeZipTemp)
        Expand-Archive -LiteralPath $nodeZipTemp -DestinationPath $nodeContainer -Force
        Remove-Item -LiteralPath $nodeZipTemp -Force -ErrorAction SilentlyContinue
        $extractedNode = Get-ChildItem -Path $nodeContainer -Directory | Select-Object -First 1
        if ($extractedNode) {
            $env:PATH = "$($extractedNode.FullName);$env:PATH"
            $nodeFound = $true
        }
    } catch {
        Write-Host "      [WARNING] Automated Node.js download failed: $($_.Exception.Message)" -ForegroundColor DarkYellow
    }
}

if (-not $nodeFound -and -not (Get-Command "node" -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Node.js is required for Frontend UI." -ForegroundColor Red
    Write-Host "Please install Node.js LTS from https://nodejs.org/" -ForegroundColor Red
    Pause
    exit 1
}

# Verify frontend node_modules
$nodeModules = Join-Path $frontendDir "node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Host "      [SETUP] Installing frontend dependencies..." -ForegroundColor Cyan
    Push-Location $frontendDir
    & npm install --no-fund --no-audit
    Pop-Location
}

$nodeVer = (& node -v 2>$null).Trim()
Write-Host "      [SUCCESS] Frontend Node.js engine ready: $nodeVer" -ForegroundColor Green
Write-Host ""

# ------------------------------------------------------------------------------
# [4/4] Coordinated Process Launch & Health Synchronization
# ------------------------------------------------------------------------------
Write-Host "[4/4] Launching RAISE..." -ForegroundColor Yellow
Write-Host ""

# Check existing port bindings
if (Test-PortOpen -Address "127.0.0.1" -Port 8000) {
    Write-Host "      [NOTICE] Port 8000 is already active (Reusing existing Backend instance)." -ForegroundColor DarkYellow
}
if (Test-PortOpen -Address "127.0.0.1" -Port 5173) {
    Write-Host "      [NOTICE] Port 5173 is already active (Reusing existing Frontend instance)." -ForegroundColor DarkYellow
}

# Launch Backend Process
$backendScript = Join-Path $backendDir "server.py"
Write-Host "  -> Starting Backend on http://localhost:8000..." -ForegroundColor Cyan

$backendProcInfo = New-Object System.Diagnostics.ProcessStartInfo
$backendProcInfo.FileName = $activePy
$backendProcInfo.Arguments = "`"$backendScript`" --no-tunnel"
$backendProcInfo.WorkingDirectory = $backendDir
$backendProcInfo.UseShellExecute = $true
$backendProcInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Minimized
$backendProc = [System.Diagnostics.Process]::Start($backendProcInfo)

# Launch Frontend Process
Write-Host "  -> Starting Frontend on http://localhost:5173..." -ForegroundColor Cyan

$frontendProcInfo = New-Object System.Diagnostics.ProcessStartInfo
$frontendProcInfo.FileName = "cmd.exe"
$frontendProcInfo.Arguments = "/c npm run dev"
$frontendProcInfo.WorkingDirectory = $frontendDir
$frontendProcInfo.UseShellExecute = $true
$frontendProcInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Minimized
$frontendProc = [System.Diagnostics.Process]::Start($frontendProcInfo)

# Poll until servers are reachable
Write-Host ""
Write-Host "  Synchronizing RAISE..." -ForegroundColor DarkGray

$backendReady = $false
$frontendReady = $false
$timeoutSeconds = 30
$sw = [System.Diagnostics.Stopwatch]::StartNew()

while ($sw.Elapsed.TotalSeconds -lt $timeoutSeconds) {
    if (-not $backendReady) {
        $backendReady = Test-PortOpen -Address "127.0.0.1" -Port 8000 -TimeoutMs 400
    }
    if (-not $frontendReady) {
        $frontendReady = Test-PortOpen -Address "127.0.0.1" -Port 5173 -TimeoutMs 400
    }
    if ($backendReady -and $frontendReady) { break }
    Start-Sleep -Milliseconds 600
}

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Green
Write-Host "                                   RAISE" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  FastAPI Backend Gateway: http://localhost:8000" -ForegroundColor Cyan
Write-Host "  Swagger Documentation:   http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  React Workstation UI:    http://localhost:5173" -ForegroundColor Cyan
Write-Host ""
Write-Host "  [!] KEEP THIS WINDOW OPEN while using RAISE." -ForegroundColor Yellow
Write-Host "  Press Ctrl+C (or close this window) to terminate all services cleanly." -ForegroundColor Yellow
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""

# Automatically launch browser to frontend
try {
    Start-Process "http://localhost:5173"
} catch {}

# Monitor loop and clean teardown handler
try {
    while ($true) {
        if ($backendProc.HasExited -and $frontendProc.HasExited) { break }
        Start-Sleep -Seconds 1
    }
} finally {
    Write-Host ""
    Write-Host "[SHUTDOWN] Stopping RAISE cleanly..." -ForegroundColor Yellow
    if ($backendProc -and -not $backendProc.HasExited) {
        $backendProc.Kill()
    }
    if ($frontendProc -and -not $frontendProc.HasExited) {
        $frontendProc.Kill()
    }
    Write-Host "[SHUTDOWN] Teardown complete. Ports 8000 and 5173 released." -ForegroundColor Green
}
