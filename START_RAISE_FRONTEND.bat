@echo off
title RAISE Frontend
cd /d "%~dp0"
set "BAT_FILE=%~f0"

:: ============================================================================
::  RAISE Frontend — Windows Single-Click Startup
::  Self-contained script supporting clean Windows 10/11 & Windows Sandbox.
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
[Console]::Title = "RAISE Frontend"
$ErrorActionPreference = "Continue"

$root = (Get-Location).Path

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "                              RAISE FRONTEND" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# ------------------------------------------------------------------------------
# [0/3] Check if Frontend Source Code is Present; Auto-fetch if missing
# ------------------------------------------------------------------------------
if (Test-Path (Join-Path $root "package.json")) {
    Write-Host "[0/3] Workspace verification: ready." -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "[0/3] Initializing workspace: fetching frontend assets from repository..." -ForegroundColor Cyan
    Write-Host ""
    $zipUrl = "https://github.com/semanticClimate/RAISE/archive/refs/heads/frontend.zip"
    $zipTemp = Join-Path $env:TEMP "RAISE-frontend-$([guid]::NewGuid().ToString('N')).zip"
    $extTemp = Join-Path $env:TEMP "RAISE-frontend-ext-$([guid]::NewGuid().ToString('N'))"
    
    $downloaded = $false
    try {
        if (Get-Command git -ErrorAction SilentlyContinue) {
            Write-Host "      [GIT] Cloning frontend branch from semanticClimate/RAISE..." -ForegroundColor Gray
            $tempGit = Join-Path $root ".temp_git_frontend"
            git clone --depth 1 -b frontend https://github.com/semanticClimate/RAISE.git $tempGit
            if (Test-Path (Join-Path $tempGit "package.json")) {
                Copy-Item -Path "$tempGit\*" -Destination $root -Recurse -Force
                Remove-Item -Path $tempGit -Recurse -Force -ErrorAction SilentlyContinue
                $downloaded = $true
            }
        }
    } catch {}

    if (-not $downloaded) {
        try {
            Write-Host "      [WEB] Downloading frontend branch archive..." -ForegroundColor Gray
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri $zipUrl -OutFile $zipTemp -UseBasicParsing
            Expand-Archive -Path $zipTemp -DestinationPath $extTemp -Force
            $inner = Get-ChildItem -Path $extTemp -Directory | Select-Object -First 1
            if ($inner) {
                Copy-Item -Path "$($inner.FullName)\*" -Destination $root -Recurse -Force
                $downloaded = $true
            }
            Remove-Item -Path $zipTemp -Force -ErrorAction SilentlyContinue
            Remove-Item -Path $extTemp -Recurse -Force -ErrorAction SilentlyContinue
        } catch {
            Write-Host "      [WARN] Direct download attempt failed: $_" -ForegroundColor DarkYellow
        }
    }

    if (-not (Test-Path (Join-Path $root "package.json"))) {
        Write-Host ""
        Write-Host "============================================================================" -ForegroundColor Red
        Write-Host " [ERROR] Could not fetch frontend code automatically." -ForegroundColor Red
        Write-Host " Please clone the frontend branch manually:" -ForegroundColor Red
        Write-Host "   git clone -b frontend https://github.com/semanticClimate/RAISE.git" -ForegroundColor Red
        Write-Host "============================================================================" -ForegroundColor Red
        Pause
        exit 1
    }
    Write-Host "      [SUCCESS] Frontend source code downloaded and prepared!" -ForegroundColor Green
    Write-Host ""
}

# ------------------------------------------------------------------------------
# [1/3] Detect or Automatically Download Node.js LTS
# ------------------------------------------------------------------------------
Write-Host "[1/3] Checking environment & Node.js installation..." -ForegroundColor Yellow

$targetNodeVer   = "v22.14.0"
$portableNodeDir = Join-Path $root ".node\node-$targetNodeVer-win-x64"
$portableNodeExe = Join-Path $portableNodeDir "node.exe"
$portableNpmCmd  = Join-Path $portableNodeDir "npm.cmd"

$nodeFound = $false

# 1. Check if portable Node.js is Available in .node
if (Test-Path -LiteralPath $portableNodeExe) {
    $env:PATH = "$portableNodeDir;$env:PATH"
    $nodeFound = $true
    Write-Host "      [SUCCESS] Local portable Node.js ($targetNodeVer) Available in .node folder." -ForegroundColor Green
}
# 2. Check if system Node.js is Available and meets minimum requirements (Node 22 LTS)
elseif (Get-Command "node" -ErrorAction SilentlyContinue) {
    $sysVerRaw = (& node -v 2>$null).Trim()
    $sysMajor = 0
    if ($sysVerRaw -match "^v?(\d+)") { $sysMajor = [int]$matches[1] }
    if ($sysMajor -ge 22) {
        $nodeFound = $true
        Write-Host "      [SUCCESS] Modern system Node.js ($sysVerRaw) Available in PATH." -ForegroundColor Green
    } else {
        Write-Host "      [WARNING] Detected outdated Node.js ($sysVerRaw). Node 22.14+ LTS is required." -ForegroundColor Yellow
        Write-Host "      Switching to portable Node.js ($targetNodeVer)..." -ForegroundColor Yellow
    }
}

