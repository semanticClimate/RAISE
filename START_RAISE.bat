@echo off
title RAISE
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "BAT_FILE=%~f0"
set "BAT_DIR=%~dp0"
set "RAISE_CLI_ARGS=%*"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$raw = [System.IO.File]::ReadAllText($env:BAT_FILE, [System.Text.Encoding]::UTF8); $tag = '<' + '#PS_CODE#>'; $idx = $raw.LastIndexOf($tag); if ($idx -ge 0) { Invoke-Expression $raw.Substring($idx + $tag.Length) }"
set "EXIT_CODE=%ERRORLEVEL%"
if %EXIT_CODE% neq 0 (if "%~1"=="" (echo. & echo [ERROR] Process exited with code %EXIT_CODE%. & pause))
exit /b %EXIT_CODE%

<#PS_CODE#>
param([switch]$NoBrowser)

$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch {}
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [enum]::Parse([Net.SecurityProtocolType], 'Tls13') } catch {}
$ProgressPreference = 'SilentlyContinue'

$repoRoot = if ($env:BAT_DIR -and (Test-Path -LiteralPath $env:BAT_DIR)) { (Resolve-Path -LiteralPath $env:BAT_DIR).Path } else { (Get-Location).Path }
Set-Location -LiteralPath $repoRoot

$logsDir = Join-Path $repoRoot "logs"
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }
$backendLog = Join-Path $logsDir "backend.log"; $frontendLog = Join-Path $logsDir "frontend.log"

function Write-Info { param([string]$Text, [string]$Color = "Cyan"); Write-Host "[RAISE] $Text" -ForegroundColor $Color }
Write-Info "Starting application..." "Cyan"

# 1. Locate Backend and Frontend directories
$backendDir = Join-Path $repoRoot "backend"; $frontendDir = Join-Path $repoRoot "frontend"
if (-not (Test-Path (Join-Path $backendDir "server.py"))) { Write-Host "[ERROR] Backend folder not found at: $backendDir" -ForegroundColor Red; exit 1 }
if (-not (Test-Path (Join-Path $frontendDir "package.json"))) { Write-Host "[ERROR] Frontend folder not found at: $frontendDir" -ForegroundColor Red; exit 1 }

