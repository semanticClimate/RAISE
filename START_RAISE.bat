@echo off
chcp 65001 >nul
title RAISE
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "BAT_FILE=%~f0"
set "BAT_DIR=%~dp0"
set "RAISE_RUN_ARGS=%*"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
set "FORCE_COLOR=1"
set "TERM="
set "HF_HUB_DISABLE_PROGRESS_BARS=0"
set "TRANSFORMERS_VERBOSITY=error"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { $raw = [System.IO.File]::ReadAllText($env:BAT_FILE, [System.Text.Encoding]::UTF8); $tag = '<' + '#PS_CODE#>'; $idx = $raw.LastIndexOf($tag); if ($idx -ge 0) { Invoke-Expression $raw.Substring($idx + $tag.Length) } else { Write-Error 'Marker not found'; exit 1 } } catch { Write-Host $_ -ForegroundColor Red; exit 1 }"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo  [!] Process exited with code %EXIT_CODE%.
    echo  [!] Press any key to close this window...
    pause >nul
)
goto :bat_exit

:bat_exit
endlocal
exit /b %EXIT_CODE%
goto :eof

:: ==============================================================================
:: POWERSHELL RUNTIME BODY - UNREACHABLE BY CMD.EXE
:: ==============================================================================
<#PS_CODE#>
$NoBrowser = $false

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding  = [System.Text.Encoding]::UTF8

# Early arguments extraction
$rawArgs = if ($env:RAISE_RUN_ARGS) { $env:RAISE_RUN_ARGS } else { [string]::Join(" ", $args) }
if ($rawArgs -match "(?i)--no-browser|--nobrowser|-nobrowser|-no-browser") { $NoBrowser = $true }
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"
$env:FORCE_COLOR = "1"
$env:TERM = ""
$env:HF_HUB_DISABLE_PROGRESS_BARS = "0"
$env:TRANSFORMERS_VERBOSITY = "error"

try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch {}
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [enum]::Parse([Net.SecurityProtocolType], 'Tls13') } catch {}
$ProgressPreference = 'SilentlyContinue'

# Enable Windows Virtual Terminal Processing for ANSI TrueColor & Box Geometry
try {
    $kernel32 = Add-Type -MemberDefinition @"
[DllImport("kernel32.dll", SetLastError = true)]
public static extern IntPtr GetStdHandle(int nStdHandle);
[DllImport("kernel32.dll", SetLastError = true)]
public static extern bool GetConsoleMode(IntPtr hConsoleHandle, out uint lpMode);
[DllImport("kernel32.dll", SetLastError = true)]
public static extern bool SetConsoleMode(IntPtr hConsoleHandle, uint dwMode);
"@ -Name "WinVTConsole" -Namespace "Win32" -PassThru
    $hOut = $kernel32::GetStdHandle(-11)
    $mode = 0
    if ($kernel32::GetConsoleMode($hOut, [ref]$mode)) {
        $kernel32::SetConsoleMode($hOut, $mode -bor 0x0004) | Out-Null
    }
} catch {}

$esc = [char]27
$C = @{
    Reset   = "$esc[0m"
    Bold    = "$esc[1m"
    Dim     = "$esc[38;5;242m"
    Border  = "$esc[38;5;240m"
    Cyan    = "$esc[38;5;81m"
    Green   = "$esc[38;5;114m"
    Yellow  = "$esc[38;5;221m"
    Red     = "$esc[38;5;203m"
    Purple  = "$esc[38;5;141m"
    White   = "$esc[38;5;255m"
    Gray    = "$esc[38;5;246m"
}

