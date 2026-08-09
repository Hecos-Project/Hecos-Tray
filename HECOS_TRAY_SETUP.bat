@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title HECOS - SETUP WIZARD
color 0B

:: ─── WIZARD LOG ────────────────────────────────────────────────────────────
:: All wizard output is mirrored to logs\wizard.log for debugging
if not exist "logs" mkdir "logs"
set "WIZARD_LOG=%~dp0logs\wizard.log"
echo [%DATE% %TIME%] HECOS TRAY SETUP STARTED >> "!WIZARD_LOG!"
echo [%DATE% %TIME%] Tray dir: %~dp0 >> "!WIZARD_LOG!"

:: ─────────────────────────────────────────────────────────────────────────────
::  HECOS TRAY SETUP  (launched from C:\Hecos-Tray)
::  This script handles:
::    1. Detecting the Hecos Core directory
::    2. Detecting ANY available Python (no re-download if already present)
::    3. Installing Tray-only dependencies from pyproject.toml if missing
::    4. Offering the user a choice: Setup Wizard OR launch Tray directly
::    5. Downloading the Core from GitHub if not found
:: ─────────────────────────────────────────────────────────────────────────────

:: --- Determine TRAY_DIR (where this script lives) ---
set "TRAY_DIR=%~dp0"
if "!TRAY_DIR:~-1!"=="\" set "TRAY_DIR=!TRAY_DIR:~0,-1!"

:: ─── SELF-HEALING FOLDER CHECK ──────────────────────────────────────────────
set "CANONICAL=C:\Hecos-Tray"
if /i not "!TRAY_DIR!"=="!CANONICAL!" (
    echo.
    echo  [AUTO-FIX] Hecos-Tray is in the wrong location:
    echo  [AUTO-FIX]   Found at: !TRAY_DIR!
    echo  [AUTO-FIX]   Moving to: !CANONICAL! ...
    echo.
    robocopy "!TRAY_DIR!" "!CANONICAL!" /E /IS /IT /NFL /NDL /NJH /NJS /NC /NS /NP >nul 2>&1
    if !ERRORLEVEL! GEQ 8 (
        color 0C
        echo  [ERROR] Auto-move failed. Please move the folder manually:
        echo    From: !TRAY_DIR!
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

:: --- Determine ROOT_DIR (Hecos Core) ---
set "ROOT_DIR=C:\Hecos"

if exist "%~dp0..\..\hecos\core\version" (
    pushd "%~dp0..\.."
    set "ROOT_DIR=!CD!"
    popd
) else if exist "C:\Hecos\hecos\core\version" (
    set "ROOT_DIR=C:\Hecos"
) else (
    :: Try to find the canonical core next to a versioned tray folder
    for /d %%D in ("%~dp0..\Hecos") do (
        if exist "%%D\hecos\core\version" (
            set "ROOT_DIR=%%D"
        )
    )
)

echo ==============================================================================
echo                          HECOS TRAY SETUP
echo ==============================================================================
echo.

:: ─────────────────────────────────────────────────────────────────────────────
:: 1. SYSTEM CHECK
:: ─────────────────────────────────────────────────────────────────────────────
echo [SYSTEM CHECK]

:: Check Tray
echo [OK] Tray found at: !TRAY_DIR!

:: Check Core
set "CORE_FOUND=0"
if exist "%ROOT_DIR%\hecos\core\version" (
    echo [OK] Core found at: %ROOT_DIR%
    set "CORE_FOUND=1"
) else (
    echo [-] Core NOT found - will offer download below.
)
echo.

:: ─────────────────────────────────────────────────────────────────────────────
:: 2. PYTHON DETECTION - find ANY python, never re-download if already present
:: ─────────────────────────────────────────────────────────────────────────────
echo [PYTHON DETECTION]
set "PYTHON_CMD="
set "PYTHON_LOC="

:: Priority 1: Tray's own portable python_env (installed by this wizard on first run)
if exist "%TRAY_DIR%\python_env\python.exe" (
    set PYTHON_CMD="%TRAY_DIR%\python_env\python.exe"
    set "PYTHON_LOC=Tray Portable (%TRAY_DIR%\python_env)"
    goto PYTHON_FOUND
)

:: Priority 2: py launcher (system Python — correct for Tray)
py -3 --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PYTHON_CMD=py -3"
    set "PYTHON_LOC=System (py launcher)"
    goto PYTHON_FOUND
)

:: Priority 3: python3 on PATH
python3 --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PYTHON_CMD=python3"
    set "PYTHON_LOC=System (python3)"
    goto PYTHON_FOUND
)

