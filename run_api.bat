@echo off
rem ════════════════════════════════════════════════════════════════════════
rem  run_api.bat – Start the GEX Data API server
rem  • Uses local .venv\Scripts\python.exe
rem  • Starts FastAPI server on http://localhost:8000
rem  • Access docs at http://localhost:8000/docs
rem ════════════════════════════════════════════════════════════════════════

setlocal

:: 1) Full path to the venv's interpreter
set "PY=%~dp0.venv\Scripts\python.exe"

:: 2) Abort if venv not found
if not exist "%PY%" (
    echo ❌ Could not find %PY%
    echo Please ensure your Python virtual environment is set up
    pause
    exit /b 1
)

:: 3) Start the API server
echo 🚀 Starting GEX Data API server...
echo 📡 API will be available at: http://localhost:8000
echo 📚 Documentation available at: http://localhost:8000/docs
echo 💾 Data source: raw_levels_with_spot\
echo.
echo Press Ctrl+C to stop the server
echo.

"%PY%" -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload

endlocal

