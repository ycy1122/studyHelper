@echo off
echo ========================================
echo Starting Auto Process Service
echo ========================================
echo.
echo This will automatically process new questions every 5 minutes.
echo Press Ctrl+C to stop.
echo.
echo ========================================
echo.

cd /d "%~dp0"
python auto_process.py

pause
