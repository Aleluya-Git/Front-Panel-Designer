@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Ejecute primero install.bat & pause & exit /b 1)
.venv\Scripts\python.exe tools\autoprueba.py %*
echo.
echo Resultado guardado en autoprueba_resultado.txt  (capturas en autoprueba_salida\)
pause