:: Priority 4: python on PATH
python --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PYTHON_CMD=python"
    set "PYTHON_LOC=System (python)"
    goto PYTHON_FOUND
)

:: No Python found at all - must install
echo [!] Python is NOT installed or not found anywhere on this system.
echo.
echo  Hecos Tray requires Python 3.10 or later.
echo  Choose an option:
echo.
echo   1. Download and install Portable Python 3.11 (Recommended)
echo   2. Exit (and install Python manually from python.org)
echo.
set /p CH="Select an option (1-2): "
if "!CH!"=="1" goto INSTALL_PYTHON
exit


:PYTHON_FOUND
echo [OK] Python found: !PYTHON_LOC!
!PYTHON_CMD! --version
echo [%DATE% %TIME%] Python found: !PYTHON_LOC! with cmd: !PYTHON_CMD! >> "!WIZARD_LOG!"
echo.

:: ─────────────────────────────────────────────────────────────────────────────
:: 3. TRAY DEPENDENCY CHECK - install from pyproject.toml if missing
:: ─────────────────────────────────────────────────────────────────────────────
echo [DEPENDENCY CHECK]
echo [%DATE% %TIME%] Running dependency check... >> "!WIZARD_LOG!"

:: Quick check: ALL required tray modules must be importable
!PYTHON_CMD! -c "import tomli_w, pystray, PIL, customtkinter" >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    echo [OK] All Tray dependencies are already installed.
    echo [%DATE% %TIME%] Deps OK - going to READY >> "!WIZARD_LOG!"
    echo.
    goto READY
)

echo [!] Some Tray dependencies are missing. Installing...
echo.

!PYTHON_CMD! -m pip install --quiet --upgrade pip >nul 2>&1
!PYTHON_CMD! -m pip install --quiet pystray pillow tomli-w packaging psutil pyyaml customtkinter qrcode pywin32

:: Verify install succeeded
!PYTHON_CMD! -c "import tomli_w, pystray, PIL" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo  [!] ERROR: Failed to install Tray dependencies.
    echo  [!] Try running manually: pip install pystray pillow tomli-w packaging psutil pyyaml customtkinter
    pause
    exit
)
echo [+] Tray dependencies installed successfully.
echo.

:: ─────────────────────────────────────────────────────────────────────────────
:: 4. READY - let the user choose what to do
:: ─────────────────────────────────────────────────────────────────────────────
:READY
echo [%DATE% %TIME%] Reached READY block. CORE_FOUND=!CORE_FOUND! >> "!WIZARD_LOG!"
echo ==============================================================================
echo                       HECOS TRAY IS READY
echo ==============================================================================
echo.
echo  The Tray is fully configured and ready to launch.
echo  What would you like to do?
echo.

if "!CORE_FOUND!"=="1" goto MENU_CORE_FOUND
goto MENU_NO_CORE

:MENU_CORE_FOUND
echo   1. Open the Hecos Setup Wizard ^(configure AI, voices, install deps^)
echo   2. Launch the Tray Icon directly
echo   3. Exit
echo.
set /p READY_CHOICE="Select an option (1-3): "
if "!READY_CHOICE!"=="1" goto LAUNCH_SETUP_WIZARD
if "!READY_CHOICE!"=="2" goto LAUNCH_TRAY_ONLY
exit

