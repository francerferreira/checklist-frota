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
set "REMOTE_API_URL=https://checklist-frota-qngw.onrender.com"
set "LOCAL_API_URL=http://127.0.0.1:5000"
set "WEB_PORT=5500"
set "WEB_LOCAL_URL=http://127.0.0.1:%WEB_PORT%"
set "API_URL=%REMOTE_API_URL%"
if defined CHECKLIST_API_URL set "API_URL=%CHECKLIST_API_URL%"

if not exist "%ROOT%\desktop\main.py" goto :missing_files
if not exist "%ROOT%\web_app\index.html" goto :missing_files

set "PYTHON_RUN="
if exist "%ROOT%\.venv\Scripts\python.exe" set "PYTHON_RUN="%ROOT%\.venv\Scripts\python.exe""
if not defined PYTHON_RUN (
    where py >nul 2>&1
    if not errorlevel 1 set "PYTHON_RUN=py -3"
)
if not defined PYTHON_RUN (
    where python >nul 2>&1
    if not errorlevel 1 set "PYTHON_RUN=python"
)
if not defined PYTHON_RUN goto :missing_python

if not defined CHECKLIST_MODE (
    echo ============================================
    echo       CHECKLIST DE FROTA - ENTRADA
    echo ============================================
    echo.
    echo [1] Desktop - API em nuvem
    echo [2] Desktop - modo local de contingencia
    echo [3] Web Mobile - API em nuvem
    echo [4] Web Mobile - modo local de contingencia
    echo [0] Sair
    echo.
    choice /c 12340 /n /m "Escolha uma opcao: "
    if errorlevel 5 goto :done
    if errorlevel 4 goto :web_local
    if errorlevel 3 goto :web_cloud
    if errorlevel 2 goto :desktop_local
    goto :desktop_cloud
)

if /I "%CHECKLIST_MODE%"=="DESKTOP_LOCAL" goto :desktop_local
if /I "%CHECKLIST_MODE%"=="WEB_LOCAL" goto :web_local
if /I "%CHECKLIST_MODE%"=="WEB_CLOUD" goto :web_cloud
goto :desktop_cloud

:desktop_cloud
set "API_URL=%REMOTE_API_URL%"
if defined CHECKLIST_API_URL set "API_URL=%CHECKLIST_API_URL%"
echo.
echo Verificando API em nuvem: %API_URL%
call :probe_api "%API_URL%"
if errorlevel 1 (
    echo.
    echo A API em nuvem nao respondeu no tempo esperado.
    echo O modo local nao usa os dados da nuvem; escolha conscientemente a contingencia.
    if defined CHECKLIST_DRY_RUN goto :failed_probe
    choice /c LN /n /m "Abrir modo Local ou Encerrar? [L/N]: "
    if errorlevel 2 goto :done
    goto :desktop_local
)
echo API em nuvem respondendo.
if defined CHECKLIST_DRY_RUN goto :dry_run_success
start "Checklist Desktop" cmd /c "set ""CHECKLIST_API_URL=%API_URL%""&& cd /d ""%ROOT%\desktop""&& %PYTHON_RUN% main.py"
goto :done

:desktop_local
echo.
echo Iniciando Desktop em modo local de contingencia...
call :start_local_backend
if errorlevel 1 goto :startup_error
if defined CHECKLIST_DRY_RUN goto :dry_run_success
start "Checklist Desktop Local" cmd /c "set ""CHECKLIST_API_URL=%LOCAL_API_URL%""&& set ""CHECKLIST_FORCE_LOCAL_DB=1""&& set ""DATABASE_URL=""&& cd /d ""%ROOT%\desktop""&& %PYTHON_RUN% main.py"
goto :done

:web_cloud
set "API_URL=%REMOTE_API_URL%"
if defined CHECKLIST_API_URL set "API_URL=%CHECKLIST_API_URL%"
echo.
echo Verificando API em nuvem: %API_URL%
call :probe_api "%API_URL%"
if errorlevel 1 (
    echo A API em nuvem nao respondeu. O Web Mobile nao sera aberto com falso status online.
    goto :startup_error
)
if defined CHECKLIST_DRY_RUN goto :dry_run_success
start "Checklist Web Mobile" cmd /c "cd /d ""%ROOT%\web_app""&& %PYTHON_RUN% -m http.server %WEB_PORT% --bind 0.0.0.0"
timeout /t 2 >nul
start "" "%WEB_LOCAL_URL%/?v=20260713-02"
goto :done

:web_local
echo.
echo Iniciando Web Mobile em modo local de contingencia...
call :start_local_backend
if errorlevel 1 goto :startup_error
if defined CHECKLIST_DRY_RUN goto :dry_run_success
start "Checklist Web Mobile Local" cmd /c "cd /d ""%ROOT%\web_app""&& %PYTHON_RUN% -m http.server %WEB_PORT% --bind 0.0.0.0"
timeout /t 2 >nul
start "" "%WEB_LOCAL_URL%/?v=20260713-02"
goto :done

:probe_api
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -Uri '%~1/health' -UseBasicParsing -TimeoutSec 12; if ($r.StatusCode -eq 200) { exit 0 }; exit 1 } catch { exit 1 }"
exit /b %errorlevel%

:start_local_backend
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -Uri '%LOCAL_API_URL%/health' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if not errorlevel 1 (
    echo Backend local ja esta respondendo.
    exit /b 0
)
if defined CHECKLIST_DRY_RUN (
    echo [TESTE] Backend local seria iniciado com SQLite local.
    exit /b 0
)
start "Checklist Backend Local" powershell -NoExit -ExecutionPolicy Bypass -Command "$env:CHECKLIST_FORCE_LOCAL_DB='1'; $env:DATABASE_URL=''; Set-Location -LiteralPath '%ROOT%\backend'; %PYTHON_RUN% -u run.py"
echo Aguardando backend local...
for /l %%N in (1,1,12) do (
    timeout /t 1 >nul
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -Uri '%LOCAL_API_URL%/health' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
    if not errorlevel 1 (
        echo Backend local respondendo.
        exit /b 0
    )
)
echo Backend local nao respondeu.
exit /b 1

:dry_run_success
echo [TESTE] Entrada validada sem abrir janelas.
goto :done

:failed_probe
echo [TESTE] API indisponivel; nenhuma janela sera aberta.
goto :done

:missing_files
echo Arquivos principais do sistema nao foram encontrados em:
echo %ROOT%
goto :startup_error

:missing_python
echo Python nao foi encontrado. Instale Python ou configure .venv\Scripts\python.exe.
goto :startup_error

:startup_error
echo.
echo Entrada nao concluida. Corrija o item informado e tente novamente.
pause

:done
popd
exit /b 0
