@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title HECOS - TRAY SETUP WIZARD

rem --- Enable ANSI Cyber Colors (Windows 10/11 native VT support) ---
for /f %%A in ('echo prompt $E^| cmd') do set "ESC=%%A"
set "C_CYAN=%ESC%[96m"
set "C_MAG=%ESC%[95m"
set "C_GREEN=%ESC%[92m"
set "C_YELLOW=%ESC%[93m"
set "C_RED=%ESC%[91m"
set "C_DIM=%ESC%[90m"
set "C_WHITE=%ESC%[97m"
set "C_RST=%ESC%[0m"

rem --- Determine TRAY_DIR dynamically ---
set "TRAY_DIR=%~dp0"
if "!TRAY_DIR:~-1!"=="\" set "TRAY_DIR=!TRAY_DIR:~0,-1!"

rem --- Setup Wizard Log ---
if not exist "!TRAY_DIR!\logs" mkdir "!TRAY_DIR!\logs" >nul 2>&1
set "WIZARD_LOG=!TRAY_DIR!\logs\wizard.log"
echo [%DATE% %TIME%] HECOS TRAY SETUP STARTED ^(tray_dir=!TRAY_DIR!^) >> "!WIZARD_LOG!"

rem --- Read Tray version ---
set "TRAY_VER=unknown"
if exist "!TRAY_DIR!\tray\version" set /p TRAY_VER=<"!TRAY_DIR!\tray\version"

echo.
echo %C_CYAN%==============================================================================%C_RST%
echo   %C_MAG%HECOS TRAY SETUP WIZARD%C_RST%   %C_CYAN%v!TRAY_VER!%C_RST%
echo %C_CYAN%==============================================================================%C_RST%
echo.

rem ===========================================================================
rem [1/4] PATH SAFETY & SYSTEM CHECK
rem ===========================================================================
echo %C_CYAN%[1/4] Path ^& System Check%C_RST%

call :VALIDATE_PATH "!TRAY_DIR!"
if /i "!PATH_STATUS!"=="ERR" (
    echo %C_RED%[FAIL]%C_RST% Unsafe Tray folder path: !TRAY_DIR!
    echo        Reason: %C_YELLOW%!PATH_MSG!%C_RST%
    echo [%DATE% %TIME%] FAIL unsafe tray path: !TRAY_DIR! ^(!PATH_MSG!^) >> "!WIZARD_LOG!"
    echo.
    echo   Hecos Tray can live on ANY drive or folder, provided the path has no spaces,
    echo   non-ASCII accents, or special shell characters.
    echo.
    set "DEFAULT_TRAY=C:\Hecos-Tray"
    echo   Would you like to relocate Hecos Tray automatically?
    echo   %C_DIM%Press Enter for [!DEFAULT_TRAY!], type a custom path, or type N to exit.%C_RST%
    echo.
    set "NEW_TRAY="
    set /p NEW_TRAY="  %C_CYAN%>>%C_RST% Target folder [!DEFAULT_TRAY!]: "
    if /i "!NEW_TRAY!"=="N" exit /b 1
    if "!NEW_TRAY!"=="" set "NEW_TRAY=!DEFAULT_TRAY!"
    call :VALIDATE_PATH "!NEW_TRAY!"
    if /i "!PATH_STATUS!"=="ERR" (
        echo %C_RED%[FAIL]%C_RST% Chosen target is also unsafe: !PATH_MSG!
        pause
        exit /b 1
    )
    echo %C_CYAN%[ .. ]%C_RST% Relocating Hecos Tray to !NEW_TRAY! ...
    robocopy "!TRAY_DIR!" "!NEW_TRAY!" /E /IS /IT /NFL /NDL /NJH /NJS /NC /NS /NP >nul 2>&1
    if !ERRORLEVEL! GEQ 8 (
        echo %C_RED%[FAIL]%C_RST% Relocation failed. Move the folder manually to !NEW_TRAY!.
        pause
        exit /b 1
    )
    echo %C_GREEN%[ OK ]%C_RST% Hecos Tray relocated to !NEW_TRAY!.
    echo %C_CYAN%[ ^>^> ]%C_RST% Restarting Tray Setup from the new location...
    start "" "!NEW_TRAY!\%~nx0"
    exit /b 0
)

