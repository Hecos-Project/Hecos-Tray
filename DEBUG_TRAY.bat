@echo off
setlocal enabledelayedexpansion
title Debug Hecos Tray
cd /d "%~dp0"

echo [*] Working directory: %CD%
echo.

:: Detect Python using the exact same logic as HECOS_TRAY_SETUP.bat
set "ROOT_DIR=C:\Hecos"

:: Priority 1: Tray's own portable python_env (if it has one)
set "THIS_DIR=%~dp0"
if "%THIS_DIR:~-1%"=="\" set "THIS_DIR=%THIS_DIR:~0,-1%"
if exist "%THIS_DIR%\python_env\python.exe" (
    set PY_CMD="%THIS_DIR%\python_env\python.exe"
    goto PYTHON_FOUND
)

:: Priority 2: py launcher (system Python — the correct one for the Tray)
py -3 --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PY_CMD=py -3"
    goto PYTHON_FOUND
)

:: Priority 3: python3
python3 --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PY_CMD=python3"
    goto PYTHON_FOUND
)

:: Priority 4: python
python --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PY_CMD=python"
    goto PYTHON_FOUND
)

echo [!] Could not find Python.
pause
exit

:PYTHON_FOUND
echo [*] Python: %PY_CMD%
echo.

set PYTHONPATH=%~dp0

echo [*] Launching Tray in Debug Mode...
echo [*] Check logs\tray_error.log for output.
echo.

:: DO NOT redirect output here, the internal logger handles it!
%PY_CMD% -m tray.tray_app

echo.
echo [*] Tray process ended. Check logs\tray_error.log for details.
pause
