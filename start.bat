@echo off
chcp 65001 >nul
title Jianpu Converter

echo ========================================
echo   Jianpu Converter System
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python not found, please install Python first
    pause
    exit /b 1
)

echo Starting server...
echo Visit: http://127.0.0.1:5000
echo Press Ctrl+C to stop
echo.

python backend\app.py

if %errorlevel% neq 0 (
    echo.
    echo Startup failed! Please check:
    echo 1. Install dependencies: pip install -r requirements.txt
    echo 2. Check if port 5000 is available
    echo.
)

pause
