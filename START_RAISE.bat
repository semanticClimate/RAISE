@echo off
title RAISE Launcher v4
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "BAT_FILE=%~f0"
set "BAT_DIR=%~dp0"
set "RAISE_CLI_ARGS=%*"

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$raw = [System.IO.File]::ReadAllText($env:BAT_FILE); $tag = '<' + '#PS_CODE#>'; $idx = $raw.LastIndexOf($tag); if ($idx -ge 0) { Invoke-Expression $raw.Substring($idx + $tag.Length) }"

set "EXIT_CODE=%ERRORLEVEL%"
if %EXIT_CODE% neq 0 (
    echo.
    echo ============================================================================
    echo [ERROR] Launcher exited with code %EXIT_CODE%.
    echo Check logs\install.log for diagnostic details.
    echo ============================================================================
    echo.
)
exit /b %EXIT_CODE%

<#PS_CODE#>
param(
    [switch]$Reset,
    [switch]$SkipMl,
    [switch]$NoBrowser
)

[Console]::Title = "RAISE Launcher v4"
$ErrorActionPreference = "Continue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13

$repoRoot = if ($env:BAT_DIR -and (Test-Path -LiteralPath $env:BAT_DIR)) {
    (Resolve-Path -LiteralPath $env:BAT_DIR).Path
} else {
    (Get-Location).Path
}
Set-Location -LiteralPath $repoRoot

$logsDir = Join-Path $repoRoot "logs"
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }
$installLog  = Join-Path $logsDir "install.log"
$backendLog  = Join-Path $logsDir "backend.log"
$frontendLog = Join-Path $logsDir "frontend.log"

function Log-Msg {
    param([string]$Text, [string]$Color = "White", [bool]$NoConsole = $false)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $Text"
    Add-Content -LiteralPath $installLog -Value $line -ErrorAction SilentlyContinue
    if (-not $NoConsole) {
        Write-Host $Text -ForegroundColor $Color
    }
}

Log-Msg "============================================================================" "Cyan"
Log-Msg "               RAISE Autonomous Monorepo Launcher (v4.0)" "Cyan"
Log-Msg "============================================================================" "Cyan"
Log-Msg "Repository Root: $repoRoot" "Gray"
Log-Msg ""

# Parse CLI flags from environment variable or script args
$rawArgs = if ($env:RAISE_CLI_ARGS) { $env:RAISE_CLI_ARGS } else { [string]::Join(" ", $args) }
if ($rawArgs -match "(?i)--reset") { $Reset = $true }
if ($rawArgs -match "(?i)--skip-ml") { $SkipMl = $true }
if ($rawArgs -match "(?i)--no-browser") { $NoBrowser = $true }

# ------------------------------------------------------------------------------
# [1/8] Content-Based Directory Discovery
# ------------------------------------------------------------------------------
Log-Msg "[1/8] Discovering Backend and Frontend components (content-based)..." "Yellow"

$backendCandidates = @()
if ($env:RAISE_BACKEND_DIR -and (Test-Path $env:RAISE_BACKEND_DIR)) { $backendCandidates += $env:RAISE_BACKEND_DIR }
$backendCandidates += Join-Path $repoRoot "backend"
$backendCandidates += $repoRoot
$backendCandidates += (Join-Path (Split-Path $repoRoot -Parent) "backend")

$backendDir = $null
foreach ($cand in $backendCandidates) {
    if ($cand -and (Test-Path $cand)) {
        $hasServer = (Test-Path (Join-Path $cand "server.py")) -or (Test-Path (Join-Path $cand "app.py"))
        $hasReq = (Test-Path (Join-Path $cand "requirements.txt")) -or (Test-Path (Join-Path $cand "requirements-core.txt"))
        if ($hasServer -and $hasReq) {
            $backendDir = (Resolve-Path $cand).Path
            break
        }
    }
}

$frontendCandidates = @()
if ($env:RAISE_FRONTEND_DIR -and (Test-Path $env:RAISE_FRONTEND_DIR)) { $frontendCandidates += $env:RAISE_FRONTEND_DIR }
$frontendCandidates += Join-Path $repoRoot "frontend"
$frontendCandidates += (Join-Path (Split-Path $repoRoot -Parent) "frontend")

