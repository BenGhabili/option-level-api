@echo off
rem ════════════════════════════════════════════════════════════════════════
rem  run_oi.bat  –  grab SPY OI snapshot
rem  • Uses the local .venv\Scripts\python.exe  (no global Python needed)
rem  • Adds today’s date (YYYYMMDD) as --expiry
rem  • Logs output to oi_log.txt
rem ════════════════════════════════════════════════════════════════════════

@echo off
chcp 65001 > nul
set "PYTHONIOENCODING=utf-8"
set "PY=%~dp0.venv\Scripts\python.exe"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%i"

rem ─── Pick up command-line args or fall back to defaults ────────────────
set "TICKER=%~1"
if "%TICKER%"=="" set "TICKER=SPY"

"%PY%" "%~dp0scripts\option_async.py" ^
      --expiry=%TODAY% ^
      --ticker=%TICKER% ^
      --csv=N ^
      --gex=N ^
      --up_level=5 --down_level=5 ^
      --quiet >> "%~dp0oi_log.txt" 2>&1
      
timeout /t 20 /nobreak > nul      rem ← exact 20-second gap

"%PY%" "%~dp0scripts\option_async.py" ^
      --expiry=%TODAY% ^
      --ticker=%TICKER% ^
      --csv=Y ^
      --gex=N ^
      --up_level=10 --down_level=10 ^
      --quiet >> "%~dp0oi_log.txt" 2>&1      