# 2. Release Ports 8000 & 5173
function Free-Port {
    param([int]$Port)
    try {
        foreach ($c in (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)) {
            if ($c.OwningProcess -gt 0 -and $c.OwningProcess -ne $PID) {
                Write-Info "Releasing port $Port (terminating process $($c.OwningProcess))..." "DarkYellow"
                Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {}
    try {
        foreach ($m in (netstat.exe -ano | Select-String ":$Port\s+.*LISTENING\s+(\d+)")) {
            $p = [int]$m.Matches[0].Groups[1].Value
            if ($p -gt 0 -and $p -ne $PID) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }
        }
    } catch {}
}
Free-Port -Port 8000; Free-Port -Port 5173; Start-Sleep -Milliseconds 300

# Helper: Reliable Archive Extractor (tar.exe fast-path with Expand-Archive fallback)
function Extract-ArchiveReliable {
    param([string]$Archive, [string]$Destination)
    if (-not (Test-Path -LiteralPath $Destination)) { New-Item -ItemType Directory -Path $Destination -Force | Out-Null }
    if (Get-Command "tar.exe" -ErrorAction SilentlyContinue) {
        & tar.exe -xf $Archive -C $Destination 2>&1 | Out-Null
        if ((Get-ChildItem -LiteralPath $Destination).Count -gt 0) { return $true }
    }
    try { Expand-Archive -LiteralPath $Archive -DestinationPath $Destination -Force; return $true } catch { return $false }
}

# Helper: Reliable File Downloader
function Download-FileReliable {
    param([string]$Url, [string]$Destination)
    $destDir = Split-Path -Parent $Destination
    if ($destDir -and -not (Test-Path -LiteralPath $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
    if (Test-Path -LiteralPath $Destination) { Remove-Item -LiteralPath $Destination -Force -ErrorAction SilentlyContinue }
    if (Get-Command "curl.exe" -ErrorAction SilentlyContinue) {
        & curl.exe -sSL --ssl-revoke-best-effort --connect-timeout 20 --max-time 300 -o $Destination $Url
        if ((Test-Path -LiteralPath $Destination) -and (Get-Item $Destination).Length -gt 1000) { return $true }
        & curl.exe -sSL -k --connect-timeout 20 --max-time 300 -o $Destination $Url
        if ((Test-Path -LiteralPath $Destination) -and (Get-Item $Destination).Length -gt 1000) { return $true }
    }
    try {
        $wc = New-Object System.Net.WebClient; $wc.Headers.Add("User-Agent", "Mozilla/5.0 RAISE-Bootstrapper"); $wc.DownloadFile($Url, $Destination)
        if ((Test-Path -LiteralPath $Destination) -and (Get-Item $Destination).Length -gt 1000) { return $true }
    } catch {}
    try {
        Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing -TimeoutSec 90
        if ((Test-Path -LiteralPath $Destination) -and (Get-Item $Destination).Length -gt 1000) { return $true }
    } catch {}
    return $false
}

# Helper: Validate functional Python 3 runtime (rejects Windows Store execution aliases & 0-byte stubs)
function Test-ValidPython {
    param([string]$Path)
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) { return $false }
    $resolved = try { (Resolve-Path -LiteralPath $Path -ErrorAction SilentlyContinue).Path } catch { $Path }
    if ($resolved -like "*\WindowsApps\*" -or $resolved -like "*\MICROS~1\*") { return $false }
    try { if ((Get-Item -LiteralPath $resolved -ErrorAction SilentlyContinue).Length -le 4096) { return $false } } catch { return $false }
    try { return ((& $resolved -c "import sys; sys.stdout.write(str(sys.version_info[0]))" 2>$null) -eq "3") } catch { return $false }
}

# 3. Locate or Provision Python Runtime
$pythonExe = $null
$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$rootVenvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (Test-ValidPython $venvPython) { $pythonExe = $venvPython }
elseif (Test-ValidPython $rootVenvPython) { $pythonExe = $rootVenvPython }
else {
    $pyCandidates = @()
    foreach ($c in @("python", "python3", "py")) {
        $cmd = Get-Command $c -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source) { $pyCandidates += $cmd.Source }
    }
    $pyCandidates += @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python310\python.exe"),
        "C:\Program Files\Python311\python.exe", "C:\Program Files\Python312\python.exe", "C:\Program Files\Python310\python.exe",
        (Join-Path $env:APPDATA "uv\python\cpython-3.11-windows-x86_64-none\python.exe")
    )
    foreach ($cand in $pyCandidates) { if ($cand -and (Test-ValidPython $cand)) { $pythonExe = $cand; break } }
}

# Auto-provision Python if not found or execution alias stub detected
$uvDir = Join-Path $repoRoot ".uv"; $uvExe = Join-Path $uvDir "uv.exe"

if (-not $pythonExe) {
    Write-Info "Python runtime not detected. Auto-provisioning isolated Python..." "Cyan"
    if (-not (Test-Path -LiteralPath $uvExe)) {
        if (Get-Command "uv" -ErrorAction SilentlyContinue) { $uvExe = (Get-Command "uv").Source }
        else {
            Write-Info "Downloading uv bootstrapper..." "Yellow"
            $uvZip = Join-Path $env:TEMP "uv-win-x64.zip"
            if (Download-FileReliable -Url "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip" -Destination $uvZip) {
                Extract-ArchiveReliable -Archive $uvZip -Destination $uvDir | Out-Null
                Remove-Item -LiteralPath $uvZip -Force -ErrorAction SilentlyContinue
            }
        }
    }
    if (Test-Path -LiteralPath $uvExe) {
        Write-Info "Fetching standalone Python 3.11 via uv..." "Cyan"
        & $uvExe python install 3.11 2>&1 | Out-Null
        $foundPy = (& $uvExe python find 3.11 2>$null)
        if ($foundPy) {
            $candPy = ($foundPy | Select-Object -First 1)
            if ($candPy -and (Test-ValidPython $candPy.Trim())) { $pythonExe = $candPy.Trim() }
        }
    }
    if (-not $pythonExe -and (Get-Command "winget" -ErrorAction SilentlyContinue)) {
        & winget install --id Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements 2>&1 | Out-Null
        $wingetPy = Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"
        if (Test-ValidPython $wingetPy) { $pythonExe = $wingetPy }
    }
    if (-not $pythonExe) {
        $pyInst = Join-Path $env:TEMP "python-installer.exe"
        if (Download-FileReliable -Url "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe" -Destination $pyInst) {
            Start-Process -FilePath $pyInst -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 SimpleInstall=1 Include_pip=1" -Wait
            Remove-Item -LiteralPath $pyInst -Force -ErrorAction SilentlyContinue
            $sysPy = Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"
            if (Test-ValidPython $sysPy) { $pythonExe = $sysPy }
        }
    }
}

if (-not $pythonExe -and -not (Test-Path -LiteralPath $uvExe) -and -not (Get-Command "uv" -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Python was not found and auto-provisioning could not complete." -ForegroundColor Red; exit 1
}

# Auto-provision isolated virtual environment on clean repository clone
$targetVenv = Join-Path $backendDir ".venv"
if (-not (Test-ValidPython $venvPython)) {
    Write-Info "Provisioning isolated virtual environment (backend\.venv)..." "Cyan"
    $activeUv = if (Test-Path -LiteralPath $uvExe) { $uvExe } elseif (Get-Command "uv" -ErrorAction SilentlyContinue) { "uv" } else { $null }
    if (Test-Path -LiteralPath $targetVenv) { Remove-Item -LiteralPath $targetVenv -Recurse -Force -ErrorAction SilentlyContinue }
    if ($activeUv) {
        if ($pythonExe) { & $activeUv venv $targetVenv --python $pythonExe 2>$null | Out-Null }
        else { & $activeUv venv $targetVenv --python 3.11 2>$null | Out-Null }
    } elseif ($pythonExe) { & $pythonExe -m venv $targetVenv 2>$null | Out-Null }
    if (Test-ValidPython $venvPython) { $pythonExe = $venvPython }
}

# Ensure backend core dependencies are installed
$coreDepsOk = $false
try {
    $chk = & $pythonExe -c "import sys, fastapi, uvicorn, pydantic, orjson; sys.stdout.write('OK')" 2>$null
    if ($chk -match "OK") { $coreDepsOk = $true }
} catch {}

if (-not $coreDepsOk) {
    Write-Info "Installing backend core dependencies..." "Yellow"
    $reqFile = Join-Path $backendDir "requirements-core.txt"
    $activeUv = if (Test-Path -LiteralPath $uvExe) { $uvExe } elseif (Get-Command "uv" -ErrorAction SilentlyContinue) { "uv" } else { $null }
    if ($activeUv) { & $activeUv pip install -r $reqFile --python $pythonExe }
    else { & $pythonExe -m pip install -r $reqFile }
    $chkAfter = & $pythonExe -c "import sys, fastapi, uvicorn, pydantic; sys.stdout.write('OK')" 2>$null
    if ($chkAfter -notmatch "OK") {
        Write-Host "[ERROR] Failed to install backend core dependencies. Check network connectivity." -ForegroundColor Red; exit 1
    }
}

# Native Rust acceleration engine check
$rustDll = Join-Path $backendDir "rust\raise_engine\target\release\raise_engine.dll"
if ((-not (Test-Path $rustDll)) -and (Get-Command "cargo" -ErrorAction SilentlyContinue)) {
    $cargoToml = Join-Path $backendDir "rust\raise_engine\Cargo.toml"
    if (Test-Path $cargoToml) {
        Write-Info "Compiling native Rust acceleration engine (raise_engine)..." "Cyan"
        & cargo build --manifest-path $cargoToml --release 2>&1 | Out-Null
    }
}

# 4. Locate or Provision Node.js & npm Runtime
function Test-ValidNode {
    param([string]$Path)
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) { return $false }
    try { return ((& $Path -v 2>$null) -match "^v\d+") } catch { return $false }
}

$nodeExe = $null
$targetNodeVer = "v22.14.0"; $portableNodeDir = Join-Path $repoRoot ".node\node-$targetNodeVer-win-x64"; $portableNodeExe = Join-Path $portableNodeDir "node.exe"
$frontendPortableDir = Join-Path $frontendDir ".node\node-$targetNodeVer-win-x64"; $frontendPortableExe = Join-Path $frontendPortableDir "node.exe"

if (Test-ValidNode $portableNodeExe) { $nodeExe = $portableNodeExe }
elseif (Test-ValidNode $frontendPortableExe) { $nodeExe = $frontendPortableExe; $portableNodeDir = $frontendPortableDir }
elseif (Get-Command "node" -ErrorAction SilentlyContinue) {
    $cmdNode = (Get-Command "node").Source; if (Test-ValidNode $cmdNode) { $nodeExe = $cmdNode }
}

if (-not $nodeExe) {
    $nodeCandidates = @("C:\Program Files\nodejs\node.exe", "C:\Program Files (x86)\nodejs\node.exe", (Join-Path $env:LOCALAPPDATA "Programs\node\node.exe"), (Join-Path $env:ProgramW6432 "nodejs\node.exe"))
    foreach ($cand in $nodeCandidates) { if ($cand -and (Test-ValidNode $cand)) { $nodeExe = $cand; break } }
}

# Auto-download portable Node.js LTS if not found
if (-not $nodeExe) {
    Write-Info "Node.js not detected. Auto-provisioning portable Node.js LTS ($targetNodeVer)..." "Cyan"
    $nodeZipPath = Join-Path $env:TEMP "node-$targetNodeVer-win-x64.zip"
    $nodeTargetDir = Join-Path $repoRoot ".node"
    if (Download-FileReliable -Url "https://nodejs.org/dist/$targetNodeVer/node-$targetNodeVer-win-x64.zip" -Destination $nodeZipPath) {
        Write-Info "Extracting portable Node.js runtime..." "Cyan"
        Extract-ArchiveReliable -Archive $nodeZipPath -Destination $nodeTargetDir | Out-Null
        Remove-Item -LiteralPath $nodeZipPath -Force -ErrorAction SilentlyContinue
    }
    if (Test-ValidNode $portableNodeExe) {
        $nodeExe = $portableNodeExe; Write-Info "Portable Node.js ($targetNodeVer) initialized successfully." "Green"
    }
}

if (-not $nodeExe) { Write-Host "[ERROR] Node.js was not found and could not be provisioned automatically." -ForegroundColor Red; exit 1 }

$nodeDir = Split-Path -Parent $nodeExe
if ($env:PATH -notlike "*$nodeDir*") { $env:PATH = "$nodeDir;$env:PATH" }
$npmCmd = Join-Path $nodeDir "npm.cmd"
if (-not (Test-Path -LiteralPath $npmCmd)) {
    $npmCmd = if (Get-Command "npm.cmd" -ErrorAction SilentlyContinue) { (Get-Command "npm.cmd").Source } else { "npm.cmd" }
}

# 5. Ensure Environment Config (.env) & First-Time Detection
$rootEnv = Join-Path $repoRoot ".env"; $rootEnvEx = Join-Path $repoRoot ".env.example"
$backendEnv = Join-Path $backendDir ".env"; $runtimeDir = Join-Path $repoRoot ".runtime"
if (-not (Test-Path $runtimeDir)) { New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null }
$setupMarker = Join-Path $runtimeDir "setup_completed"; $backendMarker = Join-Path $backendDir ".runtime\setup_completed"; $hasMarker = (Test-Path $setupMarker) -or (Test-Path $backendMarker)

if (-not (Test-Path $backendEnv)) {
    if (Test-Path $rootEnv) { Copy-Item -Path $rootEnv -Destination $backendEnv -Force }
    elseif (Test-Path $rootEnvEx) { Copy-Item -Path $rootEnvEx -Destination $backendEnv -Force }
}
if (-not (Test-Path $rootEnv) -and (Test-Path $backendEnv)) { Copy-Item -Path $backendEnv -Destination $rootEnv -Force }

# Inspect active .env file for configured Cloud/Local AI keys
$hasConfiguredProvider = $false
$envToCheck = if (Test-Path $backendEnv) { $backendEnv } elseif (Test-Path $rootEnv) { $rootEnv } else { $null }
if ($envToCheck) {
    $c = Get-Content -Path $envToCheck -Raw -ErrorAction SilentlyContinue
    if ($c) {
        $hasCloudKey = $c -match "(?m)^[ \t]*(?:GROQ_API_KEY|GEMINI_API_KEY|OPENAI_API_KEY|MISTRAL_API_KEY|DEEPSEEK_API_KEY|NVIDIA_API_KEY|ANTHROPIC_API_KEY|COHERE_API_KEY)[ \t]*=[ \t]*['""]?([a-zA-Z0-9_\-]{8,})"
        $hasSetupFlag = $c -match "(?m)^[ \t]*SETUP_COMPLETED[ \t]*=[ \t]*['""]?true"
        $hasLocalLlm = ($hasMarker -or $hasSetupFlag) -and ($c -match "(?m)^[ \t]*LLM_BACKEND[ \t]*=[ \t]*['""]?(ollama|vllm)")
        if ($hasCloudKey -or $hasLocalLlm -or $hasSetupFlag) { $hasConfiguredProvider = $true }
    }
}

# First-time launch occurs when neither the completion marker nor a configured provider exists
$isFirstLaunch = (-not $hasMarker -and -not $hasConfiguredProvider)

# 6. Launch Backend Server
Write-Info "Launching backend on http://localhost:8000..." "Green"
$backendScript = Join-Path $backendDir "server.py"
$backendProc = Start-Process -FilePath $pythonExe -ArgumentList "-u `"$backendScript`" --no-tunnel" -WorkingDirectory $backendDir -RedirectStandardOutput $backendLog -RedirectStandardError "$backendLog.err" -WindowStyle Hidden -PassThru

# Wait for backend health check
$backendReady = $false
$swB = [System.Diagnostics.Stopwatch]::StartNew()
while ($swB.Elapsed.TotalSeconds -lt 60) {
    if ($backendProc.HasExited) { break }
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 2 -ErrorAction Stop
        if ($resp) { $backendReady = $true; break }
    } catch {}
    Start-Sleep -Seconds 1
}

if (-not $backendReady) {
    Write-Host "[ERROR] Backend service failed to start. Check logs/backend.log for details." -ForegroundColor Red
    $errFile = if (Test-Path "$backendLog.err") { "$backendLog.err" } elseif (Test-Path $backendLog) { $backendLog } else { $null }
    if ($errFile) { Get-Content $errFile -Tail 15 -ErrorAction SilentlyContinue | Write-Host -ForegroundColor DarkRed }
    if ($backendProc -and -not $backendProc.HasExited) { Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue }
    Free-Port -Port 8000; Free-Port -Port 5173
    exit 1
}

# 7. Launch Frontend Dev Server
$vitePkg = Join-Path $frontendDir "node_modules\vite"
if (-not (Test-Path -LiteralPath $vitePkg)) {
    Write-Info "Installing frontend packages (npm install)..." "Yellow"
    Push-Location -LiteralPath $frontendDir
    try { & $npmCmd install --no-fund --no-audit } finally { Pop-Location }
}

Write-Info "Launching frontend on http://localhost:5173..." "Green"
$viteJs = Join-Path $frontendDir "node_modules\vite\bin\vite.js"; $viteCmd = Join-Path $frontendDir "node_modules\.bin\vite.cmd"
if (Test-Path $viteJs) {
    $frontendProc = Start-Process -FilePath $nodeExe -ArgumentList "`"$viteJs`"" -WorkingDirectory $frontendDir -RedirectStandardOutput $frontendLog -RedirectStandardError "$frontendLog.err" -WindowStyle Hidden -PassThru
} elseif (Test-Path $viteCmd) {
    $frontendProc = Start-Process -FilePath $viteCmd -WorkingDirectory $frontendDir -RedirectStandardOutput $frontendLog -RedirectStandardError "$frontendLog.err" -WindowStyle Hidden -PassThru
} else {
    $frontendProc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c npm run dev" -WorkingDirectory $frontendDir -RedirectStandardOutput $frontendLog -RedirectStandardError "$frontendLog.err" -WindowStyle Hidden -PassThru
}

