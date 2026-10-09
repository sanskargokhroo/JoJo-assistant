@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0jojo_start.py"
) else (
    python "%~dp0jojo_start.py"
)
if errorlevel 1 pause
