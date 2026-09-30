@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if not errorlevel 1 goto use_py
where python >nul 2>&1
if not errorlevel 1 goto use_python
if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" goto use_bundled
echo Python 3 non trovato.
pause
exit /b 1

:use_py
set "SIDEE_PY=py -3"
goto launch
:use_python
set "SIDEE_PY=python"
goto launch
:use_bundled
set SIDEE_PY="%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

:launch
echo Sidee - raccolta isolata
echo TV sull'hotspot di questo PC: DNS primario 192.168.137.1.
echo Sulla TV apri http://vidaahub.com e premi Raccogli una volta.
%SIDEE_PY% sidee.py --bridge-source-check --check-port 80
pause