# Wait for frontend
$frontendReady = $false
$swF = [System.Diagnostics.Stopwatch]::StartNew()
while ($swF.Elapsed.TotalSeconds -lt 30) {
    if ($frontendProc.HasExited) { break }
    try {
        $respF = Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($respF.StatusCode -ge 200 -and $respF.StatusCode -lt 400) { $frontendReady = $true; break }
    } catch {}
    Start-Sleep -Seconds 1
}

if (-not $frontendReady) {
    Write-Host "[ERROR] Frontend service failed to start. Check logs/frontend.log for details." -ForegroundColor Red
    $errFileF = if (Test-Path "$frontendLog.err") { "$frontendLog.err" } elseif (Test-Path $frontendLog) { $frontendLog } else { $null }
    if ($errFileF) { Get-Content $errFileF -Tail 15 -ErrorAction SilentlyContinue | Write-Host -ForegroundColor DarkRed }
    if ($backendProc -and -not $backendProc.HasExited) { Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue }
    if ($frontendProc -and -not $frontendProc.HasExited) { Stop-Process -Id $frontendProc.Id -Force -ErrorAction SilentlyContinue }
    Free-Port -Port 8000; Free-Port -Port 5173
    exit 1
}

# 8. Ready Notification & Browser Launch
Write-Host "`n[RAISE] Services are running:" -ForegroundColor Green
Write-Host "  - Backend:  http://localhost:8000 (API & Docs: http://localhost:8000/docs)" -ForegroundColor White
Write-Host "  - Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "  - Terminal: Live log telemetry active (streaming backend activity & inference events)" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop all services.`n" -ForegroundColor Yellow

