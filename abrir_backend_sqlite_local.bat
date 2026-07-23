@echo off
setlocal
set "CHECKLIST_ENV=development"
set "CHECKLIST_FORCE_LOCAL_DB=1"
set "CHECKLIST_ALLOW_SQLITE=1"
set "CHECKLIST_LEGACY_LOCAL_BOOTSTRAP=1"
cd /d "%~dp0backend"
python run.py
