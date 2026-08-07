@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Hecos - Restart Tray Icon
color 0B

echo.
echo  [*] Restoring system tray icon...
echo.

:: Detect PythonW
set PYTHONW_CMD=
set ROOT_DIR=..\Hecos
if exist "C:\Hecos" set ROOT_DIR=C:\Hecos

if exist "%ROOT_DIR%\python_env\pythonw.exe" (
    set PYTHONW_CMD="%ROOT_DIR%\python_env\pythonw.exe"
) else if exist "%ROOT_DIR%\venv\Scripts\pythonw.exe" (
    set PYTHONW_CMD="%ROOT_DIR%\venv\Scripts\pythonw.exe"
) else (
    python --version >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        set PYTHONW_CMD=pythonw
    )
)

if "!PYTHONW_CMD!"=="" (
    color 0C
    echo [!] ERROR: Python is not installed or not found.
    echo.
    echo Hecos Tray requires Python to run.
    echo Please run HECOS_SETUP_WIZARD.bat to install the portable Python environment.
    echo.
    pause
    exit
)

:: Run the tray app in detached mode
start "" !PYTHONW_CMD! -m tray.tray_app

echo  [+] Command sent. The icon will appear in the system tray.
echo  [!] This window will close in 2 seconds...
echo.
timeout /t 2 >nul
exit
