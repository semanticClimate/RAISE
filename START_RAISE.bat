@echo off
chcp 65001 >nul
title RAISE
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

:: Auto-launch in Windows Terminal if available and running in standalone console
if "%TERM_PROGRAM%"=="" if "%CI%"=="" if not defined WT_SESSION if not "%~1"=="--no-wt" (
    where wt.exe >nul 2>nul && (
        start wt.exe -d "%~dp0" cmd.exe /k ""%~f0" --no-wt %*"
        exit /b 0
    )
)

set "BAT_FILE=%~f0"
set "BAT_DIR=%~dp0"
set "RAISE_RUN_ARGS=%*"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
set "FORCE_COLOR=1"
set "TERM="
set "HF_HUB_DISABLE_PROGRESS_BARS=1"
set "TQDM_DISABLE=1"
set "TRANSFORMERS_VERBOSITY=error"
set "TOKENIZERS_PARALLELISM=false"

if not exist "%~dp0START_RAISE.ps1" (
    echo.
    echo  [ERROR] START_RAISE.ps1 not found in: %~dp0
    echo  Please ensure START_RAISE.ps1 is present in the repository root.
    echo.
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0START_RAISE.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo  [!] Process exited with code %EXIT_CODE%.
    echo  [!] Press any key to close this window...
    pause >nul
)
endlocal
exit /b %EXIT_CODE%