if /i "!PATH_STATUS!"=="WARN" (
    echo %C_YELLOW%[WARN]%C_RST% Path advisory: !PATH_MSG!
) else (
    echo %C_GREEN%[ OK ]%C_RST% Tray path verified: !TRAY_DIR!
)

rem --- Resolve Hecos Core location ---
call :DETECT_CORE
if "!CORE_FOUND!"=="1" (
    set "CORE_VER=unknown"
    if exist "!ROOT_DIR!\hecos\core\version" set /p CORE_VER=<"!ROOT_DIR!\hecos\core\version"
    echo %C_GREEN%[ OK ]%C_RST% Hecos Core v!CORE_VER! detected: !ROOT_DIR!
) else (
    echo %C_DIM%[ -- ]%C_RST% Hecos Core not installed yet ^(can download in the menu below^)
)
echo.

rem ===========================================================================
rem [2/4] PYTHON DETECTION (REQUIRES PYTHON 3.10+ WITH TKINTER)
rem ===========================================================================
echo %C_CYAN%[2/4] Python Runtime ^(3.10+ with tkinter^)%C_RST%
set "PYTHON_CMD="
set "PYTHON_LOC="

rem --- Priority 1: Tray's own standalone python_env ---
if exist "!TRAY_DIR!\python_env\python.exe" (
    "!TRAY_DIR!\python_env\python.exe" -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        set PYTHON_CMD="!TRAY_DIR!\python_env\python.exe"
        set "PYTHON_LOC=Tray Standalone Python (!TRAY_DIR!\python_env)"
        goto PYTHON_FOUND
    ) else (
        echo %C_YELLOW%[WARN]%C_RST% Existing !TRAY_DIR!\python_env lacks tkinter or is below 3.10.
    )
)

rem --- Priority 2: System Python via py launcher (must have tkinter + 3.10+) ---
py -3 -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PYTHON_CMD=py -3"
    set "PYTHON_LOC=System Python (py -3)"
    goto PYTHON_FOUND
)

rem --- Priority 3: python3 on PATH ---
python3 -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PYTHON_CMD=python3"
    set "PYTHON_LOC=System Python (python3)"
    goto PYTHON_FOUND
)

rem --- Priority 4: python on PATH ---
python -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PYTHON_CMD=python"
    set "PYTHON_LOC=System Python (python)"
    goto PYTHON_FOUND
)

rem --- No suitable Python (3.10+ with tkinter) found anywhere ---
echo %C_YELLOW%[WARN]%C_RST% No compatible Python ^(3.10+ with tkinter^) was found on this system.
echo.
echo   Hecos Tray can automatically download a self-contained Portable Python 3.11.18
echo   ^(with tkinter, pip, and C runtime included — no manual install required^).
echo.
echo   %C_CYAN%1.%C_RST% Download ^& Install Standalone Python 3.11.18 %C_GREEN%(Recommended)%C_RST%
echo   %C_DIM%2. Exit%C_RST%
echo.
set "PY_CH="
set /p PY_CH="  %C_CYAN%>>%C_RST% Select an option (1-2) [1]: "
if "!PY_CH!"=="" set "PY_CH=1"
if "!PY_CH!"=="1" goto INSTALL_PYTHON
exit /b 0

:INSTALL_PYTHON
echo.
echo %C_CYAN%------------------------------------------------------------------------------%C_RST%
echo   %C_MAG%PROVISIONING STANDALONE PYTHON 3.11.18 FOR TRAY%C_RST%
echo %C_CYAN%------------------------------------------------------------------------------%C_RST%
call :PROVISION_TRAY_PYTHON "!TRAY_DIR!\python_env"
if !ERRORLEVEL! NEQ 0 (
    echo %C_RED%[FAIL]%C_RST% Could not provision standalone Python 3.11.18.
    echo        Check your internet connection and retry, or install Python 3.11 from python.org.
    echo [%DATE% %TIME%] FAIL Tray Python provisioning failed >> "!WIZARD_LOG!"
    pause
    exit /b 1
)
set PYTHON_CMD="!TRAY_DIR!\python_env\python.exe"
set "PYTHON_LOC=Tray Standalone Python (!TRAY_DIR!\python_env)"

