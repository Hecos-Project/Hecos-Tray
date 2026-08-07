@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title HECOS - SETUP WIZARD
color 0B

:: Determine ROOT directory dynamically
set "ROOT_DIR=C:\Hecos"
set "TRAY_DIR="
set "TRAY_WARN="

if exist "%~dp0..\..\..\hecos\core\version" (
    :: Running from C:\Hecos\scripts\windows\setup\
    pushd "%~dp0..\..\.."
    set "ROOT_DIR=!CD!"
    popd
) else if exist "%~dp0..\Hecos\hecos\core\version" (
    :: Running from C:\Hecos-Tray variant folder
    pushd "%~dp0..\Hecos"
    set "ROOT_DIR=!CD!"
    popd
)

:: Smart Tray detection: exact match first, then wildcard for versioned folders like Hecos-Tray-1.5.3
if exist "C:\Hecos-Tray\tray\version" (
    set "TRAY_DIR=C:\Hecos-Tray"
) else (
    for /d %%D in ("C:\Hecos-Tray-*") do (
        if exist "%%D\tray\version" (
            if "!TRAY_DIR!"=="" (
                set "TRAY_DIR=%%D"
                set "TRAY_WARN=1"
            )
        )
    )
)

echo ==============================================================================
echo                          HECOS SETUP WIZARD
echo ==============================================================================
echo.

:: 1. Check Folders
echo [SYSTEM CHECK]
if exist "%ROOT_DIR%\hecos\core\version" (
    echo [OK] Core found at: %ROOT_DIR%
) else (
    echo [!] Core NOT found at: %ROOT_DIR%
)

if not "!TRAY_DIR!"=="" (
    echo [OK] Tray found at: !TRAY_DIR!
    if "!TRAY_WARN!"=="1" (
        echo.
        echo  [!] WARNING: The Tray folder has a version suffix in its name.
        echo  [!] For Hecos to work correctly, please rename the folder:
        echo  [!]   FROM: !TRAY_DIR!
        echo  [!]   TO:   C:\Hecos-Tray
    )
) else (
    echo [!] Tray NOT found in C:\ drive.
    echo  [!] Please make sure the Hecos-Tray folder is placed directly in C:\
    echo  [!] It should be at:  C:\Hecos-Tray
)
echo.

:: 2. Python Detection
echo [PYTHON DETECTION]
set PYTHON_CMD=
set PYTHON_LOC=

if exist "%ROOT_DIR%\python_env\python.exe" (
    set PYTHON_CMD="%ROOT_DIR%\python_env\python.exe"
    set PYTHON_LOC="Portable Environment (%ROOT_DIR%\python_env)"
) else if exist "%ROOT_DIR%\venv\Scripts\python.exe" (
    set PYTHON_CMD="%ROOT_DIR%\venv\Scripts\python.exe"
    set PYTHON_LOC="Virtual Environment (%ROOT_DIR%\venv)"
) else (
    :: Check global system Python
    python --version >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        set PYTHON_CMD=python
        set PYTHON_LOC="Global System Path"
    )
)

if not "%PYTHON_CMD%"=="" (
    echo [OK] Python found: !PYTHON_LOC!
    !PYTHON_CMD! --version
    echo.
    echo [*] Python is already installed. Proceeding to Setup...
    timeout /t 2 >nul
    goto LAUNCH
) else (
    echo [!] Python is NOT installed or not found.
    echo.
    echo In order to run Hecos Core or the Setup Wizard, you need Python.
    echo You can install a self-contained Portable Python environment now.
    echo.
    echo  1. Install Portable Python ^(Recommended^)
    echo  2. Exit
    echo.
    set /p CH="Select an option (1-2): "
    if "!CH!"=="1" goto INSTALL_PYTHON
    if "!CH!"=="2" exit
    exit
)

:INSTALL_PYTHON
echo.
echo ==============================================================================
echo                DOWNLOADING PORTABLE PYTHON ENVIRONMENT
echo ==============================================================================
set PYTHON_VERSION=3.11.9
set PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-embed-amd64.zip
set PYTHON_DIR=%ROOT_DIR%\python_env

echo [*] Downloading Portable Python %PYTHON_VERSION%...
mkdir "%PYTHON_DIR%" >nul 2>&1
powershell -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile 'python.zip'"

echo [*] Extracting Python...
powershell -Command "Expand-Archive -Path 'python.zip' -DestinationPath '%PYTHON_DIR%' -Force"
del python.zip

echo [*] Configuring python._pth to enable site-packages...
for %%f in ("%PYTHON_DIR%\*._pth") do set PTH_FILE=%%f
powershell -Command "(Get-Content '!PTH_FILE!') -replace '#import site', 'import site' | Set-Content '!PTH_FILE!'"

echo [*] Downloading get-pip.py...
powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%PYTHON_DIR%\get-pip.py'"

echo [*] Installing PIP...
"%PYTHON_DIR%\python.exe" "%PYTHON_DIR%\get-pip.py"

echo.
echo [*] Installing Hecos dependencies...
if exist "%ROOT_DIR%\requirements.txt" (
    "%PYTHON_DIR%\Scripts\pip.exe" install --upgrade pip
    "%PYTHON_DIR%\Scripts\pip.exe" install -r "%ROOT_DIR%\requirements.txt"
) else (
    echo [!] requirements.txt not found! Skipping dependencies.
)

set PYTHON_CMD="%PYTHON_DIR%\python.exe"
echo.
echo [SUCCESS] Portable Python Installed!
timeout /t 2 >nul
goto LAUNCH



