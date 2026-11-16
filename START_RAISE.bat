@echo off
chcp 65001 >nul
title RAISE - Research Assessment Intelligence & Semantic Extraction
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

set "BAT_FILE=%~f0"
set "BAT_DIR=%~dp0"
set "RAISE_RUN_ARGS=%*"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
set "FORCE_COLOR=1"
set "NO_COLOR="
set "TERM="
set "HF_HUB_DISABLE_PROGRESS_BARS=1"
set "TQDM_DISABLE=1"
set "TRANSFORMERS_VERBOSITY=error"
set "TOKENIZERS_PARALLELISM=false"

:: Primary helper location inside modular connector/ directory
set "PS_HELPER=%~dp0connector\helper.ps1"
if not exist "%PS_HELPER%" set "PS_HELPER=%~dp0connector\runner.ps1"
if not exist "%PS_HELPER%" set "PS_HELPER=%~dp0start_helper.ps1"
if not exist "%PS_HELPER%" set "PS_HELPER=%~dp0START_RAISE.ps1"

if not exist "%PS_HELPER%" (
    echo.
    echo  ======================================================================
    echo   [ERROR] RAISE launcher helper script not found!
    echo  ======================================================================
    echo   Expected location: %~dp0connector\helper.ps1
    echo   Please check your clone integrity and ensure the connector/ directory exists.
    echo.
    pause
    exit /b 1
)

:: Execute the PowerShell bootstrapper with execution policy bypass
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS_HELPER%" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo  ======================================================================
    echo   [!] RAISE launcher exited with error code %EXIT_CODE%.
    echo  ======================================================================
    echo   Press any key to close this terminal...
    pause >nul
)
endlocal
exit /b %EXIT_CODE%
