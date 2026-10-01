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
echo Sidee - verifica VIDAA v2 in sola lettura
echo Diagnostica browser e osservazioni manuali. Nessuna installazione automatica.
%SIDEE_V2_PY% sidee.py --vidaa-check-v2 --check-port 8083
pause