:PYTHON_FOUND
set "PY_VER="
for /f "tokens=2 delims= " %%V in ('!PYTHON_CMD! --version 2^>^&1') do set "PY_VER=%%V"
echo %C_GREEN%[ OK ]%C_RST% Python ready: !PYTHON_LOC! ^(v!PY_VER!^)
echo [%DATE% %TIME%] Python ready: !PYTHON_LOC! ^(!PY_VER!^) >> "!WIZARD_LOG!"
echo.

rem ===========================================================================
rem [3/4] TRAY DEPENDENCY CHECK
rem ===========================================================================
echo %C_CYAN%[3/4] Tray Dependencies%C_RST%
echo [%DATE% %TIME%] Checking Tray dependencies... >> "!WIZARD_LOG!"

!PYTHON_CMD! -c "import tomli_w, pystray, PIL, customtkinter, qrcode, yaml, psutil, packaging" >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    echo %C_GREEN%[ OK ]%C_RST% All Tray dependencies are already installed.
    echo [%DATE% %TIME%] Tray deps OK >> "!WIZARD_LOG!"
) else (
    echo %C_CYAN%[ .. ]%C_RST% Installing missing Tray dependencies...
    !PYTHON_CMD! -m pip install --quiet "pystray>=0.19,<1.0" "pillow>=10.0,<14.0" "tomli-w>=1.0,<2.0" "packaging>=23.0,<28.0" "psutil>=5.9,<8.0" "pyyaml>=6.0,<7.0" "customtkinter>=5.2,<7.0" "qrcode>=7.4,<9.0" "pywin32>=306"
    !PYTHON_CMD! -c "import tomli_w, pystray, PIL, customtkinter, qrcode" >nul 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo %C_RED%[FAIL]%C_RST% Failed to install Tray dependencies.
        echo        Try manually: !PYTHON_CMD! -m pip install pystray pillow tomli-w packaging psutil pyyaml customtkinter qrcode pywin32
        echo [%DATE% %TIME%] FAIL Tray deps install failed >> "!WIZARD_LOG!"
        pause
        exit /b 1
    )
    echo %C_GREEN%[ OK ]%C_RST% Tray dependencies installed successfully.
)
echo.

rem ===========================================================================
rem [4/4] SHARED INSTALL REGISTRY UPDATE
rem ===========================================================================
echo %C_CYAN%[4/4] Install Registry%C_RST%
call :UPDATE_REGISTRY_FROM_TRAY
echo.

rem ===========================================================================
rem READY MENU
rem ===========================================================================
:READY
call :DETECT_CORE
echo [%DATE% %TIME%] Reached READY menu. CORE_FOUND=!CORE_FOUND! ROOT_DIR=!ROOT_DIR! >> "!WIZARD_LOG!"
echo %C_CYAN%==============================================================================%C_RST%
echo   %C_MAG%HECOS TRAY IS READY%C_RST%
echo %C_CYAN%==============================================================================%C_RST%
echo   %C_DIM%Tray Path:%C_RST% %C_WHITE%!TRAY_DIR!%C_RST%
if "!CORE_FOUND!"=="1" (
    echo   %C_DIM%Core Path:%C_RST% %C_GREEN%!ROOT_DIR!%C_RST%
) else (
    echo   %C_DIM%Core Path:%C_RST% %C_YELLOW%Not installed yet%C_RST%
)
echo %C_CYAN%------------------------------------------------------------------------------%C_RST%
echo.

if "!CORE_FOUND!"=="1" goto MENU_CORE_FOUND
goto MENU_NO_CORE