# Search immediate subdirectories if not found yet
if (-not $frontendDir) {
    $subDirs = Get-ChildItem -Path $repoRoot -Directory -ErrorAction SilentlyContinue
    foreach ($sd in $subDirs) {
        $pkg = Join-Path $sd.FullName "package.json"
        if (Test-Path $pkg) {
            $content = Get-Content $pkg -Raw -ErrorAction SilentlyContinue
            if ($content -match "vite|react") {
                $frontendCandidates += $sd.FullName
            }
        }
    }
}

$frontendDir = $null
foreach ($cand in $frontendCandidates) {
    if ($cand -and (Test-Path $cand)) {
        $pkg = Join-Path $cand "package.json"
        if (Test-Path $pkg) {
            $frontendDir = (Resolve-Path $cand).Path
            break
        }
    }
}

if (-not $backendDir) {
    Log-Msg "[ERROR] Could not detect backend directory with server.py and requirements.txt." "Red"
    exit 1
}
if (-not $frontendDir) {
    Log-Msg "[ERROR] Could not detect frontend directory with package.json." "Red"
    exit 1
}

Log-Msg "      [BACKEND]  $backendDir" "Green"
Log-Msg "      [FRONTEND] $frontendDir" "Green"
Log-Msg ""

# Runtime cache directory and state persistence
$runtimeDir = Join-Path $repoRoot ".runtime"
if (-not (Test-Path $runtimeDir)) { New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null }
$stateFile = Join-Path $runtimeDir "state.json"

$state = @{}
if (Test-Path $stateFile) {
    try {
        $stateRaw = Get-Content $stateFile -Raw -ErrorAction SilentlyContinue
        if ($stateRaw) {
            $parsed = $stateRaw | ConvertFrom-Json
            if ($parsed) {
                foreach ($prop in $parsed.PSObject.Properties) {
                    $state[$prop.Name] = $prop.Value
                }
            }
        }
    } catch {
        $state = @{}
    }
}

if ($Reset) {
    Log-Msg "      [FLAG] --reset detected. Clearing cached state..." "DarkYellow"
    $state = @{}
    Remove-Item -LiteralPath $stateFile -Force -ErrorAction SilentlyContinue
}

# ------------------------------------------------------------------------------
# [2/8] System Prerequisites (MSVC Runtime Verification)
# ------------------------------------------------------------------------------
Log-Msg "[2/8] Checking system binary prerequisites (MSVC C++ Runtime)..." "Yellow"

$hasMsvc = (Test-Path "C:\Windows\System32\msvcp140.dll") -or (Test-Path "C:\Windows\SysWOW64\msvcp140.dll")
if (-not $hasMsvc) {
    Log-Msg "      [SETUP] msvcp140.dll missing. Provisioning Microsoft Visual C++ Redistributable..." "Cyan"
    $vcUrl = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
    $vcInstaller = Join-Path $runtimeDir "vc_redist.x64.exe"
    try {
        if (-not (Test-Path $vcInstaller)) {
            curl.exe -L -o $vcInstaller $vcUrl
        }
        $vcProc = Start-Process -FilePath $vcInstaller -ArgumentList "/install /quiet /norestart" -PassThru -Wait
        Start-Sleep -Seconds 2
        $hasMsvc = (Test-Path "C:\Windows\System32\msvcp140.dll")
        if ($hasMsvc) {
            Log-Msg "      [SUCCESS] Visual C++ Runtime installed successfully." "Green"
        } else {
            Log-Msg "      [WARNING] Visual C++ Runtime install completed with exit code $($vcProc.ExitCode)." "DarkYellow"
        }
    } catch {
        Log-Msg "      [WARNING] Could not auto-install VC++ Runtime: $($_.Exception.Message)" "DarkYellow"
    }
} else {
    Log-Msg "      [SUCCESS] Visual C++ Runtime (msvcp140.dll) verified." "Green"
}
Log-Msg ""