$rawArgs = if ($env:RAISE_CLI_ARGS) { $env:RAISE_CLI_ARGS } else { [string]::Join(" ", $args) }
$showMode = ($rawArgs -match "(?i)--show|-show|--verbose|-v")
if ($showMode) {
    Write-Host "[DEBUG] Verbose live terminal streaming active (--show flag detected)." -ForegroundColor DarkGreen
}
if ($rawArgs -match "(?i)--no-browser") { $NoBrowser = $true }
if ($rawArgs -match "(?i)--setup|--control-center") { $isFirstLaunch = $true }
$targetUrl = if ($isFirstLaunch) { "http://localhost:5173/?setup=true" } else { "http://localhost:5173" }

if (-not $NoBrowser) {
    try {
        $msg = if ($isFirstLaunch) { "Opening RAISE Control Center for first-time workstation configuration ($targetUrl)..." } else { "Opening RAISE workstation in default browser ($targetUrl)..." }
        Write-Info $msg "Green"; Start-Process $targetUrl
    } catch {}
}

# 9. Clean Process Lifecycle Management & Live Terminal Streaming
$unexpectedExit = $false

$backendFs = $null
$backendReader = $null
$errFs = $null
$errReader = $null
$frontendFs = $null
$frontendReader = $null
$frontendErrFs = $null
$frontendErrReader = $null

