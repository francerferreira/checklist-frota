@echo off
setlocal enabledelayedexpansion

:: Resolve o diretório base de forma robusta para caminhos com espaços e OneDrive
cd /d "%~dp0"
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "PYTHON_EXE=python"
if exist "%ROOT%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%ROOT%\.venv\Scripts\python.exe"
)

set "API_URL=https://checklist-frota-qngw.onrender.com"
if defined CHECKLIST_API_URL set "API_URL=%CHECKLIST_API_URL%"

echo ============================================
echo   Checklist de Frota - Desktop na Nuvem
echo ============================================
echo.
echo API em uso: %API_URL%
echo Caminho:    %ROOT%
echo Python:     %PYTHON_EXE%
echo.
echo Iniciando aplicativo Desktop...

:: Inicia o sistema tratando corretamente as aspas para caminhos com espaços
start "Checklist Desktop" cmd /k "set "CHECKLIST_API_URL=%API_URL%" && cd /d "%ROOT%\desktop" && "%PYTHON_EXE%" main.py"

exit