:MENU_CORE_FOUND
echo   %C_CYAN%1.%C_RST% %C_WHITE%Open Hecos Core Setup Wizard%C_RST%   %C_DIM%(Python, deps, Piper TTS, doctor)%C_RST%
echo   %C_CYAN%2.%C_RST% %C_WHITE%Launch Hecos Tray Icon%C_RST%         %C_DIM%(Start system tray ^& dashboard)%C_RST%
echo   %C_CYAN%3.%C_RST% %C_WHITE%Download / Reinstall Core%C_RST%      %C_DIM%(Choose custom folder)%C_RST%
echo   %C_DIM%4. Exit%C_RST%
echo.
set "READY_CHOICE="
set /p READY_CHOICE="  %C_CYAN%>>%C_RST% Select an option (1-4): "
if "!READY_CHOICE!"=="1" goto LAUNCH_SETUP_WIZARD
if "!READY_CHOICE!"=="2" goto LAUNCH_TRAY_ONLY
if "!READY_CHOICE!"=="3" goto DOWNLOAD_CORE
if "!READY_CHOICE!"=="4" exit /b 0
goto READY

:MENU_NO_CORE
echo   %C_CYAN%1.%C_RST% %C_WHITE%Download ^& Install Hecos Core%C_RST%  %C_DIM%(Choose folder, download, run setup)%C_RST%
echo   %C_CYAN%2.%C_RST% %C_WHITE%Launch Tray Icon Only%C_RST%          %C_DIM%(Download Core later from Dashboard)%C_RST%
echo   %C_DIM%3. Exit%C_RST%
echo.
set "READY_CHOICE="
set /p READY_CHOICE="  %C_CYAN%>>%C_RST% Select an option (1-3): "
if "!READY_CHOICE!"=="1" goto DOWNLOAD_CORE
if "!READY_CHOICE!"=="2" goto LAUNCH_TRAY_ONLY
if "!READY_CHOICE!"=="3" exit /b 0
goto READY

