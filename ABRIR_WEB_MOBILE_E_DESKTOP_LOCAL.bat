@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

pushd "%~dp0" >nul 2>&1
if errorlevel 1 (
    echo Nao foi possivel acessar a pasta do sistema.
    pause
    exit /b 1
)

set "ROOT=%CD%"
set "LOCAL_API_URL=http://127.0.0.1:5000"
set "WEB_PORT=5500"
set "WEB_URL=http://127.0.0.1:%WEB_PORT%/?api=%LOCAL_API_URL%"
set "PYTHON_EXE=python"
if exist "%ROOT%\.venv\Scripts\python.exe" set "PYTHON_EXE=%ROOT%\.venv\Scripts\python.exe"

if not exist "%ROOT%\backend\run.py" goto :missing_files
if not exist "%ROOT%\web_app\index.html" goto :missing_files
if not exist "%ROOT%\desktop\main.py" goto :missing_files

echo ============================================
echo  CHECKLIST DE FROTA - WEB MOBILE E DESKTOP
echo ============================================
echo.
echo API local: %LOCAL_API_URL%
echo Web Mobile: %WEB_URL%
echo.

if defined CHECKLIST_DRY_RUN (
    echo [TESTE] Backend SQLite local seria iniciado se necessario.
    echo [TESTE] Web Mobile, navegador e Desktop seriam abertos.
    goto :done
)

set "CHECKLIST_ENV=development"
set "CHECKLIST_FORCE_LOCAL_DB=1"
set "CHECKLIST_ALLOW_SQLITE=1"
set "CHECKLIST_LEGACY_LOCAL_BOOTSTRAP=1"
set "DATABASE_URL="

call :api_online
if errorlevel 1 (
    echo [1/4] Iniciando backend local com SQLite...
    start "Checklist Backend Local" /D "%ROOT%\backend" "%PYTHON_EXE%" -u run.py
    call :wait_for_api
    if errorlevel 1 goto :backend_error
) else (
    echo [1/4] Backend local ja esta online.
)

call :web_online
if errorlevel 1 (
    echo [2/4] Iniciando servidor do Web Mobile...
    start "Checklist Web Mobile" /D "%ROOT%\web_app" "%PYTHON_EXE%" -m http.server %WEB_PORT% --bind 0.0.0.0
    timeout /t 2 >nul
) else (
    echo [2/4] Servidor do Web Mobile ja esta online.
)

echo [3/4] Abrindo Web Mobile no navegador...
start "" "%WEB_URL%"

echo [4/4] Abrindo aplicativo Desktop local...
set "CHECKLIST_API_URL=%LOCAL_API_URL%"
start "Checklist Desktop Local" /D "%ROOT%\desktop" "%PYTHON_EXE%" main.py

echo.
echo Web Mobile e Desktop foram iniciados usando a mesma base SQLite local.
goto :done

:api_online
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%LOCAL_API_URL%/health' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
exit /b %errorlevel%

:web_online
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'http://127.0.0.1:%WEB_PORT%/' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
exit /b %errorlevel%

:wait_for_api
for /l %%N in (1,1,15) do (
    timeout /t 1 >nul
    call :api_online
    if not errorlevel 1 exit /b 0
)
exit /b 1

:missing_files
echo Arquivos principais nao foram encontrados em:
echo %ROOT%
goto :failed

:backend_error
echo O backend local nao respondeu em %LOCAL_API_URL%.
goto :failed

:failed
echo Corrija o item informado e execute novamente.
pause
popd
exit /b 1

:done
popd
exit /b 0
