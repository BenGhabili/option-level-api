@echo off
rem ════════════════════════════════════════════════════════════════════════
rem  run_batch_multi.bat – run option_async_multi.py for SPY, QQQ, SPX
rem  • Uses local .venv\Scripts\python.exe
rem  • Adds today’s date (YYYYMMDD) as --expiry
rem  • Logs output to gex_log.txt
rem ════════════════════════════════════════════════════════════════════════

setlocal enabledelayedexpansion

:: 1) Full path to the venv’s interpreter (relative to this file)
set "PY=%~dp0.venv\Scripts\python.exe"

:: Force console to UTF-8
chcp 65001 > nul
set "PYTHONIOENCODING=utf-8"

:: 2) Abort if venv not found
if not exist "%PY%" (
    echo ❌  Could not find %PY%
    pause
    exit /b 1
)

:: 3) Today’s date → YYYYMMDD
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%i"

:: 4) Run multi‑ticker collector (SPY, QQQ, SPX inside the script)
"%PY%" "%~dp0scripts\option_async_multi.py" ^
        --expiry=!TODAY! ^
        --data=1 ^
        --up_level=7 ^
        --down_level=7 ^
        --spx_step=10 ^
        --csv=Y ^
        --gex=Y ^
        --quiet >> "%~dp0gex_log.txt" 2>&1

endlocal