rem ===========================================================================
rem LAUNCH CORE SETUP WIZARD (always delegates to Core's own bootstrap script)
rem ===========================================================================
:LAUNCH_SETUP_WIZARD
echo.
set "CORE_WIZ=!ROOT_DIR!\scripts\windows\setup\HECOS_SETUP_WIZARD.bat"
if not exist "!CORE_WIZ!" (
    echo %C_RED%[FAIL]%C_RST% Core setup script not found at: !CORE_WIZ!
    pause
    goto READY
)
echo %C_CYAN%[ ^>^> ]%C_RST% Delegating to Hecos Core Setup Wizard...
echo [%DATE% %TIME%] Calling Core wizard: !CORE_WIZ! --tray-dir !TRAY_DIR! >> "!WIZARD_LOG!"
call "!CORE_WIZ!" --tray-dir "!TRAY_DIR!"
set "CORE_WIZ_RC=!ERRORLEVEL!"
echo [%DATE% %TIME%] Core wizard returned code !CORE_WIZ_RC! >> "!WIZARD_LOG!"
cd /d "!TRAY_DIR!"
echo.
if !CORE_WIZ_RC! EQU 0 (
    echo %C_GREEN%[ OK ]%C_RST% Core Setup Wizard completed cleanly.
) else if !CORE_WIZ_RC! EQU 2 (
    echo %C_YELLOW%[WARN]%C_RST% Core Setup completed with optional warnings.
) else (
    echo %C_RED%[FAIL]%C_RST% Core Setup Wizard exited with code !CORE_WIZ_RC!.
)
echo.
goto READY

rem ===========================================================================
rem LAUNCH TRAY ONLY
rem ===========================================================================
:LAUNCH_TRAY_ONLY
echo.
echo %C_CYAN%[ ^>^> ]%C_RST% Launching Hecos Tray...
echo %C_DIM%       The tray icon will appear near your system clock.%C_RST%
cd /d "!TRAY_DIR!"
call "!TRAY_DIR!\START_HECOS_TRAY_WIN.bat"
exit /b !ERRORLEVEL!

rem ===========================================================================
rem DOWNLOAD HECOS CORE FROM GITHUB (USER-SELECTABLE FOLDER)
rem ===========================================================================
:DOWNLOAD_CORE
echo.
echo %C_CYAN%==============================================================================%C_RST%
echo   %C_MAG%DOWNLOADING HECOS CORE FROM GITHUB%C_RST%
echo %C_CYAN%==============================================================================%C_RST%
echo.

for %%P in ("!TRAY_DIR!\..") do set "TRAY_PARENT=%%~fP"
if "!TRAY_PARENT:~-1!"=="\" set "TRAY_PARENT=!TRAY_PARENT:~0,-1!"
set "DEFAULT_CORE=!TRAY_PARENT!\Hecos"

:ASK_CORE_TARGET
echo   Where should Hecos Core be installed?
echo   %C_DIM%Press Enter for [!DEFAULT_CORE!] or type any safe path ^(e.g. D:\Apps\Hecos^).%C_RST%
set "CHOSEN_CORE="
set /p CHOSEN_CORE="  %C_CYAN%>>%C_RST% Core install folder [!DEFAULT_CORE!]: "
if "!CHOSEN_CORE!"=="" set "CHOSEN_CORE=!DEFAULT_CORE!"
call :VALIDATE_PATH "!CHOSEN_CORE!"
if /i "!PATH_STATUS!"=="ERR" (
    echo %C_RED%[FAIL]%C_RST% Unsafe path: !PATH_MSG!
    echo        Choose a path without spaces, accents, or special shell characters.
    echo.
    goto ASK_CORE_TARGET
)
if /i "!PATH_STATUS!"=="WARN" (
    echo %C_YELLOW%[WARN]%C_RST% Path advisory: !PATH_MSG!
)
set "ROOT_DIR=!CHOSEN_CORE!"

set "GH_API_URL=https://api.github.com/repos/Hecos-Project/Hecos/releases/latest"
set "DL_TMP=%TEMP%\hecos_core_dl_%RANDOM%"
mkdir "!DL_TMP!" >nul 2>&1
set "TEMP_JSON=!DL_TMP!\release.json"
set "TEMP_ZIP=!DL_TMP!\hecos_core.zip"
set "TEMP_EXTRACT=!DL_TMP!\extract"

echo.
echo %C_CYAN%[ .. ]%C_RST% Fetching latest release info from GitHub...
powershell -NoProfile -NonInteractive -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; try { Invoke-RestMethod -Uri '!GH_API_URL!' -Headers @{'User-Agent'='HecosTraySetup/2.0'} -UseBasicParsing | ConvertTo-Json -Depth 5 | Out-File -Encoding utf8 '!TEMP_JSON!'; exit 0 } catch { Write-Host ('[FAIL] ' + $_.Exception.Message); exit 1 }"
if !ERRORLEVEL! NEQ 0 (
    echo %C_RED%[FAIL]%C_RST% Failed to connect to GitHub.
    echo        Manual download: https://github.com/Hecos-Project/Hecos/releases/latest
    rmdir /s /q "!DL_TMP!" >nul 2>&1
    pause
    goto READY
)

set "ZIPBALL_URL="
for /f "usebackq tokens=*" %%U in (`powershell -NoProfile -NonInteractive -Command "(Get-Content '!TEMP_JSON!' -Raw | ConvertFrom-Json).zipball_url"`) do set "ZIPBALL_URL=%%U"
if "!ZIPBALL_URL!"=="" (
    echo %C_RED%[FAIL]%C_RST% Could not determine release download URL.
    rmdir /s /q "!DL_TMP!" >nul 2>&1
    pause
    goto READY
)

echo %C_CYAN%[ .. ]%C_RST% Downloading Hecos Core ^(~50-100 MB^)...
where curl.exe >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    curl.exe --fail -L --retry 3 --retry-delay 2 --progress-bar -H "User-Agent: HecosTraySetup/2.0" -o "!TEMP_ZIP!" "!ZIPBALL_URL!"
) else (
    powershell -NoProfile -NonInteractive -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '!ZIPBALL_URL!' -Headers @{'User-Agent'='HecosTraySetup/2.0'} -OutFile '!TEMP_ZIP!' -UseBasicParsing"
)
if !ERRORLEVEL! NEQ 0 (
    echo %C_RED%[FAIL]%C_RST% Download failed. Check your internet connection.
    rmdir /s /q "!DL_TMP!" >nul 2>&1
    pause
    goto READY
)

