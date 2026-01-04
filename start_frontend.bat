@echo off
setlocal enabledelayedexpansion
echo ========================================
echo Starting Frontend Server
echo ========================================
echo.

cd /d "%~dp0web"

echo Current directory: %CD%
echo Files in directory:
dir /b
echo.

echo Getting local IP address...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    set LOCAL_IP=%%a
    set LOCAL_IP=!LOCAL_IP:~1!
    goto :found_ip
)
:found_ip

echo.
echo Starting HTTP server (accessible from network)...
echo ========================================
echo Local access: http://localhost:3001/index.html
if defined LOCAL_IP (
    echo Network access: http://!LOCAL_IP!:3001/index.html
) else (
    echo Network access: http://192.168.4.1:3001/index.html
)
echo.
echo Make sure your phone is on the same WiFi network!
echo Press Ctrl+C to stop
echo ========================================
echo.

py -m http.server 3001 --bind 0.0.0.0
if errorlevel 1 (
    echo.
    echo ERROR: Failed to start server
    echo Please check if Python is installed
)

pause
