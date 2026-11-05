@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Electronic Front Panel Designer: instalacion ===
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% --version || (echo No se encontro Python 3.10+. Instalelo desde https://www.python.org & pause & exit /b 1)
if not exist .venv (
  %PY% -m venv .venv || (echo Error creando el entorno virtual & pause & exit /b 1)
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt || (echo Error instalando dependencias & pause & exit /b 1)
echo.
echo Instalacion completada. Use run.bat para iniciar o autoprueba.bat para verificar.
pause