echo %C_CYAN%[ .. ]%C_RST% Extracting files...
mkdir "!TEMP_EXTRACT!" >nul 2>&1
powershell -NoProfile -NonInteractive -Command "Expand-Archive -Path '!TEMP_ZIP!' -DestinationPath '!TEMP_EXTRACT!' -Force"
if !ERRORLEVEL! NEQ 0 (
    echo %C_RED%[FAIL]%C_RST% Failed to extract downloaded ZIP archive.
    rmdir /s /q "!DL_TMP!" >nul 2>&1
    pause
    goto READY
)

echo %C_CYAN%[ .. ]%C_RST% Installing Core to !ROOT_DIR! ...
mkdir "!ROOT_DIR!" >nul 2>&1
for /d %%D in ("!TEMP_EXTRACT!\*") do (
    robocopy "%%D" "!ROOT_DIR!" /E /MOVE /NFL /NDL /NJH /NJS /NC /NS /NP >nul 2>&1
)
rmdir /s /q "!DL_TMP!" >nul 2>&1

if not exist "!ROOT_DIR!\hecos\core\version" (
    echo %C_RED%[FAIL]%C_RST% Extraction completed but Core files were not found at !ROOT_DIR!.
    pause
    goto READY
)

set "CORE_FOUND=1"
echo %C_GREEN%[ OK ]%C_RST% Hecos Core downloaded to !ROOT_DIR!

rem --- Persist core_path in tray_settings.toml and shared install.toml ---
call :UPDATE_REGISTRY_FROM_TRAY

echo.
echo %C_CYAN%[ ^>^> ]%C_RST% Running Core Setup Wizard ^(provisions Core Python, deps, Piper TTS^)...
echo.
if exist "!ROOT_DIR!\scripts\windows\setup\HECOS_SETUP_WIZARD.bat" (
    call "!ROOT_DIR!\scripts\windows\setup\HECOS_SETUP_WIZARD.bat" --unattended --tray-dir "!TRAY_DIR!"
    set "CORE_RC=!ERRORLEVEL!"
    cd /d "!TRAY_DIR!"
    echo.
    if !CORE_RC! EQU 0 (
        echo %C_GREEN%[ OK ]%C_RST% Core setup finished successfully!
    ) else if !CORE_RC! EQU 2 (
        echo %C_YELLOW%[WARN]%C_RST% Core setup finished with optional warnings ^(you can review in Doctor^).
    ) else (
        echo %C_RED%[FAIL]%C_RST% Core setup reported errors ^(exit code !CORE_RC!^).
    )
) else (
    echo %C_YELLOW%[WARN]%C_RST% Core setup script not found inside !ROOT_DIR!.
)
echo.
goto READY


rem ===========================================================================
rem SUBROUTINES
rem ===========================================================================

:PROVISION_TRAY_PYTHON
set "TARGET_PY_DIR=%~1"
set "PBS_ASSET=cpython-3.11.18+20261110-x86_64-pc-windows-msvc-install_only.tar.gz"
set "PBS_URL=https://github.com/astral-sh/python-build-standalone/releases/download/20261110/cpython-3.11.18%%2B20261110-x86_64-pc-windows-msvc-install_only.tar.gz"
set "PBS_SUMS_URL=https://github.com/astral-sh/python-build-standalone/releases/download/20261110/SHA256SUMS"
set "TMP_WORK=%TEMP%\hecos_tray_py_%RANDOM%"
set "TMP_TGZ=!TMP_WORK!\python_standalone.tar.gz"
set "TMP_SUMS=!TMP_WORK!\SHA256SUMS"

mkdir "!TMP_WORK!" >nul 2>&1

echo %C_CYAN%[ .. ]%C_RST% Downloading standalone Python 3.11.18 ^(~47 MB, includes tkinter ^& pip^)...
where curl.exe >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    curl.exe --fail -L --retry 3 --retry-delay 2 --progress-bar -o "!TMP_TGZ!" "!PBS_URL!"
) else (
    powershell -NoProfile -NonInteractive -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '!PBS_URL!' -OutFile '!TMP_TGZ!' -UseBasicParsing"
)
if !ERRORLEVEL! NEQ 0 (
    rmdir /s /q "!TMP_WORK!" >nul 2>&1
    exit /b 1
)
if not exist "!TMP_TGZ!" (
    rmdir /s /q "!TMP_WORK!" >nul 2>&1
    exit /b 1
)

