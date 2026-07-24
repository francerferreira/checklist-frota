@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\backend"
set "CHECKLIST_ENV=development"
set "CHECKLIST_FORCE_LOCAL_DB=1"
set "CHECKLIST_ALLOW_SQLITE=1"
set "CHECKLIST_LEGACY_LOCAL_BOOTSTRAP=1"
python tools\validate_local_homologation.py
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" pause
endlocal & exit /b %EXIT_CODE%