# 3. If Node.js is missing, auto-download portable Node.js LTS
if (-not $nodeFound) {
    Write-Host ""
    Write-Host "============================================================================" -ForegroundColor Yellow
    Write-Host " [NOTICE] Node.js is NOT installed on this machine." -ForegroundColor Yellow
    Write-Host ""
    Write-Host " Automatically downloading portable Node.js LTS $targetNodeVer..." -ForegroundColor Yellow
    Write-Host " (One-time ~35MB download so you do NOT need to install anything manually!)" -ForegroundColor Yellow
    Write-Host "============================================================================" -ForegroundColor Yellow
    Write-Host ""

    $nodeZipUrl = "https://nodejs.org/dist/$targetNodeVer/node-$targetNodeVer-win-x64.zip"
    $tempZip = Join-Path $env:TEMP "node-$targetNodeVer-win-x64.zip"
    $nodeContainer = Join-Path $root ".node"

    if (-not (Test-Path -LiteralPath $nodeContainer)) {
        New-Item -ItemType Directory -Path $nodeContainer -Force | Out-Null
    }

    # Download Node.js zip with native progress
    Write-Host "[DOWNLOADING] Fetching Node.js LTS from nodejs.org (~35MB)..." -ForegroundColor Cyan
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
        $webClient = New-Object System.Net.WebClient
        $webClient.DownloadFile($nodeZipUrl, $tempZip)
        Write-Host "      [SUCCESS] Download finished successfully." -ForegroundColor Green
    } catch {
        Write-Host "      [WARNING] WebClient download failed, falling back to Invoke-WebRequest..." -ForegroundColor Yellow
        Invoke-WebRequest -Uri $nodeZipUrl -OutFile $tempZip -UseBasicParsing
    }

    # Extract Node.js zip
    Write-Host "[EXTRACTING] Unpacking portable Node.js into .node folder..." -ForegroundColor Cyan
    Expand-Archive -LiteralPath $tempZip -DestinationPath $nodeContainer -Force
    Remove-Item -LiteralPath $tempZip -Force -ErrorAction SilentlyContinue

    if (Test-Path -LiteralPath $portableNodeExe) {
        $env:PATH = "$portableNodeDir;$env:PATH"
        Write-Host "      [SUCCESS] Portable Node.js runtime is installed and ready!" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Could not find extracted node.exe at $portableNodeExe" -ForegroundColor Red
        Read-Host "Press Enter to exit..."
        exit 1
    }
}

# Determine npm command path
$npmCmd = "npm.cmd"
if (Test-Path -LiteralPath $portableNpmCmd) {
    $npmCmd = $portableNpmCmd
}

$nodeVersion = (& node -v 2>$null).Trim()
$npmVersion = (& $npmCmd -v 2>$null).Trim()



Write-Host ""
Write-Host "      - Node.js version: $nodeVersion" -ForegroundColor White
Write-Host "      - npm version:     $npmVersion" -ForegroundColor White
Write-Host "      - Engine status:   READY" -ForegroundColor Green
Write-Host ""

# Safely approve ONLY esbuild for install-scripts if supported
try {
    & $npmCmd install-scripts approve esbuild --no-allow-scripts-pin 2>$null | Out-Null
} catch {}

# ------------------------------------------------------------------------------
# [2/3] Check and Install Project Dependencies (node_modules)
# ------------------------------------------------------------------------------
Write-Host "[2/3] Checking project dependencies (node_modules)..." -ForegroundColor Yellow

$nodeModulesDir = Join-Path $root "node_modules"

if (Test-Path -LiteralPath $nodeModulesDir) {
    Write-Host "      [SUCCESS] Dependencies (node_modules) Available." -ForegroundColor Green
} else {
    Write-Host "      [DOWNLOADING] Dependencies missing. Installing npm packages..." -ForegroundColor Cyan
    Write-Host "                    (Downloading React 19, Vite, Tailwind, and UI components)" -ForegroundColor DarkGray
    Write-Host ""

    & $npmCmd install --no-fund --no-audit
    $installCode = $LASTEXITCODE

    if ($installCode -ne 0) {
        Write-Host ""
        Write-Host "[ERROR] npm install failed with exit code $installCode." -ForegroundColor Red
        Write-Host "        Please verify your network connection and disk permissions." -ForegroundColor Red
        Read-Host "Press Enter to exit..."
        exit 1
    }

    # Verify esbuild and Vite are present and functional
    $viteBin = Join-Path $root "node_modules\.bin\vite.cmd"
    if (-not (Test-Path -LiteralPath $viteBin)) {
        Write-Host "      [WARNING] Vite binary was not found in node_modules\.bin. Retrying package verification..." -ForegroundColor Yellow
        & $npmCmd install --no-fund --no-audit
    }

    Write-Host ""
    Write-Host "      [SUCCESS] Dependencies installed and verified successfully!" -ForegroundColor Green
}

Write-Host ""

# ------------------------------------------------------------------------------
# [3/3] Launch Vite Development Server
# ------------------------------------------------------------------------------
Write-Host "[3/3] Starting RAISE Frontend Development Server (Vite)..." -ForegroundColor Yellow
Write-Host ""
Write-Host "============================================================================" -ForegroundColor Green
Write-Host "  Vite server is launching..." -ForegroundColor Green
Write-Host "  Local Address: http://localhost:5173/" -ForegroundColor Cyan
Write-Host ""
Write-Host "  [!] KEEP THIS WINDOW OPEN while using the application." -ForegroundColor Yellow
Write-Host "  Press Ctrl+C to stop the server when finished." -ForegroundColor Yellow
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""

& $npmCmd run dev
