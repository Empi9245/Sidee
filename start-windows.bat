@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel% equ 0 (
  set "SIDEE_PY=py -3"
) else (
  where python >nul 2>&1
  if %errorlevel% equ 0 (
    set "SIDEE_PY=python"
  ) else if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
    set "SIDEE_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
  ) else (
    echo Python 3 was not found. Install Python 3 and try again.
    pause
    exit /b 1
  )
)

net session >nul 2>&1
if %errorlevel% neq 0 (
  echo Requesting Administrator rights for DNS port 53 and HTTP/HTTPS ports 80, 443 and 8080...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%ComSpec%' -ArgumentList '/c','"%~f0"' -WorkingDirectory '"%~dp0"' -Verb RunAs"
  exit /b
)

netsh advfirewall firewall add rule name="Sidee DNS UDP 53" dir=in action=allow protocol=UDP localport=53 profile=private >nul 2>&1
netsh advfirewall firewall add rule name="Sidee HTTPS TCP 443" dir=in action=allow protocol=TCP localport=443 profile=private >nul 2>&1
netsh advfirewall firewall add rule name="Sidee HTTP TCP 80" dir=in action=allow protocol=TCP localport=80 profile=private >nul 2>&1
netsh advfirewall firewall add rule name="Sidee HTTP TCP 8080" dir=in action=allow protocol=TCP localport=8080 profile=private >nul 2>&1

echo Closing any previous Sidee Python instance...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match '(^|[\\/ ])sidee\.py([ "'']|$)' }; foreach ($p in $procs) { try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop; Write-Host ('Stopped stale Sidee PID ' + $p.ProcessId) } catch {} }"
timeout /t 1 /nobreak >nul

where git >nul 2>&1
if %errorlevel% equ 0 (
  for /f %%H in ('git rev-parse HEAD 2^>nul') do echo Sidee Git HEAD: %%H
)

%SIDEE_PY% sidee.py
pause
