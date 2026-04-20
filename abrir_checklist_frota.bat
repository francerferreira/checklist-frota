@echo off
setlocal
chcp 65001 >nul

pushd "%~dp0"
set "ROOT=%CD%"

for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$root = Get-ChildItem $env:USERPROFILE -Directory | Where-Object { $_.Name -like 'OneDrive*' -and $_.Name -like '*Chibat*' } | Select-Object -First 1 -ExpandProperty FullName; if (-not $root) { exit 1 }; $pg = Join-Path $root 'Documentos\Postgres\pgsql'; if (Test-Path $pg) { Write-Output $pg } else { exit 1 }"`) do set "PGROOT=%%I"

if not defined PGROOT (
    echo Nao foi possivel localizar o PostgreSQL portatil em Documentos\Postgres\pgsql.
    pause
    exit /b 1
)

set "PGBIN=%PGROOT%\bin"
set "PGDATA=%PGROOT%\data"
set "PGLOG=%PGROOT%\postgres.log"

echo ============================================
echo   Checklist de Frota Portuaria
echo ============================================
echo.

echo [1/3] Verificando PostgreSQL...
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
echo [2/3] Verificando backend Flask...
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'http://127.0.0.1:5000/' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
    echo Backend parado. Iniciando em nova janela...
    start "Checklist Backend" cmd /k "cd /d ""%ROOT%\backend"" && python run.py"
    timeout /t 5 >nul
) else (
    echo Backend ja esta online em http://127.0.0.1:5000
)

echo.
echo [3/3] Abrindo aplicativo desktop...
start "Checklist Desktop" cmd /c "cd /d ""%ROOT%\desktop"" && python main.py"

echo.
echo Sistema iniciado.
echo Login padrao: admin
echo Senha padrao: 123456
echo.
pause
