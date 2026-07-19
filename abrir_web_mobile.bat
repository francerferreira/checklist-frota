@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

pushd "%~dp0"
set "ROOT=%CD%"
set "WEB_PORT=5500"
set "WEB_URL=http://127.0.0.1:%WEB_PORT%"
if not defined CHECKLIST_API_URL set "CHECKLIST_API_URL=https://checklist-frota-qngw.onrender.com"
set "USE_LOCAL_API=0"
echo API padrao do Web Mobile: %CHECKLIST_API_URL%
echo.

echo ============================================
echo   Checklist de Frota - Web Mobile
echo ============================================
echo.

echo [1/4] Verificando API na nuvem...
echo %CHECKLIST_API_URL% | findstr /I "127.0.0.1 localhost" >nul
if not errorlevel 1 set "USE_LOCAL_API=1"
if "!USE_LOCAL_API!"=="0" (
    powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%CHECKLIST_API_URL%/health' -UseBasicParsing -TimeoutSec 8 | Out-Null; exit 0 } catch { exit 1 }"
    if errorlevel 1 (
        echo API na nuvem indisponivel. Usando backend local.
        set "USE_LOCAL_API=1"
    ) else (
        echo API na nuvem respondeu.
    )
)

echo.
echo [2/4] Verificando backend Flask...
if "!USE_LOCAL_API!"=="1" (
    set "CHECKLIST_API_URL=http://127.0.0.1:5000"
    powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'http://127.0.0.1:5000/' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
    if errorlevel 1 (
        echo Backend nao respondeu em http://127.0.0.1:5000.
        echo Iniciando backend em nova janela...
        start "Checklist Backend" powershell -NoExit -Command "$env:CHECKLIST_FORCE_LOCAL_DB='1'; $env:DATABASE_URL=''; Set-Location -LiteralPath '%ROOT%\backend'; python -u run.py"
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
if "!USE_LOCAL_API!"=="1" if defined LOCAL_IP set "CHECKLIST_API_URL=http://!LOCAL_IP!:5000"
set "WEB_OPEN_URL=%WEB_URL%/?v=20260719-01^&api=!CHECKLIST_API_URL!"

echo.
echo [4/4] Abrindo navegador...
start "" "%WEB_OPEN_URL%"

echo.
echo Web Mobile aberto no computador:
echo %WEB_OPEN_URL%
echo.
if defined LOCAL_IP (
    echo Para abrir no celular na mesma rede Wi-Fi:
    echo http://!LOCAL_IP!:%WEB_PORT%/?v=20260719-01^&api=!CHECKLIST_API_URL!
    echo.
)
echo Na tela de login do Web Mobile, use a API:
echo %CHECKLIST_API_URL%
echo.
pause

