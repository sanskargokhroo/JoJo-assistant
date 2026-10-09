@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
start "JoJo Desktop" pythonw "%~dp0jojo_desktop.py" --start-core