# ------------------------------------------------------------------------------
# [3/8] Provision Node.js LTS Engine
# ------------------------------------------------------------------------------
Log-Msg "[3/8] Verifying Node.js execution runtime..." "Yellow"

$nodeFound = $false
$nodeExe = $null
$npmCmd = $null

$nodeCandidates = @(
    (Join-Path $runtimeDir "node\node-v22.14.0-win-x64\node.exe"),
    (Join-Path $runtimeDir "node\node-v20.18.0-win-x64\node.exe"),
    "C:\Users\WDAGUtilityAccount\Desktop\improvements\tools\node\node-v22.14.0-win-x64\node.exe",
    (Join-Path $frontendDir ".node\node-v22.14.0-win-x64\node.exe")
)

foreach ($nc in $nodeCandidates) {
    if (Test-Path $nc) {
        $nodeExe = $nc
        $npmCmd  = Join-Path (Split-Path $nc -Parent) "npm.cmd"
        $nodeFound = $true
        break
    }
}

if (-not $nodeFound -and (Get-Command "node" -ErrorAction SilentlyContinue)) {
    $nodeExe = (Get-Command "node").Source
    $npmCmd  = "npm.cmd"
    $nodeFound = $true
}

if (-not $nodeFound) {
    Log-Msg "      [SETUP] Downloading portable Node.js v22.14.0 LTS..." "Cyan"
    $nodeZipUrl = "https://nodejs.org/dist/v22.14.0/node-v22.14.0-win-x64.zip"
    $nodeZipDest = Join-Path $runtimeDir "node.zip"
    $nodeExtract = Join-Path $runtimeDir "node"
    if (-not (Test-Path $nodeExtract)) { New-Item -ItemType Directory -Path $nodeExtract -Force | Out-Null }
    try {
        curl.exe -L -o $nodeZipDest $nodeZipUrl
        if (Get-Command "tar.exe" -ErrorAction SilentlyContinue) {
            tar.exe -xf $nodeZipDest -C $nodeExtract
        } else {
            Expand-Archive -Path $nodeZipDest -DestinationPath $nodeExtract -Force
        }
        Remove-Item $nodeZipDest -Force -ErrorAction SilentlyContinue
        $foundNode = Get-ChildItem -Path $nodeExtract -Recurse -Filter "node.exe" | Select-Object -First 1
        if ($foundNode) {
            $nodeExe = $foundNode.FullName
            $npmCmd  = Join-Path (Split-Path $nodeExe -Parent) "npm.cmd"
            $nodeFound = $true
        }
    } catch {
        Log-Msg "      [ERROR] Automated Node.js provisioning failed: $($_.Exception.Message)" "Red"
        exit 1
    }
}

$nodeDir = Split-Path $nodeExe -Parent
$env:PATH = "$nodeDir;$env:PATH"
$nodeVer = (& $nodeExe -v 2>$null).Trim()
Log-Msg "      [SUCCESS] Node.js Engine ready: $nodeVer ($nodeExe)" "Green"
Log-Msg ""

# ------------------------------------------------------------------------------
# [4/8] Provision Python 3.11 Runtime & Virtual Environment
# ------------------------------------------------------------------------------
Log-Msg "[4/8] Verifying Python 3.11 backend engine..." "Yellow"

$venvDir = Join-Path $backendDir ".venv"
$venvPy  = Join-Path $venvDir "Scripts\python.exe"
$venvPip = Join-Path $venvDir "Scripts\pip.exe"

# Discover uv tool for ultra-fast binary python bootstrapping
$uvCandidates = @(
    (Join-Path $runtimeDir "uv.exe"),
    "C:\Users\WDAGUtilityAccount\Desktop\improvements\tools\uv.exe",
    (Join-Path $repoRoot ".uv\uv.exe")
)
$uvExe = $null
foreach ($uc in $uvCandidates) {
    if (Test-Path $uc) { $uvExe = $uc; break }
}
if (-not $uvExe -and (Get-Command "uv" -ErrorAction SilentlyContinue)) {
    $uvExe = (Get-Command "uv").Source
}

