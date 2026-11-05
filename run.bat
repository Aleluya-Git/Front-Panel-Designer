@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (echo Ejecute primero install.bat & pause & exit /b 1)
start "" .venv\Scripts\pythonw.exe main.py %*