:MENU_NO_CORE
echo   1. Download Hecos Core from GitHub ^(then open Setup Wizard^)
echo   2. Launch the Tray Icon only ^(download Core later from the Dashboard^)
echo   3. Exit
echo.
set /p READY_CHOICE="Select an option (1-3): "
if "!READY_CHOICE!"=="1" goto DOWNLOAD_CORE
if "!READY_CHOICE!"=="2" goto LAUNCH_TRAY_ONLY
exit


:: ─────────────────────────────────────────────────────────────────────────────
:: LAUNCH_SETUP_WIZARD
:: ─────────────────────────────────────────────────────────────────────────────
:LAUNCH_SETUP_WIZARD
echo.
echo [*] Launching Hecos Setup Wizard...
echo [%DATE% %TIME%] Launching setup_wizard.py from ROOT_DIR: %ROOT_DIR% >> "!WIZARD_LOG!"
cd /d "%ROOT_DIR%"
%PYTHON_CMD% "hecos\setup_wizard.py" --web 2>> "!WIZARD_LOG!"
echo [%DATE% %TIME%] setup_wizard.py exited with code: !ERRORLEVEL! >> "!WIZARD_LOG!"
echo.
echo [!] Setup Wizard exited. If there was an error, check logs\wizard.log
pause
goto END


:: ─────────────────────────────────────────────────────────────────────────────
:: LAUNCH_TRAY_ONLY
:: ─────────────────────────────────────────────────────────────────────────────
:LAUNCH_TRAY_ONLY
echo.
echo [*] Launching Hecos Tray...
echo [*] The tray icon will appear near your system clock.
timeout /t 2 >nul
cd /d "%TRAY_DIR%"
call "%TRAY_DIR%\START_HECOS_TRAY_WIN.bat"
goto END


:: ─────────────────────────────────────────────────────────────────────────────
:: INSTALL_PYTHON (only reached if NO Python was found anywhere)
:: ─────────────────────────────────────────────────────────────────────────────
:INSTALL_PYTHON
echo.
echo ==============================================================================
echo              DOWNLOADING PORTABLE PYTHON ENVIRONMENT
echo ==============================================================================
set "PYTHON_VERSION=3.11.9"
set "PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-embed-amd64.zip"
set "PYTHON_DIR=%TRAY_DIR%\python_env"

echo [*] Downloading Portable Python %PYTHON_VERSION%...
mkdir "%PYTHON_DIR%" >nul 2>&1
powershell -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile 'python.zip' -UseBasicParsing"

echo [*] Extracting Python...
powershell -Command "Expand-Archive -Path 'python.zip' -DestinationPath '%PYTHON_DIR%' -Force"
del python.zip

echo [*] Enabling site-packages...
for %%f in ("%PYTHON_DIR%\*._pth") do (
    powershell -Command "(Get-Content '%%f') -replace '#import site', 'import site' | Set-Content '%%f'"
)

echo [*] Installing pip...
powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%PYTHON_DIR%\get-pip.py' -UseBasicParsing"
"%PYTHON_DIR%\python.exe" "%PYTHON_DIR%\get-pip.py" --quiet

set "PYTHON_CMD=%PYTHON_DIR%\python.exe"
echo [+] Portable Python installed!
echo.
goto DEPENDENCY_CHECK_AFTER_INSTALL

:DEPENDENCY_CHECK_AFTER_INSTALL
echo [*] Installing Tray dependencies...
"%PYTHON_DIR%\python.exe" -m pip install --quiet pystray pillow tomli-w packaging psutil pyyaml
echo [+] Done.
echo.
goto READY


:: ─────────────────────────────────────────────────────────────────────────────
:: DOWNLOAD_CORE
:: ─────────────────────────────────────────────────────────────────────────────
:DOWNLOAD_CORE
echo.
echo ==============================================================================
echo                   DOWNLOADING HECOS CORE FROM GITHUB
echo ==============================================================================
echo.