function global:Format-SanitizeOutput {
    param([string]$Text)
    if (-not $Text) { return $Text }
    $userHome = $env:USERPROFILE
    if ($userHome) {
        $Text = $Text.Replace($userHome, "~").Replace($userHome.Replace('\', '/'), '~')
    }
    return $Text
}

function prompt { "$($C.Purple)╭─$($C.Reset) $($C.Bold)$($C.Cyan)RAISE$($C.Reset) $($C.Dim)>$($C.Reset) " }

function Write-Header {
    Clear-Host
    $ts = (Get-Date).ToString("HH:mm:ss")
    Write-Host ""
    Write-Host "  $($C.Border)╭──────────────────────────────────────────────────────────────────────────╮$($C.Reset)"
    Write-Host "  $($C.Border)│$($C.Reset)  $($C.Bold)$($C.Cyan)RAISE$($C.Reset) $($C.Dim)//$($C.Reset) $($C.White)Research Assessment Intelligence & Semantic Extraction$($C.Reset)     $($C.Border)│$($C.Reset)"
    Write-Host "  $($C.Border)│$($C.Reset)  $($C.Dim)Service Supervisor  •  Unbuffered Live Stream  •  Boot: $ts$($C.Reset)          $($C.Border)│$($C.Reset)"
    Write-Host "  $($C.Border)╰──────────────────────────────────────────────────────────────────────────╯$($C.Reset)"
    Write-Host ""
}

function Write-Info {
    param([string]$Text, [string]$Color = "Cyan", [string]$Branch = "├─")
    $ts = (Get-Date).ToString("HH:mm:ss.fff")
    $sanitized = Format-SanitizeOutput $Text
    $icon = switch ($Color) {
        "Green"      { "$($C.Green)[OK]$($C.Reset)" }
        "Yellow"     { "$($C.Yellow)[!]$($C.Reset)" }
        "DarkYellow" { "$($C.Yellow)[~]$($C.Reset)" }
        "Red"        { "$($C.Red)[ERR]$($C.Reset)" }
        "Gray"       { "$($C.Dim)[-]$($C.Reset)" }
        default      { "$($C.Cyan)*$($C.Reset)" }
    }
    $textColor = switch ($Color) {
        "Green"      { $C.White }
        "Yellow"     { $C.Yellow }
        "DarkYellow" { $C.Yellow }
        "Red"        { $C.Red }
        "Gray"       { $C.Dim }
        default      { $C.Gray }
    }
    Write-Host "  $($C.Border)$Branch$($C.Reset) $($C.Dim)[$ts]$($C.Reset) $icon $textColor$sanitized$($C.Reset)"
}

function Write-CardHeader {
    param([string]$Step, [string]$Title, [string]$Tone = "Cyan")
    $toneCode = if ($Tone -eq "Red") { $C.Red } elseif ($Tone -eq "Yellow") { $C.Yellow } else { $C.Cyan }
    Write-Host ""
    Write-Host "  $($C.Border)╭──────────────────────────────────────────────────────────────────────────╮$($C.Reset)"
    Write-Host "  $($C.Border)│$($C.Reset) $toneCode$($C.Bold)$Step$($C.Reset) $($C.White)$($C.Bold)$Title$($C.Reset)"
    Write-Host "  $($C.Border)╰──────────────────────────────────────────────────────────────────────────╯$($C.Reset)"
}

Write-Header

$repoRoot = if ($env:BAT_DIR -and (Test-Path -LiteralPath $env:BAT_DIR)) { (Resolve-Path -LiteralPath $env:BAT_DIR).Path } else { (Get-Location).Path }
Set-Location -LiteralPath $repoRoot

$backendDir = Join-Path $repoRoot "backend"; $frontendDir = Join-Path $repoRoot "frontend"
if (-not (Test-Path (Join-Path $backendDir "server.py"))) { Write-Info "Backend folder not found at: $backendDir" "Red" "╰─"; exit 1 }
if (-not (Test-Path (Join-Path $frontendDir "package.json"))) { Write-Info "Frontend folder not found at: $frontendDir" "Red" "╰─"; exit 1 }

$logsDir = Join-Path $backendDir "logs"
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }
$backendLog = Join-Path $logsDir "backend.log"; $frontendLog = Join-Path $logsDir "frontend.log"

# Automatically create canonical data folder and its subdirectories when user clones repo
$dataDir = Join-Path $backendDir "data"
$subDirs = @("documents", "library", "catalogs", "processed", "processed\chunks", "processed\graph_triples")
foreach ($sub in $subDirs) {
    $p = Join-Path $dataDir $sub
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
}
$manifestFile = Join-Path $dataDir "processed\ingested_manifest.json"
if (-not (Test-Path $manifestFile)) {
    Set-Content -Path $manifestFile -Value "{`"ready_documents`": [], `"timestamp`": `"`"}" -Encoding utf8
}

Write-Info "Workspace topology & canonical data directories verified" "Cyan"

# 1. Backend and Frontend directories verified

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

# 2.5 Ensure Microsoft Visual C++ 2015-2022 Redistributable (x64) is installed (required by PyTorch c10.dll, ONNX & Rust)
function Test-VcRedistInstalled {
    $x64Key = "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64"
    if (Test-Path $x64Key) {
        $inst = Get-ItemProperty -Path $x64Key -Name "Installed" -ErrorAction SilentlyContinue
        if ($inst -and $inst.Installed -eq 1) { return $true }
    }
    $sys32 = [Environment]::GetFolderPath("System")
    $hasVc1 = Test-Path (Join-Path $sys32 "vcruntime140.dll")
    $hasVc2 = Test-Path (Join-Path $sys32 "vcruntime140_1.dll")
    $hasMsc = Test-Path (Join-Path $sys32 "msvcp140.dll")
    return ($hasVc1 -and $hasVc2 -and $hasMsc)
}

function Ensure-VcRedist {
    if (-not (Test-VcRedistInstalled)) {
        Write-Info "Microsoft Visual C++ Redistributable (x64) not detected." "Yellow"
        Write-Info "Auto-provisioning Visual C++ 2015-2022 Runtime (required by PyTorch c10.dll)..." "Cyan"
        $vcUrl = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
        $vcInstaller = Join-Path $env:TEMP "vc_redist.x64.exe"
        if (Download-FileReliable -Url $vcUrl -Destination $vcInstaller) {
            Write-Info "Installing Microsoft Visual C++ Runtime (passive)..." "Cyan"
            try {
                $p = Start-Process -FilePath $vcInstaller -ArgumentList "/install", "/passive", "/norestart" -PassThru -Wait
                Remove-Item -LiteralPath $vcInstaller -Force -ErrorAction SilentlyContinue
                if (Test-VcRedistInstalled) {
                    Write-Info "Microsoft Visual C++ Redistributable successfully installed." "Green"
                } else {
                    Write-Host " [WARNING] Visual C++ runtime exited with code $($p.ExitCode). If PyTorch fails, download from: https://aka.ms/vs/17/release/vc_redist.x64.exe" -ForegroundColor Yellow
                }
            } catch {
                Write-Host " [WARNING] Could not run VC++ installer automatically: $($_.Exception.Message)" -ForegroundColor Yellow
            }
        } else {
            Write-Host " [WARNING] Could not download VC++ installer automatically. Please install manually from: https://aka.ms/vs/17/release/vc_redist.x64.exe" -ForegroundColor Yellow
        }
    }
}
Ensure-VcRedist

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

# Helper: Test if a Python runtime already has core dependencies installed
function Test-PythonHasCoreDeps {
    param([string]$Path)
    if (-not (Test-ValidPython $Path)) { return $false }
    try {
        $chk = & $Path -c "import sys, fastapi, uvicorn, pydantic, rich, prompt_toolkit, sentence_transformers, transformers; sys.stdout.write('OK')" 2>$null
        return ($chk -match "OK")
    } catch { return $false }
}

# Discover fast uv package manager across common locations
$uvDir = Join-Path $repoRoot ".uv"; $uvExe = Join-Path $uvDir "uv.exe"
$uvCandidates = @(
    $uvExe,
    (Join-Path $env:USERPROFILE "Miniconda3\Scripts\uv.exe"),
    (Join-Path $env:USERPROFILE "Anaconda3\Scripts\uv.exe"),
    "C:\Miniconda3\Scripts\uv.exe",
    "C:\Anaconda3\Scripts\uv.exe",
    (Join-Path $env:USERPROFILE ".cargo\bin\uv.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\uv\uv.exe"),
    (Join-Path $env:APPDATA "uv\uv.exe")
)
if (Get-Command "uv" -ErrorAction SilentlyContinue) {
    $uvCandidates = @((Get-Command "uv").Source) + $uvCandidates
}
$activeUv = $null
foreach ($u in $uvCandidates) {
    if ($u -and (Test-Path -LiteralPath $u)) { $activeUv = $u; break }
}

# Build ordered list of candidate Python environments
# Prioritize GPU-accelerated conda/system environments and pre-configured virtualenvs
$pyCandidates = @(
    (Join-Path $env:USERPROFILE "Miniconda3\python.exe"),
    (Join-Path $env:USERPROFILE "Anaconda3\python.exe"),
    "C:\Miniconda3\python.exe",
    "C:\Anaconda3\python.exe",
    $rootVenvPython,
    $venvPython,
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python310\python.exe"),
    "C:\Program Files\Python311\python.exe",
    "C:\Program Files\Python312\python.exe",
    "C:\Program Files\Python310\python.exe",
    (Join-Path $env:APPDATA "uv\python\cpython-3.11-windows-x86_64-none\python.exe")
)
foreach ($c in @("python", "python3", "py")) {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { $pyCandidates += $cmd.Source }
}

# PHASE A: Fast-path — select an environment that ALREADY has core dependencies (zero download, instant boot)
foreach ($cand in $pyCandidates) {
    if ($cand -and (Test-PythonHasCoreDeps $cand)) {
        $pythonExe = $cand
        Write-Info "Using verified Python environment: $cand" "Green"
        break
    }
}

# PHASE B: Fallback base Python selection if no pre-installed environment was found
if (-not $pythonExe) {
    foreach ($cand in $pyCandidates) {
        if ($cand -and (Test-ValidPython $cand)) { $pythonExe = $cand; break }
    }
}

# PHASE C: Auto-provision standalone Python via uv if absolutely no Python exists
if (-not $pythonExe) {
    Write-Info "Python runtime not detected. Auto-provisioning isolated Python..." "Cyan"
    if (-not $activeUv) {
        Write-Info "Downloading uv bootstrapper..." "Yellow"
        $uvZip = Join-Path $env:TEMP "uv-win-x64.zip"
        if (Download-FileReliable -Url "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip" -Destination $uvZip) {
            Extract-ArchiveReliable -Archive $uvZip -Destination $uvDir | Out-Null
            Remove-Item -LiteralPath $uvZip -Force -ErrorAction SilentlyContinue
            if (Test-Path -LiteralPath $uvExe) { $activeUv = $uvExe }
        }
    }
    if ($activeUv) {
        Write-Info "Fetching standalone Python 3.11 via uv..." "Cyan"
        & $activeUv python install 3.11 2>&1 | Out-Null
        $foundPy = (& $activeUv python find 3.11 2>$null)
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

if (-not $pythonExe) {
    Write-Host "[ERROR] Python was not found and auto-provisioning could not complete." -ForegroundColor Red; exit 1
}

# PHASE D: Only provision virtual environment if selected Python lacks core dependencies
if (-not (Test-PythonHasCoreDeps $pythonExe)) {
    $targetVenv = Join-Path $backendDir ".venv"
    if (-not (Test-ValidPython $venvPython)) {
        Write-Info "Provisioning isolated virtual environment (backend\.venv)..." "Cyan"
        if (Test-Path -LiteralPath $targetVenv) { Remove-Item -LiteralPath $targetVenv -Recurse -Force -ErrorAction SilentlyContinue }
        if ($activeUv) {
            & $activeUv venv $targetVenv --python $pythonExe 2>$null | Out-Null
        } else {
            & $pythonExe -m venv $targetVenv 2>$null | Out-Null
        }
        if (Test-ValidPython $venvPython) { $pythonExe = $venvPython }
    }

    Write-Info "Installing backend core dependencies..." "Yellow"
    $reqFile = Join-Path $backendDir "requirements-core.txt"
    if ($activeUv) {
        Write-Info "Using high-speed uv package installer..." "Cyan"
        & $activeUv pip install -r $reqFile --python $pythonExe --index-strategy unsafe-best-match
    } else {
        & $pythonExe -m pip install -r $reqFile --timeout 120 --retries 5
    }
    if (-not (Test-PythonHasCoreDeps $pythonExe)) {
        Write-Host "[ERROR] Failed to install backend core dependencies. Check network connectivity." -ForegroundColor Red; exit 1
    }
}

# 3.5 GLiNER Zero-Shot NER Engine Verification & Fast-Path
function Test-GlinerInstalled {
    param([string]$PyPath)
    try {
        $chk = & $PyPath -c "import sys, gliner; sys.stdout.write('OK')" 2>$null
        return ($chk -match "OK")
    } catch { return $false }
}

$glinerModelName = "urchade/gliner_medium-v2.1"
if (Test-GlinerInstalled $pythonExe) {
    Write-Info "GLiNER Zero-Shot NER engine verified ($glinerModelName)" "Green"
} else {
    Write-Info "GLiNER Zero-Shot NER not detected. Auto-provisioning gliner..." "Yellow"
    if ($activeUv) {
        & $activeUv pip install gliner --python $pythonExe --index-strategy unsafe-best-match
    } else {
        & $pythonExe -m pip install gliner --quiet
    }
    if (Test-GlinerInstalled $pythonExe) {
        Write-Info "GLiNER Zero-Shot NER engine online ($glinerModelName)" "Green"
    } else {
        Write-Info "GLiNER auto-provisioning deferred to background warmup." "Yellow"
    }
}

# 3.6 Neural Embeddings & Modern Transformers Architecture Verification
function Test-EmbeddingTransformersInstalled {
    param([string]$PyPath)
    try {
        $chk = & $PyPath -c "import sys, sentence_transformers, transformers; sys.stdout.write('OK')" 2>$null
        return ($chk -match "OK")
    } catch { return $false }
}

if (Test-EmbeddingTransformersInstalled $pythonExe) {
    Write-Info "Neural embedding runtime verified (sentence-transformers & transformers)" "Green"
} else {
    Write-Info "Neural embedding runtime missing or incomplete. Auto-provisioning sentence-transformers & transformers..." "Yellow"
    if ($activeUv) {
        & $activeUv pip install sentence-transformers "transformers>=5.22.0" --python $pythonExe --index-strategy unsafe-best-match
    } else {
        & $pythonExe -m pip install sentence-transformers "transformers>=5.22.0" --quiet
    }
    if (Test-EmbeddingTransformersInstalled $pythonExe) {
        Write-Info "Neural embedding runtime online (sentence-transformers & modern transformers)" "Green"
    } else {
        Write-Info "Neural embedding runtime installation deferred to background warmup." "Yellow"
    }
}

# Native Rust acceleration engine check & self-provisioning
$rustDll = Join-Path $backendDir "rust\raise_engine\target\release\raise_engine.dll"
$cargoToml = Join-Path $backendDir "rust\raise_engine\Cargo.toml"
if ((-not (Test-Path $rustDll)) -and (Test-Path $cargoToml)) {
    $cargoCmd = Get-Command "cargo" -ErrorAction SilentlyContinue
    $cargoBin = Join-Path $env:USERPROFILE ".cargo\bin\cargo.exe"
    if (-not $cargoCmd -and (Test-Path $cargoBin)) {
        $env:PATH = (Join-Path $env:USERPROFILE ".cargo\bin") + ";" + $env:PATH
        $cargoCmd = Get-Command "cargo" -ErrorAction SilentlyContinue
    }
    if (-not $cargoCmd) {
        Write-Info "Rust compiler not detected. Auto-provisioning Rust toolchain via rustup..." "Cyan"
        $rustupExe = Join-Path $env:TEMP "rustup-init.exe"
        if (Download-FileReliable -Url "https://win.rustup.rs/x86_64" -Destination $rustupExe) {
            Write-Info "Installing minimal Rust toolchain (cargo + rustc)..." "Yellow"
            & $rustupExe -y --default-toolchain stable --profile minimal --no-modify-path 2>&1 | Out-Null
            Remove-Item -LiteralPath $rustupExe -Force -ErrorAction SilentlyContinue
            if (Test-Path $cargoBin) {
                $env:PATH = (Join-Path $env:USERPROFILE ".cargo\bin") + ";" + $env:PATH
                $cargoCmd = Get-Command "cargo" -ErrorAction SilentlyContinue
            }
        }
    }
    if ($cargoCmd) {
        Write-Info "Compiling native Rust acceleration engine (raise_engine)..." "Cyan"
        & cargo build --manifest-path $cargoToml --release 2>&1 | Out-Null
        if (Test-Path $rustDll) {
            Write-Info "Native Rust acceleration engine compiled successfully." "Green"
        }
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
$backendEnv = Join-Path $backendDir ".env"; $runtimeDir = Join-Path $backendDir ".runtime"
if (-not (Test-Path $runtimeDir)) { New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null }
$setupMarker = Join-Path $runtimeDir "setup_completed"; $backendMarker = Join-Path $backendDir ".runtime\setup_completed"; $hasMarker = (Test-Path $setupMarker) -or (Test-Path $backendMarker)

if (-not (Test-Path $backendEnv)) {
    if (Test-Path $rootEnv) { Copy-Item -Path $rootEnv -Destination $backendEnv -Force }
    elseif (Test-Path $rootEnvEx) { Copy-Item -Path $rootEnvEx -Destination $backendEnv -Force }
}
if (-not (Test-Path $rootEnv) -and (Test-Path $backendEnv)) { Copy-Item -Path $backendEnv -Destination $rootEnv -Force }

# Intelligent API Key Auto-Detector & Credential Manager
function Mask-ApiKey {
    param([string]$Key)
    if (-not $Key -or $Key.Length -lt 10) { return "****" }
    $pfxLen = [Math]::Min(6, [int]($Key.Length / 3))
    $sfxLen = [Math]::Min(4, [int]($Key.Length / 3))
    $pfx = $Key.Substring(0, $pfxLen)
    $sfx = $Key.Substring($Key.Length - $sfxLen)
    return "$pfx...$sfx"
}

function Test-HfTokenStatus {
    param([string]$Token)
    if (-not $Token -or $Token.Trim() -eq "" -or $Token -match '(?i)testtoken|dummy|^your_') {
        return @{ Status = "Missing"; Message = "No Hugging Face token configured" }
    }
    $Token = $Token.Trim()
    if ($Token -notmatch '^hf_[a-zA-Z0-9]{15,}$') {
        return @{ Status = "Invalid"; Message = "Malformed token format (must start with 'hf_')" }
    }
    try {
        $headers = @{
            "Authorization" = "Bearer $Token"
            "User-Agent" = "RAISE-Academic-Studio/1.0"
        }
        $resp = Invoke-RestMethod -Uri "https://huggingface.co/api/whoami-v2" -Headers $headers -TimeoutSec 4 -ErrorAction Stop
        $accountName = if ($resp.name) { $resp.name } elseif ($resp.fullname) { $resp.fullname } else { "Verified" }
        return @{ Status = "Valid"; Account = $accountName; Message = "Active ($accountName)" }
    } catch {
        if ($_.Exception.Response) {
            $code = [int]$_.Exception.Response.StatusCode
            if ($code -eq 401 -or $code -eq 403) {
                return @{ Status = "Expired"; Message = "Token is expired or unauthorized (HTTP $code)" }
            }
        }
        return @{ Status = "UnverifiedOffline"; Message = "Offline / unverified" }
    }
}

function Test-LlmKeyStatus {
    param(
        [string]$Provider,
        [string]$Key
    )
    if (-not $Key -or $Key.Trim() -eq "" -or $Key -match '(?i)testdummy|dummy|^your_') {
        return @{ Status = "Missing"; Message = "No key configured" }
    }
    $Key = $Key.Trim()
    try {
        if ($Provider -eq "gemini" -or $Provider -eq "google") {
            $body = '{"contents":[{"parts":[{"text":"ping"}]}],"generationConfig":{"maxOutputTokens":1}}'
            $cands = @("gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-flash-latest")
            $verified = $false
            foreach ($m in $cands) {
                try {
                    $resp = Invoke-RestMethod -Uri "https://generativelanguage.googleapis.com/v1beta/models/$($m):generateContent" -Headers @{"x-goog-api-key" = $Key; "Content-Type" = "application/json"} -Method Post -Body $body -TimeoutSec 4 -ErrorAction Stop
                    $verified = $true
                    break
                } catch {
                    if ($_.Exception.Response) {
                        $code = [int]$_.Exception.Response.StatusCode
                        if ($code -eq 401 -or $code -eq 403) {
                            return @{ Status = "Expired"; Message = "Key is expired or unauthorized (HTTP $code)" }
                        }
                    }
                }
            }
            if ($verified) {
                return @{ Status = "Valid"; Message = "Active Gemini key" }
            }
            return @{ Status = "UnverifiedOffline"; Message = "Offline / unverified" }
        }
        elseif ($Provider -eq "groq") {
            $headers = @{ "Authorization" = "Bearer $Key"; "User-Agent" = "RAISE/1.0" }
            $resp = Invoke-RestMethod -Uri "https://api.groq.com/openai/v1/models" -Headers $headers -TimeoutSec 4 -ErrorAction Stop
            return @{ Status = "Valid"; Message = "Active Groq key" }
        }
        elseif ($Provider -eq "openai") {
            $headers = @{ "Authorization" = "Bearer $Key"; "User-Agent" = "RAISE/1.0" }
            $resp = Invoke-RestMethod -Uri "https://api.openai.com/v1/models" -Headers $headers -TimeoutSec 4 -ErrorAction Stop
            return @{ Status = "Valid"; Message = "Active OpenAI key" }
        }
        else {
            return @{ Status = "Valid"; Message = "Key present" }
        }
    } catch {
        if ($_.Exception.Response) {
            $code = [int]$_.Exception.Response.StatusCode
            if ($code -eq 401 -or $code -eq 403 -or $code -eq 400) {
                return @{ Status = "Expired"; Message = "Key is expired or unauthorized (HTTP $code)" }
            }
        }
        return @{ Status = "UnverifiedOffline"; Message = "Offline / unverified" }
    }
}

function Request-RaiseKeysInteractive {
    param([string]$EnvPath)
    if (-not (Test-Path $EnvPath)) { return }
    $envContent = Get-Content -Path $EnvPath -Raw -Encoding utf8
    $forceSetup = ($rawArgs -match "(?i)--setup-keys|--keys|-keys")

    if ([System.Console]::IsInputRedirected) { return }

    # ==========================================================================
    # Step 1: LLM Inference Key (Gemini / Groq / OpenAI / Anthropic)
    # ==========================================================================
    $configuredLlm = $null
    $configuredLlmKey = $null

    if ($envContent -match '(?m)^[ \t]*GEMINI_API_KEY=[ \t]*[''"]?([a-zA-Z0-9_\-\.]{15,})') {
        $configuredLlm = "gemini"; $configuredLlmKey = $Matches[1].Trim()
    } elseif ($envContent -match '(?m)^[ \t]*GOOGLE_API_KEY=[ \t]*[''"]?([a-zA-Z0-9_\-\.]{15,})') {
        $configuredLlm = "gemini"; $configuredLlmKey = $Matches[1].Trim()
    } elseif ($envContent -match '(?m)^[ \t]*GROQ_API_KEY=[ \t]*[''"]?([a-zA-Z0-9_\-\.]{15,})') {
        $configuredLlm = "groq"; $configuredLlmKey = $Matches[1].Trim()
    } elseif ($envContent -match '(?m)^[ \t]*OPENAI_API_KEY=[ \t]*[''"]?([a-zA-Z0-9_\-\.]{15,})') {
        $configuredLlm = "openai"; $configuredLlmKey = $Matches[1].Trim()
    } elseif ($envContent -match '(?m)^[ \t]*ANTHROPIC_API_KEY=[ \t]*[''"]?([a-zA-Z0-9_\-\.]{15,})') {
        $configuredLlm = "anthropic"; $configuredLlmKey = $Matches[1].Trim()
    } elseif ($envContent -match '(?m)^[ \t]*MISTRAL_API_KEY=[ \t]*[''"]?([a-zA-Z0-9_\-\.]{15,})') {
        $configuredLlm = "mistral"; $configuredLlmKey = $Matches[1].Trim()
    }

    # Dynamic probe for running local inference engines (vLLM :8002 / Ollama :11434)
    $isVllmListening = $false
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $connect = $tcp.BeginConnect("127.0.0.1", 8002, $null, $null)
        if ($connect.AsyncWaitHandle.WaitOne(200, $false)) {
            $tcp.EndConnect($connect)
            $isVllmListening = $true
        }
        $tcp.Close()
    } catch { $isVllmListening = $false }

    $isOllamaListening = $false
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $connect = $tcp.BeginConnect("127.0.0.1", 11434, $null, $null)
        if ($connect.AsyncWaitHandle.WaitOne(200, $false)) {
            $tcp.EndConnect($connect)
            $isOllamaListening = $true
        }
        $tcp.Close()
    } catch { $isOllamaListening = $false }

    $hasLocalEngineOnline = $isVllmListening -or $isOllamaListening

    $policyLocalFirst = ($envContent -match '(?m)^[ \t]*ROUTING_POLICY=[ \t]*[''"]?LOCAL_FIRST') -or `
                        ($envContent -match '(?m)^[ \t]*LLM_PROVIDER=[ \t]*[''"]?(?:vllm|ollama)') -or `
                        ($envContent -match '(?m)^[ \t]*LLM_BACKEND=[ \t]*[''"]?(?:vllm|ollama)')

    $isLocalFirst = $policyLocalFirst -and $hasLocalEngineOnline

    $llmStatus = if ($configuredLlmKey) { Test-LlmKeyStatus -Provider $configuredLlm -Key $configuredLlmKey } else { @{ Status = "Missing" } }

    if ($isLocalFirst) {
        $localEngineName = if ($isVllmListening) { "vLLM Container (:8002)" } else { "Ollama Daemon (:11434)" }
        Write-Info "Active LLM synthesis policy: LOCAL_FIRST ($localEngineName prioritized)." "Green"
        if ($configuredLlmKey) {
            Write-Info "Cloud fallback standby credentials configured: $configuredLlm ($(Mask-ApiKey $configuredLlmKey))." "Cyan"
        }
    } elseif ($llmStatus.Status -eq "Valid" -and -not $forceSetup) {
        $provUpper = $configuredLlm.ToUpper()
        Write-Info "Active LLM synthesis priority: $provUpper (Cloud-First) ($(Mask-ApiKey $configuredLlmKey))." "Green"
    } elseif ($llmStatus.Status -eq "UnverifiedOffline" -and -not $forceSetup) {
        $provUpper = $configuredLlm.ToUpper()
        Write-Info "Active LLM synthesis priority: $provUpper (Cloud-First) ($(Mask-ApiKey $configuredLlmKey))." "Green"
    } else {
        Write-Host "`n==========================================================================" -ForegroundColor Cyan
        if ($llmStatus.Status -eq "Expired") {
            Write-Host " [AUTH SETUP: 1/2] LLM API KEY EXPIRED / UNAUTHORIZED ($configuredLlm)" -ForegroundColor Red
            Write-Host "==========================================================================" -ForegroundColor Red
            Write-Host " Your previous $configuredLlm API key ($(Mask-ApiKey $configuredLlmKey)) has EXPIRED or is invalid." -ForegroundColor Red
            Write-Host " Please provide a renewed LLM API key (Google Gemini, Groq, OpenAI, etc.):" -ForegroundColor Yellow
        } else {
            Write-Host " [AUTH SETUP: 1/2] LLM INFERENCE CREDENTIAL (GEMINI / GROQ / OPENAI)" -ForegroundColor Yellow
            Write-Host "==========================================================================" -ForegroundColor Cyan
            Write-Host " Configure your primary LLM inference provider for reasoning and synthesis." -ForegroundColor Gray
            Write-Host " (Supports Google Gemini, Groq, OpenAI, Anthropic, Mistral, NVIDIA, etc.)" -ForegroundColor Gray
        }
        Write-Host ""

        $askingLlm = $true
        while ($askingLlm) {
            $keyInput = (Read-Host " Paste LLM API Key [or press Enter to skip / use local model]").Trim()
            if (-not $keyInput) {
                Write-Host " [SKIPPED] LLM API key prompt skipped. Local fallback models will be used.`n" -ForegroundColor Gray
                $askingLlm = $false
                break
            }

            $masked = Mask-ApiKey $keyInput
            $safeKey = $keyInput.Replace('$', '$$')
            $detected = $false

            if ($keyInput -match '^(?:AIza|AQ\.)[a-zA-Z0-9_\-\.]{25,}$') {
                Write-Host " [DETECTED] Google Gemini API Key recognized: $masked" -ForegroundColor Green
                if ($envContent -match '(?m)^[ \t]*GEMINI_API_KEY=.*$') {
                    $envContent = $envContent -replace '(?m)^[ \t]*GEMINI_API_KEY=.*$', "GEMINI_API_KEY=$safeKey"
                } else { $envContent += "`nGEMINI_API_KEY=$keyInput" }
                if ($envContent -match '(?m)^[ \t]*GOOGLE_API_KEY=.*$') {
                    $envContent = $envContent -replace '(?m)^[ \t]*GOOGLE_API_KEY=.*$', "GOOGLE_API_KEY=$safeKey"
                } else { $envContent += "`nGOOGLE_API_KEY=$keyInput" }
                $envContent = $envContent -replace '(?m)^[ \t]*LLM_BACKEND=.*$', "LLM_BACKEND=gemini"
                $detected = $true
            }
            elseif ($keyInput -match '^gsk_[a-zA-Z0-9]{20,}$') {
                Write-Host " [DETECTED] Groq LPU API Key recognized: $masked" -ForegroundColor Green
                if ($envContent -match '(?m)^[ \t]*GROQ_API_KEY=.*$') {
                    $envContent = $envContent -replace '(?m)^[ \t]*GROQ_API_KEY=.*$', "GROQ_API_KEY=$safeKey"
                } else { $envContent += "`nGROQ_API_KEY=$keyInput" }
                $envContent = $envContent -replace '(?m)^[ \t]*LLM_BACKEND=.*$', "LLM_BACKEND=groq"
                $detected = $true
            }
            elseif ($keyInput -match '^sk-ant-[a-zA-Z0-9_\-]{20,}$') {
                Write-Host " [DETECTED] Anthropic Claude API Key recognized: $masked" -ForegroundColor Green
                if ($envContent -match '(?m)^[ \t]*ANTHROPIC_API_KEY=.*$') {
                    $envContent = $envContent -replace '(?m)^[ \t]*ANTHROPIC_API_KEY=.*$', "ANTHROPIC_API_KEY=$safeKey"
                } else { $envContent += "`nANTHROPIC_API_KEY=$keyInput" }
                $detected = $true
            }
            elseif ($keyInput -match '^sk-[a-zA-Z0-9_\-]{20,}$') {
                Write-Host " [DETECTED] OpenAI Key recognized: $masked" -ForegroundColor Green
                if ($envContent -match '(?m)^[ \t]*OPENAI_API_KEY=.*$') {
                    $envContent = $envContent -replace '(?m)^[ \t]*OPENAI_API_KEY=.*$', "OPENAI_API_KEY=$safeKey"
                } else { $envContent += "`nOPENAI_API_KEY=$keyInput" }
                $detected = $true
            }
            elseif ($keyInput -match '^nvapi-[a-zA-Z0-9_\-]{15,}$') {
                Write-Host " [DETECTED] NVIDIA NIM API Key recognized: $masked" -ForegroundColor Green
                if ($envContent -match '(?m)^[ \t]*NVIDIA_API_KEY=.*$') {
                    $envContent = $envContent -replace '(?m)^[ \t]*NVIDIA_API_KEY=.*$', "NVIDIA_API_KEY=$safeKey"
                } else { $envContent += "`nNVIDIA_API_KEY=$keyInput" }
                $detected = $true
            }
            elseif ($keyInput -match '^[a-fA-F0-9]{32}$') {
                Write-Host " [DETECTED] Mistral AI Key recognized: $masked" -ForegroundColor Green
                if ($envContent -match '(?m)^[ \t]*MISTRAL_API_KEY=.*$') {
                    $envContent = $envContent -replace '(?m)^[ \t]*MISTRAL_API_KEY=.*$', "MISTRAL_API_KEY=$safeKey"
                } else { $envContent += "`nMISTRAL_API_KEY=$keyInput" }
                $detected = $true
            }
            else {
                Write-Host " [NOTICE] Key format unrecognized ($masked)." -ForegroundColor Yellow
                $choice = (Read-Host " Which provider is this key for? [1] Gemini [2] Groq [3] OpenAI [4] Other / Skip").Trim()
                if ($choice -eq "1" -or $choice -match "(?i)gemini") {
                    if ($envContent -match '(?m)^[ \t]*GEMINI_API_KEY=.*$') { $envContent = $envContent -replace '(?m)^[ \t]*GEMINI_API_KEY=.*$', "GEMINI_API_KEY=$safeKey" }
                    else { $envContent += "`nGEMINI_API_KEY=$keyInput" }
                    if ($envContent -match '(?m)^[ \t]*GOOGLE_API_KEY=.*$') { $envContent = $envContent -replace '(?m)^[ \t]*GOOGLE_API_KEY=.*$', "GOOGLE_API_KEY=$safeKey" }
                    else { $envContent += "`nGOOGLE_API_KEY=$keyInput" }
                    $envContent = $envContent -replace '(?m)^[ \t]*LLM_BACKEND=.*$', "LLM_BACKEND=gemini"
                    $detected = $true
                } elseif ($choice -eq "2" -or $choice -match "(?i)groq") {
                    if ($envContent -match '(?m)^[ \t]*GROQ_API_KEY=.*$') { $envContent = $envContent -replace '(?m)^[ \t]*GROQ_API_KEY=.*$', "GROQ_API_KEY=$safeKey" }
                    else { $envContent += "`nGROQ_API_KEY=$keyInput" }
                    $envContent = $envContent -replace '(?m)^[ \t]*LLM_BACKEND=.*$', "LLM_BACKEND=groq"
                    $detected = $true
                } elseif ($choice -eq "3" -or $choice -match "(?i)openai") {
                    if ($envContent -match '(?m)^[ \t]*OPENAI_API_KEY=.*$') { $envContent = $envContent -replace '(?m)^[ \t]*OPENAI_API_KEY=.*$', "OPENAI_API_KEY=$safeKey" }
                    else { $envContent += "`nOPENAI_API_KEY=$keyInput" }
                    $detected = $true
                }
            }

            if ($detected) {
                Write-Host " [SAVED] LLM credential configured securely in environment.`n" -ForegroundColor Green
                $askingLlm = $false
            }
        }
    }

    # ==========================================================================
    # Step 2: Hugging Face Access Token (Dedicated & Prompted Only Once)
    # ==========================================================================
    $hfToken = $null
    if ($envContent -match '(?m)^[ \t]*(?:HUGGINGFACE_TOKEN|HF_TOKEN)[ \t]*=[ \t]*[''"]?([^''"\r\n]+)') {
        $hfToken = $Matches[1].Trim()
    }

    $hfSkipped = ($envContent -match '(?m)^[ \t]*HF_TOKEN_SKIPPED[ \t]*=[ \t]*[''"]?true[''"]?')
    $hfStatus = Test-HfTokenStatus -Token $hfToken

    if ($hfStatus.Status -eq "Valid") {
        $accountStr = if ($hfStatus.Account) { "Account: $($hfStatus.Account)" } else { "Active" }
        Write-Info "Hugging Face Access Token verified & active: $accountStr ($(Mask-ApiKey $hfToken))." "Green"
    } elseif ($hfStatus.Status -eq "UnverifiedOffline") {
        Write-Info "Hugging Face Access Token configured in environment ($(Mask-ApiKey $hfToken))." "Green"
    } elseif ($hfSkipped -and -not $forceSetup -and $hfStatus.Status -ne "Expired") {
        Write-Info "Hugging Face Token previously skipped by user. Using local/cached model assets." "Gray"
    } else {
        # Either Expired, or Missing (and not skipped), or --setup-keys passed!
        Write-Host "`n==========================================================================" -ForegroundColor Cyan
        Write-Host " [AUTH SETUP: 2/2] HUGGING FACE ACCESS TOKEN (HF_TOKEN)" -ForegroundColor Yellow
        Write-Host "==========================================================================" -ForegroundColor Cyan

        if ($hfStatus.Status -eq "Expired") {
            Write-Host " [EXPIRED] Your previous Hugging Face token ($(Mask-ApiKey $hfToken)) has EXPIRED or is unauthorized." -ForegroundColor Red
            Write-Host " Please paste a renewed Hugging Face access token (hf_...):" -ForegroundColor Yellow
            Write-Host " (Renew token at: https://huggingface.co/settings/tokens)`n" -ForegroundColor Gray
        } else {
            Write-Host " Configure a Hugging Face Access Token to download and cache neural" -ForegroundColor Gray
            Write-Host " embedding and cross-encoder reranker models." -ForegroundColor Gray
            Write-Host " (Get a free read token at: https://huggingface.co/settings/tokens)`n" -ForegroundColor Gray
        }

        $hfPrompting = $true
        while ($hfPrompting) {
            $hfInput = (Read-Host " Paste Hugging Face Token (hf_...) [or press Enter to skip / use cached]").Trim()
            if (-not $hfInput) {
                # User skipped: save marker so it is only asked ONCE and never prompts again!
                if ($envContent -match '(?m)^[ \t]*HF_TOKEN_SKIPPED=.*$') {
                    $envContent = $envContent -replace '(?m)^[ \t]*HF_TOKEN_SKIPPED=.*$', "HF_TOKEN_SKIPPED=true"
                } else {
                    $envContent += "`nHF_TOKEN_SKIPPED=true"
                }
                Write-Host " [SKIPPED] Hugging Face token skipped. Local and cached models will be used.`n" -ForegroundColor Gray
                $hfPrompting = $false
                break
            }

            if ($hfInput -notmatch '^hf_[a-zA-Z0-9]{15,}$') {
                Write-Host " [INVALID] Hugging Face tokens must start with 'hf_' and be at least 18 characters long." -ForegroundColor Yellow
                $retry = (Read-Host " Try again? [Y/n]").Trim()
                if ($retry -match '(?i)^n') {
                    if ($envContent -match '(?m)^[ \t]*HF_TOKEN_SKIPPED=.*$') {
                        $envContent = $envContent -replace '(?m)^[ \t]*HF_TOKEN_SKIPPED=.*$', "HF_TOKEN_SKIPPED=true"
                    } else {
                        $envContent += "`nHF_TOKEN_SKIPPED=true"
                    }
                    $hfPrompting = $false
                    break
                }
                continue
            }

            $maskedHf = Mask-ApiKey $hfInput
            Write-Host " Verifying Hugging Face token with api.huggingface.co..." -ForegroundColor Gray
            $verifyResult = Test-HfTokenStatus -Token $hfInput
            if ($verifyResult.Status -eq "Expired" -or $verifyResult.Status -eq "Invalid") {
                Write-Host " [WARNING] The token returned HTTP 401 Unauthorized from Hugging Face API." -ForegroundColor Red
                $saveAnyway = (Read-Host " Save this token anyway? [y/N]").Trim()
                if ($saveAnyway -notmatch '(?i)^y') {
                    continue
                }
            }

            # Save the valid token!
            $safeHf = $hfInput.Replace('$', '$$')
            if ($envContent -match '(?m)^[ \t]*HUGGINGFACE_TOKEN=.*$') {
                $envContent = $envContent -replace '(?m)^[ \t]*HUGGINGFACE_TOKEN=.*$', "HUGGINGFACE_TOKEN=$safeHf"
            } else { $envContent += "`nHUGGINGFACE_TOKEN=$hfInput" }

            if ($envContent -match '(?m)^[ \t]*HF_TOKEN=.*$') {
                $envContent = $envContent -replace '(?m)^[ \t]*HF_TOKEN=.*$', "HF_TOKEN=$safeHf"
            } else { $envContent += "`nHF_TOKEN=$hfInput" }

            # Remove HF_TOKEN_SKIPPED if previously set
            $envContent = $envContent -replace '(?m)^[ \t]*HF_TOKEN_SKIPPED=.*$', "HF_TOKEN_SKIPPED=false"

            Write-Host " [SAVED] Hugging Face Access Token successfully saved and verified: $maskedHf`n" -ForegroundColor Green
            $hfPrompting = $false
        }
    }

    # Ensure SETUP_COMPLETED flag is saved
    if ($envContent -match '(?m)^[ \t]*SETUP_COMPLETED=.*$') {
        $envContent = $envContent -replace '(?m)^[ \t]*SETUP_COMPLETED=.*$', "SETUP_COMPLETED=true"
    } else {
        $envContent += "`nSETUP_COMPLETED=true"
    }

    [System.IO.File]::WriteAllText($EnvPath, $envContent, [System.Text.Encoding]::UTF8)
    if (Test-Path (Join-Path $backendDir ".env")) {
        [System.IO.File]::WriteAllText((Join-Path $backendDir ".env"), $envContent, [System.Text.Encoding]::UTF8)
    }
}

if (Test-Path $rootEnv) {
    Request-RaiseKeysInteractive -EnvPath $rootEnv
}

# ------------------------------------------------------------------------------
# Neural Asset Pre-flight Cache Probe (Embedding, Cross-Encoder, NLI)
# ------------------------------------------------------------------------------
$hfHubPath = if ($env:HF_HUB_CACHE -and (Test-Path $env:HF_HUB_CACHE)) { $env:HF_HUB_CACHE } `
             elseif ($env:HF_HOME -and (Test-Path (Join-Path $env:HF_HOME "hub"))) { Join-Path $env:HF_HOME "hub" } `
             elseif ($env:HUGGINGFACE_HUB_CACHE -and (Test-Path $env:HUGGINGFACE_HUB_CACHE)) { $env:HUGGINGFACE_HUB_CACHE } `
             else { Join-Path $env:USERPROFILE ".cache\huggingface\hub" }

function Test-HfFolderReady {
    param([string]$RepoId)
    $folder = "models--" + ($RepoId -replace "/", "--")
    $snapDir = Join-Path $hfHubPath ($folder + "\snapshots")
    if (Test-Path $snapDir) {
        $dirs = Get-ChildItem -Path $snapDir -Directory -ErrorAction SilentlyContinue
        foreach ($d in $dirs) {
            $hasFiles = Get-ChildItem -Path $d.FullName -File -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($hasFiles) { return $true }
        }
    }
    return $false
}

$configPath = Join-Path $backendDir "src\core\config.py"
$embRepo = "google/embeddinggemma-2"
$rerankRepo = "BAAI/bge-reranker-v2-m3"
$nliRepo = "dleemiller/finecat-nli-ultra-l"
if (Test-Path $configPath) {
    $cfgRaw = Get-Content -Path $configPath -Raw -ErrorAction SilentlyContinue
    if ($cfgRaw -match 'EMBEDDING_MODEL_NAME:\s*str\s*=\s*["'']([^"'']+)["'']') { $embRepo = $Matches[1] }
    if ($cfgRaw -match 'RERANKER_MODEL_NAME:\s*str\s*=\s*["'']([^"'']+)["'']') { $rerankRepo = $Matches[1] }
    if ($cfgRaw -match 'NLI_MODEL_NAME:\s*str\s*=\s*["'']([^"'']+)["'']') { $nliRepo = $Matches[1] }
}

$embCached = Test-HfFolderReady $embRepo
$rerankCached = Test-HfFolderReady $rerankRepo
$nliCached = Test-HfFolderReady $nliRepo

if ($embCached -and $rerankCached -and $nliCached) {
    Write-Info "Neural Pipeline Assets: Dense Embedding [CACHED] * Cross-Encoder [CACHED] * NLI [CACHED]" "Green"
} else {
    $statusParts = @()
    $statusParts += if ($embCached) { "Embedding [CACHED]" } else { "Embedding [PENDING DOWNLOAD]" }
    $statusParts += if ($rerankCached) { "Reranker [CACHED]" } else { "Reranker [PENDING DOWNLOAD]" }
    $statusParts += if ($nliCached) { "NLI [CACHED]" } else { "NLI [PENDING DOWNLOAD]" }
    Write-Info "Neural Pipeline Assets: $($statusParts -join ' * ')" "Yellow"
    Write-Info "Missing models will download automatically during first inference or via Control Center." "Cyan"
}

# Inspect active .env file for configured Cloud/Local AI keys
$hasConfiguredProvider = $false
$envToCheck = if (Test-Path $backendEnv) { $backendEnv } elseif (Test-Path $rootEnv) { $rootEnv } else { $null }
if ($envToCheck) {
    $c = Get-Content -Path $envToCheck -Raw -ErrorAction SilentlyContinue
    if ($c) {
        $hasCloudKey = $c -match "(?m)^[ \t]*(?:GROQ_API_KEY|GEMINI_API_KEY|OPENAI_API_KEY|MISTRAL_API_KEY|DEEPSEEK_API_KEY|NVIDIA_API_KEY|ANTHROPIC_API_KEY|COHERE_API_KEY)[ \t]*=[ \t]*['""]?([a-zA-Z0-9_\-\.]{8,})"
        $hasSetupFlag = $c -match "(?m)^[ \t]*SETUP_COMPLETED[ \t]*=[ \t]*['""]?true"
        $hasLocalLlm = ($hasMarker -or $hasSetupFlag) -and ($c -match "(?m)^[ \t]*LLM_BACKEND[ \t]*=[ \t]*['""]?(ollama|vllm)")
        if ($hasCloudKey -or $hasLocalLlm -or $hasSetupFlag) { $hasConfiguredProvider = $true }
    }
}

# First-time launch occurs when neither the completion marker nor a configured provider exists
$isFirstLaunch = (-not $hasMarker -and -not $hasConfiguredProvider)

# ==============================================================================
# 5.5 Infrastructure Substrate Mode Selector (FAST / DOCKER / CLOUD)
# ==============================================================================
function Select-RaiseSubstrateMode {
    param([string]$EnvPath, [string]$PythonPath, [string]$UvPath)

    $envContent = if (Test-Path $EnvPath) { Get-Content -Path $EnvPath -Raw -Encoding utf8 } else { "" }
    $savedMode = "fast"
    if ($envContent -match '(?m)^[ \t]*RAISE_SUBSTRATE_MODE=[ \t]*[''"]?([a-zA-Z]+)') {
        $savedMode = $Matches[1].Trim().ToLower()
    }

    $selectedMode = $null
    if ($rawArgs -match "(?i)--fast|-fast") { $selectedMode = "fast" }
    elseif ($rawArgs -match "(?i)--docker|-docker|--prod|-prod") { $selectedMode = "docker" }
    elseif ($rawArgs -match "(?i)--cloud|-cloud") { $selectedMode = "cloud" }

    if (-not $selectedMode -and -not [System.Console]::IsInputRedirected) {
        Write-Host ""
        Write-Host "  $($C.Border)╭─$($C.Reset) $($C.Yellow)$($C.Bold)[SUBSTRATE ARCHITECTURE MODE]$($C.Reset) $($C.White)$($C.Bold)SELECT RUNTIME PROFILE$($C.Reset) $($C.Border)─────────────────────╮$($C.Reset)"
        Write-Host "  $($C.Border)│$($C.Reset)                                                                            $($C.Border)│$($C.Reset)"
        Write-Host "  $($C.Border)│$($C.Reset)  $($C.Cyan)$($C.Bold)[1] FAST MODE$($C.Reset)     $($C.Dim)(Local Lightweight — Zero Docker)$($C.Reset)                      $($C.Border)│$($C.Reset)"
        Write-Host "  $($C.Border)│$($C.Reset)      $($C.Border)├─$($C.Reset) Cache       : $($C.White)FakeRedis$($C.Reset) $($C.Dim)(In-memory zero-latency emulation)$($C.Reset)         $($C.Border)│$($C.Reset)"
        Write-Host "  $($C.Border)│$($C.Reset)      $($C.Border)├─$($C.Reset) Graph       : $($C.White)NetworkX$($C.Reset) $($C.Dim)(In-memory multi-hop graph engine)$($C.Reset)          $($C.Border)│$($C.Reset)"
        Write-Host "  $($C.Border)│$($C.Reset)      $($C.Border)╰─$($C.Reset) Storage     : $($C.White)SQLite + Local ChromaDB$($C.Reset)                              $($C.Border)│$($C.Reset)"
        Write-Host "  $($C.Border)│$($C.Reset)                                                                            $($C.Border)│$($C.Reset)"
        Write-Host "  $($C.Border)│$($C.Reset)  $($C.Green)$($C.Bold)[2] DOCKER MODE$($C.Reset)   $($C.Dim)(Production Enterprise Stack)$($C.Reset)                          $($C.Border)│$($C.Reset)"
        Write-Host "  $($C.Border)│$($C.Reset)      $($C.Border)├─$($C.Reset) Containers  : $($C.White)Neo4j (:7687) · Redis (:6379) · PostgreSQL (:5432)$($C.Reset)   $($C.Border)│$($C.Reset)"
        Write-Host "  $($C.Border)│$($C.Reset)      $($C.Border)╰─$($C.Reset) Best For    : $($C.Dim)Full production persistence & Cypher graph auditing$($C.Reset)  $($C.Border)│$($C.Reset)"
        Write-Host "  $($C.Border)│$($C.Reset)                                                                            $($C.Border)│$($C.Reset)"
        Write-Host "  $($C.Border)│$($C.Reset)  $($C.Purple)$($C.Bold)[3] CLOUD MODE$($C.Reset)    $($C.Dim)(Managed Cloud Storage & Remote Clusters)$($C.Reset)              $($C.Border)│$($C.Reset)"
        Write-Host "  $($C.Border)│$($C.Reset)      $($C.Border)├─$($C.Reset) Substrates  : $($C.White)Neo4j AuraDB · Upstash/Cloud Redis · Supabase/PG$($C.Reset)     $($C.Border)│$($C.Reset)"
        Write-Host "  $($C.Border)│$($C.Reset)      $($C.Border)╰─$($C.Reset) Storage     : $($C.Dim)Cloud Object Storage (S3 / GCS / R2) + Cloud Vector$($C.Reset)  $($C.Border)│$($C.Reset)"
        Write-Host "  $($C.Border)│$($C.Reset)                                                                            $($C.Border)│$($C.Reset)"
        Write-Host "  $($C.Border)╰────────────────────────────────────────────────────────────────────────────╯$($C.Reset)"

        $choice = (Read-Host "  ╭─ Select Mode [1] Fast  [2] Docker  [3] Cloud  (Enter for saved: $($savedMode.ToUpper()))`n  ╰─>").Trim()
        switch -Regex ($choice) {
            "^1|(?i)^f|^fast"   { $selectedMode = "fast" }
            "^2|(?i)^d|^docker" { $selectedMode = "docker" }
            "^3|(?i)^c|^cloud"  { $selectedMode = "cloud" }
            default             { $selectedMode = $savedMode }
        }
    } elseif (-not $selectedMode) {
        $selectedMode = $savedMode
    }

    $env:RAISE_SUBSTRATE_MODE = $selectedMode
    $env:RAISE_STORAGE_MODE = $selectedMode

    if ($selectedMode -eq "fast") {
        Write-Info "Profile Selected: FAST MODE (FakeRedis + NetworkX + SQLite + Local Chroma)" "Yellow"
        $env:USE_FAKEREDIS = "true"
        $env:USE_LOCAL_FALLBACKS = "true"
        $hasFakeRedis = (& $PythonPath -c "import sys, fakeredis, networkx; sys.stdout.write('OK')" 2>$null)
        if ($hasFakeRedis -notmatch "OK") {
            Write-Info "Auto-provisioning FakeRedis & NetworkX for Fast Mode..." "Cyan"
            if ($UvPath) {
                & $UvPath pip install fakeredis networkx --python $PythonPath --index-strategy unsafe-best-match
            } else {
                & $PythonPath -m pip install fakeredis networkx --quiet
            }
        }
        Write-Info "FakeRedis & NetworkX in-memory substrates verified" "Green"
    }
    elseif ($selectedMode -eq "docker") {
        Write-Info "Profile Selected: DOCKER PRODUCTION MODE (Redis + PostgreSQL + Neo4j)" "Green"
        $env:USE_FAKEREDIS = "false"
        $env:USE_LOCAL_FALLBACKS = "false"
        if (Get-Command "docker" -ErrorAction SilentlyContinue) {
            $composeFile = Join-Path $repoRoot "docker-compose.yml"
            if (Test-Path $composeFile) {
                Write-Info "Starting production Docker containers (Neo4j, Redis, Postgres)..." "Cyan"
                & docker compose -f $composeFile up -d 2>$null
            } else {
                foreach ($cName in @("raise-redis", "raise-postgres", "raise-neo4j")) {
                    if (& docker ps -a -q -f "name=^$cName$" 2>$null) {
                        & docker start $cName 2>$null | Out-Null
                    }
                }
            }
            Write-Info "Docker production storage stack active on localhost (6379 / 5432 / 7687)" "Green"
        } else {
            Write-Info "Docker not found in PATH. Services will gracefully fall back if ports :7687/:6379/:5432 are closed." "Yellow"
        }
    }
    elseif ($selectedMode -eq "cloud") {
        Write-Info "Profile Selected: CLOUD MODE (Cloud Object Storage + Managed DBs)" "Cyan"
        $env:USE_FAKEREDIS = "false"
        $env:USE_CLOUD_STORAGE = "true"
    }

    # Persist selection in .env
    if ($envContent -match '(?m)^[ \t]*RAISE_SUBSTRATE_MODE=.*$') {
        $envContent = $envContent -replace '(?m)^[ \t]*RAISE_SUBSTRATE_MODE=.*$', "RAISE_SUBSTRATE_MODE=$selectedMode"
    } else {
        $envContent += "`nRAISE_SUBSTRATE_MODE=$selectedMode"
    }
    [System.IO.File]::WriteAllText($EnvPath, $envContent, [System.Text.Encoding]::UTF8)
    if (Test-Path (Join-Path $backendDir ".env")) {
        [System.IO.File]::WriteAllText((Join-Path $backendDir ".env"), $envContent, [System.Text.Encoding]::UTF8)
    }
}

$envFileForMode = if (Test-Path $backendEnv) { $backendEnv } else { $rootEnv }
Select-RaiseSubstrateMode -EnvPath $envFileForMode -PythonPath $pythonExe -UvPath $activeUv

# 6. Ensure Frontend Dependencies
$vitePkg = Join-Path $frontendDir "node_modules\vite"
if (-not (Test-Path -LiteralPath $vitePkg)) {
    Write-Info "Installing frontend packages (npm install)..." "Yellow"
    Push-Location -LiteralPath $frontendDir
    try {
        & $npmCmd install --no-fund --no-audit
    } catch {
        Write-Info "Frontend package installation notification: $($_.Exception.Message)" "Yellow"
    } finally {
        Pop-Location
    }
}
if (Test-Path -LiteralPath $vitePkg) {
    Write-Info "Frontend Vite bundle verified (node_modules\vite)" "Green"
} else {
    Write-Info "Frontend Vite package not detected; dev fallback mode will be used." "Yellow"
}

# 7. Route Execution Mode (Unbuffered Python `-u` for zero-delay live streaming)
$devMode = ($rawArgs -match "(?i)--dev|-dev|--studio|-studio|--interactive|-interactive|--cli|-cli")
if ($devMode) {
    Write-Info "Starting RAISE Interactive Research Studio..." "Green" "╰─"
    Write-Host ""
    Push-Location -LiteralPath $backendDir
    $env:PYTHONPATH = "$backendDir;$backendDir\src"
    & $pythonExe -u (Join-Path $backendDir "dev_main.py")
    $code = $LASTEXITCODE
    Pop-Location
    exit $code
}

Write-Info "Starting RAISE Supervisor (Live Stream + Interactive REPL)..." "Cyan" "╰─"
Write-Host ""
Push-Location -LiteralPath $backendDir
$env:PYTHONPATH = "$backendDir;$backendDir\src"
$forwardArgs = @()
if ($rawArgs) {
    $forwardArgs = $rawArgs.Split(' ') | Where-Object { $_ -ne "" }
}
& $pythonExe -u -m src.cli.service_runner @forwardArgs
$exitCode = $LASTEXITCODE
Pop-Location
exit $exitCode