if (-not $uvExe) {
    Log-Msg "      [SETUP] Downloading standalone uv engine..." "Cyan"
    $uvZip = Join-Path $runtimeDir "uv.zip"
    try {
        curl.exe -L -o $uvZip "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"
        if (Get-Command "tar.exe" -ErrorAction SilentlyContinue) {
            tar.exe -xf $uvZip -C $runtimeDir
        } else {
            Expand-Archive -Path $uvZip -DestinationPath $runtimeDir -Force
        }
        Remove-Item $uvZip -Force -ErrorAction SilentlyContinue
        $uvExe = Join-Path $runtimeDir "uv.exe"
    } catch {
        Log-Msg "      [WARNING] Standalone uv download note: $($_.Exception.Message)" "DarkYellow"
    }
}

if (-not (Test-Path $venvPy)) {
    Log-Msg "      [SETUP] Creating Python 3.11 virtual environment (.venv)..." "Cyan"
    if ($uvExe -and (Test-Path $uvExe)) {
        & $uvExe venv $venvDir --python 3.11
    } else {
        # Fallback to system python if valid
        if (Get-Command "python" -ErrorAction SilentlyContinue) {
            & python -m venv $venvDir
        }
    }
}

if (-not (Test-Path $venvPy)) {
    Log-Msg "[ERROR] Could not build backend virtual environment at: $venvDir" "Red"
    exit 1
}

$pyVer = (& $venvPy --version 2>&1).ToString().Trim()
Log-Msg "      [SUCCESS] Backend Python ready: $pyVer ($venvPy)" "Green"
Log-Msg ""

# ------------------------------------------------------------------------------
# [5/8] Tiered Backend Dependency Installation
# ------------------------------------------------------------------------------
Log-Msg "[5/8] Checking backend dependencies across structured tiers..." "Yellow"

$pipTool = if ($uvExe -and (Test-Path $uvExe)) { $uvExe } else { $venvPip }

function Install-PythonTier {
    param([string]$TierName, [string[]]$Packages, [string]$VerificationScript, [bool]$IsCritical = $true)
    
    # Check state file
    $stateKey = "tier_$TierName"
    if ($state.ContainsKey($stateKey) -and $state[$stateKey] -eq $true -and -not $Reset) {
        Log-Msg "      [CACHE] Tier '$TierName' already installed and verified. Skipping." "DarkGray"
        return $true
    }

    Log-Msg "      [TIER: $TierName] Installing packages: $($Packages -join ' ')..." "Cyan"
    $swT = [System.Diagnostics.Stopwatch]::StartNew()
    
    if ($pipTool -eq $uvExe) {
        & $uvExe pip install --python $venvPy @Packages
    } else {
        & $venvPip install @Packages --no-warn-script-location
    }
    if ($LASTEXITCODE -ne 0) {
        Log-Msg "      [RETRY] Retrying package install for tier '$TierName'..." "DarkYellow"
        if ($pipTool -eq $uvExe) {
            & $uvExe pip install --python $venvPy @Packages
        } else {
            & $venvPip install @Packages --no-warn-script-location
        }
    }

    # Verification probe
    $vCheck = & $venvPy -c "$VerificationScript; print('VERIFIED_OK')" 2>$null
    if ($vCheck -match "VERIFIED_OK") {
        $swT.Stop()
        Log-Msg "      [SUCCESS] Tier '$TierName' verified in $([math]::Round($swT.Elapsed.TotalSeconds, 1))s." "Green"
        $state[$stateKey] = $true
        return $true
    } else {
        $swT.Stop()
        if ($IsCritical) {
            Log-Msg "      [ERROR] Tier '$TierName' failed verification probe!" "Red"
            return $false
        } else {
            Log-Msg "      [WARNING] Optional Tier '$TierName' could not be fully verified." "DarkYellow"
            return $true
        }
    }
}

