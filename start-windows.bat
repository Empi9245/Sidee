@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel% equ 0 (
  set "SIDEE_PY=py -3"
) else (
  where python >nul 2>&1
  if %errorlevel% neq 0 (
    echo Python 3 was not found. Install Python 3 and try again.
    pause
    exit /b 1
  )
  set "SIDEE_PY=python"
)

net session >nul 2>&1
if %errorlevel% neq 0 (
  echo Requesting Administrator rights for DNS port 53 and HTTPS port 443...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%ComSpec%' -ArgumentList '/c','"%~f0"' -WorkingDirectory '"%~dp0"' -Verb RunAs"
  exit /b
)

%SIDEE_PY% sidee.py
pause
