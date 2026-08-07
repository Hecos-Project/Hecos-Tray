@echo off
setlocal enabledelayedexpansion

echo Testing goto inside block...
if "1"=="1" (
    echo Inside block
    set /p CHOICE="Press 1: "
    if "!CHOICE!"=="1" goto MY_LABEL
    echo Exiting block normally
    exit /b
)

:MY_LABEL
echo Successfully jumped to MY_LABEL!
pause
