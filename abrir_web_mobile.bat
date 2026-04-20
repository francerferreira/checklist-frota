@echo off
setlocal
chcp 65001 >nul

pushd "%~dp0"
set "ROOT=%CD%"
set "WEB_PORT=5500"
set "WEB_URL=http://127.0.0.1:%WEB_PORT%"
set "WEB_OPEN_URL=%WEB_URL%/?v=20260420-02"
if not defined CHECKLIST_API_URL set "CHECKLIST_API_URL=https://checklist-frota-qngw.onrender.com"
echo API padrao do Web Mobile: %CHECKLIST_API_URL%
echo.

echo ============================================
echo   Checklist de Frota - Web Mobile
echo ============================================
echo.

for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$root = Get-ChildItem $env:USERPROFILE -Directory | Where-Object { $_.Name -like 'OneDrive*' -and $_.Name -like '*Chibat*' } | Select-Object -First 1 -ExpandProperty FullName; if (-not $root) { exit 1 }; $pg = Join-Path $root 'Documentos\Postgres\pgsql'; if (Test-Path $pg) { Write-Output $pg } else { exit 1 }"`) do set "PGROOT=%%I"

if not defined PGROOT (
    echo Nao foi possivel localizar o PostgreSQL portatil em Documentos\Postgres\pgsql.
    echo Abra primeiro pelo arquivo abrir_checklist_frota.bat ou verifique a pasta do PostgreSQL.
    pause
    exit /b 1
)

set "PGBIN=%PGROOT%\bin"
set "PGDATA=%PGROOT%\data"
set "PGLOG=%PGROOT%\postgres.log"

echo [1/4] Verificando PostgreSQL...
"%PGBIN%\pg_isready.exe" -h 127.0.0.1 -p 5432 >nul 2>&1
if errorlevel 1 (
    echo PostgreSQL parado. Iniciando na porta 5432...
    "%PGBIN%\pg_ctl.exe" -D "%PGDATA%" -l "%PGLOG%" start
    if errorlevel 1 (
        echo Falha ao iniciar PostgreSQL.
        pause
        exit /b 1
    )
    timeout /t 3 >nul
) else (
    echo PostgreSQL ja esta ativo.
)

echo.
echo [2/4] Verificando backend Flask...
echo %CHECKLIST_API_URL% | findstr /I "127.0.0.1 localhost" >nul
if not errorlevel 1 (
    powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'http://127.0.0.1:5000/' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
    if errorlevel 1 (
        echo Backend nao respondeu em http://127.0.0.1:5000.
        echo Iniciando backend em nova janela...
        start "Checklist Backend" powershell -NoExit -Command "Set-Location -LiteralPath '%ROOT%\backend'; python -u run.py"
        timeout /t 15 >nul
    ) else (
        echo Backend online em http://127.0.0.1:5000.
    )
) else (
    echo Rodando em nuvem. Nao vou iniciar backend local.
    echo API: %CHECKLIST_API_URL%
)

echo.
echo [3/4] Verificando servidor Web Mobile na porta %WEB_PORT%...
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%WEB_URL%' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
    echo Servidor Web Mobile parado. Iniciando em nova janela...
    start "Checklist Web Mobile" powershell -NoExit -Command "Set-Location -LiteralPath '%ROOT%\web_app'; python -m http.server %WEB_PORT% --bind 0.0.0.0"
    timeout /t 3 >nul
) else (
    echo Web Mobile ja esta online em %WEB_URL%.
)

for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$ip = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' } | Sort-Object InterfaceMetric | Select-Object -First 1 -ExpandProperty IPAddress; if ($ip) { Write-Output $ip }"`) do set "LOCAL_IP=%%I"

echo.
echo [4/4] Abrindo navegador...
start "" "%WEB_OPEN_URL%"

echo.
echo Web Mobile aberto no computador:
echo %WEB_OPEN_URL%
echo.
if defined LOCAL_IP (
    echo Para abrir no celular na mesma rede Wi-Fi:
    echo http://%LOCAL_IP%:%WEB_PORT%/?v=20260420-02
    echo.
)
echo Na tela de login do Web Mobile, use a API:
echo %CHECKLIST_API_URL%
echo.
pause