rem --- Best-effort SHA256 verification ---
echo %C_CYAN%[ .. ]%C_RST% Verifying archive checksum...
set "SUMS_OK=0"
where curl.exe >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    curl.exe --fail -sSL --retry 2 -o "!TMP_SUMS!" "!PBS_SUMS_URL!" >nul 2>&1
    if !ERRORLEVEL! EQU 0 set "SUMS_OK=1"
)
if "!SUMS_OK!"=="1" (
    set "HASH_CHECK_FILE=!TMP_TGZ!"
    set "HASH_SUMS_FILE=!TMP_SUMS!"
    set "HASH_ASSET=!PBS_ASSET!"
    powershell -NoProfile -NonInteractive -Command "$line = Get-Content $env:HASH_SUMS_FILE | Where-Object { $_ -like ('*' + $env:HASH_ASSET) } | Select-Object -First 1; if (-not $line) { exit 2 }; $expected = ($line -split '\s+')[0].Trim().ToLower(); $actual = (Get-FileHash -Algorithm SHA256 $env:HASH_CHECK_FILE).Hash.ToLower(); if ($actual -eq $expected) { exit 0 } else { exit 1 }"
    set "HASH_RC=!ERRORLEVEL!"
    if !HASH_RC! EQU 0 (
        echo %C_GREEN%[ OK ]%C_RST% SHA256 checksum verified.
    ) else if !HASH_RC! EQU 1 (
        echo %C_RED%[FAIL]%C_RST% SHA256 checksum MISMATCH! Deleting corrupted download...
        rmdir /s /q "!TMP_WORK!" >nul 2>&1
        exit /b 1
    ) else (
        echo %C_YELLOW%[WARN]%C_RST% Asset hash entry not found; continuing anyway.
    )
) else (
    echo %C_YELLOW%[WARN]%C_RST% Could not fetch SHA256SUMS; skipping checksum verification.
)

echo %C_CYAN%[ .. ]%C_RST% Extracting Python into !TARGET_PY_DIR! ...
tar -xzf "!TMP_TGZ!" -C "!TMP_WORK!"
if !ERRORLEVEL! NEQ 0 (
    rmdir /s /q "!TMP_WORK!" >nul 2>&1
    exit /b 1
)
if not exist "!TMP_WORK!\python\python.exe" (
    rmdir /s /q "!TMP_WORK!" >nul 2>&1
    exit /b 1
)

if exist "!TARGET_PY_DIR!" rmdir /s /q "!TARGET_PY_DIR!" >nul 2>&1
mkdir "!TARGET_PY_DIR!" >nul 2>&1
robocopy "!TMP_WORK!\python" "!TARGET_PY_DIR!" /E /MOVE /NFL /NDL /NJH /NJS /NC /NS /NP >nul 2>&1
rmdir /s /q "!TMP_WORK!" >nul 2>&1

if not exist "!TARGET_PY_DIR!\python.exe" exit /b 1
"!TARGET_PY_DIR!\python.exe" -c "import tkinter" >nul 2>&1
if !ERRORLEVEL! NEQ 0 exit /b 1

echo %C_GREEN%[ OK ]%C_RST% Standalone Python 3.11.18 ^(with tkinter^) ready.
exit /b 0

:DETECT_CORE
set "ROOT_DIR="
set "CORE_FOUND=0"

rem 1. tray_settings.toml core_path
if exist "!TRAY_DIR!\tray\tray_settings.toml" (
    for /f "usebackq tokens=1,* delims==" %%K in ("!TRAY_DIR!\tray\tray_settings.toml") do (
        set "RK=%%~K"
        set "RV=%%~L"
        set "RK=!RK: =!"
        if /i "!RK!"=="core_path" (
            set "RV=!RV:'=!"
            set "RV=!RV:"=!"
            if "!RV:~0,1!"==" " set "RV=!RV:~1!"
            set "RV=!RV:\\=\!"
            if exist "!RV!\hecos\core\version" (
                set "ROOT_DIR=!RV!"
                set "CORE_FOUND=1"
                exit /b 0
            )
        )
    )
)

