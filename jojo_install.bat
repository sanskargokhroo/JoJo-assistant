@echo off
cd /d "%~dp0"
python jojo_install.py --gui
if errorlevel 1 pause
