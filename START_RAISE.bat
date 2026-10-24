@echo off
title RAISE
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "BAT_FILE=%~f0"
set "BAT_DIR=%~dp0"
set "RAISE_CLI_ARGS=%*"

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$raw = [System.IO.File]::ReadAllText($env:BAT_FILE); $tag = '<' + '#PS_CODE#>'; $idx = $raw.LastIndexOf($tag); if ($idx -ge 0) { Invoke-Expression $raw.Substring($idx + $tag.Length) }"
exit /b %ERRORLEVEL%

<#PS_CODE#>
param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Continue"
$repoRoot = if ($env:BAT_DIR -and (Test-Path -LiteralPath $env:BAT_DIR)) {
    (Resolve-Path -LiteralPath $env:BAT_DIR).Path
} else {
    (Get-Location).Path
}
Set-Location -LiteralPath $repoRoot

$logsDir = Join-Path $repoRoot "logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
}
$backendLog = Join-Path $logsDir "backend.log"
$frontendLog = Join-Path $logsDir "frontend.log"

function Write-Info {
    param([string]$Text, [string]$Color = "Cyan")
    Write-Host "[RAISE] $Text" -ForegroundColor $Color
}

Write-Info "Starting application..." "Cyan"

# 1. Locate Backend and Frontend directories
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"

if (-not (Test-Path (Join-Path $backendDir "server.py"))) {
    Write-Host "[ERROR] Backend folder not found at: $backendDir" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path (Join-Path $frontendDir "package.json"))) {
    Write-Host "[ERROR] Frontend folder not found at: $frontendDir" -ForegroundColor Red
    exit 1
}

