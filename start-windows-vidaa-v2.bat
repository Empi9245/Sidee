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
set "SIDEE_V2_PY=py -3"
goto launch
:use_python
set "SIDEE_V2_PY=python"
goto launch
:use_bundled
set SIDEE_V2_PY="%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
:launch
echo Sidee - installazione VIDAA v2
echo Avvia il ricevitore su HTTP/80. Ogni fase parte solo dal pulsante sulla TV.
%SIDEE_V2_PY% sidee.py --vidaa-install-v2 --check-port 80
pause
