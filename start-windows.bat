@echo off
setlocal
cd /d "%~dp0"
title Sidee
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-windows.ps1" %*
if errorlevel 1 (
    echo.
    echo Sidee could not start. Read the message above, then try again.
    pause
    exit /b 1
)