# 2. Check Port Availability (Ports 8000 and 5173)
function Free-Port {
    param([int]$Port)
    try {
        $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        foreach ($c in $conns) {
            $pId = $c.OwningProcess
            if ($pId -gt 0 -and $pId -ne $PID) {
                Write-Info "Releasing port $Port (terminating process $pId)..." "DarkYellow"
                Stop-Process -Id $pId -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {}
}

Free-Port -Port 8000
Free-Port -Port 5173
Start-Sleep -Milliseconds 300

# 3. Locate Python Runtime
$pythonExe = $null
$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$rootVenvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $pythonExe = $venvPython
} elseif (Test-Path $rootVenvPython) {
    $pythonExe = $rootVenvPython
} elseif (Get-Command "python" -ErrorAction SilentlyContinue) {
    $pythonExe = (Get-Command "python").Source
} elseif (Get-Command "python3" -ErrorAction SilentlyContinue) {
    $pythonExe = (Get-Command "python3").Source
} elseif (Get-Command "py" -ErrorAction SilentlyContinue) {
    $pythonExe = (Get-Command "py").Source
}

if (-not $pythonExe) {
    Write-Host "[ERROR] Python was not found. Please install Python." -ForegroundColor Red
    exit 1
}

# 4. Locate Node.js & npm Runtime
$nodeExe = $null
if (Get-Command "node" -ErrorAction SilentlyContinue) {
    $nodeExe = (Get-Command "node").Source
} else {
    $candidates = @(
        "C:\Program Files\nodejs\node.exe",
        "C:\Program Files (x86)\nodejs\node.exe",
        (Join-Path $env:LOCALAPPDATA "Programs\node\node.exe")
    )
    foreach ($cand in $candidates) {
        if ($cand -and (Test-Path $cand)) {
            $nodeExe = $cand
            break
        }
    }
}

if (-not $nodeExe) {
    Write-Host "[ERROR] Node.js was not found. Please install Node.js." -ForegroundColor Red
    exit 1
}

# 5. Ensure Environment Config (.env)
$rootEnv = Join-Path $repoRoot ".env"
$rootEnvEx = Join-Path $repoRoot ".env.example"
$backendEnv = Join-Path $backendDir ".env"

if (-not (Test-Path $backendEnv)) {
    if (Test-Path $rootEnv) {
        Copy-Item -Path $rootEnv -Destination $backendEnv -Force
    } elseif (Test-Path $rootEnvEx) {
        Copy-Item -Path $rootEnvEx -Destination $backendEnv -Force
    }
}

# 6. Launch Backend Server
Write-Info "Launching backend on http://localhost:8000..." "Green"
$backendScript = Join-Path $backendDir "server.py"
$backendProc = Start-Process -FilePath $pythonExe -ArgumentList "-u `"$backendScript`" --no-tunnel" -WorkingDirectory $backendDir -RedirectStandardOutput $backendLog -RedirectStandardError "$backendLog.err" -PassThru

# Wait for backend health check
$backendReady = $false
$swB = [System.Diagnostics.Stopwatch]::StartNew()
while ($swB.Elapsed.TotalSeconds -lt 60) {
    if ($backendProc.HasExited) { break }
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 2 -ErrorAction Stop
        if ($resp) {
            $backendReady = $true
            break
        }
    } catch {}
    Start-Sleep -Seconds 1
}

if (-not $backendReady) {
    Write-Host "[ERROR] Backend service failed to start. Check logs/backend.log for details." -ForegroundColor Red
    if ($backendProc -and -not $backendProc.HasExited) {
        Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    }
    exit 1
}

# 7. Launch Frontend Dev Server
if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Info "Installing frontend packages (npm install)..." "Yellow"
    $npmCmd = if (Get-Command "npm.cmd" -ErrorAction SilentlyContinue) { "npm.cmd" } else { "npm" }
    Start-Process -FilePath $npmCmd -ArgumentList "install" -WorkingDirectory $frontendDir -Wait -NoNewWindow
}

Write-Info "Launching frontend on http://localhost:5173..." "Green"
$viteJs = Join-Path $frontendDir "node_modules\vite\bin\vite.js"
if (Test-Path $viteJs) {
    $frontendProc = Start-Process -FilePath $nodeExe -ArgumentList "`"$viteJs`"" -WorkingDirectory $frontendDir -RedirectStandardOutput $frontendLog -RedirectStandardError "$frontendLog.err" -PassThru
} elseif (Test-Path (Join-Path $frontendDir "node_modules\.bin\vite.cmd")) {
    $frontendProc = Start-Process -FilePath (Join-Path $frontendDir "node_modules\.bin\vite.cmd") -WorkingDirectory $frontendDir -RedirectStandardOutput $frontendLog -RedirectStandardError "$frontendLog.err" -PassThru
} else {
    $frontendProc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c npm run dev" -WorkingDirectory $frontendDir -RedirectStandardOutput $frontendLog -RedirectStandardError "$frontendLog.err" -PassThru
}

# Wait for frontend
$frontendReady = $false
$swF = [System.Diagnostics.Stopwatch]::StartNew()
while ($swF.Elapsed.TotalSeconds -lt 30) {
    if ($frontendProc.HasExited) { break }
    try {
        $respF = Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($respF.StatusCode -ge 200 -and $respF.StatusCode -lt 400) {
            $frontendReady = $true
            break
        }
    } catch {}
    Start-Sleep -Seconds 1
}

# 8. Ready Notification
Write-Host ""
Write-Info "Services are running:" "Green"
Write-Host "  - Backend:  http://localhost:8000 (API & Docs: http://localhost:8000/docs)" -ForegroundColor White
Write-Host "  - Frontend: http://localhost:5173" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop all services." -ForegroundColor Yellow
Write-Host ""

$rawArgs = if ($env:RAISE_CLI_ARGS) { $env:RAISE_CLI_ARGS } else { [string]::Join(" ", $args) }
if ($rawArgs -match "(?i)--no-browser") { $NoBrowser = $true }

if (-not $NoBrowser) {
    try {
        Start-Process "http://localhost:5173"
    } catch {}
}

# 9. Clean Process Lifecycle Management
try {
    while ($true) {
        if ($backendProc.HasExited -or $frontendProc.HasExited) {
            Write-Info "Service shutdown detected." "DarkYellow"
            break
        }
        Start-Sleep -Seconds 1
    }
} finally {
    Write-Info "Stopping services..." "Yellow"
    if ($backendProc -and -not $backendProc.HasExited) {
        & taskkill.exe /PID $backendProc.Id /T /F 2>&1 | Out-Null
    }
    if ($frontendProc -and -not $frontendProc.HasExited) {
        & taskkill.exe /PID $frontendProc.Id /T /F 2>&1 | Out-Null
    }
    Free-Port -Port 8000
    Free-Port -Port 5173
    Write-Info "All services stopped." "Green"
}
