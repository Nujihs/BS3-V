@echo off
chcp 65001 >nul
title Jianpu Converter - Installation

echo ========================================
echo   Jianpu to BD Converter - Installation
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python not found, please install Python first
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python is installed
python --version
echo.

REM Create virtual environment (optional)
set /p CREATE_VENV="Create virtual environment? (Y/N): "
if /i "%CREATE_VENV%"=="Y" (
    echo.
    echo Creating virtual environment...
    python -m venv venv
    echo Virtual environment created
    echo.
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo.
echo Installing dependencies...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo Installation failed!
    echo Please check network or try using mirror:
    echo pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo To run:
echo 1. Double-click start.bat
echo.
echo Visit: http://127.0.0.1:5000
echo.

pause
