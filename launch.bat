@echo off
REM Launch script for Laptop Recommendation System
REM Starts FastAPI (uvicorn) and HTTP server in parallel

echo.
echo ========================================
echo Laptop Recommendation System - LAUNCH
echo ========================================
echo.
echo ✅ Starting FastAPI server (port 8000)...
echo ✅ Starting HTTP server (port 3000)...
echo.

REM Start uvicorn in one window
start "FastAPI Server" cmd /k "cd /d "%~dp0" && uvicorn app:app --reload --host 0.0.0.0 --port 8000"

REM Wait a moment for FastAPI to start
timeout /t 2 /nobreak

REM Start HTTP server in another window
start "HTTP Server" cmd /k "cd /d "%~dp0" && python -m http.server 3000"

echo.
echo ========================================
echo Servers launching...
echo ========================================
echo.
echo 📡 FastAPI API: http://localhost:8000
echo 📡 API Docs: http://localhost:8000/docs
echo 📡 HTTP Server: http://localhost:3000
echo.
echo ⏸️  Press Ctrl+C in each window to stop servers
echo.
pause
