@echo off
setlocal
cd /d "%~dp0"
title Hecos - Restart Tray Icon
color 0B

echo.
echo  [*] Restoring system tray icon...
echo.

:: Detect PythonW (Windowless) from Hecos Core for now
set PYTHONW_CMD=pythonw
if exist "..\Hecos\venv\Scripts\pythonw.exe" (
    set PYTHONW_CMD="..\Hecos\venv\Scripts\pythonw.exe"
) else if exist "C:\Hecos\venv\Scripts\pythonw.exe" (
    set PYTHONW_CMD="C:\Hecos\venv\Scripts\pythonw.exe"
)

:: Run the tray app in detached mode
start "" %PYTHONW_CMD% -m tray.tray_app

echo  [+] Command sent. The icon will appear in the system tray.
echo  [!] This window will close in 2 seconds...
echo.
timeout /t 2 >nul
exit
