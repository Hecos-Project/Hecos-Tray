@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Hecos - Restart Tray Icon
color 0B

:: ─── SELF-HEALING FOLDER CHECK ──────────────────────────────────────────────
set "THIS_DIR=%~dp0"
if "!THIS_DIR:~-1!"=="\" set "THIS_DIR=!THIS_DIR:~0,-1!"
set "CANONICAL=C:\Hecos-Tray"
if /i not "!THIS_DIR!"=="!CANONICAL!" (
    echo.
    echo  [AUTO-FIX] Hecos-Tray is in the wrong location:
    echo  [AUTO-FIX]   Found at: !THIS_DIR!
    echo  [AUTO-FIX]   Moving to: !CANONICAL! ...
    echo.
    robocopy "!THIS_DIR!" "!CANONICAL!" /E /IS /IT /NFL /NDL /NJH /NJS /NC /NS /NP >nul 2>&1
    if !ERRORLEVEL! GEQ 8 (
        color 0C
        echo  [ERROR] Auto-move failed. Please move the folder manually:
        echo    From: !THIS_DIR!
        echo    To:   !CANONICAL!
        pause
        exit
    )
    echo.
    echo ========================================================================
    echo  [!] IMPORTANT: FOLDER HAS BEEN RELOCATED
    echo ========================================================================
    echo  Hecos requires its folders to be in a specific location to work.
    echo  Your Tray folder has been automatically moved to:
    echo    -^> !CANONICAL!
    echo.
    echo  Please remember this new location for the future!
    echo  The application will now restart automatically.
    echo ========================================================================
    echo.
    pause
    start "" "!CANONICAL!\%~nx0"
    exit
)
:: ─────────────────────────────────────────────────────────────────────────────

echo.
echo.

:: Detect PythonW - try multiple strategies
set "PYTHONW_CMD="
set "ROOT_DIR=C:\Hecos"

:: Strategy 1: Tray's own portable python_env
if exist "%THIS_DIR%\python_env\pythonw.exe" (
    set PYTHONW_CMD="%THIS_DIR%\python_env\pythonw.exe"
    goto START_TRAY
)

:: Strategy 2: Core's portable python_env (fallback)
if exist "%ROOT_DIR%\python_env\pythonw.exe" (
    set PYTHONW_CMD="%ROOT_DIR%\python_env\pythonw.exe"
    goto START_TRAY
)

:: Strategy 3: Core venv
if exist "%ROOT_DIR%\venv\Scripts\pythonw.exe" (
    set PYTHONW_CMD="%ROOT_DIR%\venv\Scripts\pythonw.exe"
    goto START_TRAY
)

:: Strategy 3: Locate pythonw.exe from the py launcher (handles Python 3.14+ installs)
py -3 --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    for /f "tokens=*" %%P in ('py -3 -c "import sys,os; print(os.path.dirname(sys.executable))"') do set "PY_DIR=%%P"
    if exist "!PY_DIR!\pythonw.exe" (
        set PYTHONW_CMD="!PY_DIR!\pythonw.exe"
        goto START_TRAY
    )
    :: py launcher exists but no pythonw.exe - use python directly via start (detached)
    set "PYTHONW_CMD=py -3"
    goto START_TRAY
)

:: Strategy 4: pythonw on PATH
pythonw --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PYTHONW_CMD=pythonw"
    goto START_TRAY
)

:: Strategy 5: python3 on PATH → find its directory
python3 --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    for /f "tokens=*" %%P in ('python3 -c "import sys,os; print(os.path.dirname(sys.executable))"') do set "PY_DIR=%%P"
    if exist "!PY_DIR!\pythonw.exe" (
        set PYTHONW_CMD="!PY_DIR!\pythonw.exe"
        goto START_TRAY
    )
    set "PYTHONW_CMD=python3"
    goto START_TRAY
)

:: Strategy 6: python on PATH → find its directory
python --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    for /f "tokens=*" %%P in ('python -c "import sys,os; print(os.path.dirname(sys.executable))"') do set "PY_DIR=%%P"
    if exist "!PY_DIR!\pythonw.exe" (
        set PYTHONW_CMD="!PY_DIR!\pythonw.exe"
        goto START_TRAY
    )
    set "PYTHONW_CMD=python"
    goto START_TRAY
)

:: No Python found
color 0C
echo [ERROR] Python is not installed or not found.
echo.
echo Hecos Tray requires Python to run.
echo Please run HECOS_SETUP_WIZARD.bat to install Python.
echo.
pause
exit


:START_TRAY
:: Use "start" to detach the process so no console window stays open
:: Works whether PYTHONW_CMD is pythonw.exe (no window) or python (window hidden by start)
echo  [+] Launching with: !PYTHONW_CMD!
start "" /b !PYTHONW_CMD! -c "import sys; sys.path.insert(0, r'%THIS_DIR%'); import runpy; runpy.run_module('tray.tray_app', run_name='__main__')" > "%THIS_DIR%\tray_crash.log" 2>&1

echo  [+] Command sent. The icon will appear in the system tray shortly.
echo  [!] This window will close in 2 seconds...
echo.
timeout /t 2 >nul
exit
