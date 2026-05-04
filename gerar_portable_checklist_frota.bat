@echo off
setlocal
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File ".\tools\build_portable_desktop.ps1" -Clean
endlocal
