@echo off
setlocal EnableExtensions
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

if exist "%PYTHON_EXE%" goto :python_ok
where python >nul 2>&1
if errorlevel 1 goto :missing_python
:python_ok

set "CHECKLIST_ENV=development"
set "CHECKLIST_FORCE_LOCAL_DB=1"
set "CHECKLIST_ALLOW_SQLITE=1"
set "CHECKLIST_LEGACY_LOCAL_BOOTSTRAP=1"
set "DATABASE_URL="

echo ============================================
echo              SIS MMP - WEB
echo ============================================
echo.
echo Iniciando somente a Web do SIS MMP...
echo API local: %LOCAL_API_URL%
echo Web: %WEB_URL%
echo.

if defined CHECKLIST_DRY_RUN (
    echo [TESTE] A API local e o servidor Web seriam iniciados.
    goto :done
)

call :api_online
if errorlevel 1 (
    echo Iniciando API local...
    start "SIS MMP API Local" /D "%ROOT%\backend" "%PYTHON_EXE%" -u run.py
    call :wait_for_api
    if errorlevel 1 goto :backend_error
) else (
    echo API local ja esta online.
)

call :web_online
if errorlevel 1 (
    echo Iniciando servidor Web...
    start "SIS MMP Web" /D "%ROOT%\web_app" "%PYTHON_EXE%" -m http.server %WEB_PORT% --bind 0.0.0.0
    timeout /t 2 >nul
) else (
    echo Servidor Web ja esta online.
)

echo Abrindo a Web no navegador...
start "" "%WEB_URL%"
echo.
echo SIS MMP Web iniciado. O Desktop nao sera aberto.
goto :done

:api_online
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -Uri '%LOCAL_API_URL%/health' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
exit /b %errorlevel%

:web_online
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -Uri 'http://127.0.0.1:%WEB_PORT%/' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
exit /b %errorlevel%

:wait_for_api
for /l %%N in (1,1,15) do (
    timeout /t 1 >nul
    call :api_online
    if not errorlevel 1 exit /b 0
)
exit /b 1

:missing_files
echo Arquivos principais do sistema nao foram encontrados em:
echo %ROOT%
goto :failed

:missing_python
echo Python nao foi encontrado. Instale Python ou configure .venv\Scripts\python.exe.
goto :failed

:backend_error
echo A API local nao respondeu em %LOCAL_API_URL%.
goto :failed

:failed
echo Corrija o item informado e execute novamente.
pause

:done
popd
exit /b 0
