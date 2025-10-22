@echo off
title R6 Siege Tracker - Launcher
color 0A
cls

echo ============================================================
echo    R6 SIEGE TRACKER - AUTO LAUNCHER
echo ============================================================
echo.
echo Checking Python installation...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo.
    echo Please install Python from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

echo [OK] Python found!
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
    echo [OK] Virtual environment created!
    echo.
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

REM Check and install requirements
echo.
echo ============================================================
echo    CHECKING DEPENDENCIES
echo ============================================================
echo.

if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found!
    echo.
    pause
    exit /b 1
)

echo [INFO] Checking/Installing Python packages...
echo This may take a few minutes on first run...
echo.

pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to install dependencies!
    echo.
    pause
    exit /b 1
)

echo.
echo [OK] All dependencies installed!
echo.

REM Check if config.txt exists
if not exist "config.txt" (
    echo.
    echo ============================================================
    echo    WARNING: config.txt not found!
    echo ============================================================
    echo.
    echo The server will help you create it on first run.
    echo.
    timeout /t 3 >nul
)

REM Start the Flask server
echo.
echo ============================================================
echo    STARTING R6 TRACKER SERVER
echo ============================================================
echo.
echo Server will start automatically...
echo Browser will open in 2 seconds...
echo.
echo Keep this window open to see logs!
echo Press CTRL+C to stop the server.
echo.
echo ============================================================
echo.

REM Start server
python app.py

REM If server exits, pause to see any errors
echo.
echo.
echo ============================================================
echo    SERVER STOPPED
echo ============================================================
echo.
pause
