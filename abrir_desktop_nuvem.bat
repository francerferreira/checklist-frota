@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "PYTHON_EXE=python"
if exist "%ROOT%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%ROOT%\.venv\Scripts\python.exe"
)

set "REMOTE_API_URL=https://checklist-frota-qngw.onrender.com"
set "LOCAL_API_URL=http://127.0.0.1:5000"
set "API_URL=%REMOTE_API_URL%"
if defined CHECKLIST_API_URL set "API_URL=%CHECKLIST_API_URL%"

echo ============================================
echo   Checklist de Frota - Desktop
echo ============================================
echo.
echo API solicitada: %API_URL%
echo Caminho:        %ROOT%
echo Python:         %PYTHON_EXE%
echo.

if /I not "%API_URL%"=="%LOCAL_API_URL%" (
    echo Validando API remota...
    powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri '%API_URL%/health' -UseBasicParsing -TimeoutSec 8; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 } else { exit 1 } } catch { exit 1 }"
    if errorlevel 1 (
        echo API remota indisponivel. Vou abrir no modo local.
        set "API_URL=%LOCAL_API_URL%"
    )
)

if /I "%API_URL%"=="%LOCAL_API_URL%" (
    echo Verificando backend local...
    powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%LOCAL_API_URL%/' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
    if errorlevel 1 (
        echo Iniciando backend local...
        start "Checklist Backend Local" cmd /k "set ""CHECKLIST_FORCE_LOCAL_DB=1"" && set ""DATABASE_URL="" && cd /d ""%ROOT%\backend"" && ""%PYTHON_EXE%"" run.py"
        timeout /t 5 >nul
    ) else (
        echo Backend local ja esta online.
    )
)

echo.
echo Iniciando aplicativo Desktop...
start "Checklist Desktop" cmd /k "set ""CHECKLIST_API_URL=%API_URL%"" && if /I ""%API_URL%""==""%LOCAL_API_URL%"" set ""CHECKLIST_FORCE_LOCAL_DB=1"" && if /I ""%API_URL%""==""%LOCAL_API_URL%"" set ""DATABASE_URL="" && cd /d ""%ROOT%\desktop"" && ""%PYTHON_EXE%"" main.py"

exit
