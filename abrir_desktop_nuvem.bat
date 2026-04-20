@echo off
setlocal
chcp 65001 >nul

pushd "%~dp0"
set "ROOT=%CD%"
if not defined CHECKLIST_API_URL set "CHECKLIST_API_URL=https://checklist-frota-qngw.onrender.com"

echo ============================================
echo   Checklist de Frota - Desktop na Nuvem
echo ============================================
echo.
echo API em uso:
echo %CHECKLIST_API_URL%
echo.
echo Abrindo apenas o desktop. Nenhum servico local sera iniciado.
echo.

start "Checklist Desktop" cmd /c "set ""CHECKLIST_API_URL=%CHECKLIST_API_URL%"" && cd /d ""%ROOT%\desktop"" && python main.py"

echo Desktop iniciado.
echo Se quiser voltar ao ambiente local, use a conexao avancada no login.
echo.
pause
