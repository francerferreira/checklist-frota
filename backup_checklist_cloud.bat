@echo off
setlocal
chcp 65001 >nul

set "API_URL=https://checklist-api.onrender.com"
set "LOGIN=admin"
set "SENHA=123456"
set "DESTINO=%USERPROFILE%\OneDrive - Chibatao Navegacao e Comercio Ltda\BACKUPS_CHECKLIST"

echo ============================================
echo   Backup Checklist Live - Nuvem
echo ============================================
echo.
echo Ajuste API_URL neste arquivo depois que o backend estiver no Render.
echo API atual: %API_URL%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0backup_checklist_cloud.ps1" -ApiUrl "%API_URL%" -Login "%LOGIN%" -Senha "%SENHA%" -Destino "%DESTINO%"
echo.
pause