:LAUNCH
echo.
echo ==============================================================================
echo                          STARTING INTERFACE
echo ==============================================================================
if exist "%ROOT_DIR%\hecos\setup_wizard.py" (
    echo [*] Launching Core Setup Wizard...
    cd /d "%ROOT_DIR%"
    %PYTHON_CMD% "hecos\setup_wizard.py"
    goto END
)

:: Core is not downloaded yet — offer to download it
echo.
echo  [!] Hecos Core is not installed on this machine yet.
echo.
echo  The Core is the AI engine that powers Hecos. It needs to be
echo  downloaded from GitHub before setup can continue.
echo.
echo  ============================================================
echo   DOWNLOAD HECOS CORE
echo  ============================================================
echo.
echo  The download is approximately 50-100 MB.
echo  It will be extracted to: %ROOT_DIR%
echo.
echo   1. Download Core from GitHub (Recommended)
echo   2. Skip and launch Tray only
echo   3. Exit
echo.
set /p DL_CHOICE="Select an option (1-3): "

if "!DL_CHOICE!"=="1" goto DOWNLOAD_CORE
if "!DL_CHOICE!"=="2" goto LAUNCH_TRAY_ONLY
if "!DL_CHOICE!"=="3" exit
exit


:DOWNLOAD_CORE
echo.
echo ==============================================================================
echo                     DOWNLOADING HECOS CORE FROM GITHUB
echo ==============================================================================
echo.

:: Fetch the latest release zipball URL via GitHub API
set "GH_API_URL=https://api.github.com/repos/Hecos-Project/Hecos/releases/latest"
set "TEMP_JSON=%TEMP%\hecos_release.json"
set "TEMP_ZIP=%TEMP%\hecos_core.zip"
set "TEMP_EXTRACT=%TEMP%\hecos_extract"

echo [*] Fetching latest release info from GitHub...
powershell -Command "try { Invoke-RestMethod -Uri '%GH_API_URL%' -UseBasicParsing | ConvertTo-Json | Out-File -Encoding utf8 '%TEMP_JSON%'; Write-Host '[OK] Release info fetched.' } catch { Write-Host '[ERROR]' $_.Exception.Message; exit 1 }"
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo  [!] Failed to connect to GitHub. Please check your internet connection.
    echo  [!] You can manually download the Core from:
    echo  [!]   https://github.com/Hecos-Project/Hecos/releases/latest
    echo  [!]   and extract it to: %ROOT_DIR%
    echo.
    pause
    goto END
)

echo [*] Parsing download URL...
for /f "usebackq tokens=*" %%U in (`powershell -Command "(Get-Content '%TEMP_JSON%' | ConvertFrom-Json).zipball_url"`) do set "ZIPBALL_URL=%%U"

if "!ZIPBALL_URL!"=="" (
    echo.
    echo  [!] Could not determine download URL. Please check your internet connection
    echo  [!] or download manually from: https://github.com/Hecos-Project/Hecos/releases/latest
    pause
    goto END
)

echo [*] Downloading from: !ZIPBALL_URL!
echo [*] This may take a moment...
powershell -Command "try { Invoke-WebRequest -Uri '!ZIPBALL_URL!' -OutFile '%TEMP_ZIP%' -UseBasicParsing; Write-Host '[OK] Download complete.' } catch { Write-Host '[ERROR]' $_.Exception.Message; exit 1 }"
if !ERRORLEVEL! NEQ 0 (
    echo  [!] Download failed. Please check your internet connection.
    pause
    goto END
)

echo.
echo [*] Extracting files to: %ROOT_DIR%
if exist "%TEMP_EXTRACT%" rmdir /s /q "%TEMP_EXTRACT%"
mkdir "%TEMP_EXTRACT%" 2>nul
powershell -Command "Expand-Archive -Path '%TEMP_ZIP%' -DestinationPath '%TEMP_EXTRACT%' -Force"

:: GitHub zipballs extract into a single subfolder like Hecos-Project-Hecos-abc123
:: Move its contents directly into ROOT_DIR
echo [*] Installing to %ROOT_DIR%...
mkdir "%ROOT_DIR%" 2>nul
for /d %%D in ("%TEMP_EXTRACT%\*") do (
    robocopy "%%D" "%ROOT_DIR%" /e /move /nfl /ndl /njh /njs >nul 2>&1
)

:: Cleanup temp files
del "%TEMP_JSON%" >nul 2>&1
del "%TEMP_ZIP%" >nul 2>&1
rmdir /s /q "%TEMP_EXTRACT%" >nul 2>&1

if exist "%ROOT_DIR%\hecos\core\version" (
    echo.
    echo  [+] Hecos Core downloaded and installed successfully!
    echo.
    timeout /t 2 >nul
    goto LAUNCH
) else (
    echo.
    echo  [!] WARNING: Extraction completed but Core files were not found in:
    echo  [!]   %ROOT_DIR%
    echo  [!] Please try extracting the ZIP manually from GitHub.
    pause
    goto END
)


:LAUNCH_TRAY_ONLY
echo.
if not "!TRAY_DIR!"=="" (
    if exist "!TRAY_DIR!\START_HECOS_TRAY_WIN.bat" (
        echo [*] Launching Hecos Tray. Use the Dashboard to download the Core later.
        timeout /t 2 >nul
        call "!TRAY_DIR!\START_HECOS_TRAY_WIN.bat"
        goto END
    )
)
echo [!] Tray not found either. Cannot proceed.
pause

:END
exit
