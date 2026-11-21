@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem --- Silent / Boot flag detection ---
set "SILENT=0"
if /i "%~1"=="--silent" set "SILENT=1"
if /i "%~1"=="/silent" set "SILENT=1"
if /i "%~1"=="-s" set "SILENT=1"
if /i "%~1"=="--boot" set "SILENT=1"

if "!SILENT!"=="0" (
    title Hecos - Tray Launcher
    for /f %%A in ('echo prompt $E^| cmd') do set "ESC=%%A"
    set "C_CYAN=!ESC![96m"
    set "C_MAG=!ESC![95m"
    set "C_GREEN=!ESC![92m"
    set "C_RED=!ESC![91m"
    set "C_DIM=!ESC![90m"
    set "C_RST=!ESC![0m"
)

set "THIS_DIR=%~dp0"
if "!THIS_DIR:~-1!"=="\" set "THIS_DIR=!THIS_DIR:~0,-1!"

if not exist "!THIS_DIR!\logs" mkdir "!THIS_DIR!\logs" >nul 2>&1

if "!SILENT!"=="0" (
    echo.
    echo !C_CYAN!================================================================!C_RST!
    echo   !C_MAG!HECOS TRAY LAUNCHER!C_RST!
    echo !C_CYAN!================================================================!C_RST!
    echo   !C_DIM!Location:!C_RST! !THIS_DIR!
    echo.
)

rem --- Detect PythonW: Tray's own python_env first, then system Python ---
set "PYTHONW_CMD="

if exist "!THIS_DIR!\python_env\pythonw.exe" (
    set PYTHONW_CMD="!THIS_DIR!\python_env\pythonw.exe"
    goto START_TRAY
)

if exist "!THIS_DIR!\python_env\python.exe" (
    set PYTHONW_CMD="!THIS_DIR!\python_env\python.exe"
    goto START_TRAY
)

py -3 --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    for /f "tokens=*" %%P in ('py -3 -c "import sys,os; print(os.path.dirname(sys.executable))" 2^>nul') do set "PY_DIR=%%P"
    if exist "!PY_DIR!\pythonw.exe" (
        set PYTHONW_CMD="!PY_DIR!\pythonw.exe"
        goto START_TRAY
    )
    set "PYTHONW_CMD=py -3"
    goto START_TRAY
)

pythonw --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PYTHONW_CMD=pythonw"
    goto START_TRAY
)

python3 --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    for /f "tokens=*" %%P in ('python3 -c "import sys,os; print(os.path.dirname(sys.executable))" 2^>nul') do set "PY_DIR=%%P"
    if exist "!PY_DIR!\pythonw.exe" (
        set PYTHONW_CMD="!PY_DIR!\pythonw.exe"
        goto START_TRAY
    )
    set "PYTHONW_CMD=python3"
    goto START_TRAY
)

python --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    for /f "tokens=*" %%P in ('python -c "import sys,os; print(os.path.dirname(sys.executable))" 2^>nul') do set "PY_DIR=%%P"
    if exist "!PY_DIR!\pythonw.exe" (
        set PYTHONW_CMD="!PY_DIR!\pythonw.exe"
        goto START_TRAY
    )
    set "PYTHONW_CMD=python"
    goto START_TRAY
)

rem --- No Python found ---
if "!SILENT!"=="0" (
    echo !C_RED![FAIL]!C_RST! Python is not installed or not found.
    echo.
    echo   Hecos Tray requires Python to run.
    echo   Please run HECOS_TRAY_SETUP.bat to install Standalone Python automatically.
    echo.
    pause
)
exit /b 1

:START_TRAY
if "!SILENT!"=="1" (
    start "" /b !PYTHONW_CMD! -c "import sys; sys.path.insert(0, r'!THIS_DIR!'); import runpy; runpy.run_module('tray.tray_app', run_name='__main__')" > "!THIS_DIR!\logs\tray_crash.log" 2>&1
    exit /b 0
)

echo  !C_GREEN![ OK ]!C_RST! Launching with: !PYTHONW_CMD!
start "" /b !PYTHONW_CMD! -c "import sys; sys.path.insert(0, r'!THIS_DIR!'); import runpy; runpy.run_module('tray.tray_app', run_name='__main__')" > "!THIS_DIR!\logs\tray_crash.log" 2>&1

echo  !C_GREEN![ OK ]!C_RST! Tray started. The icon will appear near your system clock shortly.
echo  !C_DIM![ .. ] Closing launcher window in 2 seconds...!C_RST!
echo.
timeout /t 2 >nul 2>&1 || ping 127.0.0.1 -n 3 >nul
exit /b 0
