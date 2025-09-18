@echo off
rem ========================================================================
rem  run_gex_complete.bat - Complete GEX Pipeline with Optimized Parameters
rem  Fetches latest option data via option_async_multi.py
rem  Derives metrics via derive_gex_metrics.py --latest
rem  Generates regimes via rolling_gex_regimes.py --latest (optimized params)
rem  Minimized logging + log rotation for scheduled tasks
rem ========================================================================

setlocal enabledelayedexpansion

rem 1) Full path to the venv's interpreter
set "PY=%~dp0.venv\Scripts\python.exe"

rem 2) Abort if venv not found
if not exist "%PY%" (
    echo %date% %time% ERROR: Could not find %PY% >> gex_log.txt
    exit /b 1
)

rem 3) Log rotation - archive if gex_log.txt > 10MB
if exist "gex_log.txt" (
    for %%F in ("gex_log.txt") do (
        if %%~zF gtr 10485760 (
            move "gex_log.txt" "gex_log_old.txt" 2>nul
            echo %date% %time% INFO: Rotated gex_log.txt to gex_log_old.txt >> gex_log.txt
        )
    )
)

rem 4) Log start
echo %date% %time% INFO: Starting complete GEX pipeline >> gex_log.txt

rem 5) Step 1: Fetch latest option data
rem Get today's date in YYYYMMDD format
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%i"
echo %date% %time% INFO: Step 1 - Fetching option data for %TODAY% >> gex_log.txt
"%PY%" -u ./scripts/option_async_multi.py --expiry=%TODAY% --data=1 --up_level=7 --down_level=7 --spx_step=10 --csv=Y --gex=Y --quiet 2>>gex_log.txt
if errorlevel 1 (
    echo %date% %time% ERROR: option_async_multi.py failed >> gex_log.txt
    exit /b 1
) else (
    echo %date% %time% SUCCESS: Option data fetched >> gex_log.txt
)

rem 6) Step 2: Derive GEX metrics (incremental with --latest, per ticker)
echo %date% %time% INFO: Step 2 - Deriving GEX metrics for SPY/QQQ/SPX >> gex_log.txt
for %%S in (SPY QQQ SPX) do (
    echo %date% %time% INFO: Deriving metrics for %%S %TODAY% >> gex_log.txt
    "%PY%" -u ./scripts/derive_gex_metrics.py --ticker=%%S --date=%TODAY% --spx_step=10 --csv=Y --latest=Y --quiet 2>>gex_log.txt
    if errorlevel 1 (
        echo %date% %time% ERROR: derive_gex_metrics.py failed for %%S %TODAY% >> gex_log.txt
        exit /b 1
    ) else (
        echo %date% %time% SUCCESS: Metrics derived for %%S %TODAY% >> gex_log.txt
    )
)

rem 7) Step 3: Generate regimes with OPTIMIZED parameters (incremental with --latest, per ticker)
echo %date% %time% INFO: Step 3 - Generating regimes for SPY/QQQ/SPX >> gex_log.txt
for %%S in (SPY QQQ SPX) do (
    echo %date% %time% INFO: Generating regimes for %%S %TODAY% >> gex_log.txt
    "%PY%" -u ./scripts/rolling_gex_regimes.py --ticker=%%S --date=%TODAY% --csv=Y --latest=Y --compression_max=60.0 --ramp_max=25.0 --expansion_score_max=40.0 --expansion_ramp_max=75.0 --compression_enter=0.65 --compression_exit=0.58 --zgamma_min_drift=0.1 --flip_strike_dist=0.75 --quiet 2>>gex_log.txt
    if errorlevel 1 (
        echo %date% %time% ERROR: rolling_gex_regimes.py failed for %%S %TODAY% >> gex_log.txt
        exit /b 1
    ) else (
        echo %date% %time% SUCCESS: Regimes generated for %%S %TODAY% >> gex_log.txt
    )
)

rem 8) Log completion
echo %date% %time% INFO: Complete GEX pipeline finished successfully >> gex_log.txt

endlocal