rem 2. Shared install.toml core_path
set "REG_FILE=%LOCALAPPDATA%\Hecos\install.toml"
if exist "!REG_FILE!" (
    for /f "usebackq tokens=1,* delims==" %%K in ("!REG_FILE!") do (
        set "RK=%%~K"
        set "RV=%%~L"
        set "RK=!RK: =!"
        if /i "!RK!"=="core_path" (
            set "RV=!RV:'=!"
            if "!RV:~0,1!"==" " set "RV=!RV:~1!"
            if exist "!RV!\hecos\core\version" (
                set "ROOT_DIR=!RV!"
                set "CORE_FOUND=1"
                exit /b 0
            )
        )
    )
)

rem 3. Sibling <tray_parent>\Hecos
for %%P in ("!TRAY_DIR!\..") do set "TRAY_PARENT_TMP=%%~fP"
if "!TRAY_PARENT_TMP:~-1!"=="\" set "TRAY_PARENT_TMP=!TRAY_PARENT_TMP:~0,-1!"
if exist "!TRAY_PARENT_TMP!\Hecos\hecos\core\version" (
    set "ROOT_DIR=!TRAY_PARENT_TMP!\Hecos"
    set "CORE_FOUND=1"
    exit /b 0
)

rem 4. Default C:\Hecos
if exist "C:\Hecos\hecos\core\version" (
    set "ROOT_DIR=C:\Hecos"
    set "CORE_FOUND=1"
    exit /b 0
)
exit /b 0

:UPDATE_REGISTRY_FROM_TRAY
set "ENV_TRAY_DIR=!TRAY_DIR!"
set "ENV_CORE_DIR=!ROOT_DIR!"
set "ENV_CORE_FOUND=!CORE_FOUND!"
!PYTHON_CMD! -c "import os, sys; td=os.environ['ENV_TRAY_DIR']; sys.path.insert(0, td); from tray.install_registry import update_registry; pyw=os.path.join(os.path.dirname(sys.executable), 'pythonw.exe'); tpy=pyw if os.path.isfile(pyw) else sys.executable; core=os.environ.get('ENV_CORE_DIR','') if os.environ.get('ENV_CORE_FOUND')=='1' else None; p=update_registry(tray_path=td, tray_python=tpy, core_path=core); print('[ OK ] Registry updated:', p); (core and __import__('tray.config', fromlist=['set_core_path']).set_core_path(core))"
exit /b 0

:VALIDATE_PATH
set "CHECK_PATH=%~1"
set "PATH_STATUS=OK"
set "PATH_MSG=Safe path"
for /f "usebackq tokens=1,* delims==" %%S in (`powershell -NoProfile -NonInteractive -Command "$p=$env:CHECK_PATH; $e=@(); $w=@(); if($p -match '\s'){$e+='contains spaces'}; if($p -cmatch '[\u0080-\uFFFF]'){$e+='contains non-ASCII characters'}; $c=if($p.Length -ge 2 -and $p[1] -eq ':'){$p.Substring(2)}else{$p}; if($c -match '[\x21\x25\x5E\x26\x28\x29\x3D\x3B\x2C\x60\x22\x27]'){$e+='contains unsafe characters'}; if($p.Length -gt 80){$w+='path longer than 80 chars'}; if($p -imatch 'onedrive'){$w+='inside OneDrive'}; if($p -imatch 'program files|\\windows\\'){$w+='inside protected system folder'}; if($p -imatch '\\temp\\|\\tmp\\'){$w+='inside Temp folder'}; if($e.Count -gt 0){'ERR=' + ($e -join '; ')} elseif($w.Count -gt 0){'WARN=' + ($w -join '; ')} else {'OK=Safe path'}"`) do (
    set "PATH_STATUS=%%S"
    set "PATH_MSG=%%T"
)
exit /b 0
