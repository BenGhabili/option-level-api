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

:: 3)  Ratios ─────────────────────────────────────────────────────────────
"%PY%" "%~dp0scripts\\asset_price_fetch.py" >> "%~dp0ratios_log.txt" 2>&1
        