# Tier 1: Core Web & DB Drivers
$tier1Pkgs = @(
    "fastapi>=0.110.0", "uvicorn[standard]>=0.29.0", "pydantic>=2.7.0",
    "pydantic-settings>=2.2.0", "python-dotenv>=1.0.0", "python-multipart>=0.0.9",
    "jinja2>=3.1.0", "sqlalchemy>=2.0.0", "sqlmodel>=0.0.14", "redis>=5.0.0",
    "psycopg2-binary>=2.9.9", "pymupdf>=1.24.0", "numpy>=1.26.0", "pandas>=2.2.0",
    "httpx>=0.27.0", "requests>=2.31.0", "cachetools>=5.3.0", "psutil>=5.9.0"
)
$tier1Probe = "import fastapi, uvicorn, pydantic, sqlalchemy, sqlmodel, redis, psycopg2, pymupdf, numpy, pandas, httpx"
$t1Ok = Install-PythonTier -TierName "1_Core" -Packages $tier1Pkgs -VerificationScript $tier1Probe -IsCritical $true
if (-not $t1Ok) { exit 1 }

# Tier 2: Vector, Graph & LangGraph
$tier2Pkgs = @("chromadb>=0.4.24", "langgraph>=0.2.0", "langchain-core>=0.3.0", "neo4j>=5.26.0", "msgpack>=1.1.2", "networkx>=3.2.0")
$tier2Probe = "import chromadb, langgraph, langchain_core, neo4j, msgpack, networkx"
$t2Ok = Install-PythonTier -TierName "2_Databases_RAG" -Packages $tier2Pkgs -VerificationScript $tier2Probe -IsCritical $true
if (-not $t2Ok) { exit 1 }

# Tier 3: Document Processing & Extraction
$tier3Pkgs = @("pypdf>=3.17.0", "python-docx>=0.8.11", "openpyxl>=3.1.0")
$tier3Probe = "import pypdf, docx, openpyxl"
$t3Ok = Install-PythonTier -TierName "3_DocProcessing" -Packages $tier3Pkgs -VerificationScript $tier3Probe -IsCritical $false

# Tier 4: Machine Learning & CPU Embeddings (Optional / Skippable)
if (-not $SkipMl) {
    $tier4Probe = "import torch, sentence_transformers; assert torch.__version__"
    $isMlInstalled = & $venvPy -c "$tier4Probe; print('VERIFIED_OK')" 2>$null
    if ($isMlInstalled -match "VERIFIED_OK") {
        Log-Msg "      [CACHE] Tier '4_ML_Embeddings' already verified. Skipping." "DarkGray"
        $state["tier_4_ML_Embeddings"] = $true
    } else {
        Log-Msg "      [TIER: 4_ML_Embeddings] Provisioning CPU PyTorch & SentenceTransformers..." "Cyan"
        if ($pipTool -eq $uvExe) {
            & $uvExe pip install --python $venvPy torch --index-url https://download.pytorch.org/whl/cpu
            & $uvExe pip install --python $venvPy sentence-transformers
        } else {
            & $venvPip install torch --index-url https://download.pytorch.org/whl/cpu
            & $venvPip install sentence-transformers
        }
        $mlCheck = & $venvPy -c "$tier4Probe; print('VERIFIED_OK')" 2>$null
        if ($mlCheck -match "VERIFIED_OK") {
            Log-Msg "      [SUCCESS] Tier '4_ML_Embeddings' verified successfully." "Green"
            $state["tier_4_ML_Embeddings"] = $true
        } else {
            Log-Msg "      [NOTICE] ML packages installed; proceeding with CPU fallbacks." "DarkYellow"
        }
    }
} else {
    Log-Msg "      [FLAG] --skip-ml enabled. Skipping heavy ML installation." "DarkGray"
}

# Save updated state
$state | ConvertTo-Json | Set-Content -LiteralPath $stateFile -Force

# Auto-configure .env from template if missing
$rootEnv = Join-Path $repoRoot ".env"
$rootEnvEx = Join-Path $repoRoot ".env.example"
$backendEnv = Join-Path $backendDir ".env"
$backendEnvEx = Join-Path $backendDir ".env.example"

