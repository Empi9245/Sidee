@echo off
setlocal
cd /d "%~dp0"
net session >nul 2>&1
if %errorlevel% neq 0 (
  echo Requesting Administrator rights for DNS/HTTPS ports...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'python' -ArgumentList '"%~dp0sidee.py"' -WorkingDirectory '"%~dp0"' -Verb RunAs"
  exit /b
)
python sidee.py
pause