set "GH_API_URL=https://api.github.com/repos/Hecos-Project/Hecos/releases/latest"
set "TEMP_JSON=%TEMP%\hecos_release.json"
set "TEMP_ZIP=%TEMP%\hecos_core.zip"
set "TEMP_EXTRACT=%TEMP%\hecos_extract"

echo [*] Fetching latest release info from GitHub...
powershell -Command "try { Invoke-RestMethod -Uri '%GH_API_URL%' -UseBasicParsing | ConvertTo-Json | Out-File -Encoding utf8 '%TEMP_JSON%'; Write-Host '[OK] Release info fetched.' } catch { Write-Host '[ERROR]' $_.Exception.Message; exit 1 }"
if !ERRORLEVEL! NEQ 0 (
    echo  [!] Failed to connect to GitHub. Download manually from:
    echo  [!]   https://github.com/Hecos-Project/Hecos/releases/latest
    echo  [!]   and extract to: %ROOT_DIR%
    pause
    goto READY
)

echo [*] Resolving download URL...
for /f "usebackq tokens=*" %%U in (`powershell -Command "(Get-Content '%TEMP_JSON%' | ConvertFrom-Json).zipball_url"`) do set "ZIPBALL_URL=%%U"

if "!ZIPBALL_URL!"=="" (
    echo  [!] Could not determine download URL.
    pause
    goto READY
)

echo [*] Downloading Core (~50-100 MB)... please wait.
powershell -Command "try { Invoke-WebRequest -Uri '!ZIPBALL_URL!' -OutFile '%TEMP_ZIP%' -UseBasicParsing; Write-Host '[OK] Download complete.' } catch { Write-Host '[ERROR]' $_.Exception.Message; exit 1 }"
if !ERRORLEVEL! NEQ 0 (
    echo  [!] Download failed. Check your internet connection.
    pause
    goto READY
)

echo [*] Extracting files...
if exist "%TEMP_EXTRACT%" rmdir /s /q "%TEMP_EXTRACT%"
mkdir "%TEMP_EXTRACT%" 2>nul
powershell -Command "Expand-Archive -Path '%TEMP_ZIP%' -DestinationPath '%TEMP_EXTRACT%' -Force"

echo [*] Installing to %ROOT_DIR%...
mkdir "%ROOT_DIR%" 2>nul
for /d %%D in ("%TEMP_EXTRACT%\*") do (
    robocopy "%%D" "%ROOT_DIR%" /e /move /nfl /ndl /njh /njs >nul 2>&1
)

del "%TEMP_JSON%" >nul 2>&1
del "%TEMP_ZIP%" >nul 2>&1
rmdir /s /q "%TEMP_EXTRACT%" >nul 2>&1

if exist "%ROOT_DIR%\hecos\core\version" (
    echo.
    echo  [+] Hecos Core installed successfully!
    set "CORE_FOUND=1"
    echo.
    echo  [*] Now running the Core self-installer to set up Python and dependencies...
    echo  [*] This may take a few minutes on first run. Please wait.
    echo.
    :: Run the Core's own setup bat which installs portable Python + all Core pip deps
    if exist "%ROOT_DIR%\scripts\windows\setup\HECOS_SETUP_WIZARD.bat" (
        call "%ROOT_DIR%\scripts\windows\setup\HECOS_SETUP_WIZARD.bat" --silent
    ) else (
        echo  [!] Warning: Core setup script not found. Dependencies may be missing.
        echo  [!] Run %ROOT_DIR%\scripts\windows\setup\HECOS_SETUP_WIZARD.bat manually if Hecos fails to start.
    )
    echo.
    echo  [+] Core setup complete! Returning to menu.
    timeout /t 2 >nul
    goto READY
) else (
    echo  [!] Extraction done but Core files not found. Extract the ZIP manually.
    pause
    goto END
)


:END
exit