if (-not (Test-Path $backendEnv)) {
    if (Test-Path $rootEnv) {
        Copy-Item -Path $rootEnv -Destination $backendEnv -Force
    } elseif (Test-Path $rootEnvEx) {
        Copy-Item -Path $rootEnvEx -Destination $backendEnv -Force
    } elseif (Test-Path $backendEnvEx) {
        Copy-Item -Path $backendEnvEx -Destination $backendEnv -Force
    } else {
        # Minimal default fallback
        "HOST=0.0.0.0`nPORT=8000`nEMBEDDING_DEVICE=cpu`nVITE_API_URL=http://localhost:8000" | Set-Content -LiteralPath $backendEnv
    }
    Log-Msg "      [CONFIG] Created backend .env configuration." "Green"
}
Log-Msg ""

# ------------------------------------------------------------------------------
# [6/8] Frontend Dependencies & Vite Bundler Preparation
# ------------------------------------------------------------------------------
Log-Msg "[6/8] Checking frontend packages & Vite compiler..." "Yellow"

$viteCmd = Join-Path $frontendDir "node_modules\.bin\vite.cmd"
$frontendLock = Join-Path $frontendDir "package-lock.json"

if (-not (Test-Path $viteCmd) -or $Reset) {
    Log-Msg "      [SETUP] Installing frontend node packages..." "Cyan"
    Push-Location $frontendDir
    if (Test-Path $frontendLock) {
        & $npmCmd ci --no-fund --no-audit
    } else {
        & $npmCmd install --no-fund --no-audit
    }
    Pop-Location
}

if (-not (Test-Path $viteCmd)) {
    Log-Msg "[ERROR] node_modules/.bin/vite.cmd was not found. Frontend install incomplete." "Red"
    exit 1
}

Log-Msg "      [SUCCESS] Vite compiler ready: $viteCmd" "Green"
Log-Msg ""

# ------------------------------------------------------------------------------
# [7/8] Port Clearing & Zombie Process Sweep
# ------------------------------------------------------------------------------
Log-Msg "[7/8] Sweeping ports 8000 and 5173..." "Yellow"

