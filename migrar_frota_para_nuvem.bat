@echo off
setlocal
title Migracao da Frota para a Nuvem

echo =====================================================
echo   Checklist de Frota - Migracao para Nuvem
echo =====================================================
echo.

python "%~dp0tools\migrate_vehicles_to_cloud.py"
set EXIT_CODE=%ERRORLEVEL%

echo.
if %EXIT_CODE% EQU 0 (
  echo Migracao concluida.
) else (
  echo Migracao falhou com codigo %EXIT_CODE%.
)
echo.
pause
exit /b %EXIT_CODE%

