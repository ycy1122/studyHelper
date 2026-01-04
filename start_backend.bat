@echo off
echo ========================================
echo Starting Backend Server
echo ========================================
echo.

cd /d "%~dp0backend"

echo [1/2] Checking dependencies...
py -c "import fastapi" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    py -m pip install -r requirements.txt
)

echo.
echo [2/2] Starting backend service...
echo Backend URL: http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop
echo ========================================
echo.

py main.py

pause