try {
    if (Test-Path -LiteralPath $backendLog) {
        $backendFs = [System.IO.File]::Open($backendLog, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        $backendReader = [System.IO.StreamReader]::new($backendFs, [System.Text.Encoding]::UTF8)
        if (-not $showMode) {
            $backendFs.Seek(0, [System.IO.SeekOrigin]::End) | Out-Null
        }
    }
} catch {}

try {
    $errFileCandidate = "$backendLog.err"
    if (Test-Path -LiteralPath $errFileCandidate) {
        $errFs = [System.IO.File]::Open($errFileCandidate, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        $errReader = [System.IO.StreamReader]::new($errFs, [System.Text.Encoding]::UTF8)
        if (-not $showMode) {
            $errFs.Seek(0, [System.IO.SeekOrigin]::End) | Out-Null
        }
    }
} catch {}

try {
    if (Test-Path -LiteralPath $frontendLog) {
        $frontendFs = [System.IO.File]::Open($frontendLog, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        $frontendReader = [System.IO.StreamReader]::new($frontendFs, [System.Text.Encoding]::UTF8)
        if (-not $showMode) {
            $frontendFs.Seek(0, [System.IO.SeekOrigin]::End) | Out-Null
        }
    }
} catch {}

try {
    $frontendErrCandidate = "$frontendLog.err"
    if (Test-Path -LiteralPath $frontendErrCandidate) {
        $frontendErrFs = [System.IO.File]::Open($frontendErrCandidate, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        $frontendErrReader = [System.IO.StreamReader]::new($frontendErrFs, [System.Text.Encoding]::UTF8)
        if (-not $showMode) {
            $frontendErrFs.Seek(0, [System.IO.SeekOrigin]::End) | Out-Null
        }
    }
} catch {}

try {
    while ($true) {
        if ($backendProc.HasExited -or $frontendProc.HasExited) {
            $unexpectedExit = $true
            $failedService = if ($backendProc.HasExited) { "Backend (Exit Code: $($backendProc.ExitCode))" } else { "Frontend (Exit Code: $($frontendProc.ExitCode))" }
            Write-Host "[ERROR] $failedService service terminated unexpectedly." -ForegroundColor Red
            $logToCheck = if ($backendProc.HasExited) { $backendLog } else { $frontendLog }
            $errFile = if (Test-Path "$logToCheck.err") { "$logToCheck.err" } elseif (Test-Path $logToCheck) { $logToCheck } else { $null }
            if ($errFile) { Get-Content $errFile -Tail 15 -ErrorAction SilentlyContinue | Write-Host -ForegroundColor DarkRed }
            break
        }

        # Stream new backend stdout lines
        if ($backendReader) {
            try {
                while (-not $backendReader.EndOfStream) {
                    $line = $backendReader.ReadLine()
                    if ($line -and $line.Trim()) {
                        if ($line -match "\[INFERENCE\]|Executing task") {
                            Write-Host $line -ForegroundColor Green
                        } elseif ($line -match "POST|GET|OPTIONS|DELETE|WebSocket") {
                            Write-Host $line -ForegroundColor Cyan
                        } elseif ($line -match "ERROR|Traceback|Exception") {
                            Write-Host $line -ForegroundColor Red
                        } elseif ($line -match "WARNING") {
                            Write-Host $line -ForegroundColor Yellow
                        } else {
                            Write-Host $line -ForegroundColor Gray
                        }
                    }
                }
            } catch {}
        }

        # Stream new backend stderr lines
        if ($errReader) {
            try {
                while (-not $errReader.EndOfStream) {
                    $errLine = $errReader.ReadLine()
                    if ($errLine -and $errLine.Trim()) {
                        Write-Host "[BACKEND-ERR] $errLine" -ForegroundColor DarkYellow
                    }
                }
            } catch {}
        }

        # Stream new frontend stdout lines
        if ($frontendReader) {
            try {
                while (-not $frontendReader.EndOfStream) {
                    $fLine = $frontendReader.ReadLine()
                    if ($fLine -and $fLine.Trim()) {
                        if ($fLine -match "ready in|Local:|Network:") {
                            Write-Host "[FRONTEND] $fLine" -ForegroundColor DarkCyan
                        } elseif ($fLine -match "error|failed|exception") {
                            Write-Host "[FRONTEND] $fLine" -ForegroundColor Red
                        } else {
                            Write-Host "[FRONTEND] $fLine" -ForegroundColor DarkGray
                        }
                    }
                }
            } catch {}
        }

        # Stream new frontend stderr lines
        if ($frontendErrReader) {
            try {
                while (-not $frontendErrReader.EndOfStream) {
                    $fErrLine = $frontendErrReader.ReadLine()
                    if ($fErrLine -and $fErrLine.Trim()) {
                        Write-Host "[FRONTEND-ERR] $fErrLine" -ForegroundColor DarkYellow
                    }
                }
            } catch {}
        }

        Start-Sleep -Milliseconds 250
    }
} finally {
    if ($backendReader) { try { $backendReader.Dispose() } catch {} }
    if ($backendFs) { try { $backendFs.Dispose() } catch {} }
    if ($errReader) { try { $errReader.Dispose() } catch {} }
    if ($errFs) { try { $errFs.Dispose() } catch {} }
    if ($frontendReader) { try { $frontendReader.Dispose() } catch {} }
    if ($frontendFs) { try { $frontendFs.Dispose() } catch {} }
    if ($frontendErrReader) { try { $frontendErrReader.Dispose() } catch {} }
    if ($frontendErrFs) { try { $frontendErrFs.Dispose() } catch {} }

    Write-Info "Stopping services..." "Yellow"
    if ($backendProc -and -not $backendProc.HasExited) {
        & taskkill.exe /PID $backendProc.Id /T /F 2>&1 | Out-Null
        Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    }
    if ($frontendProc -and -not $frontendProc.HasExited) {
        & taskkill.exe /PID $frontendProc.Id /T /F 2>&1 | Out-Null
        Stop-Process -Id $frontendProc.Id -Force -ErrorAction SilentlyContinue
    }
    Free-Port -Port 8000; Free-Port -Port 5173
    Write-Info "All services stopped." "Green"
}
if ($unexpectedExit) { exit 1 }