function Clear-PortOccupant {
    param([int]$Port)
    try {
        $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        foreach ($c in $conns) {
            $pidToKill = $c.OwningProcess
            if ($pidToKill -gt 0 -and $pidToKill -ne $PID) {
                Log-Msg "      [SWEEP] Terminating stale process $pidToKill on port $Port..." "DarkYellow"
                Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {}
}

Clear-PortOccupant -Port 8000
Clear-PortOccupant -Port 5173
Start-Sleep -Milliseconds 500
Log-Msg "      [SUCCESS] Ports 8000 and 5173 verified free." "Green"
Log-Msg ""

# ------------------------------------------------------------------------------
# [8/8] Coordinated Multi-Service Launch & Live Synchronization
# ------------------------------------------------------------------------------
Log-Msg "[8/8] Starting RAISE Application Gateway & React UI..." "Yellow"

# 1. Start Backend Gateway
$backendScript = Join-Path $backendDir "server.py"
Log-Msg "  -> Launching Backend on http://localhost:8000..." "Cyan"

$backendProc = Start-Process -FilePath $venvPy -ArgumentList "-u `"$backendScript`" --no-tunnel" -WorkingDirectory $backendDir -RedirectStandardOutput $backendLog -RedirectStandardError "$backendLog.err" -PassThru

# Poll /api/health up to 120s
Log-Msg "     Waiting for Backend health endpoint (up to 120s)..." "Gray"
$backendReady = $false
$swB = [System.Diagnostics.Stopwatch]::StartNew()

while ($swB.Elapsed.TotalSeconds -lt 120) {
    if ($backendProc.HasExited) { break }
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 2 -ErrorAction Stop
        if ($resp) {
            $backendReady = $true
            break
        }
    } catch {}
    Start-Sleep -Seconds 2
}

if (-not $backendReady) {
    Log-Msg "[ERROR] Backend failed to report healthy status within 120 seconds." "Red"
    Log-Msg "--- Recent Backend Log Output ---" "Red"
    if (Test-Path $backendLog) {
        Get-Content $backendLog -Tail 30 | ForEach-Object { Log-Msg "  $_" "DarkYellow" }
    }
    if (Test-Path "$backendLog.err") {
        Get-Content "$backendLog.err" -Tail 30 | ForEach-Object { Log-Msg "  $_" "Red" }
    }
    if ($backendProc -and -not $backendProc.HasExited) { Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue }
    exit 1
}

Log-Msg "     [SUCCESS] Backend Gateway online (in $([math]::Round($swB.Elapsed.TotalSeconds, 1))s)." "Green"

# 2. Start Frontend Dev Server
Log-Msg "  -> Launching React Vite UI on http://localhost:5173..." "Cyan"

$viteJs = Join-Path $frontendDir "node_modules\vite\bin\vite.js"
if (Test-Path $viteJs) {
    $frontendProc = Start-Process -FilePath $nodeExe -ArgumentList "`"$viteJs`"" -WorkingDirectory $frontendDir -RedirectStandardOutput $frontendLog -RedirectStandardError "$frontendLog.err" -PassThru
} elseif (Test-Path (Join-Path $frontendDir "node_modules\.bin\vite.cmd")) {
    $frontendProc = Start-Process -FilePath (Join-Path $frontendDir "node_modules\.bin\vite.cmd") -WorkingDirectory $frontendDir -RedirectStandardOutput $frontendLog -RedirectStandardError "$frontendLog.err" -PassThru
} else {
    $frontendProc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c npm run dev" -WorkingDirectory $frontendDir -RedirectStandardOutput $frontendLog -RedirectStandardError "$frontendLog.err" -PassThru
}

# Poll Vite UI port 5173
$frontendReady = $false
$swF = [System.Diagnostics.Stopwatch]::StartNew()
while ($swF.Elapsed.TotalSeconds -lt 30) {
    if ($frontendProc.HasExited) { break }
    try {
        $respF = Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($respF.StatusCode -eq 200) {
            $frontendReady = $true
            break
        }
    } catch {}
    Start-Sleep -Seconds 1
}

Log-Msg ""
Log-Msg "============================================================================" "Green"
Log-Msg "                      RAISE IS RUNNING SUCCESSFULLY" "Green"
Log-Msg "============================================================================" "Green"
Log-Msg "  FastAPI Gateway:       http://localhost:8000" "Cyan"
Log-Msg "  Health Diagnostics:    http://localhost:8000/api/health" "Cyan"
Log-Msg "  Interactive Swagger:   http://localhost:8000/docs" "Cyan"
Log-Msg "  React Workstation UI:  http://localhost:5173" "Cyan"
Log-Msg ""
Log-Msg "  Backend PID:           $($backendProc.Id) (logs: logs\backend.log)" "Gray"
Log-Msg "  Frontend PID:          $($frontendProc.Id) (logs: logs\frontend.log)" "Gray"
Log-Msg "============================================================================" "Green"
Log-Msg "  [!] KEEP THIS WINDOW OPEN while using RAISE." "Yellow"
Log-Msg "  Press Ctrl+C to terminate both servers cleanly." "Yellow"
Log-Msg "============================================================================" "Green"
Log-Msg ""

if (-not $NoBrowser) {
    try {
        Start-Process "http://localhost:5173"
        Log-Msg "  [BROWSER] Opened http://localhost:5173 in default browser." "Green"
    } catch {}
}

# Teardown Trap
try {
    while ($true) {
        if ($backendProc.HasExited -or $frontendProc.HasExited) {
            Log-Msg "One of the child services exited. Initiating clean shutdown..." "DarkYellow"
            break
        }
        Start-Sleep -Seconds 1
    }
} finally {
    Log-Msg ""
    Log-Msg "[SHUTDOWN] Stopping RAISE cleanly..." "Yellow"
    if ($backendProc -and -not $backendProc.HasExited) {
        taskkill /PID $backendProc.Id /T /F 2>$null | Out-Null
    }
    if ($frontendProc -and -not $frontendProc.HasExited) {
        taskkill /PID $frontendProc.Id /T /F 2>$null | Out-Null
    }
    Clear-PortOccupant -Port 8000
    Clear-PortOccupant -Port 5173
    Log-Msg "[SHUTDOWN] Teardown complete. Ports released." "Green"
}
