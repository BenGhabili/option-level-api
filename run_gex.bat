@echo off
rem ════════════════════════════════════════════════════════════════════════
rem  run_gex.bat  –  grab SPY GEX snapshot
rem  • Uses the local .venv\Scripts\python.exe  (no global Python needed)
rem  • Adds today’s date (YYYYMMDD) as --expiry
rem  • Logs output to gex_log.txt
rem ════════════════════════════════════════════════════════════════════════

:: 1) Full path to the venv’s interpreter (relative to *this* batch file)
set "PY=%~dp0.venv\Scripts\python.exe"

:: Force the console to UTF-8 and make Python inherit it
**chcp 65001 > nul
set "PYTHONIOENCODING=utf-8"**

:: 2) Abort if the venv isn’t where we expect
if not exist "%PY%" (
    echo ❌  Could not find %PY%
    pause
    exit /b 1
)

:: 3) Today’s date → YYYYMMDD
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%i"

:: 4)  QQQ ─────────────────────────────────────────────────────────────
"%PY%" "%~dp0scripts\option_async.py" ^
        --expiry=%TODAY% --ticker=QQQ --csv=Y --gex=Y --quiet ^
        >> "%~dp0gex_log.txt" 2>&1
        
:: 5)  wait 20 seconds before the next ticker ──────────────────────────
timeout /t 20 /nobreak > nul      rem ← exact 20-second gap

:: 6) Run the script
"%PY%" "%~dp0scripts\option_async.py" ^
        --expiry=%TODAY% ^
        --ticker=SPY ^
        --csv=Y ^
        --gex=Y ^
        --quiet  >> "%~dp0gex_log.txt" 2>&1

