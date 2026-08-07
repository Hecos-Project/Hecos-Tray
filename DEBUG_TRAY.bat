@echo off
setlocal
title Debug Hecos Tray
cd /d "%~dp0"

echo [*] Working directory: %CD%
echo.

set PY_CMD=python
if exist "C:\Hecos\python_env\python.exe" (
    set PY_CMD="C:\Hecos\python_env\python.exe"
) else if exist "C:\Hecos\venv\Scripts\python.exe" (
    set PY_CMD="C:\Hecos\venv\Scripts\python.exe"
)

echo [*] Python: %PY_CMD%
echo.

set PYTHONPATH=%~dp0
%PY_CMD% tray\tray_app.py 2> debug_error.log

echo.
if exist debug_error.log (
    echo [*] Error log:
    type debug_error.log
)
echo.
echo [*] Tray exited.
pause
